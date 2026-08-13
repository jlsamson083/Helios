import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict

import httpx

from app.core.logger import logger
from app.core.settings import settings


class SolisClient:
    def __init__(self):
        self.base_url = settings.SOLIS_BASE_URL.rstrip("/")
        self.api_key_id = settings.SOLIS_API_KEY_ID
        self.api_secret = settings.SOLIS_API_SECRET

    async def get_inverter_detail(
        self,
        inverter_sn: str,
    ) -> Dict[str, Any]:
        resource = "/v1/api/inverterDetail"

        body = json.dumps(
            {"sn": inverter_sn},
            separators=(",", ":"),
        )

        content_type = "application/json"

        content_md5 = base64.b64encode(
            hashlib.md5(
                body.encode("utf-8")
            ).digest()
        ).decode("utf-8")

        date = datetime.now(
            timezone.utc
        ).strftime("%a, %d %b %Y %H:%M:%S GMT")

        sign_string = "\n".join(
            [
                "POST",
                content_md5,
                content_type,
                date,
                resource,
            ]
        )

        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode("utf-8"),
                sign_string.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        authorization = (
            f"API {self.api_key_id}:{signature}"
        )

        headers = {
            "Content-Type": content_type,
            "Content-MD5": content_md5,
            "Date": date,
            "Authorization": authorization,
        }

        logger.info(
            "Calling Solis API: %s",
            resource,
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}{resource}",
                content=body,
                headers=headers,
                timeout=15.0,
            )

            response.raise_for_status()

            return response.json()