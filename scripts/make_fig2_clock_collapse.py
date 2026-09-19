"""
Module: scripts/make_fig2_clock_collapse.py

Draws Figure 2, the clock domain collapse, from the Level 8 study output.

Two of the three panels the build plan specified carry no information and are
replaced. Panel A is drawn as asked.

The plan's Panel C was mean iterations to termination. That is 3.0 in every
clock mode, for the reason L7.5 established and L7.8.6 confirmed against a
real model: the 0.8 convergence threshold is never reached, so every analysis
terminates by exhausting its three iteration budget whatever the clock does.

The plan's Panel B was the convergence fraction and the mean final UNKNOWN
confidence. The first is 0.000 in all three modes, for the same reason. The
second is 0.509, 0.512 and 0.511, a spread of three thousandths against seed
deviations of about one. Both are reported as text in the study output rather
than drawn as six near identical bars.

What replaces them is the causal chain the study actually demonstrates.
Panel B is the mechanism: conflating the clocks makes every situation look
stale, staleness marks it quiet, and quiet drives abstention. Panel C is the
consequence for the outcome metrics, where conflation appears to improve
correctness while in fact only abstaining more often on a suite whose ground
truth mostly says abstain.

Colour encodes the clock mode and nothing else, consistently across all three
panels, so a reader learns the mapping once. Each panel groups by measure
rather than by mode for the same reason. The palette is the project's
existing series triple, which passes the categorical checks for lightness,
chroma, colour vision deficiency separation and normal vision separation; its
green sits below a three to one contrast ratio against the surface, so every
bar carries a printed value as the required relief.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results" / "clock_study"
FIGURES_DIR = PROJECT_ROOT / "figures"
PREVIEW_DIR = FIGURES_DIR / "preview"

SERIES = {
    "conflated": "#eb6834",
    "wall": "#2a78d6",
    "separated": "#1baf7a",
}
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
AXIS_LINE = "#c3c2b7"
SURFACE = "#fcfcfb"

TREND_ORDER = ("escalating", "stable", "deescalating")


def style() -> None:
    """Apply the project's figure styling."""
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "axes.titlesize": 9.5,
            "axes.labelcolor": INK_SECONDARY,
            "axes.edgecolor": AXIS_LINE,
            "axes.titlecolor": INK_PRIMARY,
            "axes.linewidth": 0.8,
            "xtick.color": INK_MUTED,
            "ytick.color": INK_MUTED,
            "xtick.labelcolor": INK_SECONDARY,
            "ytick.labelcolor": INK_SECONDARY,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "grid.color": GRIDLINE,
            "grid.linewidth": 0.7,
            "legend.frameon": False,
            "legend.fontsize": 8.5,
        }
    )


def grouped(ax, categories, series_values, series_errors, modes, ymax=1.0):
    """Draw one grouped bar panel with direct value labels."""
    positions = np.arange(len(categories), dtype=float)
    width = 0.26
    for index, mode in enumerate(modes):
        offset = (index - (len(modes) - 1) / 2.0) * width
        values = series_values[mode]
        errors = series_errors.get(mode)
        bars = ax.bar(
            positions + offset,
            values,
            width * 0.92,
            label=mode,
            color=SERIES[mode],
            edgecolor=SURFACE,
            linewidth=1.2,
            yerr=errors,
            error_kw={"ecolor": INK_SECONDARY, "elinewidth": 0.8, "capsize": 2},
            zorder=3,
        )
        for bar, value in zip(bars, values):
            ax.annotate(
                f"{value:.2f}",
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                textcoords="offset points",
                xytext=(0, 2.5),
                ha="center",
                va="bottom",
                fontsize=6.6,
                color=INK_SECONDARY,
                zorder=4,
            )
    ax.set_xticks(positions)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, ymax)
    ax.yaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def main() -> int:
    """Build Figure 2 as a PDF with a PNG preview."""
    parser = argparse.ArgumentParser(description="Figure 2, clock collapse.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    report = json.loads(
        (RESULTS_DIR / f"study_seed{args.seed}.json").read_text(encoding="utf-8")
    )
    summaries = {s["clock_mode"]: s for s in report["summaries"]}
    modes = [m for m in ("conflated", "wall", "separated") if m in summaries]

    style()
    figure, axes = plt.subplots(1, 3, figsize=(10.5, 3.5))

    shares = {
        mode: [summaries[mode]["trend_distribution_share"].get(t, 0.0) for t in TREND_ORDER]
        for mode in modes
    }
    grouped(axes[0], list(TREND_ORDER), shares, {}, modes)
    axes[0].set_title("A  Trend label distribution", loc="left", pad=8)
    axes[0].set_ylabel("share of iterations")

    panel_b_fields = [
        ("quiet_fraction", "quiet detected"),
        ("abstention_rate", "abstention rate"),
    ]
    values_b = {
        mode: [summaries[mode][f"{f}_mean"] for f, _ in panel_b_fields] for mode in modes
    }
    errors_b = {
        mode: [summaries[mode][f"{f}_sd"] for f, _ in panel_b_fields] for mode in modes
    }
    grouped(axes[1], [label for _, label in panel_b_fields], values_b, errors_b, modes)
    axes[1].set_title("B  Quiescence and abstention", loc="left", pad=8)
    axes[1].set_ylabel("fraction")

    panel_c_fields = [
        ("false_conclusion_rate", "false\nconclusion"),
        ("premature_convergence_rate", "premature\nconvergence"),
        ("appropriate_abstention_rate", "appropriate\nabstention"),
    ]
    values_c = {
        mode: [summaries[mode][f"{f}_mean"] for f, _ in panel_c_fields] for mode in modes
    }
    errors_c = {
        mode: [summaries[mode][f"{f}_sd"] for f, _ in panel_c_fields] for mode in modes
    }
    grouped(axes[2], [label for _, label in panel_c_fields], values_c, errors_c, modes)
    axes[2].set_title("C  What that does to the outcome metrics", loc="left", pad=8)
    axes[2].set_ylabel("fraction")

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="lower center",
        ncol=len(modes),
        bbox_to_anchor=(0.5, -0.02),
        title=None,
    )
    figure.suptitle(
        "Clock domain conflation collapses trend detection and forces abstention",
        x=0.008,
        y=0.995,
        ha="left",
        fontsize=10.5,
        color=INK_PRIMARY,
    )
    seeds = report.get("seeds", [])
    figure.text(
        0.008,
        0.915,
        f"Sub-suite {report['suite_hash'][:8]}, {report['scenarios']} scenarios, "
        f"{len(seeds)} seeds, {report['model_name']}. Error bars are one standard "
        f"deviation across seeds.",
        ha="left",
        fontsize=7.4,
        color=INK_MUTED,
    )

    figure.tight_layout(rect=(0, 0.06, 1, 0.90))

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = FIGURES_DIR / "fig2_clock_collapse.pdf"
    png_path = PREVIEW_DIR / "fig2_clock_collapse.png"
    figure.savefig(pdf_path, bbox_inches="tight")
    figure.savefig(png_path, dpi=200, bbox_inches="tight")
    plt.close(figure)

    print(f"seed {args.seed}")
    print(f"modes {modes}")
    print("panel B replaced: convergence_fraction 0.000 in every mode, and")
    print("  mean_final_unknown_confidence spans 0.509 to 0.512")
    print("panel C replaced: mean_iterations_to_termination is 3.0 in every mode")
    for mode in modes:
        s = summaries[mode]
        print(
            f"  {mode:<11} trends {len(s['trend_distribution_pooled'])}  "
            f"quiet {s['quiet_fraction_mean']:.4f}  "
            f"iters {s['mean_iterations_to_termination_mean']:.2f}"
        )
    print(f"written {pdf_path.relative_to(PROJECT_ROOT)}")
    print(f"written {png_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
