"""Data-lake sink selection by configuration.

The one place that decides which implementation backs the ``DataLakeSink`` Protocol, mirroring
``app.providers.factory``. Emitters depend on the Protocol, so flipping
``HOLOFY_DATALAKE_SINK`` from ``mock`` to a real EU-region backend swaps the lake writer in
with no change at the emission sites.

The ``match`` has an explicit guard that raises on an unwired backend rather than returning
``None`` — adding a backend enum value without wiring it here is a loud startup failure, not
a confusing ``NoneType`` at the first consented emission.
"""

from __future__ import annotations

from app.config import DataLakeBackend, Settings
from app.datalake.base import DataLakeSink
from app.datalake.mock import MockDataLakeSink


def build_datalake_sink(settings: Settings) -> DataLakeSink:
    match settings.datalake_sink:
        case DataLakeBackend.MOCK:
            return MockDataLakeSink()
        case unknown:  # pragma: no cover - guards an unwired enum value
            raise ValueError(f"unsupported data-lake sink: {unknown}")
