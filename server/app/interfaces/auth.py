"""Authentication provider seam.

The default PassphraseAuth derives a session token from the shared team
passphrase. A future OAuthProvider (GitHub / enterprise SSO) implements the
same login()/verify() contract — no call-site changes (see
interfaces/__init__.get_auth_provider).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from abc import ABC, abstractmethod
from typing import Any

# Fixed HMAC context: token = HMAC-SHA256(key=passphrase, msg=this). The Next
# login route (web/lib/session.ts) derives the IDENTICAL value, so the cookie
# it sets is verifiable here without any shared state — and unforgeable
# without the passphrase, unlike the previous constant "authenticated" cookie
# that anyone could set by hand.
_TOKEN_CONTEXT = b"openmontage-session-v1"


class AuthProvider(ABC):
    """Abstract authentication provider."""

    name: str = "abstract"

    @property
    def enabled(self) -> bool:
        """Whether this provider is configured to enforce authentication.

        main.py's auth middleware skips enforcement when False — the
        local single-user, zero-config mode.
        """
        return True

    @abstractmethod
    def login(self, credentials: dict[str, Any]) -> str | None:
        """Validate credentials; return a session token, or None on failure."""

    @abstractmethod
    def verify(self, token: str | None) -> bool:
        """Return True if the session token is valid."""


class PassphraseAuth(AuthProvider):
    """Single shared team passphrase → an HMAC-derived session token."""

    name = "passphrase"

    def __init__(self, passphrase: str | None = None) -> None:
        # OM_TEAM_PASSPHRASE is the single source of truth for the passphrase.
        # (The web login route reads the same variable, keeping its legacy
        # ACCESS_PASSPHRASE only as a fallback — they were previously two
        # unrelated env vars despite a comment here claiming otherwise.)
        self._passphrase = (
            passphrase if passphrase is not None
            else os.environ.get("OM_TEAM_PASSPHRASE", "")
        )
        self._token = (
            hmac.new(self._passphrase.encode(), _TOKEN_CONTEXT, hashlib.sha256).hexdigest()
            if self._passphrase
            else ""
        )

    @property
    def enabled(self) -> bool:
        return bool(self._passphrase)

    def login(self, credentials: dict[str, Any]) -> str | None:
        supplied = str(credentials.get("passphrase", ""))
        if self._passphrase and hmac.compare_digest(supplied, self._passphrase):
            return self._token
        return None

    def verify(self, token: str | None) -> bool:
        if not self.enabled:
            # No passphrase configured — local single-user mode, nothing to
            # verify against. The middleware also short-circuits on
            # `enabled`, so this is just a consistent answer for direct calls.
            return True
        return bool(token) and hmac.compare_digest(token, self._token)
