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
VENDOR_DIR = REPO_ROOT / "vendor" / "gsap"

# Every generated composition references GSAP by this bare relative src, which
# resolves against whichever directory the loading document sits in.
GSAP_SRC = "gsap.min.js"

# Plugins ship in the same npm tarball under the same license as the core, and
# are staged next to it so a composition that needs one can reference it by a
# bare src too. `techniques.md` (MotionPathPlugin) and `rules/gsap-effects.md`
# (TextPlugin) document techniques that require them; without a local copy to
# point at, those docs would have to teach a CDN <script> tag, which is what put
# the network on the render path in the first place.
PLUGIN_SRCS = ("TextPlugin.min.js", "MotionPathPlugin.min.js")

_VENDORED_FILES = (GSAP_SRC, *PLUGIN_SRCS)

# `hyperframes validate` evaluates each composition file in isolation, so a
# sub-composition's <script src> resolves against compositions/. `hyperframes
# render` inlines that same sub-composition into index.html, where the identical
# src resolves against the workspace root instead. Staging a copy in both places
# is what lets one bare src be correct under both.
_WORKSPACE_STAGE_DIRS = ("", "compositions")


def _copy_to(directory: Path) -> None:
    for name in _VENDORED_FILES:
        source = VENDOR_DIR / name
        if not source.exists():
            raise FileNotFoundError(
                f"Vendored GSAP file missing at {source}. It is committed to the "
                "repo on purpose — compositions must not fetch it from a CDN. "
                "Restore it with: npm pack gsap@" + GSAP_VERSION
            )
    directory.mkdir(parents=True, exist_ok=True)
    for name in _VENDORED_FILES:
        shutil.copy2(VENDOR_DIR / name, directory / name)


def stage_gsap_in_workspace(workspace: Path) -> str:
    """Stage GSAP + plugins into a workspace; return the core src to reference.

    Plugins land beside the core under their `PLUGIN_SRCS` names; a composition
    that needs one adds its own <script src="TextPlugin.min.js"> tag.
    """
    for relative_dir in _WORKSPACE_STAGE_DIRS:
        _copy_to(workspace / relative_dir if relative_dir else workspace)
    return GSAP_SRC


def stage_gsap_beside(html_path: Path) -> str:
    """Stage GSAP + plugins next to a standalone HTML file; return the core src."""
    _copy_to(html_path.parent)
    return GSAP_SRC
