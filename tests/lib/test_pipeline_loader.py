"""Regression tests for the mtime-aware pipeline manifest cache.

_load_pipeline_cached used to be a bare functools.lru_cache with no
invalidation: once a manifest was loaded, every subsequent call returned the
same parsed dict for the lifetime of the process, even if the YAML file on
disk changed underneath it. lib/checkpoint.py routes gate checks through this
cache (via load_pipeline_readonly) on every checkpoint write -- a hot path --
so a live operator hotfix to a pipeline_defs/*.yaml manifest (e.g. flipping
human_approval_default for a stage) would silently keep being ignored until a
full process restart, which would also kill any in-flight pipeline.

These tests verify: (a) repeated calls for an unchanged manifest are served
from cache without re-reading the file, and (b) editing the manifest on disk
and bumping its mtime is picked up on the very next call, with no explicit
cache-clear or process restart needed.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from lib import pipeline_loader  # noqa: E402
from lib.pipeline_loader import load_pipeline_readonly  # noqa: E402


MINIMAL_MANIFEST = """\
name: mtime-cache-test
version: "1.0"
stages:
  - name: research
    human_approval_default: true
"""


@pytest.fixture(autouse=True)
def _clear_cache():
    """Each test gets a clean in-process cache regardless of call order."""
    pipeline_loader._pipeline_cache.clear()
    yield
    pipeline_loader._pipeline_cache.clear()


@pytest.fixture
def manifest_dir(tmp_path):
    manifest_path = tmp_path / "mtime-cache-test.yaml"
    manifest_path.write_text(MINIMAL_MANIFEST)
    return tmp_path, manifest_path


def test_unchanged_manifest_is_served_from_cache(manifest_dir, monkeypatch):
    """A second call for the same unchanged file must not re-read/re-parse it."""
    defs_dir, manifest_path = manifest_dir

    first = load_pipeline_readonly("mtime-cache-test", defs_dir)
    assert first["stages"][0]["human_approval_default"] is True

    read_calls = []
    real_load = pipeline_loader.load_pipeline

    def counting_load(name, dd=None):
        read_calls.append(name)
        return real_load(name, dd)

    monkeypatch.setattr(pipeline_loader, "load_pipeline", counting_load)

    second = load_pipeline_readonly("mtime-cache-test", defs_dir)

    assert read_calls == [], "unchanged manifest should be served from cache, not re-read"
    assert second == first


def test_edited_manifest_is_picked_up_without_restart(manifest_dir):
    """Editing the YAML on disk and bumping its mtime must be reflected on the
    next call -- no process restart, no explicit cache-clear call."""
    defs_dir, manifest_path = manifest_dir

    before = load_pipeline_readonly("mtime-cache-test", defs_dir)
    assert before["stages"][0]["human_approval_default"] is True

    # Simulate an operator hotfixing the manifest (flip a gate) while the
    # server process keeps running.
    edited = MINIMAL_MANIFEST.replace(
        "human_approval_default: true", "human_approval_default: false"
    )
    manifest_path.write_text(edited)

    # Force a distinct mtime -- some filesystems have coarse mtime
    # resolution, and a same-mtime edit is legitimately indistinguishable
    # from no edit for a stat()-based cache.
    stat = manifest_path.stat()
    new_mtime = stat.st_mtime + 5
    os.utime(manifest_path, (new_mtime, new_mtime))

    after = load_pipeline_readonly("mtime-cache-test", defs_dir)
    assert after["stages"][0]["human_approval_default"] is False


def test_load_pipeline_readonly_returns_independent_copies(manifest_dir):
    """Callers mutating their result must not poison the shared cache."""
    defs_dir, _ = manifest_dir

    first = load_pipeline_readonly("mtime-cache-test", defs_dir)
    first["stages"][0]["human_approval_default"] = "mutated"

    second = load_pipeline_readonly("mtime-cache-test", defs_dir)
    assert second["stages"][0]["human_approval_default"] is True
