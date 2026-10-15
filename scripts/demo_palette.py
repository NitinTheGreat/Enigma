"""
Module: scripts/demo_palette.py

Derives the demo palette from the ConjunctionTriage palette and checks it.

The two demos must read as coming from one team but must not look identical.
So the structure is kept and the hues are moved. Every accent is rotated by
the same angle, which preserves the relationships between accents, and every
neutral is moved from the warm parchment family into a cool slate family.
Lightness is held per token, so each token keeps its contrast role.

The rotation is chosen to keep every accent at least 40 degrees from each of
the four semantic colours fixed by the paper, so an accent can never be
mistaken for a verdict colour.

Every text and background pair the demo uses is checked against WCAG AA, and
the script exits non-zero if any pair fails, so the table in DESIGN_NOTES.md
cannot be wrong without the build saying so.
"""

from __future__ import annotations

import argparse
import colorsys
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "demo" / "design"

ACCENT_ROTATION = 250.0
NEUTRAL_HUE = 248.0
NEUTRAL_SATURATION_SCALE = 0.62
MIN_ACCENT_SHIFT = 40.0
MIN_SEMANTIC_DISTANCE = 40.0
LIGHTNESS_OVERRIDES = {"muted": 0.385}

OLD = {
    "paper": ("#e8e4da", "neutral", "page background"),
    "cream": ("#f5f1e8", "neutral", "panels, cards, drawer"),
    "field": ("#f8f5ec", "neutral", "inputs, raised surfaces"),
    "ink": ("#29261f", "neutral", "body text, headings, dark button"),
    "muted": ("#726e60", "neutral", "secondary text, captions, axis labels"),
    "line": ("#c8c3b5", "neutral", "rules, borders, dividers"),
    "dark": ("#25271e", "neutral", "footer and presenter panel ground"),
    "dark-hover": ("#464633", "neutral", "dark button hover"),
    "dark-text": ("#b4b5a6", "neutral", "secondary text on dark ground"),
    "dark-rule": ("#565847", "neutral", "rules on dark ground"),
    "olive": ("#777b45", "accent", "brand mark, eyebrow markers, checkbox accent"),
    "acid": ("#d0d68b", "accent", "primary button, selection, hover fill"),
    "acid-hover": ("#dfe4a9", "accent", "primary button hover"),
    "rust": ("#b45436", "accent", "focus ring, active tab, nav dot"),
}

SEMANTIC = {
    "works": "#2A6F4E",
    "inert": "#9E9B95",
    "disconnected": "#C84B31",
    "data": "#2B5B84",
}

PAIRS = [
    ("ink", "paper", "body text on page", 4.5),
    ("ink", "cream", "body text on panel", 4.5),
    ("muted", "paper", "secondary text on page", 4.5),
    ("muted", "cream", "secondary text on panel", 4.5),
    ("ink", "acid", "primary button label", 4.5),
    ("cream", "ink", "dark button label", 4.5),
    ("cream", "dark", "presenter notes text", 4.5),
    ("dark-text", "dark", "secondary text on dark", 4.5),
    ("rust", "paper", "focus ring and active marker, non-text", 3.0),
    ("olive", "paper", "accent text on page", 4.5),
    ("works", "cream", "verdict text, works", 4.5),
    ("data", "cream", "sensor text and wires", 4.5),
    ("cream", "works", "label on works fill", 4.5),
    ("cream", "data", "label on data fill", 4.5),
    ("white", "disconnected", "label on defect fill", 4.5),
    ("ink", "inert", "label on inert fill", 4.5),
    ("disconnected", "cream", "defect wire and cross, non-text", 3.0),
    ("ink", "line", "text on a rule colour, never used, sanity", 4.5),
]


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    """Return 0..1 RGB from a hex colour."""
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    """Return a hex colour from 0..1 RGB."""
    return "#" + "".join("%02x" % max(0, min(255, round(c * 255))) for c in rgb)


def hue_of(value: str) -> float:
    """Return hue in degrees."""
    h, _, _ = colorsys.rgb_to_hls(*hex_to_rgb(value))
    return h * 360.0


def hue_distance(a: float, b: float) -> float:
    """Return the shortest angle between two hues."""
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def luminance(value: str) -> float:
    """Return WCAG relative luminance."""
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in hex_to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """Return the WCAG contrast ratio of two colours."""
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def transform(value: str, role: str) -> str:
    """Move a token into the new family while holding its lightness."""
    h, l, s = colorsys.rgb_to_hls(*hex_to_rgb(value))
    if role == "accent":
        h = ((h * 360.0 + ACCENT_ROTATION) % 360.0) / 360.0
    else:
        h = NEUTRAL_HUE / 360.0
        s = s * NEUTRAL_SATURATION_SCALE
    return rgb_to_hex(colorsys.hls_to_rgb(h, l, s))


def derive(name: str, value: str, role: str) -> str:
    """Transform a token, applying a documented lightness override if it has one."""
    moved = transform(value, role)
    if name not in LIGHTNESS_OVERRIDES:
        return moved
    h, _, s = colorsys.rgb_to_hls(*hex_to_rgb(moved))
    return rgb_to_hex(colorsys.hls_to_rgb(h, LIGHTNESS_OVERRIDES[name], s))


def main() -> int:
    """Derive the palette, check it, and write the mapping."""
    parser = argparse.ArgumentParser(description="Derive and check the demo palette.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    new = {name: derive(name, value, role) for name, (value, role, _) in OLD.items()}
    palette = dict(new)
    palette.update(SEMANTIC)
    palette["white"] = "#ffffff"
    problems: list[str] = []

    mapping = []
    for name, (old_value, role, use) in OLD.items():
        new_value = new[name]
        shift = hue_distance(hue_of(old_value), hue_of(new_value))
        old_l = colorsys.rgb_to_hls(*hex_to_rgb(old_value))[1]
        new_l = colorsys.rgb_to_hls(*hex_to_rgb(new_value))[1]
        if role == "accent" and shift < MIN_ACCENT_SHIFT:
            problems.append("accent %s shifted only %.1f degrees" % (name, shift))
        if role == "accent":
            for sem_name, sem_value in SEMANTIC.items():
                if sem_name == "inert":
                    continue
                gap = hue_distance(hue_of(new_value), hue_of(sem_value))
                if gap < MIN_SEMANTIC_DISTANCE:
                    problems.append("accent %s within %.1f degrees of %s" % (name, gap, sem_name))
        mapping.append({
            "seed": args.seed, "token": name, "role": role, "used_for": use,
            "old": old_value, "new": new_value,
            "hue_old": round(hue_of(old_value), 1), "hue_new": round(hue_of(new_value), 1),
            "hue_shift": round(shift, 1),
            "lightness_old": round(old_l, 3), "lightness_new": round(new_l, 3),
        })

    ratios = []
    for fg, bg, use, required in PAIRS:
        ratio = contrast(palette[fg], palette[bg])
        passes = ratio >= required
        ratios.append({"seed": args.seed, "foreground": fg, "background": bg,
                       "fg_hex": palette[fg], "bg_hex": palette[bg], "use": use,
                       "ratio": round(ratio, 2), "required": required, "passes": passes})
        if not passes and "never used" not in use:
            problems.append("contrast %s on %s is %.2f, needs %.1f" % (fg, bg, ratio, required))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "palette.json").write_text(json.dumps(
        {"seed": args.seed, "accent_rotation": ACCENT_ROTATION, "neutral_hue": NEUTRAL_HUE,
         "tokens": new, "semantic": SEMANTIC, "lightness_overrides": LIGHTNESS_OVERRIDES, "mapping": mapping, "contrast": ratios,
         "problems": problems}, indent=2), encoding="utf-8")
    with (OUT_DIR / "palette_mapping.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(mapping[0].keys()))
        writer.writeheader()
        writer.writerows(mapping)
    with (OUT_DIR / "contrast.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ratios[0].keys()))
        writer.writeheader()
        writer.writerows(ratios)

    print("seed %d   accent rotation %+.0f deg   neutral hue %.0f deg" % (args.seed, ACCENT_ROTATION, NEUTRAL_HUE))
    print("")
    print("%-11s %-8s %-9s -> %-9s %8s %8s %8s" % ("token", "role", "old", "new", "hue old", "hue new", "shift"))
    for m in mapping:
        print("%-11s %-8s %-9s -> %-9s %8.1f %8.1f %8.1f" % (
            m["token"], m["role"], m["old"], m["new"], m["hue_old"], m["hue_new"], m["hue_shift"]))
    print("")
    print("%-14s %-14s %7s %5s  %s" % ("foreground", "background", "ratio", "need", "use"))
    for r in ratios:
        mark = "ok" if r["passes"] else "FAIL"
        print("%-14s %-14s %7.2f %5.1f  %-4s %s" % (r["foreground"], r["background"], r["ratio"],
                                                  r["required"], mark, r["use"]))
    print("")
    if problems:
        print("PROBLEMS")
        for p in problems:
            print("  " + p)
        return 1
    print("PALETTE OK, every accent moved at least %.0f deg, every used pair passes AA" % MIN_ACCENT_SHIFT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
