"""Wave-1 theme-bridge and subtitle-style fixes (audit 2026-07-16, ④⑤).

The playbook→theme bridge read keys that no playbook ever wrote
(heading/family/muted_text/motion.pace), so theme typography and muted
colors silently fell back to defaults for EVERY render; and raw #RRGGBB hex
went straight into ASS force_style, which requires &HAABBGGRR — playbook
subtitle styling never rendered as designed.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from styles.playbook_loader import load_playbook  # noqa: E402
from tools.video.video_compose import VideoCompose  # noqa: E402


class TestHexToAssColor:
    def test_rrggbb(self):
        # CSS #RRGGBB → ASS &HAABBGGRR with channels reversed, opaque alpha.
        assert VideoCompose._hex_to_ass_color("#1F2937") == "&H0037291F"

    def test_without_hash(self):
        assert VideoCompose._hex_to_ass_color("FFFFFF") == "&H00FFFFFF"

    def test_css_trailing_alpha_inverted(self):
        # CSS alpha FF = opaque → ASS alpha 00 = opaque.
        assert VideoCompose._hex_to_ass_color("#FF0000FF") == "&H000000FF"
        # CSS alpha 00 = transparent → ASS FF.
        assert VideoCompose._hex_to_ass_color("#FF000000") == "&HFF0000FF"

    def test_already_ass_passthrough(self):
        assert VideoCompose._hex_to_ass_color("&H00FFFFFF") == "&H00FFFFFF"

    def test_non_hex_passthrough(self):
        assert VideoCompose._hex_to_ass_color("rgba(0,0,0,0.5)") == "rgba(0,0,0,0.5)"

    def test_explicit_alpha_param(self):
        assert VideoCompose._hex_to_ass_color("#000000", alpha=0x60) == "&H60000000"

    def test_build_subtitle_style_converts_colors(self):
        style = VideoCompose._build_subtitle_style({
            "font": "Inter",
            "primary_color": "#1F2937",
            "outline_color": "#FFFFFF",
            "back_color": "#000000",
        })
        assert "PrimaryColour=&H0037291F" in style
        assert "OutlineColour=&H00FFFFFF" in style
        # Box fill defaults to semi-transparent.
        assert "BackColour=&H60000000" in style
        assert "#1F2937" not in style


class TestPlaybookThemeBridge:
    """Against the REAL playbooks — the drift was between real YAML keys and
    the bridge's lookups, so fixtures shaped 'as expected' would miss it."""

    def test_heading_font_read_from_plural_headings_key(self):
        # Old singular `heading` lookup → always fell back to "Inter".
        theme = VideoCompose._build_theme_from_playbook("anime-ghibli", None)
        assert theme["headingFont"] == "Noto Serif JP"
        theme2 = VideoCompose._build_theme_from_playbook("minimalist-diagram", None)
        assert theme2["headingFont"] == "IBM Plex Sans"

    def test_muted_color_read_from_muted_key(self):
        # anime-ghibli declares a non-default muted (#8B9A7E) — the old
        # `muted_text` lookup always returned the #6B7280 default.
        theme = VideoCompose._build_theme_from_playbook("anime-ghibli", None)
        assert theme["mutedTextColor"] == "#8B9A7E"

    def test_identity_pace_drives_spring_config(self):
        # "gentle" is a slow-family pace — the springConfig branch must fire
        # (the old motion.pace lookup matched no playbook; this branch was
        # dead for every render).
        theme = VideoCompose._build_theme_from_playbook("anime-ghibli", None)
        assert theme["springConfig"]["damping"] == 25
        assert theme["transitionDuration"] == 0.6

    def test_subtitle_style_reads_body_font(self):
        playbook = load_playbook("minimalist-diagram")
        resolved = VideoCompose._resolve_subtitle_style(None, None, playbook)
        # Old `body.family` lookup matched nothing → font stayed default.
        assert resolved["font"] == playbook["typography"]["body"]["font"]


class TestCaptionHighlightContrast:
    """The active-word highlight must be legible on its own scrim.

    Found by E2E render inspection (2026-07-17): captionHighlightColor was
    hardcoded to the playbook's `primary`, so a dark-primary playbook shipped
    an invisible highlight — anime-ghibli rendered #2D5016 forest green on the
    #0F172A scrim at 1.93:1, below even the 3:1 WCAG large-text floor. Root's
    hand-authored THEMES use `accent` for this, so the bridge contradicted the
    theme it exists to reproduce.
    """

    def test_dark_primary_playbook_uses_legible_accent(self):
        from styles.playbook_loader import validate_contrast

        theme = VideoCompose._build_theme_from_playbook("anime-ghibli", None)
        # accent, not the near-invisible dark-green primary
        assert theme["captionHighlightColor"] == "#FFB347"
        assert theme["captionHighlightColor"] != "#2D5016"
        assert validate_contrast("#FFB347", "#0F172A")["large_text"]["AA"] is True

    def test_every_playbook_caption_highlight_passes_wcag_large(self):
        from styles.playbook_loader import list_playbooks, validate_contrast

        for name in list_playbooks():
            theme = VideoCompose._build_theme_from_playbook(name, None)
            scrim = (
                "#FFFFFF" if "rgba(255" in theme["captionBackgroundColor"] else "#0F172A"
            )
            result = validate_contrast(theme["captionHighlightColor"], scrim)
            assert result["large_text"]["AA"] is True, (
                f"{name}: highlight {theme['captionHighlightColor']} on {scrim} "
                f"is {result['ratio']}:1 — below the 3:1 large-text floor"
            )

    def test_falls_back_to_neutral_when_no_candidate_passes(self):
        # Both candidates invisible on a dark scrim → guaranteed-legible light.
        assert (
            VideoCompose._pick_caption_highlight(["#111111", "#0A0A0A"], "#0F172A", False)
            == "#F8FAFC"
        )

    def test_prefers_first_passing_candidate(self):
        assert (
            VideoCompose._pick_caption_highlight(["#111111", "#FFB347"], "#0F172A", False)
            == "#FFB347"
        )


class TestSceneTypeCatalogMatchesReality:
    """video_compose advertises scene types to agents via get_info().

    Two hand-maintained lists had drifted apart AND away from the renderer:
    both listed "progress" and "chart" (never implemented by anything) while
    omitting progress_bar/hero_title/terminal_scene/anime_scene/
    screenshot_scene (which are). Agents read get_info() and act on it, so a
    stale entry is a lie. SCENE_TYPES.md is the authority.
    """

    @staticmethod
    def _documented_scene_types() -> set[str]:
        import re
        doc = (PROJECT_ROOT / "remotion-composer" / "SCENE_TYPES.md").read_text()
        # Overlay-only types are documented in the same file but are not
        # cut.type values — they belong to edit_decisions.overlays.
        overlay_only = {"section_title", "stat_reveal", "provider_chip"}
        found = set(re.findall(r"^\|\s*\*{0,2}`([a-z_]+)`", doc, re.M))
        return {t for t in found if t not in overlay_only and t != "type"}

    def test_advertises_no_nonexistent_scene_type(self):
        advertised = set(VideoCompose._REMOTION_COMPONENTS)
        ghosts = advertised - self._documented_scene_types()
        assert not ghosts, f"advertised but not implemented: {sorted(ghosts)}"

    def test_advertises_every_real_scene_type(self):
        advertised = set(VideoCompose._REMOTION_COMPONENTS)
        missing = self._documented_scene_types() - advertised
        assert not missing, f"implemented but not advertised: {sorted(missing)}"

    def test_the_two_lists_cannot_drift(self):
        assert set(VideoCompose._REMOTION_COMPONENTS) == set(VideoCompose._REMOTION_SCENE_TYPES)
