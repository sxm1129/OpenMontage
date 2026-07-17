"""Stage the vendored GSAP runtime into generated compositions.

Compositions used to load GSAP from `cdn.jsdelivr.net` at validate/render time,
which made every HyperFrames render depend on that CDN being reachable. When the
fetch failed the headless browser reported `gsap is not defined`, and the two
CLI steps disagreed about how bad that was: `hyperframes validate` caught it and
exited 1, but `hyperframes render` exited 0 and produced a near-static video with
only a `sub_timeline_script_failure` warning — a silent downgrade of the kind
AGENT_GUIDE.md forbids. Vendoring removes the network from the render path
entirely rather than retrying around it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from lib.paths import REPO_ROOT

GSAP_VERSION = "3.14.2"
VENDORED_GSAP = REPO_ROOT / "vendor" / "gsap" / "gsap.min.js"

# Every generated composition references GSAP by this bare relative src, which
# resolves against whichever directory the loading document sits in.
GSAP_SRC = "gsap.min.js"

# `hyperframes validate` evaluates each composition file in isolation, so a
# sub-composition's <script src> resolves against compositions/. `hyperframes
# render` inlines that same sub-composition into index.html, where the identical
# src resolves against the workspace root instead. Staging a copy in both places
# is what lets one bare src be correct under both.
_WORKSPACE_STAGE_DIRS = ("", "compositions")


def _copy_to(directory: Path) -> None:
    if not VENDORED_GSAP.exists():
        raise FileNotFoundError(
            f"Vendored GSAP missing at {VENDORED_GSAP}. It is committed to the "
            "repo on purpose — compositions must not fetch it from a CDN. "
            "Restore it with: npm pack gsap@" + GSAP_VERSION
        )
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VENDORED_GSAP, directory / GSAP_SRC)


def stage_gsap_in_workspace(workspace: Path) -> str:
    """Stage GSAP into a HyperFrames workspace; return the src to reference."""
    for relative_dir in _WORKSPACE_STAGE_DIRS:
        _copy_to(workspace / relative_dir if relative_dir else workspace)
    return GSAP_SRC


def stage_gsap_beside(html_path: Path) -> str:
    """Stage GSAP next to a standalone HTML file; return the src to reference."""
    _copy_to(html_path.parent)
    return GSAP_SRC
