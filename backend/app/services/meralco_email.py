import asyncio
import email
import hashlib
import html
import imaplib
import re
from datetime import datetime, timezone
from email import policy
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Iterable, Optional

from app.core.database import get_connection
from app.core.logger import logger
from app.core.settings import settings


def _message_text(message: Message) -> str:
    parts = []
    for part in message.walk():
        if part.get_content_type() not in {"text/plain", "text/html"}:
            continue
        try:
            value = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            value = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/html":
            value = re.sub(r"<[^>]+>", " ", value)
            value = html.unescape(value)
        parts.append(value)
    return " ".join(" ".join(parts).split())


def _nested_messages(message: Message) -> Iterable[Message]:
    yielded = False
    for part in message.walk():
        if part.get_content_type() == "message/rfc822":
            payload = part.get_payload()
            if isinstance(payload, list):
                for nested in payload:
                    yielded = True
                    yield nested
    if not yielded:
        yield message


def parse_meralco_email(message: Message) -> Optional[dict]:
    sender = str(message.get("From", "")).lower()
    subject = str(message.get("Subject", ""))
    if settings.MERALCO_EMAIL_SENDER.lower() not in sender:
        return None
    if "meralco bill for" not in subject.lower():
        return None

    text = _message_text(message)
    period = re.search(
        r"Billing Period:\s*(\d{1,2} [A-Za-z]+ \d{4})\s+to\s+(\d{1,2} [A-Za-z]+ \d{4})",
        text,
        re.IGNORECASE,
    )
    consumption = re.search(r"kWh Consumption:\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    amount = re.search(r"Current Amount Due:\s*(?:PHP|P|₱)\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    due = re.search(r"Due Date:\s*(\d{1,2} [A-Za-z]+ \d{4})", text, re.IGNORECASE)
    if not all((period, consumption, amount, due)):
        raise ValueError(f"Meralco email is missing required summary fields: {subject}")

    start = datetime.strptime(period.group(1), "%d %B %Y").date()
    end = datetime.strptime(period.group(2), "%d %B %Y").date()
    due_date = datetime.strptime(due.group(1), "%d %B %Y").date()
    message_id = str(message.get("Message-ID", "")).strip()
    identity = message_id or f"{subject}|{start.isoformat()}|{end.isoformat()}"
    received = message.get("Date")
    try:
        received_at = parsedate_to_datetime(received).astimezone(timezone.utc).isoformat() if received else None
    except (TypeError, ValueError):
        received_at = None
    return {
        "message_key": hashlib.sha256(identity.encode()).hexdigest(),
        "billing_period": f"{period.group(1)} to {period.group(2)}",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "consumption_kwh": float(consumption.group(1).replace(",", "")),
        "amount_due_php": float(amount.group(1).replace(",", "")),
        "due_date": due_date.isoformat(),
        "received_at": received_at,
    }


def _save_bills(bills: Iterable[dict]) -> int:
    connection = get_connection()
    saved = 0
    imported_at = datetime.now(timezone.utc).isoformat()
    try:
        for bill in bills:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO meralco_email_bills (
                    message_key, billing_period, period_start, period_end,
                    consumption_kwh, amount_due_php, due_date, received_at,
                    imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bill["message_key"], bill["billing_period"],
                    bill["period_start"], bill["period_end"],
                    bill["consumption_kwh"], bill["amount_due_php"],
                    bill["due_date"], bill["received_at"], imported_at,
                ),
            )
            saved += cursor.rowcount
        connection.commit()
    finally:
        connection.close()
    return saved


def _save_state(status: str, *, error: Optional[str] = None) -> None:
    connection = get_connection()
    try:
        count = connection.execute("SELECT COUNT(*) FROM meralco_email_bills").fetchone()[0]
        connection.execute(
            """
            INSERT OR REPLACE INTO gmail_import_state (
                id, status, last_checked_at, last_error, bills_found
            ) VALUES (1, ?, ?, ?, ?)
            """,
            (status, datetime.now(timezone.utc).isoformat(), error, count),
        )
        connection.commit()
    finally:
        connection.close()


def sync_meralco_email() -> dict:
    if not settings.HELIOS_GMAIL_USERNAME or not settings.HELIOS_GMAIL_APP_PASSWORD:
        return {"status": "not_connected", "imported": 0}
    client = None
    try:
        client = imaplib.IMAP4_SSL("imap.gmail.com")
        client.login(settings.HELIOS_GMAIL_USERNAME, settings.HELIOS_GMAIL_APP_PASSWORD)
        client.select("INBOX", readonly=True)
        status, matches = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("Unable to search the Helios Gmail inbox")
        bills = []
        for identifier in matches[0].split():
            status, payload = client.fetch(identifier, "(RFC822)")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            outer = email.message_from_bytes(payload[0][1], policy=policy.default)
            for candidate in _nested_messages(outer):
                parsed = parse_meralco_email(candidate)
                if parsed:
                    bills.append(parsed)
        imported = _save_bills(bills)
        _save_state("connected")
        return {"status": "connected", "imported": imported, "matched": len(bills)}
    except Exception as exc:
        logger.warning(f"Unable to import Meralco Gmail bills: {exc}")
        _save_state("error", error=str(exc))
        return {"status": "error", "imported": 0, "error": str(exc)}
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


async def sync_meralco_email_async() -> dict:
    return await asyncio.to_thread(sync_meralco_email)


def gmail_import_status() -> dict:
    connection = get_connection()
    try:
        state = connection.execute("SELECT * FROM gmail_import_state WHERE id = 1").fetchone()
        latest = connection.execute(
            "SELECT * FROM meralco_email_bills ORDER BY period_end DESC LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    if state is None:
        return {"status": "not_checked", "bills_found": 0, "latest_bill": None}
    result = dict(state)
    result["latest_bill"] = dict(latest) if latest else None
    return result


def email_bill_history() -> list:
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT billing_period, period_start, period_end, consumption_kwh,
                   amount_due_php, due_date, received_at, imported_at
            FROM meralco_email_bills ORDER BY period_end DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()
