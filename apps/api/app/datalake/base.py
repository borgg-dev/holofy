"""The data-lake sink seam — where a consented capture leaves the live DB for the moat.

Mirrors the provider seam (``app.providers.base``): one narrow Protocol so the mock, a real
EU-region lake writer, or a future streaming ingest are interchangeable at the call site.
The emitters depend on ``DataLakeSink``, never on a concrete writer, so the lake backend is
a config switch (``app.datalake.factory``), not a code change.

Two deliberate properties:

- ``emit`` takes an *already-consented* ``TrainingExample``. The consent gate is upstream,
  at the emission site — by the time an example reaches a sink, the privacy decision has
  been made and recorded. A sink never re-derives consent; it also never *stores* an example
  it shouldn't, because it is never handed one.
- It is async, because the real sink is a network/object-storage write. The emitters keep it
  off the request's critical path conceptually — see the emission sites for where the async
  boundary (a queue) goes when the real lake lands; a direct ``await`` is fine for the mock.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.datalake import TrainingExample


@runtime_checkable
class DataLakeSink(Protocol):
    """Accepts one consented, labelled training example for the data lake.

    Implementations must be idempotent on ``(kind, record_id)``: a record can be re-emitted
    (e.g. a retried request) without producing a duplicate lake row, so the consent decision
    and the example stay one-to-one.
    """

    async def emit(self, example: TrainingExample) -> None: ...
