"""Regression: seed=0 is a valid, meaningful value (not "unset") — reporting
it via an `or` fallback (`data.get("seed") or first.get("seed")`) silently
replaces a genuine seed=0 with whatever fallback is on the other side of the
`or`, or with None if there's nothing there. The request-building path
already treats 0 as meaningful (`if inputs.get("seed") is not None`); the
response-reporting path must use the same explicit not-None check.
"""

from __future__ import annotations

import base64

import pytest

from tools.graphics.maas_image import MaasImage


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setenv("MAAS_API_KEY", "sk-dlp-test-key")


class _FakeResponse:
    def __init__(self, json_data=None):
        self._json = json_data or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def _b64_png() -> str:
    return base64.b64encode(b"fake-png-bytes").decode()


def test_seed_zero_in_top_level_data_is_not_replaced(monkeypatch, tmp_path):
    """data.get("seed") == 0 must win, not be treated as falsy."""

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse({
            "seed": 0,
            "data": [{"b64_json": _b64_png(), "seed": 999}],
        })

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    tool = MaasImage()
    result = tool.execute({
        "prompt": "a cat",
        "seed": 0,
        "output_path": str(tmp_path / "out.png"),
    })

    assert result.success is True
    assert result.data["seed"] == 0
    assert result.seed == 0


def test_seed_zero_in_first_image_entry_is_not_replaced(monkeypatch, tmp_path):
    """No top-level seed, but images[0]["seed"] == 0 must still be reported
    as 0, not silently swapped for None."""

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse({
            "data": [{"b64_json": _b64_png(), "seed": 0}],
        })

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    tool = MaasImage()
    result = tool.execute({
        "prompt": "a cat",
        "output_path": str(tmp_path / "out.png"),
    })

    assert result.success is True
    assert result.data["seed"] == 0
    assert result.seed == 0


def test_nonzero_seed_still_reported_correctly(monkeypatch, tmp_path):
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse({
            "data": [{"b64_json": _b64_png(), "seed": 42}],
        })

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    tool = MaasImage()
    result = tool.execute({
        "prompt": "a cat",
        "output_path": str(tmp_path / "out.png"),
    })

    assert result.success is True
    assert result.data["seed"] == 42
    assert result.seed == 42


def test_missing_seed_reports_none(monkeypatch, tmp_path):
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse({
            "data": [{"b64_json": _b64_png()}],
        })

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    tool = MaasImage()
    result = tool.execute({
        "prompt": "a cat",
        "output_path": str(tmp_path / "out.png"),
    })

    assert result.success is True
    assert result.data["seed"] is None
    assert result.seed is None
