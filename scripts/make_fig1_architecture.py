"""
Module: scripts/make_fig1_architecture.py

Draws Figure 1, the architecture and data flow, drawn honestly.

Four things this figure must show that a conventional block diagram would
hide, and each is a finding from an appendix rather than a decoration.

The information barrier. assemble_context exposes ten aggregated fields and
nothing else, no raw signals, no entity identifiers, no timestamps. L8.1.1
measured what that costs: the ten fields separate the four evidence regimes
with a lift of 0.288 over the base rate and carry no narrative identity at
all, at a lift of minus 0.105. The barrier is drawn as a wall with the field
list on it.

The three unused adapters. Auth, video and a generic adapter were written
and are exercised by tests, and nothing routes to them in any experiment in
this project. They are greyed rather than omitted.

The abstention path that does not exist. The sensor emits an abstained flag
and the reasoning layer counts it into its snapshot and then reads it
nowhere. L9.8 measured the consequence: clearing the flag on every signal
changes the outcome by 0.000000. It is drawn as a dashed edge labelled
specified but not enacted.

Persistence and belief inertia. Both sit inside the LangGraph loop and both
are named in the audit table, so both are marked where they act. Persistence
carries the clamp that L9.7 identified as the reason no analysis converges.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = PROJECT_ROOT / "figures"
PREVIEW_DIR = FIGURES_DIR / "preview"

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
SURFACE = "#fcfcfb"
AXIS_LINE = "#c3c2b7"
LIVE_FILL = "#e3eefb"
LIVE_EDGE = "#2a78d6"
DEAD_FILL = "#eeeeea"
DEAD_EDGE = "#b8b7af"
BARRIER = "#1baf7a"
BROKEN = "#eb6834"


def box(ax, x, y, w, h, title, subtitle, live=True, fontsize=7.4):
    """Draw one component box, live or greyed."""
    face = LIVE_FILL if live else DEAD_FILL
    edge = LIVE_EDGE if live else DEAD_EDGE
    ink = INK_PRIMARY if live else INK_MUTED
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            linewidth=1.0,
            edgecolor=edge,
            facecolor=face,
            zorder=3,
        )
    )
    ax.text(
        x + w / 2,
        y + h - 0.024,
        title,
        ha="center",
        va="top",
        fontsize=fontsize,
        color=ink,
        fontweight="bold" if live else "normal",
        zorder=4,
    )
    if subtitle:
        ax.text(
            x + w / 2,
            y + h - 0.058,
            subtitle,
            ha="center",
            va="top",
            fontsize=fontsize - 1.6,
            color=INK_SECONDARY if live else INK_MUTED,
            zorder=4,
            linespacing=1.25,
        )


def arrow(ax, start, end, colour=INK_SECONDARY, dashed=False, label=None, label_dy=0.014, width=1.2):
    """Draw a flow edge between two points."""
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=width,
            color=colour,
            linestyle=(0, (3.5, 2.5)) if dashed else "solid",
            shrinkA=0,
            shrinkB=0,
            zorder=2,
        )
    )
    if label:
        ax.text(
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2 + label_dy,
            label,
            ha="center",
            va="bottom",
            fontsize=6.2,
            color=colour,
            zorder=4,
        )


def main() -> int:
    """Build Figure 1 as a PDF with a PNG preview."""
    parser = argparse.ArgumentParser(description="Figure 1, architecture.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.size": 7.5,
        }
    )
    figure, ax = plt.subplots(figsize=(7.16, 5.3))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.0,
        0.985,
        "Figure 1  Enigma architecture, with the audited mechanisms marked",
        ha="left",
        va="top",
        fontsize=9.6,
        color=INK_PRIMARY,
        fontweight="bold",
    )
    ax.text(
        0.0,
        0.945,
        "Greyed components exist and are tested but nothing routes to them. "
        "The dashed edge is specified and not enacted.",
        ha="left",
        va="top",
        fontsize=6.8,
        color=INK_MUTED,
    )

    box(ax, 0.00, 0.775, 0.20, 0.105, "UNSW-NB15 replay",
        "40 scenarios, 963 signals\nsub-suite a2b37f29")
    box(ax, 0.00, 0.620, 0.20, 0.115, "Sensor",
        "deep ensemble, temperature\nscaled, reject option\nabstains on 22.85%")

    box(ax, 0.265, 0.775, 0.155, 0.105, "Network adapter", "the only routed\nadapter")
    box(ax, 0.265, 0.655, 0.155, 0.085, "Auth adapter", "written, unused", live=False)
    box(ax, 0.265, 0.550, 0.155, 0.085, "Video adapter", "written, unused", live=False)
    box(ax, 0.265, 0.445, 0.155, 0.085, "Generic adapter", "written, unused", live=False)

    box(ax, 0.485, 0.775, 0.175, 0.105, "Situation store",
        "entity correlation\n66 situations")

    ax.plot([0.700, 0.700], [0.115, 0.900], color=BARRIER, linewidth=2.2,
            linestyle=(0, (5, 3)), zorder=2)
    ax.text(0.706, 0.896, "information barrier", ha="left", va="top",
            fontsize=7.0, color=BARRIER, fontweight="bold")
    ax.text(
        0.706,
        0.868,
        "assemble_context passes ten aggregate fields only:\n"
        "evidence_count, event_rate_per_minute,\n"
        "active_duration_seconds, burst_detected,\n"
        "quiet_detected, trend, confidence_level,\n"
        "source_diversity, mean_anomaly_score, iteration\n"
        "No raw signal, entity, timestamp or signal id.",
        ha="left",
        va="top",
        fontsize=6.1,
        color=INK_SECONDARY,
        linespacing=1.45,
    )

    box(ax, 0.715, 0.545, 0.275, 0.085, "LangGraph reasoning loop",
        "max 3 iterations, Gemini 2.5 Flash")

    box(ax, 0.715, 0.400, 0.128, 0.105, "generate", "U  UNKNOWN\nhypothesis")
    box(ax, 0.862, 0.400, 0.128, 0.105, "sanity gate", "S  doubt boost")
    box(ax, 0.715, 0.258, 0.128, 0.115, "evaluate", "A  asymmetric\ndecay\nP  persistence")
    box(ax, 0.862, 0.258, 0.128, 0.115, "belief inertia", "cap 0.15 on\nconfidence\nmovement")

    arrow(ax, (0.779, 0.545), (0.779, 0.500))
    arrow(ax, (0.843, 0.447), (0.862, 0.447))
    arrow(ax, (0.926, 0.398), (0.926, 0.368))
    arrow(ax, (0.862, 0.307), (0.843, 0.307))
    arrow(ax, (0.740, 0.248), (0.740, 0.140))
    ax.add_patch(
        FancyArrowPatch(
            (0.700, 0.307),
            (0.700, 0.588),
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=1.1,
            color=INK_SECONDARY,
            connectionstyle="arc3,rad=-0.45",
            shrinkA=0,
            shrinkB=0,
            zorder=2,
        )
    )
    ax.text(0.658, 0.447, "loop", ha="center", va="center", fontsize=6.2,
            color=INK_SECONDARY, rotation=90)

    box(ax, 0.715, 0.040, 0.275, 0.085, "Explanation and dashboard",
        "integrity gated, websocket feed")

    arrow(ax, (0.215, 0.830), (0.265, 0.830))
    arrow(ax, (0.107, 0.780), (0.107, 0.742))
    arrow(ax, (0.235, 0.690), (0.265, 0.740), label=None)
    arrow(ax, (0.420, 0.830), (0.485, 0.830))
    arrow(ax, (0.660, 0.800), (0.790, 0.636), label=None)

    ax.add_patch(
        FancyArrowPatch(
            (0.107, 0.598),
            (0.752, 0.248),
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=1.5,
            color=BROKEN,
            linestyle=(0, (3.5, 2.5)),
            connectionstyle="arc3,rad=0.30",
            shrinkA=0,
            shrinkB=0,
            zorder=2,
        )
    )
    ax.text(
        0.400,
        0.272,
        "abstained flag: specified but not enacted\n"
        "counted into the snapshot, read by no decision\n"
        "clearing it changes the outcome by 0.000000  (L9.8)",
        ha="center",
        va="center",
        fontsize=6.3,
        color=BROKEN,
        linespacing=1.4,
    )

    ax.text(
        0.0,
        0.205,
        "Audited mechanisms",
        ha="left",
        va="top",
        fontsize=7.4,
        color=INK_PRIMARY,
        fontweight="bold",
    )
    ax.text(
        0.0,
        0.175,
        "U  UNKNOWN hypothesis   works, main effect on abstention minus 0.0985\n"
        "S  sanity gate          works, minus 0.0833, overlaps U by 0.0833\n"
        "A  asymmetric decay     inert, minus 0.0030 at one deviation\n"
        "P  persistence          a clamp, not a requirement: no named hypothesis\n"
        "                        survives an iteration, so it holds convergence\n"
        "                        at the threshold minus 0.01  (L9.7)\n"
        "    belief inertia      no effect on convergence, plus 0.0000  (L9.10)",
        ha="left",
        va="top",
        fontsize=6.1,
        color=INK_SECONDARY,
        linespacing=1.5,
        family="DejaVu Sans Mono",
    )

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    pdf = FIGURES_DIR / "fig1_architecture.pdf"
    figure.savefig(pdf, bbox_inches="tight")
    figure.savefig(PREVIEW_DIR / "fig1_architecture.png", dpi=200, bbox_inches="tight")
    plt.close(figure)

    print(f"seed {args.seed}")
    print("information barrier marked with its ten fields")
    print("three unused adapters greyed rather than omitted")
    print("abstention path drawn dashed, labelled specified but not enacted")
    print("persistence and belief inertia marked inside the loop")
    print(f"written {pdf.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
