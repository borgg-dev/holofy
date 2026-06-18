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
   the out-of-band purge: every object-storage key the user produced — scan bundles
   (``ScanRecord.capture_ref``), pre-grade captures (``PreGradeRecord.capture_ref``) and
   authenticity-screen captures (``AuthenticityRecord.capture_ref``) — and the *record* ids,
   per capture kind, that may have been replicated into the lake. All three kinds carry their
   own revocable ``training_consent``, and each consented record can produce one training
   example (``app/datalake/emit.py``), so the lake purge must target all three — not only
   scans — or a consented pre-grade / authenticity example would survive the delete.

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

from app.db.models.authenticity import AuthenticityRecord
from app.db.models.pregrade import PreGradeRecord
from app.db.models.scan import ScanRecord


@dataclass(frozen=True)
class ErasureManifest:
    """What an out-of-band purge must delete once the DB rows are gone.

    ``capture_refs`` are object-storage keys for every still the user produced — scans,
    pre-grades and authenticity screens. The ``training_eligible_*_ids`` lists are the records
    of each kind that *may* have been replicated into the data lake (they had standing
    consent, never revoked), so the lake purge can target each example precisely by its source
    record id. The keys mirror ``TrainingExample.(kind, record_id)`` the sink stores against.
    """

    user_id: uuid.UUID
    capture_refs: list[str] = field(default_factory=list)
    training_eligible_scan_ids: list[uuid.UUID] = field(default_factory=list)
    training_eligible_pregrade_ids: list[uuid.UUID] = field(default_factory=list)
    training_eligible_authenticity_ids: list[uuid.UUID] = field(default_factory=list)


async def plan_erasure(session: AsyncSession, user_id: uuid.UUID) -> ErasureManifest:
    """Enumerate the user's out-of-band personal data *before* the cascade deletes the rows.

    Call this, then delete the user, then execute the manifest against object storage and
    the data lake — all within one transaction so a crash can't leave orphaned images.
    """
    scan_rows = (
        await session.execute(
            select(
                ScanRecord.id,
                ScanRecord.capture_ref,
                ScanRecord.training_consent,
                ScanRecord.consent_revoked_at,
            ).where(ScanRecord.user_id == user_id)
        )
    ).all()

    # Pre-grades and authenticity screens are object-storage stills too, and — like scans —
    # each carries its own revocable consent and can be replicated into the lake, so we
    # enumerate both their capture keys and their consented record ids.
    pregrade_rows = (
        await session.execute(
            select(
                PreGradeRecord.id,
                PreGradeRecord.capture_ref,
                PreGradeRecord.training_consent,
                PreGradeRecord.consent_revoked_at,
            ).where(PreGradeRecord.user_id == user_id)
        )
    ).all()
    authenticity_rows = (
        await session.execute(
            select(
                AuthenticityRecord.id,
                AuthenticityRecord.capture_ref,
                AuthenticityRecord.training_consent,
                AuthenticityRecord.consent_revoked_at,
            ).where(AuthenticityRecord.user_id == user_id)
        )
    ).all()

    capture_refs = [ref for _, ref, _, _ in scan_rows if ref]
    capture_refs.extend(ref for _, ref, _, _ in pregrade_rows if ref)
    capture_refs.extend(ref for _, ref, _, _ in authenticity_rows if ref)

    return ErasureManifest(
        user_id=user_id,
        capture_refs=capture_refs,
        training_eligible_scan_ids=_eligible_ids(scan_rows),
        training_eligible_pregrade_ids=_eligible_ids(pregrade_rows),
        training_eligible_authenticity_ids=_eligible_ids(authenticity_rows),
    )


def _eligible_ids(rows: list) -> list[uuid.UUID]:
    """The record ids that had standing consent (opted in, never revoked) — the lake targets.

    Same predicate as the repositories' ``list_training_eligible`` and the emission gate, so a
    purge can't miss an example the lake would have ingested.
    """
    return [
        record_id
        for record_id, _, training_consent, consent_revoked_at in rows
        if training_consent and consent_revoked_at is None
    ]
