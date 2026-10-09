"""
Module: scripts/make_fig1_architecture.py

Draws Figure 1, the architecture and data flow, laid out to match the graph
the builder actually compiles.

The reasoning loop is drawn in its true order. Context assembly is the first
node of every iteration, followed by generation, the sanity gate,
evaluation, belief inertia and the convergence update, which either loops
back to context assembly or ends. The persistence clamp sits on the
convergence node, where the code applies it, and not on evaluation, where an
earlier version of this figure placed it.

Four things a conventional block diagram would hide are drawn because each
is a finding: the information barrier and the ten fields that cross it, the
three adapters that are written and never routed, the sensor abstention
path that stops at the barrier, and the node at which each audited
mechanism acts.

Every label is checked geometrically after rendering. The script measures
each text against its box, against every other text, and against every
arrow and rule, and refuses to report success if anything collides, so the
layout is verified rather than judged by eye.
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
PAPER_FIGURES_DIR = PROJECT_ROOT / "paper" / "enigma-paper" / "figures"

WIDTH_IN = 7.16
HEIGHT_IN = 3.6

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
SURFACE = "#fcfcfb"
LIVE_FILL = "#e3eefb"
LIVE_EDGE = "#2a78d6"
DEAD_FILL = "#eeeeea"
DEAD_EDGE = "#b8b7af"
LOOP_FILL = "#f4f7fb"
LOOP_EDGE = "#c3cfe0"
BARRIER = "#1baf7a"
BROKEN = "#eb6834"

TITLE_SIZE = 7.4
BODY_SIZE = 6.2
FIELD_SIZE = 5.7

BARRIER_X = 0.480

TEN_FIELDS = (
    "evidence_count",
    "event_rate_per_minute",
    "active_duration_seconds",
    "burst_detected",
    "quiet_detected",
    "trend",
    "confidence_level",
    "source_diversity",
    "mean_anomaly_score",
    "iteration",
)


class Layout:
    """Records every drawn element so collisions can be measured."""

    def __init__(self, ax):
        self.ax = ax
        self.boxes: list[dict] = []
        self.free_texts: list[tuple[str, object]] = []
        self.paths: list[tuple[str, list[tuple[float, float]]]] = []

    def box(self, name, x, y, w, h, title, body="", live=True, fill=None, edge=None,
            title_at=None, body_at=None):
        """Draw a component box and remember it with its labels."""
        face = fill or (LIVE_FILL if live else DEAD_FILL)
        line = edge or (LIVE_EDGE if live else DEAD_EDGE)
        self.ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h,
                boxstyle="round,pad=0,rounding_size=0.008",
                linewidth=0.9, edgecolor=line, facecolor=face, zorder=2,
            )
        )
        ink = INK_PRIMARY if live else INK_MUTED
        texts = []
        centre = x + w / 2
        if title:
            ty = title_at if title_at is not None else (y + h * 0.70 if body else y + h / 2)
            texts.append(
                self.ax.text(centre, ty, title, ha="center", va="center",
                             fontsize=TITLE_SIZE, color=ink,
                             fontweight="bold" if live else "normal", zorder=4)
            )
        if body:
            by = body_at if body_at is not None else y + h * 0.33
            texts.append(
                self.ax.text(centre, by, body, ha="center", va="center",
                             fontsize=BODY_SIZE, linespacing=1.25,
                             color=INK_SECONDARY if live else INK_MUTED, zorder=4)
            )
        self.boxes.append({"name": name, "rect": (x, y, w, h), "texts": texts,
                           "container": False})
        return texts

    def container(self, name, x, y, w, h):
        """Draw an enclosing region that arrows and boxes may sit inside."""
        self.ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h,
                boxstyle="round,pad=0,rounding_size=0.012",
                linewidth=0.8, edgecolor=LOOP_EDGE, facecolor=LOOP_FILL, zorder=1,
            )
        )
        self.boxes.append({"name": name, "rect": (x, y, w, h), "texts": [],
                           "container": True})

    def adopt(self, box_name, handle):
        """Move a label from the free list into a box, so it is checked as inside it."""
        self.free_texts = [(n, t) for n, t in self.free_texts if t is not handle]
        for b in self.boxes:
            if b["name"] == box_name:
                b["texts"].append(handle)
                return handle
        raise KeyError(box_name)

    def text(self, name, x, y, s, **kwargs):
        """Place a free label and remember it."""
        kwargs.setdefault("fontsize", BODY_SIZE)
        kwargs.setdefault("zorder", 4)
        handle = self.ax.text(x, y, s, **kwargs)
        self.free_texts.append((name, handle))
        return handle

    def arrow(self, name, start, end, colour=INK_SECONDARY, dashed=False, width=1.0):
        """Draw a straight arrow and remember its path."""
        self.ax.add_patch(
            FancyArrowPatch(
                start, end, arrowstyle="-|>", mutation_scale=7.5,
                linewidth=width, color=colour,
                linestyle=(0, (3.2, 2.2)) if dashed else "solid",
                shrinkA=0, shrinkB=0, zorder=3,
            )
        )
        self.paths.append((name, [start, end]))

    def rule(self, name, points, colour, width, dashed=True):
        """Draw a plain line and remember its path."""
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        self.ax.plot(xs, ys, color=colour, linewidth=width,
                     linestyle=(0, (5, 3)) if dashed else "solid", zorder=1.5)
        self.paths.append((name, list(points)))

    def check(self, figure):
        """Return every collision found after rendering."""
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        to_display = self.ax.transData.transform
        problems: list[str] = []

        def rect_display(rect):
            x, y, w, h = rect
            (x0, y0), (x1, y1) = to_display([(x, y), (x + w, y + h)])
            return x0, y0, x1, y1

        def extent(handle):
            bb = handle.get_window_extent(renderer)
            return bb.x0, bb.y0, bb.x1, bb.y1

        def overlap(a, b, pad=0.0):
            return not (a[2] <= b[0] + pad or b[2] <= a[0] + pad
                        or a[3] <= b[1] + pad or b[3] <= a[1] + pad)

        def inside(a, b, margin):
            return (a[0] >= b[0] + margin and a[2] <= b[2] - margin
                    and a[1] >= b[1] + margin and a[3] <= b[3] - margin)

        dpi_scale = figure.dpi / 72.0
        margin = 1.5 * dpi_scale

        all_texts = []
        for b in self.boxes:
            box_rect = rect_display(b["rect"])
            for t in b["texts"]:
                ext = extent(t)
                all_texts.append((b["name"] + " label", ext, b["name"]))
                if not inside(ext, box_rect, margin):
                    problems.append("text overflows box: %s %r" % (b["name"], t.get_text()[:30]))
        for name, t in self.free_texts:
            all_texts.append((name, extent(t), None))

        for i in range(len(all_texts)):
            for j in range(i + 1, len(all_texts)):
                if overlap(all_texts[i][1], all_texts[j][1], pad=0.5 * dpi_scale):
                    problems.append("texts overlap: %s / %s" % (all_texts[i][0], all_texts[j][0]))

        solid_boxes = [b for b in self.boxes if not b["container"]]
        for name, ext, owner in all_texts:
            if owner is not None:
                continue
            for b in solid_boxes:
                if overlap(ext, rect_display(b["rect"])):
                    problems.append("free text sits on a box: %s / %s" % (name, b["name"]))

        for name, ext, owner in all_texts:
            for b in self.boxes:
                if not b["container"]:
                    continue
                r = rect_display(b["rect"])
                if overlap(ext, r) and not inside(ext, r, 0.0):
                    problems.append("text straddles container border: %s / %s" % (name, b["name"]))

        for path_name, points in self.paths:
            samples = []
            for (xa, ya), (xb, yb) in zip(points, points[1:]):
                for k in range(201):
                    f = k / 200.0
                    samples.append((xa + (xb - xa) * f, ya + (yb - ya) * f))
            display = to_display(samples)
            for name, ext, _ in all_texts:
                padded = (ext[0] - margin, ext[1] - margin, ext[2] + margin, ext[3] + margin)
                if any(padded[0] <= px <= padded[2] and padded[1] <= py <= padded[3]
                       for px, py in display):
                    problems.append("line crosses text: %s / %s" % (path_name, name))
            interior = display[8:-8] if len(display) > 16 else []
            for b in solid_boxes:
                r = rect_display(b["rect"])
                inner = (r[0] + margin, r[1] + margin, r[2] - margin, r[3] - margin)
                if any(inner[0] < px < inner[2] and inner[1] < py < inner[3]
                       for px, py in interior):
                    problems.append("line passes through box: %s / %s" % (path_name, b["name"]))
        return problems


def draw(layout: Layout) -> None:
    """Lay out the whole figure."""
    left_x, left_w = 0.000, 0.170
    rows = {"replay": 0.800, "sensor": 0.570, "adapter": 0.340, "store": 0.110}
    row_h = 0.160
    centre = left_x + left_w / 2

    layout.box("replay", left_x, rows["replay"], left_w, row_h,
               "UNSW-NB15 replay", "40 scenarios\n963 signals")
    layout.box("sensor", left_x, rows["sensor"], left_w, row_h,
               "Sensor", "deep ensemble with\nreject option, abstains\non 22.85% of signals",
               title_at=rows["sensor"] + row_h * 0.80, body_at=rows["sensor"] + row_h * 0.36)
    layout.box("network adapter", left_x, rows["adapter"], left_w, row_h,
               "Network adapter", "the only adapter routed")
    layout.box("store", left_x, rows["store"], left_w, row_h,
               "Situation store", "entity correlation\n66 situations")

    layout.arrow("replay to sensor", (centre, rows["replay"]), (centre, rows["sensor"] + row_h))
    layout.arrow("sensor to adapter", (centre, rows["sensor"]), (centre, rows["adapter"] + row_h))
    layout.arrow("adapter to store", (centre, rows["adapter"]), (centre, rows["store"] + row_h))

    grey_w = 0.078
    grey_xs = (0.200, 0.287, 0.374)
    for gx, label in zip(grey_xs, ("Auth", "Video", "Generic")):
        layout.box(label.lower() + " adapter", gx, rows["adapter"], grey_w, row_h,
                   label, "adapter\nunused", live=False)
    layout.text("unused note", (grey_xs[0] + grey_xs[-1] + grey_w) / 2, rows["adapter"] - 0.030,
                "written and tested, never routed", ha="center", va="top",
                fontsize=BODY_SIZE, color=INK_MUTED, style="italic")

    layout.rule("barrier", [(BARRIER_X, 0.0), (BARRIER_X, 1.0)], BARRIER, 1.8)
    layout.text("barrier label", BARRIER_X - 0.013, 0.445, "information barrier",
                rotation=90, ha="center", va="center", fontsize=TITLE_SIZE,
                color=BARRIER, fontweight="bold")

    loop_x, loop_y, loop_w, loop_h = 0.487, 0.015, 0.511, 0.970
    layout.container("reasoning loop", loop_x, loop_y, loop_w, loop_h)

    context_x, context_w = 0.505, 0.180
    context_y, context_h = 0.110, 0.850
    layout.box("context assembly", context_x, context_y, context_w, context_h, "", "")
    context_labels = []
    context_labels.append(layout.text("context title", context_x + context_w / 2, context_y + context_h - 0.022,
                "Context assembly", ha="center", va="top", fontsize=TITLE_SIZE,
                color=INK_PRIMARY, fontweight="bold"))
    context_labels.append(layout.text("context subtitle", context_x + context_w / 2, context_y + context_h - 0.075,
                "the only fields that\ncross the barrier", ha="center", va="top",
                fontsize=BODY_SIZE, linespacing=1.2, color=INK_SECONDARY))
    first_field_y = context_y + context_h - 0.205
    step = 0.064
    for index, field in enumerate(TEN_FIELDS):
        context_labels.append(layout.text("field " + field, context_x + 0.012,
                    first_field_y - index * step, field,
                    ha="left", va="center", fontsize=FIELD_SIZE, color=INK_SECONDARY,
                    family="DejaVu Sans Mono"))
    for handle in context_labels:
        layout.adopt("context assembly", handle)

    chain_x, chain_w, chain_h = 0.728, 0.262, 0.128
    chain = [
        ("generate", "Generate hypotheses", "U  UNKNOWN can never be pruned"),
        ("sanity gate", "Sanity gate", "S  boosts doubt on thin evidence"),
        ("evaluate", "Evaluate", "A  asymmetric confidence decay"),
        ("belief inertia", "Belief inertia", "cap of 0.15 on movement per step"),
        ("convergence", "Update convergence", "P  persistence clamp, threshold − 0.01"),
    ]
    tops = [0.958, 0.780, 0.602, 0.424, 0.246]
    chain_mid = chain_x + chain_w / 2
    for (name, title, body), top in zip(chain, tops):
        layout.box(name, chain_x, top - chain_h, chain_w, chain_h, title, body)
    for upper, lower in zip(tops, tops[1:]):
        layout.arrow("chain " + str(upper), (chain_mid, upper - chain_h), (chain_mid, lower))

    entry_y = tops[0] - chain_h / 2
    layout.arrow("context to generate", (context_x + context_w, entry_y), (chain_x, entry_y))
    loop_y_line = tops[-1] - chain_h / 2
    layout.arrow("loop back", (chain_x, loop_y_line), (context_x + context_w, loop_y_line))
    layout.text("loop label", (context_x + context_w + chain_x) / 2, loop_y_line - 0.020,
                "loop", ha="center", va="top", fontsize=BODY_SIZE, color=INK_SECONDARY)
    layout.text("iterations label", (context_x + context_w + chain_x) / 2, loop_y_line - 0.062,
                "at most\nthree", ha="center", va="top", fontsize=BODY_SIZE - 0.6,
                linespacing=1.1, color=INK_MUTED)

    exit_top = tops[-1] - chain_h
    layout.arrow("end", (chain_mid, exit_top), (chain_mid, 0.040))
    layout.text("end label", chain_mid + 0.012, (exit_top + 0.040) / 2,
                "end: conclude\nor abstain", ha="left", va="center", linespacing=1.15,
                fontsize=BODY_SIZE, color=INK_SECONDARY)

    store_mid = rows["store"] + row_h / 2
    layout.arrow("store to context", (left_x + left_w, store_mid), (context_x, store_mid))

    sensor_mid = rows["sensor"] + row_h * 0.55
    stop_x = BARRIER_X + 0.004
    layout.arrow("abstention flag", (left_x + left_w, sensor_mid), (stop_x, sensor_mid),
                 colour=BROKEN, dashed=True, width=1.3)
    layout.text("abstention stop", stop_x + 0.0135, sensor_mid, "×", ha="center",
                va="center", fontsize=9, color=BROKEN, fontweight="bold")
    label_x = (left_x + left_w + BARRIER_X) / 2
    layout.text("abstention label", label_x, sensor_mid + 0.030,
                "abstention flag: specified, not enacted\n"
                "counted into the snapshot, read by no decision\n"
                "clearing it changes the outcome by 0.000000",
                ha="center", va="bottom", fontsize=BODY_SIZE, linespacing=1.3,
                color=BROKEN)


def main() -> int:
    """Build Figure 1, verify its layout, and write PDF and PNG."""
    parser = argparse.ArgumentParser(description="Figure 1, architecture.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
    })
    figure = plt.figure(figsize=(WIDTH_IN, HEIGHT_IN))
    ax = figure.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_facecolor(SURFACE)

    layout = Layout(ax)
    draw(layout)
    problems = layout.check(figure)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    pdf = FIGURES_DIR / "fig1_architecture.pdf"
    figure.savefig(pdf, bbox_inches="tight", pad_inches=0.03)
    figure.savefig(PREVIEW_DIR / "fig1_architecture.png", dpi=220,
                   bbox_inches="tight", pad_inches=0.03)
    if PAPER_FIGURES_DIR.is_dir():
        figure.savefig(PAPER_FIGURES_DIR / "fig1_architecture.pdf",
                       bbox_inches="tight", pad_inches=0.03)
    plt.close(figure)

    print(f"seed {args.seed}")
    print(f"elements checked: {len(layout.boxes)} boxes, {len(layout.free_texts)} free labels, "
          f"{len(layout.paths)} arrows and rules")
    if problems:
        print(f"LAYOUT PROBLEMS {len(problems)}")
        for p in problems:
            print("  " + p)
    else:
        print("LAYOUT CLEAN, no overflow, no overlap, no line through text or box")
    print(f"written {pdf.relative_to(PROJECT_ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
