"""Pre-grade: the in-house centering measurement plus the bought-then-built grading seam.

Centering is built here, in numpy, because it is a direct geometric *measurement* the
collector can verify by eye (architecture §3.2) — never a learned guess. Corners, edges
and surface are bought first (Ximilar ``/v2/grade``) behind the ``GradingProvider``
Protocol, then replaced in-house later with no call-site change. The pre-grade service
composes the two into an honest grade *probability range* — decision support, explicitly
"not an official grade" (charter §3.1).
"""

from __future__ import annotations
