"""Playbook → Remotion theme, and subtitle styling.

Split out of video_compose.py (audit 2026-07-15, structural item 7): turning a
playbook YAML into a ThemeConfig, and a style dict into an ASS force_style
string, is design-system work, not composition. Six pure functions with no
dependency on VideoCompose's state.

VideoCompose keeps thin delegating staticmethods, so existing call sites and
tests are unchanged.
"""

from __future__ import annotations

import re
from typing import Any


def _is_light_hex(color: str) -> bool:
    """Rough perceptual lightness test for a #RRGGBB background."""
    v = (color or "").lstrip("#")
    if len(v) < 6:
        return False
    try:
        r, g, b = (int(v[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return False
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) > 140


def _pick_caption_highlight(candidates: list[str], scrim_hex: str, light_bg: bool) -> str:
    """First candidate that clears WCAG large-text contrast on the scrim.

    Uses styles.playbook_loader.validate_contrast — the playbook
    intelligence layer's own validator, which until now had no production
    caller at all (audit 2026-07-15, structural item 3). Captions are
    large, bold text, so 3:1 (AA large) is the right floor. Falls back to
    a guaranteed-legible neutral rather than shipping an invisible
    highlight.
    """
    try:
        from styles.playbook_loader import validate_contrast
    except Exception:
        return candidates[0] if candidates else "#22D3EE"
    for c in candidates:
        if not c:
            continue
        try:
            if validate_contrast(c, scrim_hex)["large_text"]["AA"]:
                return c
        except Exception:
            continue
    return "#0F172A" if light_bg else "#F8FAFC"


def _build_theme_from_playbook(playbook_name: str | None, composition_data: dict | None) -> dict[str, Any] | None:
    """Derive a Remotion ThemeConfig from a playbook's actual color values.

    Instead of passing a playbook name and hoping Remotion has a matching
    preset, we read the playbook YAML and extract concrete colors/fonts.
    This means custom playbooks, overridden palettes, and per-project
    styles all flow through to Remotion automatically.

    Falls back to extracting colors from edit_decisions metadata if
    no playbook is loadable.
    """
    theme: dict[str, Any] = {}

    # Try to load the playbook YAML
    playbook: dict[str, Any] = {}
    if playbook_name:
        try:
            from styles.playbook_loader import load_playbook
            playbook = load_playbook(playbook_name)
        except Exception:
            pass

    if playbook:
        vl = playbook.get("visual_language", {})
        palette = vl.get("color_palette", {})
        typo = playbook.get("typography", {})

        # Extract primary/accent — may be a list (gradient stops) or string
        primary_raw = palette.get("primary", ["#2563EB"])
        accent_raw = palette.get("accent", ["#F59E0B"])
        primary = primary_raw[0] if isinstance(primary_raw, list) else primary_raw
        accent = accent_raw[0] if isinstance(accent_raw, list) else accent_raw

        bg = palette.get("background", "#FFFFFF")
        text = palette.get("text", "#1F2937")
        surface = palette.get("surface", bg)
        # Schema key is `muted` — the old `muted_text` lookup never
        # matched any playbook, so the muted color silently stayed at
        # the default for every render (audit 2026-07-16, Wave 1 ⑤).
        muted = palette.get("muted") or palette.get("muted_text", "#6B7280")

        # Build chart colors from all palette entries
        chart_colors = []
        for key in ["primary", "accent", "secondary", "success", "warning", "info"]:
            val = palette.get(key)
            if val:
                chart_colors.append(val[0] if isinstance(val, list) else val)
        if len(chart_colors) < 3:
            chart_colors = [primary, accent, "#10B981", "#8B5CF6", "#EC4899", "#06B6D4"]

        theme = {
            "primaryColor": primary,
            "accentColor": accent,
            "backgroundColor": bg,
            "surfaceColor": surface,
            "textColor": text,
            "mutedTextColor": muted,
            # Schema key is `headings` (plural, see playbook.schema.json's
            # typography block) — the old singular `heading` lookup never
            # matched, so headingFont fell back to Inter for EVERY
            # playbook and theme typography was fiction.
            "headingFont": (typo.get("headings") or typo.get("heading") or {}).get("font", "Inter"),
            "bodyFont": typo.get("body", {}).get("font", "Inter"),
            "monoFont": typo.get("code", {}).get("font", "JetBrains Mono"),
            "chartColors": chart_colors[:6],
            "springConfig": {"damping": 20, "stiffness": 120, "mass": 1},
            "transitionDuration": 0.4,
        }

        # Caption background: semi-transparent scrim matching the theme.
        light_bg = _is_light_hex(bg)
        caption_bg_hex = "#FFFFFF" if light_bg else "#0F172A"
        theme["captionBackgroundColor"] = (
            "rgba(255, 255, 255, 0.85)" if light_bg else "rgba(15, 23, 42, 0.75)"
        )
        # The active-word highlight must POP against that scrim — that IS
        # its whole job. It used to be hardcoded to `primary`, which for a
        # dark-primary playbook meant an invisible highlight: anime-ghibli
        # rendered #2D5016 forest green on the #0F172A scrim — 1.93:1,
        # below even the 3:1 WCAG large-text floor, while the playbook's
        # own accent (#FFB347) scores 10.02:1. Root.tsx's hand-authored
        # THEMES already use accent for exactly this, so the bridge was
        # contradicting the theme it exists to reproduce (found by E2E
        # render inspection, 2026-07-17). Pick the first candidate that
        # actually passes, via the contrast validator the playbook
        # intelligence layer already ships.
        theme["captionHighlightColor"] = _pick_caption_highlight(
            [accent, primary], caption_bg_hex, light_bg
        )

        # Motion style from the playbook's pace. The schema puts pace
        # under identity.pace (slow/gentle/deliberate/moderate/fast/
        # rapid) — the old `motion.pace` lookup matched nothing, so this
        # branch never fired for any playbook.
        pace = (
            playbook.get("identity", {}).get("pace")
            or playbook.get("motion", {}).get("pace")
            or "moderate"
        )
        if pace in ("fast", "rapid"):
            theme["springConfig"] = {"damping": 12, "stiffness": 80, "mass": 1}
            theme["transitionDuration"] = 0.3
        elif pace in ("slow", "gentle", "deliberate"):
            theme["springConfig"] = {"damping": 25, "stiffness": 150, "mass": 1}
            theme["transitionDuration"] = 0.6

    # Fallback: try to extract from edit_decisions metadata
    if not theme and composition_data:
        meta = composition_data.get("metadata", {})
        if meta.get("primary_color"):
            theme = {
                "primaryColor": meta["primary_color"],
                "accentColor": meta.get("accent_color", "#F59E0B"),
                "backgroundColor": meta.get("background_color", "#FFFFFF"),
                "surfaceColor": meta.get("surface_color", "#F9FAFB"),
                "textColor": meta.get("text_color", "#1F2937"),
                "mutedTextColor": "#6B7280",
                "headingFont": meta.get("heading_font", "Inter"),
                "bodyFont": meta.get("body_font", "Inter"),
                "monoFont": "JetBrains Mono",
                "chartColors": meta.get("chart_colors", ["#2563EB", "#F59E0B", "#10B981"]),
                "springConfig": {"damping": 20, "stiffness": 120, "mass": 1},
                "transitionDuration": 0.4,
                "captionHighlightColor": meta["primary_color"],
                "captionBackgroundColor": "rgba(255, 255, 255, 0.85)",
            }

    return theme if theme else None


def _hex_to_ass_color(color: str, alpha: int=0) -> str:
    """Convert a #RRGGBB(AA) hex color to ASS &HAABBGGRR format.

    libass force_style color values MUST be in &HAABBGGRR (alpha 00 =
    opaque, FF = transparent; channels reversed vs CSS). Raw hex was
    previously passed straight through, so playbook-derived subtitle
    colors were misparsed or ignored on every burn — the styles never
    rendered as designed (audit 2026-07-16, Wave 1 ④). Values already in
    &H… form pass through; non-hex values (font names would never reach
    here, but rgba() strings could) fall back unchanged rather than
    producing garbage.
    """
    value = (color or "").strip()
    if value.upper().startswith("&H"):
        return value
    m = re.fullmatch(r"#?([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?", value)
    if not m:
        return value
    rgb = m.group(1)
    if m.group(2) is not None:
        # CSS trailing alpha: FF = opaque → ASS: 00 = opaque.
        alpha = 255 - int(m.group(2), 16)
    r, g, b = rgb[0:2], rgb[2:4], rgb[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _build_subtitle_style(style: dict) -> str:
    """Build ASS force_style string from style dict."""
    parts = []
    parts.append(f"FontName={style.get('font', 'Inter')}")
    parts.append(f"FontSize={style.get('font_size', 28)}")
    parts.append(f"Bold={1 if style.get('bold', True) else 0}")
    if style.get("primary_color"):
        parts.append(f"PrimaryColour={_hex_to_ass_color(style['primary_color'])}")
    if style.get("outline_color"):
        parts.append(f"OutlineColour={_hex_to_ass_color(style['outline_color'])}")
    if style.get("back_color"):
        # Semi-transparent by default: BackColour is the box fill under
        # BorderStyle=3 (and the shadow color otherwise) — a fully
        # opaque box reads heavy over video.
        parts.append(f"BackColour={_hex_to_ass_color(style['back_color'], alpha=0x60)}")
    border_style = style.get("border_style", 1)
    parts.append(f"BorderStyle={border_style}")
    parts.append(f"Outline={style.get('outline_width', 2)}")
    parts.append(f"Shadow={style.get('shadow', 0)}")
    parts.append(f"MarginV={style.get('margin_v', 40)}")
    parts.append(f"Alignment={style.get('alignment', 2)}")
    return ",".join(parts)


def _resolve_subtitle_style(explicit_style: dict | None, edit_decisions: dict | None, playbook: dict | None) -> dict:
    """Resolve subtitle style with layered priority.

    Priority: explicit_style > edit_decisions.subtitles.style > playbook > defaults.
    This prevents every video from looking identical (Arial bold white).
    """
    # Start with minimal fallback defaults
    resolved = {
        "font": "Inter",
        "font_size": 28,
        "bold": True,
        "outline_width": 2,
        "shadow": 0,
        "margin_v": 40,
        "alignment": 2,
    }

    # Layer 1: Playbook-derived style
    if playbook:
        typo = playbook.get("typography", {})
        colors = playbook.get("visual_language", {}).get("color_palette", {})
        # Schema key is `font` (see playbook.schema.json font_spec) — the
        # old `family` lookup never matched, so the subtitle font
        # silently stayed at the default for every playbook.
        body_font = typo.get("body", {}).get("font") or typo.get("body", {}).get("family")
        if body_font:
            resolved["font"] = body_font
        if colors.get("text"):
            resolved["primary_color"] = colors["text"]
        if colors.get("background"):
            resolved["outline_color"] = colors["background"]
            # Semi-transparent background for readability
            bg = colors["background"]
            resolved["back_color"] = bg

    # Layer 2: edit_decisions subtitle style
    if edit_decisions:
        ed_style = edit_decisions.get("subtitles", {}).get("style", {})
        for k, v in ed_style.items():
            if v is not None:
                resolved[k] = v

    # Layer 3: Explicit override (highest priority)
    if explicit_style:
        for k, v in explicit_style.items():
            if v is not None:
                resolved[k] = v

    return resolved
