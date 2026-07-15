"""Auth enforcement: the require_session_token middleware + PassphraseAuth.

Audit findings SEC-1/SEC-2 (2026-07-15): no route checked
AuthProvider.verify() and the session cookie was the forgeable constant
"authenticated" — the login page was cosmetic. The middleware now enforces an
HMAC-derived token on every route whenever OM_TEAM_PASSPHRASE is configured;
without one the server stays zero-config (local single-user mode).
"""

from __future__ import annotations

import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from app import interfaces
from app import main
from app.interfaces.auth import PassphraseAuth

PASSPHRASE = "correct horse battery staple"
TOKEN = hmac.new(PASSPHRASE.encode(), b"openmontage-session-v1", hashlib.sha256).hexdigest()


@pytest.fixture
def open_client(monkeypatch):
    """Client with NO passphrase configured — auth disabled."""
    monkeypatch.delenv("OM_TEAM_PASSPHRASE", raising=False)
    interfaces.get_auth_provider.cache_clear()
    yield TestClient(main.app)
    interfaces.get_auth_provider.cache_clear()


@pytest.fixture
def locked_client(monkeypatch):
    """Client with a passphrase configured — auth enforced on every route."""
    monkeypatch.setenv("OM_TEAM_PASSPHRASE", PASSPHRASE)
    interfaces.get_auth_provider.cache_clear()
    yield TestClient(main.app)
    interfaces.get_auth_provider.cache_clear()


class TestPassphraseAuth:
    def test_login_returns_hmac_token_not_a_constant(self):
        auth = PassphraseAuth(PASSPHRASE)
        token = auth.login({"passphrase": PASSPHRASE})
        assert token == TOKEN
        assert token != "authenticated"

    def test_login_rejects_wrong_passphrase(self):
        auth = PassphraseAuth(PASSPHRASE)
        assert auth.login({"passphrase": "nope"}) is None

    def test_verify_rejects_forged_constant_cookie(self):
        # The pre-fix cookie value must no longer grant access.
        auth = PassphraseAuth(PASSPHRASE)
        assert auth.verify("authenticated") is False
        assert auth.verify(TOKEN) is True

    def test_disabled_provider_verifies_everything(self):
        auth = PassphraseAuth("")
        assert auth.enabled is False
        assert auth.verify(None) is True


class TestMiddlewareDisabled:
    def test_routes_stay_open_without_a_passphrase(self, open_client):
        # Local single-user mode: configuring nothing must not lock the
        # tool (regression guard for the zero-config default).
        assert open_client.get("/jobs").status_code == 200
        assert open_client.get("/health").status_code == 200


class TestMiddlewareEnforced:
    def test_request_without_token_is_401(self, locked_client):
        assert locked_client.get("/jobs").status_code == 401

    def test_health_stays_open(self, locked_client):
        assert locked_client.get("/health").status_code == 200

    def test_x_om_token_header_grants_access(self, locked_client):
        r = locked_client.get("/jobs", headers={"X-OM-Token": TOKEN})
        assert r.status_code == 200

    def test_bearer_token_grants_access(self, locked_client):
        r = locked_client.get("/jobs", headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200

    def test_session_cookie_grants_access(self, locked_client):
        r = locked_client.get("/jobs", cookies={"om_session": TOKEN})
        assert r.status_code == 200

    def test_forged_constant_cookie_is_rejected(self, locked_client):
        r = locked_client.get("/jobs", cookies={"om_session": "authenticated"})
        assert r.status_code == 401

    def test_media_mount_is_protected(self, locked_client):
        # /media serves every project's artifacts and cost logs — it must be
        # behind the same gate as the API, not just the routers.
        assert locked_client.get("/media/anything.txt").status_code == 401

    def test_sse_endpoint_accepts_cookie(self, locked_client):
        # EventSource cannot set custom headers — the cookie path must work.
        # 404 (unknown job) proves auth passed and the route logic ran.
        r = locked_client.get("/jobs/nonexistent/events", cookies={"om_session": TOKEN})
        assert r.status_code == 404
