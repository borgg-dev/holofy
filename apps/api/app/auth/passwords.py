"""Password hashing with scrypt — a real, memory-hard KDF from the standard library.

No third-party dependency: ``hashlib.scrypt`` (OpenSSL-backed) is a sound password hash, so
account credentials are stored as a salted, memory-hard digest, never reversible plaintext.
The stored string is self-describing — ``scrypt$n$r$p$salt_b64$hash_b64`` — so the cost
parameters travel with the hash and can be raised later without invalidating old hashes
(verification reads the params from the stored value, not from today's constants).
"""

from __future__ import annotations

import base64
import hmac
import os
from hashlib import scrypt

# Cost parameters. n must be a power of two; (n, r, p) = (2**14, 8, 1) is ~16 MB of work per
# hash — comfortably above interactive-login cost while staying within OpenSSL's default
# memory budget. Raise n over time; old hashes still verify against their embedded params.
_N = 2**14
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16
_PREFIX = "scrypt"


def hash_password(password: str) -> str:
    """Return a self-describing scrypt hash of ``password`` with a fresh random salt."""
    if not password:
        raise ValueError("password must not be empty")
    salt = os.urandom(_SALT_BYTES)
    derived = scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return "$".join(
        [_PREFIX, str(_N), str(_R), str(_P), _b64(salt), _b64(derived)]
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of ``password`` against a stored ``hash_password`` value.

    Returns ``False`` for a malformed stored value rather than raising — a corrupt row must
    fail closed (no login), not 500.
    """
    try:
        prefix, n_s, r_s, p_s, salt_b64, hash_b64 = stored.split("$")
        if prefix != _PREFIX:
            return False
        salt = _unb64(salt_b64)
        expected = _unb64(hash_b64)
        derived = scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, expected)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)
