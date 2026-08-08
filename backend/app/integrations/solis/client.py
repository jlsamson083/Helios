import httpx

from app.core.logger import logger
from app.core.settings import settings


class SolisClient:
    def __init__(self):
        self.base_url = settings.SOLIS_BASE_URL

    async def get_energy_data(self):
        logger.info("Requesting energy data from Solis")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.base_url,
                timeout=10.0
            )

            response.raise_for_status()

            return response.json()