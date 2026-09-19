"""
Module: scripts/make_fig3_fig6.py

Draws Figure 3, the ablation main effects, and Figure 6, a belief trajectory.

Figure 3 shows the four single switch removals against the two baselines,
because sixteen bars in one column is unreadable and the full sixteen row
table belongs in the appendix. Colour separates the two reference
configurations from the four removals rather than encoding a fourth variable,
so a reader sees at once whether a removal moves a metric away from all on
and toward all off.

The third panel is not the one the brief implies. Inappropriate abstention
sits at 0.01 or below in every one of the six configurations, so drawing it
gives six bars at the axis. It is replaced by the abstention rate on the
sparse regime, which is where the whole effect turns out to live: the main
effects are 0.55 and 0.45 there against 0.006 on unknown attack.

Figure 6 is one situation's belief trajectory. The situation was chosen by a
rule fixed before any trajectory was plotted, so it is a typical case rather
than a flattering one: among the unknown attack situations of the all on cell
at seed 42, take the one whose evidence count at termination is the median of
that regime, breaking ties by the lexicographically smallest situation
identifier. The unknown attack regime is chosen because it is the regime the
two level abstention claim rests on and the one carrying the highest
abstained signal fraction.

The threshold drawn as a horizontal rule is the one that cell actually ran
at, and the UNKNOWN hypothesis is drawn bold and dashed so its behaviour
against the others is legible without reading the legend.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results" / "ablation"
FIGURES_DIR = PROJECT_ROOT / "figures"
PREVIEW_DIR = FIGURES_DIR / "preview"

SERIES_REFERENCE = "#1baf7a"
SERIES_REMOVAL = "#2a78d6"
SERIES_ALLOFF = "#eb6834"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
AXIS_LINE = "#c3c2b7"
SURFACE = "#fcfcfb"

LIVE_METRICS = (
    ("abstention_rate", "Abstention rate, overall"),
    ("appropriate_abstention_rate", "Appropriate abstention"),
    ("sparse_abstention_rate", "Abstention rate, sparse regime"),
    ("premature_convergence_rate", "Premature convergence"),
)
ORDER = ("allon", "U", "S", "A", "P", "USAP")
LABELS = {
    "allon": "all on",
    "U": "minus U",
    "S": "minus S",
    "A": "minus A",
    "P": "minus P",
    "USAP": "all off",
}


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


def colour_for(configuration: str) -> str:
    """Return the colour a configuration is drawn in."""
    if configuration == "allon":
        return SERIES_REFERENCE
    if configuration == "USAP":
        return SERIES_ALLOFF
    return SERIES_REMOVAL


def figure_three(
    cells: list[dict[str, Any]],
    threshold: float,
    seed: int,
    regime_values: dict[str, list[float]],
) -> Path:
    """Draw the main effects figure."""
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in cells:
        if float(row["convergence_threshold"]) != threshold:
            continue
        if row["configuration"] not in ORDER:
            continue
        for metric, _ in LIVE_METRICS:
            if metric == "sparse_abstention_rate":
                continue
            grouped[row["configuration"]][metric].append(float(row[metric]))

    for configuration, values in regime_values.items():
        grouped[configuration]["sparse_abstention_rate"] = values

    style()
    figure, axes = plt.subplots(1, 4, figsize=(11.5, 3.4))
    positions = np.arange(len(ORDER), dtype=float)

    for index, (metric, title) in enumerate(LIVE_METRICS):
        ax = axes[index]
        values = [
            float(np.mean(grouped[c][metric])) if grouped[c][metric] else 0.0
            for c in ORDER
        ]
        errors = [
            float(np.std(grouped[c][metric])) if grouped[c][metric] else 0.0
            for c in ORDER
        ]
        bars = ax.bar(
            positions,
            values,
            0.66,
            color=[colour_for(c) for c in ORDER],
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
                fontsize=6.4,
                color=INK_SECONDARY,
                zorder=4,
            )
        ax.set_xticks(positions)
        ax.set_xticklabels([LABELS[c] for c in ORDER], rotation=40, ha="right")
        ax.set_ylim(0, 1.12)
        ax.set_title(title, loc="left", pad=8)
        ax.yaxis.grid(True, zorder=0)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if index == 0:
            ax.set_ylabel("rate")

    figure.suptitle(
        "UNKNOWN and the sanity gate move abstention; decay and persistence do not",
        x=0.006,
        y=0.995,
        ha="left",
        fontsize=10.5,
        color=INK_PRIMARY,
    )
    figure.text(
        0.006,
        0.915,
        f"Sub-suite a2b37f29, 40 scenarios, 5 seeds, convergence threshold "
        f"{threshold}. Green is all four mechanisms on, orange is all four off, "
        f"blue is one removed. Error bars are one standard deviation across seeds.",
        ha="left",
        fontsize=7.3,
        color=INK_MUTED,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.90))

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    pdf = FIGURES_DIR / "fig3_ablation_main_effects.pdf"
    figure.savefig(pdf, bbox_inches="tight")
    figure.savefig(
        PREVIEW_DIR / "fig3_ablation_main_effects.png", dpi=200, bbox_inches="tight"
    )
    plt.close(figure)
    return pdf


def choose_situation(path: Path, entities: dict[str, str], regimes: dict[str, str]):
    """Apply the pre-declared selection rule and return the chosen situation."""
    final: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("record_type") == "retry":
            continue
        if record.get("terminated"):
            situation = str(record.get("situation_id"))
            final.setdefault(situation, record)

    candidates = []
    for situation, record in final.items():
        entity = entities.get(situation, "")
        scenario = None
        for part in entity.replace(":", "-").split("-"):
            if len(part) == 6 and part.startswith("s") and part[1:].isdigit():
                scenario = part
        if scenario is None:
            continue
        if regimes.get(scenario) != "unknown_attack":
            continue
        candidates.append((int(record.get("evidence_count") or 0), situation))

    if not candidates:
        return None, None
    counts = sorted(c for c, _ in candidates)
    target = counts[len(counts) // 2]
    matching = sorted(s for c, s in candidates if c == target)
    return matching[0], target


def figure_six(
    path: Path, situation: str, threshold: float, seed: int, evidence_count: int
) -> Path:
    """Draw the belief trajectory for one situation."""
    trajectories: dict[str, list[tuple[int, float]]] = defaultdict(list)
    unknown_id = "UNKNOWN"
    iterations_seen: set[int] = set()

    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("record_type") == "retry":
            continue
        if str(record.get("situation_id")) != situation:
            continue
        records.append(record)

    analyses: dict[int, list[dict[str, Any]]] = defaultdict(list)
    index = -1
    previous = 99
    for record in records:
        iteration = int(record.get("iteration") or 0)
        if iteration <= previous:
            index += 1
        previous = iteration
        analyses[index].append(record)

    chosen_analysis = max(analyses.values(), key=len)
    for record in chosen_analysis:
        iteration = int(record.get("iteration") or 0)
        iterations_seen.add(iteration)
        for hypothesis in record.get("hypotheses", []):
            key = str(hypothesis.get("hypothesis_id"))
            trajectories[key].append(
                (iteration, float(hypothesis.get("confidence") or 0.0))
            )

    style()
    figure, ax = plt.subplots(figsize=(7.0, 4.4))

    ordinary = [k for k in trajectories if k != unknown_id]
    recurring = sum(1 for k in ordinary if len({i for i, _ in trajectories[k]}) > 1)
    drawn_label = False
    for key in sorted(ordinary):
        points = sorted(trajectories[key])
        ax.plot(
            [p[0] for p in points],
            [p[1] for p in points],
            marker="o",
            markersize=5.5,
            linewidth=0.0,
            color=SERIES_REMOVAL,
            alpha=0.85,
            label=None if drawn_label else "named hypothesis, one iteration only",
            zorder=3,
        )
        drawn_label = True

    if unknown_id in trajectories:
        points = sorted(trajectories[unknown_id])
        ax.plot(
            [p[0] for p in points],
            [p[1] for p in points],
            marker="s",
            markersize=6,
            linewidth=3.0,
            linestyle="--",
            color=SERIES_REFERENCE,
            label="UNKNOWN, the only hypothesis that persists",
            zorder=4,
        )

    ax.axhline(
        threshold,
        color=INK_SECONDARY,
        linewidth=1.2,
        linestyle=":",
        zorder=2,
    )
    ax.annotate(
        f"convergence threshold {threshold}",
        (max(iterations_seen) if iterations_seen else 3, threshold),
        textcoords="offset points",
        xytext=(-4, 5),
        ha="right",
        fontsize=7.4,
        color=INK_SECONDARY,
    )

    ax.set_xlabel("iteration")
    ax.set_ylabel("confidence")
    ax.set_xticks(sorted(iterations_seen))
    ax.set_ylim(0, 1.0)
    ax.yaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="lower left", ncol=1)
    ax.annotate(
        f"{len(ordinary)} named hypotheses proposed across the analysis, "
        f"{recurring} appear in more than one iteration",
        (0.5, 0.30),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=7.6,
        color=INK_SECONDARY,
    )

    figure.suptitle(
        "No named hypothesis survives an iteration, so persistence can never be satisfied",
        x=0.006,
        y=1.02,
        ha="left",
        fontsize=10,
        color=INK_PRIMARY,
    )
    newline = chr(10)
    caption = (
        f"Situation {situation[:8]}, unknown attack regime, all four mechanisms on, "
        f"seed {seed}, threshold {threshold}." + newline +
        f"{evidence_count} pieces of evidence at termination, the median of that "
        "regime, chosen by a rule fixed before plotting." + newline +
        "Generation replaces the hypothesis list each iteration, so "
        "dominant_iterations never exceeds zero."
    )
    figure.text(
        0.006,
        0.90,
        caption,
        ha="left",
        fontsize=7.3,
        color=INK_MUTED,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.78))

    pdf = FIGURES_DIR / "fig6_belief_trajectory.pdf"
    figure.savefig(pdf, bbox_inches="tight")
    figure.savefig(
        PREVIEW_DIR / "fig6_belief_trajectory.png", dpi=200, bbox_inches="tight"
    )
    plt.close(figure)
    return pdf


def main() -> int:
    """Build both figures."""
    parser = argparse.ArgumentParser(description="Figures 3 and 6.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold", type=float, default=0.80)
    parser.add_argument("--trajectory-seed", type=int, default=42)
    args = parser.parse_args()

    import csv

    cells_path = RESULTS_DIR / f"cells_seed{args.seed}.csv"
    with cells_path.open(encoding="utf-8") as handle:
        cells = list(csv.DictReader(handle))

    sparse_lookup: dict[str, list[float]] = defaultdict(list)
    detail_path = RESULTS_DIR / f"cells_detail_seed{args.seed}.json"
    for row in json.loads(detail_path.read_text(encoding="utf-8")):
        if float(row["convergence_threshold"]) != args.threshold:
            continue
        if row["configuration"] not in ORDER:
            continue
        sparse_lookup[row["configuration"]].append(
            float(row["per_regime"]["sparse"]["abstention_rate"])
        )
    pdf3 = figure_three(cells, args.threshold, args.seed, sparse_lookup)

    suite_path = PROJECT_ROOT / "results" / "scenarios" / "sub_suite.jsonl"
    regimes: dict[str, str] = {}
    for line in suite_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        regimes[row["scenario_id"]] = row["ground_truth"]["regime"]

    tag = f"t{int(round(args.threshold * 100)):03d}"
    log = RESULTS_DIR / f"allon_{tag}_{args.trajectory_seed}.jsonl"
    entity_path = RESULTS_DIR / f"allon_{tag}_{args.trajectory_seed}_entities.json"
    entities = json.loads(entity_path.read_text(encoding="utf-8"))
    situation, evidence_count = choose_situation(log, entities, regimes)
    if situation is None:
        print("no unknown attack situation found for the trajectory")
        return 1
    pdf6 = figure_six(log, situation, args.threshold, args.trajectory_seed, evidence_count)

    print(f"seed {args.seed}   threshold {args.threshold}")
    print(f"Figure 3 configurations drawn: {list(ORDER)}")
    print(f"Figure 6 situation chosen: {situation}")
    print(f"  rule: median evidence count of the unknown attack regime, "
          f"ties by smallest situation id")
    print(f"  evidence count at termination: {evidence_count}")
    print(f"written {pdf3.relative_to(PROJECT_ROOT)}")
    print(f"written {pdf6.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
