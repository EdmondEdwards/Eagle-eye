from __future__ import annotations

import logging
from datetime import datetime, timezone

from .canonical import SatelliteIngestResult
from .satellite_provider import SatelliteProvider

LOGGER = logging.getLogger(__name__)


class N2YOSatelliteAdapter(SatelliteProvider):
    provider_name = "n2yo"

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    async def fetch_catalog(self) -> SatelliteIngestResult:
        observed_at = datetime.now(timezone.utc)
        if not self.api_key:
            LOGGER.info("N2YO provider is optional and remains disabled until an API key is configured.")
            return SatelliteIngestResult(provider=self.provider_name, catalog_records=[], source_snapshots=[], observed_at=observed_at)

        LOGGER.info("N2YO adapter scaffolding is present for v1.1-ready work, but v1 continues to default to CelesTrak.")
        return SatelliteIngestResult(provider=self.provider_name, catalog_records=[], source_snapshots=[], observed_at=observed_at)
