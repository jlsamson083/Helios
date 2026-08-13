from typing import Any

from app.integrations.tesla.client import TeslaClient
from app.models.energy import TeslaVehicleStatus


class TeslaService:
    """
    Read-only Tesla integration.

    This service only retrieves Tesla vehicle information.
    It does not send vehicle control commands.
    """

    def __init__(self, access_token: str) -> None:
        self.client = TeslaClient(access_token)

    async def get_vehicle_data(
        self,
        vehicle_id: str,
    ) -> dict[str, Any]:
        """
        Retrieve current vehicle data from Tesla.
        """
        return await self.client.get_vehicle_data(vehicle_id)

    @staticmethod
    def parse_vehicle_status(
        data: dict[str, Any],
        vehicle_id: str,
    ) -> TeslaVehicleStatus:
        """
        Convert normalized Tesla vehicle data into
        the Helios TeslaVehicleStatus model.

        This method does not make an API call.
        """

        return TeslaVehicleStatus(
            vehicle_id=vehicle_id,
            battery_level_percent=float(
                data["battery_level_percent"]
            ),
            charging_state=str(
                data["charging_state"]
            ),
            charging_power_kw=float(
                data["charging_power_kw"]
            ),
            charging_current_a=float(
                data["charging_current_a"]
            ),
            battery_range_km=float(
                data["battery_range_km"]
            ),
            connected=bool(
                data["connected"]
            ),
        )