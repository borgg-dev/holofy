"""Right-to-erasure: how a user delete propagates beyond the live database.

GDPR Art. 17 erasure has to reach further than the relational rows. Architecture §6 is
explicit: a deleted user's images must be purgeable from the data lake and any training
corpus, not just the live DB. This module is the single place that strategy is encoded, so
the propagation order is auditable rather than scattered.

Two distinct kinds of data are involved, handled differently:

1. **Personal data in Postgres** — ``User`` and everything owned by it (``CollectionItem``,
   ``ScanRecord``, ``PortfolioSnapshot``). Deleting the ``User`` cascades these away via
   ``ON DELETE CASCADE`` (see the relationships). Synchronous, transactional, complete.

2. **Derived/replicated personal data outside Postgres** — capture images in object
   storage and any rows already copied into the training data lake. The DB cascade cannot
   reach these, so erasure must *enumerate* them before the rows vanish and hand them to
   the out-of-band purge: the object-storage keys (``ScanRecord.capture_ref``) and the
   scan ids that may exist in a training set.

``plan_erasure`` runs inside the same transaction as the delete and returns that manifest;
the caller (an erasure job, a later slice) executes the storage/lake deletions and only
then commits, so we never drop the DB rows while still holding their images.

Reference (not personal) data — ``Card``, ``PriceObservation`` — is market/catalog data
shared across users and is intentionally never erased.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scan import ScanRecord


@dataclass(frozen=True)
class ErasureManifest:
    """What an out-of-band purge must delete once the DB rows are gone.

    ``capture_refs`` are object-storage keys for the user's scan images;
    ``training_eligible_scan_ids`` are the scans that *may* have been replicated into the
    data lake (they had standing consent), so the lake purge can target them precisely.
    """

    user_id: uuid.UUID
    capture_refs: list[str] = field(default_factory=list)
    training_eligible_scan_ids: list[uuid.UUID] = field(default_factory=list)


async def plan_erasure(session: AsyncSession, user_id: uuid.UUID) -> ErasureManifest:
    """Enumerate the user's out-of-band personal data *before* the cascade deletes the rows.

    Call this, then delete the user, then execute the manifest against object storage and
    the data lake — all within one transaction so a crash can't leave orphaned images.
    """
    stmt = select(
        ScanRecord.id, ScanRecord.capture_ref, ScanRecord.training_consent
    ).where(ScanRecord.user_id == user_id)
    rows = (await session.execute(stmt)).all()

    return ErasureManifest(
        user_id=user_id,
        capture_refs=[capture_ref for _, capture_ref, _ in rows if capture_ref],
        training_eligible_scan_ids=[
            scan_id for scan_id, _, training_consent in rows if training_consent
        ],
    )
