"""`bake-basemap.mjs` must not fetch its libraries, and must fail closed on bad imagery.

Regression test for a silent downgrade. The bake had two classes of network
dependency and handled both badly:

* The libraries (maplibre, topojson, world-atlas) came from `cdn.jsdelivr.net`.
  A jsdelivr outage produced an infinite hang (the `world-atlas` fetch had no
  `.catch()`, so its promise never settled) or a bare `TypeError`. They are now
  vendored under `vendor/maps/` and read off disk.
* The tiles (Esri/CARTO) cannot be vendored — real imagery is the point of the
  basemap lane. When they failed, the bake wrote a 1920x1080 MP4 of solid
  `#05070d`, exited 0, and logged "all N frames reached map idle (complete
  tiles)". MapLibre's `areTilesLoaded()` counts an *errored* tile as loaded, so
  `idle` fired normally and the existing idle-timeout guard never armed. That is
  the silent downgrade AGENT_GUIDE.md forbids, and it is what the tile-error
  guard now catches.

The static checks below run everywhere. The end-to-end check needs Node, Chrome
and `puppeteer-core`, and skips when they are absent.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lib.paths import REPO_ROOT

BAKE = REPO_ROOT / ".agents/skills/motion-graphics/categories/maps/bake-basemap.mjs"
VENDOR_DIR = REPO_ROOT / "vendor" / "maps"
NOTICES = REPO_ROOT / "vendor" / "THIRD_PARTY_NOTICES.md"

# Hosts that serve libraries. The Esri/CARTO tile hosts are deliberately NOT here:
# they are the irreducible dependency this skill exists to photograph.
LIBRARY_CDN_HOSTS = ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "esm.sh")

VENDORED_FILES = ("maplibre-gl.js", "topojson-client.min.js", "countries-110m.json")


def _source() -> str:
    return BAKE.read_text(encoding="utf-8")


def _strip_comments(js: str) -> str:
    """Drop // and /* */ comments so prose about the old CDN bug isn't mistaken for code."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(re.sub(r"//.*$", "", line) for line in js.splitlines())


def test_bake_script_exists() -> None:
    assert BAKE.is_file(), f"missing {BAKE}"


@pytest.mark.parametrize("host", LIBRARY_CDN_HOSTS)
def test_no_library_cdn_on_the_bake_path(host: str) -> None:
    code = _strip_comments(_source())
    assert host not in code, (
        f"{host} is referenced in bake-basemap.mjs. Libraries must be read from "
        "vendor/maps/ — a CDN on the bake path is what made an outage hang the "
        "bake or blank the basemap. See vendor/THIRD_PARTY_NOTICES.md."
    )


def test_no_network_fetch_in_page_logic() -> None:
    """The world-atlas fetch() had no .catch(), so an outage hung the bake forever."""
    code = _strip_comments(_source())
    assert "fetch(" not in code, (
        "bake-basemap.mjs calls fetch(). The dataset is vendored at "
        "vendor/maps/countries-110m.json and injected into the page; a fetch here "
        "reintroduces the hang it was removed to fix."
    )


def test_tile_endpoints_are_still_present() -> None:
    """Guard against 'fixing' the CDN problem by deleting the imagery itself."""
    code = _source()
    assert "server.arcgisonline.com" in code and "basemaps.cartocdn.com" in code


@pytest.mark.parametrize("name", VENDORED_FILES)
def test_vendored_file_present_and_non_empty(name: str) -> None:
    path = VENDOR_DIR / name
    assert path.is_file(), (
        f"{path} is missing. It is committed on purpose — restore it per "
        "vendor/THIRD_PARTY_NOTICES.md."
    )
    assert path.stat().st_size > 0


@pytest.mark.parametrize("name", VENDORED_FILES)
def test_vendored_file_matches_recorded_hash(name: str) -> None:
    """Keeps THIRD_PARTY_NOTICES.md honest: a swapped vendor file must update its hash."""
    digest = hashlib.sha256((VENDOR_DIR / name).read_bytes()).hexdigest()
    notices = NOTICES.read_text(encoding="utf-8")
    assert digest in notices, (
        f"vendor/maps/{name} has SHA-256 {digest}, which is not recorded in "
        "vendor/THIRD_PARTY_NOTICES.md. If you upgraded it on purpose, update the "
        "hash and the pinned version there and in bake-basemap.mjs."
    )


def test_world_atlas_is_the_110m_dataset() -> None:
    """The 50m/10m variants are 7x/35x larger; vendoring one by accident is worth catching."""
    atlas = json.loads((VENDOR_DIR / "countries-110m.json").read_text(encoding="utf-8"))
    assert "countries" in atlas.get("objects", {}), "not a world-atlas countries topology"
    assert (VENDOR_DIR / "countries-110m.json").stat().st_size < 200_000


def test_maplibre_css_is_not_vendored() -> None:
    """Verified dead weight: the bake renders a byte-identical frame without it."""
    assert not (VENDOR_DIR / "maplibre-gl.css").exists()


def test_pinned_versions_agree_with_notices() -> None:
    code = _source()
    notices = NOTICES.read_text(encoding="utf-8")
    for version in ("5.24.0", "3.1.0", "2.0.2"):
        assert version in code, f"version {version} not pinned in bake-basemap.mjs"
        assert version in notices, f"version {version} not recorded in THIRD_PARTY_NOTICES.md"


def test_script_parses() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    proc = subprocess.run([node, "--check", str(BAKE)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def _puppeteer_available() -> bool:
    node = shutil.which("node")
    if node is None:
        return False
    probe = subprocess.run(
        [node, "-e", "import('puppeteer-core').then(()=>process.exit(0),()=>process.exit(1))"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return probe.returncode == 0


@pytest.mark.skipif(
    not _puppeteer_available(),
    reason="puppeteer-core not resolvable from the repo — end-to-end bake cannot run",
)
def test_unreachable_tiles_fail_closed(tmp_path: Path) -> None:
    """The headline regression: a dead tile endpoint must not yield a blank MP4 + exit 0.

    Port 9 (discard) refuses connections, standing in for an unreachable tile CDN.
    COUNTRIES is empty so this exercises the tile path alone.
    """
    env = {
        **os.environ,
        "NAME": "guard",
        "STYLE": "http://127.0.0.1:9/{z}/{x}/{y}.png",
        "COUNTRIES": "",
        "CENTER": "2.6,46.6",
        "FPS": "2",
        "DUR": "1",
        "OUT": str(tmp_path),
        "MAPS_VENDOR_DIR": str(VENDOR_DIR),
    }
    proc = subprocess.run(
        [shutil.which("node"), str(BAKE)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode != 0, (
        "bake exited 0 with an unreachable tile endpoint — it fails OPEN again.\n"
        f"stdout:\n{proc.stdout}"
    )
    assert not (tmp_path / "guard.mp4").exists(), "a blank MP4 was left on disk for HF to consume"
    assert not (tmp_path / "guard-coords.json").exists()
    assert "complete tiles" not in proc.stdout, "the bake still claims complete tiles"
    assert "BAKE FAILED" in proc.stderr
