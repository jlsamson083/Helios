from typing import Any

import httpx


class TeslaClient:
    """
    Read-only Tesla Fleet API client.

    This client does not send vehicle control commands.
    """

    BASE_URL = "https://fleet-api.prd.eu.3.tesla.com"

    def __init__(
        self,
        access_token: str,
    ) -> None:
        self.access_token = access_token

    async def get_vehicle_data(
        self,
        vehicle_id: str,
    ) -> dict[str, Any]:
        """
        Read vehicle data from Tesla Fleet API.
        """

        url = (
            f"{self.BASE_URL}"
            f"/api/1/vehicles/{vehicle_id}/vehicle_data"
        )

        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                headers=headers,
            )

        response.raise_for_status()

        return response.json()
