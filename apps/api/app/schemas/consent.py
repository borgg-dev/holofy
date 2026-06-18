"""Training-consent request/response contract — the user's grip on the moat.

Training consent is the explicit, revocable permission to use a user's captures to improve
Holofy's recognition / grading / authenticity models — deliberately separate from consent to
use the app (architecture §6, charter §3.5). This contract is what the mobile privacy screen
reads and writes:

- ``ConsentState`` reports whether the account is currently training-eligible and how many of
  its captures of each kind are consented — so the UI can say plainly "12 scans are helping
  improve recognition" rather than implying a vague, unaccountable opt-in.
- ``GET`` reads it; ``PUT`` sets it. There is no implicit grant: a fresh account reads
  ``granted=false`` with zero consented records, and only an explicit ``PUT {granted: true}``
  opts in. A ``PUT {granted: false}`` revokes, marking the user's consented captures for purge
  from any derived training set.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConsentCounts(BaseModel):
    """How many of the user's captures of each kind currently feed the training lake."""

    scans: int = 0
    pregrades: int = 0
    authenticity: int = 0

    @property
    def total(self) -> int:
        return self.scans + self.pregrades + self.authenticity


class ConsentState(BaseModel):
    """The account's current training-consent posture, as the privacy screen renders it.

    ``granted`` is the account-level switch: true once any capture is consented and
    never-revoked, false otherwise (the default for a fresh or fully-revoked account).
    ``consented`` breaks that down per capture kind so the copy can be specific and honest.
    """

    granted: bool
    consented: ConsentCounts


class ConsentUpdate(BaseModel):
    """Set the account-level training consent: ``true`` opts in, ``false`` revokes.

    Applied across the user's existing captures (and, via the per-capture flag, inherited by
    future ones the client opts in at capture time). A note records the copy version / surface
    the choice was made under, for audit.
    """

    granted: bool
    note: str | None = Field(default=None, max_length=255)
