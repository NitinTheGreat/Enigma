# FIGURES

Six figures for an 8-page IEEE two-column paper. That is the practical
ceiling — six figures plus two tables consumes roughly 2.5 columns.

Assumes the recommended N1 + N2 paper from NOVELTY §4.

Status legend: **HAS DATA** (producible today from evidence already in the
repos) · **NEEDS RE-RUN** (data existed once, must be regenerated) ·
**NO DATA** (nothing exists; must be created).

---

## Fig. 1 — System architecture and data flow
**Status: HAS DATA.** Effort: **4 h** (drawing only).

Single-column block diagram: replayer → batched Keras inference → traffic
splitter → adapter registry → situation store → deterministic reasoning →
LangGraph/Gemini loop → explanation builder → dashboard. Annotate each edge
with its actual transport and address.

Every element is verified: `Streamer.py:15-18`, `main.py:13-14,107-122,130-134,145-198`,
`adapters/registry.py:73-109`, `situation_store.py:160-176`,
`reasoning_engine.py:97-130`, `graph/builder.py:33-71`,
`explain/builder.py:54-165`, `ws_dashboard.py:182-199`.

**Draw it honestly.** Mark the LLM boundary explicitly (Gemini sees only the
ten aggregate fields of `nodes.py:52-66` — this is a *selling point*, do not
hide it). Mark the three unused adapters as dashed/greyed rather than
omitting them; a reviewer who opens the artifact will find them, and showing
them as future work is better than being caught.

**Do not** reuse the README diagram (`Enigma-AIAgent/README.md:14-24`) — it
is stale and omits the explanation layer (EVIDENCE §E1).

---

## Fig. 2 — Trend-label and convergence collapse under clock conflation
**Status: NO DATA.** Effort: **6 h** (on top of the 20 h N1 experiment).
**This is the paper's headline figure.**

Three-panel grouped bar chart, one panel per configuration
(conflated / wall-clock-only / clock-separated):

- Panel A: distribution of trend labels across *N* = 5,000 replayed signals.
  Expected: conflated ≈ 100% DEESCALATING, clock-separated shows a real
  spread.
- Panel B: fraction of situations reaching convergence, plus mean final
  UNKNOWN confidence.
- Panel C: mean iterations to termination.

Instrumentation needed: log `SituationReasoningSnapshot.trend`
(`domain/reasoning.py:39`), `convergence_score` and `iteration_count`
(`graph/state.py:46-47`), and final UNKNOWN confidence per analysis. All
three values already exist in the returned state — you need a writer, not new
computation.

Blocked on GAPS G2 (dataset) and G8 (clock fix).

---

## Fig. 3 — Epistemic-control ablation
**Status: NO DATA.** Effort: **6 h** (on top of the 26 h N2 experiment).

Grouped bars: 16 configurations (2⁴ over UNKNOWN / sanity gate / asymmetric
decay / persistence) × 3 evidence regimes (sparse, ambiguous, clear).
Primary y-axis: premature-convergence rate. Secondary panel: abstention rate
on the ambiguous regime.

If 16 bars is too dense for one column — it will be — collapse to a main
effects plot with the four single-factor removals plus the all-off baseline,
and put the full 16-row table in an appendix.

Ablation switches already exist (EVAL_STATUS §4). **Prerequisite:** GAPS G10
must be fixed first, or one of the four factors is a no-op (EVIDENCE §D2).

---

## Fig. 4 — Classifier performance: confusion matrix + per-class F1
**Status: NEEDS RE-RUN.** Effort: **3 h** (on top of GAPS G1's 10 h).

Two panels: (a) 10×10 normalised confusion matrix after merging
`backdoor`/`backdoors` (GAPS G21); (b) horizontal bars of per-class
precision/recall/F1 with support counts annotated.

Everything needed is imported and never called at `Model.ipynb` cell 1. Must
be regenerated on the clean split (GAPS G1) — the existing numbers are
leakage-contaminated (EVIDENCE §A5).

**Report the ugly classes.** `worms` (171 real examples) and `backdoors`
(300) will have poor recall. Showing that is credibility, not weakness, and
it directly supports demoting the ML layer to "sensor" per NOVELTY §4.

---

## Fig. 5 — End-to-end latency distribution by pipeline stage
**Status: NO DATA — no instrumentation exists anywhere.** Effort: **12 h**
(= GAPS G7 in full).

Stacked box plots or violins across four stages: signal ingest → situation
attach → deterministic reasoning → LangGraph+Gemini → explanation build →
broadcast. Report p50/p95/p99 and mark the Gemini stage clearly — it will
dominate by one to two orders of magnitude, and that is the honest finding.

Consider a second panel: queue depth versus offered load at 1, 4, 16, 64
records/s, showing where the pipeline saturates.

**Decision point.** If you do not fund G7, **cut this figure and remove
"Real-Time" from the title** (NOVELTY §4). Do not substitute the
frontend's HTTP round-trip number (`useHealth.ts:19-26`) — it measures a
counter endpoint, not the pipeline, and presenting it as pipeline latency
would be misrepresentation.

---

## Fig. 6 — Worked example: one situation's belief trajectory
**Status: NO DATA (fields exist, nothing logs them).** Effort: **5 h.**

Line chart: hypothesis confidence versus reasoning iteration for one
representative situation, one line per hypothesis, with UNKNOWN drawn as a
bold dashed reference line and the convergence threshold (0.8,
`config.py:37`) as a horizontal rule. Annotate the iteration at which
sustained-dominance persistence is satisfied.

Beside it, a small inset or side panel showing the corresponding
`ExplanationSnapshot` sections — this is the one place where the explanation
layer earns its half-page, and it directly serves the XAI framing.

All values are already in the returned state: `hypotheses[].confidence`,
`dominant_iterations`, `convergence_score`
(`graph/state.py:41-55`, `domain/hypothesis.py:51-89`). You need a per-
iteration writer; currently only the final state is returned
(`runner.py:103`), so this requires either a LangGraph stream/callback hook
or logging inside `update_convergence`.

Pairs naturally with Fig. 3.

---

## Optional Fig. 7 — Confidence-weight sensitivity
**Status: NO DATA.** Effort: 8 h (part of NOVELTY N5 / GAPS G12).

Only include if you have space and one of the six above gets cut. Heatmap or
parallel-coordinates over the weight simplex versus AUC/ECE. Converts the
"why these five magic numbers?" objection (GAPS G12) into a design
discussion.

---

## Summary

| Fig. | Subject | Status | Marginal hours | Blocked on |
|---|---|---|---|---|
| 1 | Architecture / data flow | **HAS DATA** | 4 | — |
| 2 | Clock-conflation collapse | NO DATA | 6 | G2, G8, N1 |
| 3 | Epistemic-control ablation | NO DATA | 6 | G10, N2 |
| 4 | Confusion matrix + per-class F1 | NEEDS RE-RUN | 3 | G1, G2, G21 |
| 5 | Latency by stage | NO DATA | 12 | G7 — **cut if unfunded** |
| 6 | Belief trajectory case study | NO DATA | 5 | logging hook |
| 7 | Weight sensitivity *(optional)* | NO DATA | 8 | G11, G12 |

**One of six figures is producible today, and it is the one that contains no
measurements.** Everything quantitative requires the dataset back (GAPS G2)
first.

**Figure budget if you cut Fig. 5:** 24 marginal hours on top of the
experiment work already counted in GAPS and NOVELTY.

### Tables to plan alongside
- **Table I — baseline comparison** (GAPS G3): your MLP vs Random Forest vs
  XGBoost vs 2-3 cited UNSW-NB15 results, on the clean split, macro-F1 and
  weighted-F1 with seed variance. Expect the tree ensembles to win; report it.
- **Table II — component status / threats to validity** (GAPS G13): a
  condensed version of EVIDENCE §G. Unusual to include, and reviewers respond
  well to it.
