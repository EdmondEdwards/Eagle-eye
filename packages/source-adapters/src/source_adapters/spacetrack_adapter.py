from __future__ import annotations

import logging
from datetime import datetime, timezone

from .canonical import SatelliteIngestResult
from .satellite_provider import SatelliteProvider

LOGGER = logging.getLogger(__name__)


class SpaceTrackSatelliteAdapter(SatelliteProvider):
    provider_name = "spacetrack"

    def __init__(self, username: str | None, password: str | None) -> None:
        self.username = username
        self.password = password

    async def fetch_catalog(self) -> SatelliteIngestResult:
        observed_at = datetime.now(timezone.utc)
        if not self.username or not self.password:
            LOGGER.info("Space-Track provider is configured as optional and is disabled for first boot.")
            return SatelliteIngestResult(provider=self.provider_name, catalog_records=[], source_snapshots=[], observed_at=observed_at)

        LOGGER.info("Space-Track adapter is present for v1.1-ready integration but not enabled in v1 boot flow.")
        return SatelliteIngestResult(provider=self.provider_name, catalog_records=[], source_snapshots=[], observed_at=observed_at)
