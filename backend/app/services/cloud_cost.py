import asyncio
from datetime import datetime, timezone

from app.core.database import get_connection
from app.core.logger import logger
from app.core.settings import settings
from app.services.alerts import create_alert


def get_cost_status() -> dict:
    if not settings.OCI_COST_MONITOR_ENABLED:
        return {
            "status": "not_connected",
            "actual_spend": None,
            "forecasted_spend": None,
            "currency": "USD",
            "budget_name": settings.OCI_BUDGET_NAME,
            "checked_at": None,
            "error": None,
        }
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM cloud_cost_status WHERE id = 1"
        ).fetchone()
    finally:
        connection.close()
    if row:
        return dict(row)
    return {
        "status": "not_connected",
        "actual_spend": None,
        "forecasted_spend": None,
        "currency": "USD",
        "budget_name": settings.OCI_BUDGET_NAME,
        "checked_at": None,
        "error": None,
    }


def _save_status(payload: dict) -> dict:
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO cloud_cost_status (
                id, status, actual_spend, forecasted_spend, currency,
                budget_name, checked_at, error
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                actual_spend=excluded.actual_spend,
                forecasted_spend=excluded.forecasted_spend,
                currency=excluded.currency,
                budget_name=excluded.budget_name,
                checked_at=excluded.checked_at,
                error=excluded.error
            """,
            (
                payload["status"], payload.get("actual_spend"),
                payload.get("forecasted_spend"), payload.get("currency"),
                payload.get("budget_name"), payload.get("checked_at"),
                payload.get("error"),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return payload


def _read_oci_budget() -> dict:
    # Imported lazily so development and tests work without OCI credentials.
    import oci

    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    client = oci.budget.BudgetClient(
        config={"region": settings.OCI_REGION}, signer=signer
    )
    budgets = client.list_budgets(
        compartment_id=signer.tenancy_id,
        lifecycle_state="ACTIVE",
    ).data
    budget = next(
        (item for item in budgets if item.display_name == settings.OCI_BUDGET_NAME),
        None,
    )
    if budget is None:
        raise RuntimeError(f'OCI budget "{settings.OCI_BUDGET_NAME}" was not found')
    actual = float(budget.actual_spend or 0)
    forecast = float(budget.forecasted_spend or 0)
    return {
        "status": "billing" if actual > settings.OCI_COST_ALERT_THRESHOLD_USD else "zero_cost",
        "actual_spend": actual,
        "forecasted_spend": forecast,
        "currency": "USD",
        "budget_name": budget.display_name,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }


async def refresh_cost_status() -> dict:
    if not settings.OCI_COST_MONITOR_ENABLED:
        return get_cost_status()
    try:
        payload = await asyncio.to_thread(_read_oci_budget)
        _save_status(payload)
        if payload["status"] == "billing":
            create_alert(
                kind="cloud_cost",
                severity="critical",
                title="Oracle Cloud is no longer at zero cost",
                message=(
                    f'OCI reports {payload["currency"]} '
                    f'{payload["actual_spend"]:.2f} of actual spend this month.'
                ),
                cooldown_minutes=24 * 60,
            )
        return payload
    except Exception as exc:
        logger.warning(f"Unable to refresh OCI cost status: {exc}")
        previous = get_cost_status()
        previous.update({"status": "unavailable", "error": str(exc)})
        return _save_status(previous)
