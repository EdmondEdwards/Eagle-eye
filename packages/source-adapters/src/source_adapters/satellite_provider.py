from __future__ import annotations

from abc import ABC, abstractmethod

from .canonical import SatelliteIngestResult


class SatelliteProvider(ABC):
    provider_name: str

    @abstractmethod
    async def fetch_catalog(self) -> SatelliteIngestResult:
        raise NotImplementedError
