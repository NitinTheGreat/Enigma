# NOVELTY — Phase 4

---

## 1. The honest assessment

> **As it stands, this system contains no research contribution. It is a
> competent integration of six off-the-shelf components, and integration is
> not a contribution at a mid-tier applied security venue.**

Component by component, with citations:

| Component | Novel? | What it actually is |
|---|---|---|
| MLP on UNSW-NB15 | **No** | A 1,484-parameter MLP (`Model.ipynb` cell 46 output) trained on the most-published IDS dataset of the last decade. Hundreds of papers do this. Its 0.7382 balanced-class validation accuracy (cell 57 output) is **below** what a Random Forest typically achieves on this data with no tuning. |
| SHAP | **No** | `shap.DeepExplainer` called on one record (cell 65). Library usage, one line, standard API. |
| LangGraph + Gemini | **No** | Zero-shot prompting of a hosted API inside a stock graph framework. No fine-tuning, no novel prompting technique, no training. |
| WebSocket streaming | **No** | `asyncio` + `websockets`, textbook producer/consumer with a batching worker (`main.py:100-204`). |
| Entity correlation | **No** | A dictionary keyed on source IP (`correlation.py:48-51`). This is grouping, not correlation. |
| Explanation templates | **No** | ~25 hardcoded `if` statements emitting fixed strings (`explain/builder.py`). |
| Next.js dashboard | **No** | A visualisation client. |

Worse than "not novel," three of the marketed mechanisms **do not do what
their names say**:
- Belief inertia never modifies confidence (EVIDENCE §D2) — STUBBED.
- The counterfactuals are hand-picked constants restating thresholds
  elsewhere in the code (SYSTEM §5c), not counterfactuals in any technical
  sense.
- The `features` field carrying "XAI" information downstream is a list of CSV
  column names, identical on every signal, read by nothing (SYSTEM §5b).

And the two headline claims in the working title are not demonstrated:
- **"Cross-Layer / Multi-Source":** `source_diversity == 1` for every signal,
  always (SYSTEM §2). One source.
- **"Real-Time":** zero instrumentation, and four structural properties that
  argue against it (EVIDENCE §C4).

**A paper submitted today on the current evidence would be rejected by all
three reviewers, and correctly so.**

### What is genuinely good, and worth one honest sentence
- 216 unit tests with clean separation of deterministic from stochastic logic
  (EVAL_STATUS §6). Unusual for a project of this size.
- The **information barrier** at `graph/nodes.py:46-69`: the LLM sees ten
  aggregate metrics and never raw signals, entity identifiers, or
  timestamps. This is a deliberate, defensible privacy/leakage design.
- The **fail-closed explanation integrity validator**
  (`explain/builder.py:664-704`): every explanation bullet must reference a
  field from a fixed whitelist or the explanation is rejected. This is a real
  anti-hallucination guarantee and it is genuinely uncommon.
- The **explicit permanent UNKNOWN hypothesis** that cannot be pruned and
  competes with all others (`hypothesis.py:94-110`, `nodes.py:201-214`,
  `nodes.py:390-391`). Abstention as a first-class citizen.

**These four are the raw material.** Every viable novelty angle below is
built from them, not from the ML.

---

## 2. Five candidate novelty angles

Ranked at the end by reviewer value ÷ effort. All five reuse code that
already exists.

---

### N1. Clock-domain separation in streaming situation assessment
**Reuses:** `domain/situation.py`, `domain/temporal.py`,
`core/reasoning_engine.py`, and the entire existing test suite.

**Claim.** Streaming security-analytics pipelines that reason over both
*event time* (from the sensor) and *ingest time* (from the collector) enter a
silent degenerate regime when the two are conflated: staleness predicates
evaluated against the wall clock while rate predicates use event timestamps
cause the temporal reasoning layer to collapse to a constant output. We
characterise the failure, give a clock-domain-explicit design, and show that
the conflated design produces a fixed trend label and permanent abstention on
replayed archival data, while the corrected design recovers the intended
distribution.

**Why this is real.** This is not a hypothetical. It is a code-verified
defect in your own system (EVIDENCE §D1) with a fully traceable causal chain:
`is_quiet` → `_detect_trend` branch 3 → `evaluate_hypotheses` −0.225 per
iteration → UNKNOWN dominance → `convergence = 0.0` → permanent "undecided."
Every replay-based evaluation in the IDS literature — and there are hundreds
on UNSW-NB15, CICIDS, and similar — is exposed to this class of bug, and
almost none discuss it. **This is the most under-discussed reproducibility
hazard in replay-based IDS evaluation.**

**Experiment.**
1. Add `event_time` and `ingest_time` to `Signal`; parameterise
   `is_quiet`/`last_event_age` over a clock selector. ~6 h.
2. Run the same replay of *N* = 5,000 signals under three configurations:
   (a) conflated (current code), (b) wall-clock-only, (c) clock-separated
   (proposed).
3. Report, per configuration: distribution of trend labels
   (ESCALATING/STABLE/DEESCALATING), fraction of situations reaching
   convergence, mean iterations to termination, mean final UNKNOWN
   confidence, and mean dominant-hypothesis confidence.
4. Expected result: (a) collapses to ~100% DEESCALATING and ~0% convergence;
   (c) recovers a non-degenerate spread.

**Baseline it beats.** Its own conflated configuration — a self-ablation,
which is completely legitimate and is exactly how systems papers present
this kind of finding. Optionally strengthen by showing the same conflation
pattern in one or two open-source streaming detection projects.

**Effort:** 20 h (6 h implementation, 6 h experiment harness, 8 h analysis
and writing).

**Risk of a negative result:** **Very low (~10%).** The mechanism is
deterministic and already code-verified. The only way this fails is if
`Stime` in the CSVs turns out to be something other than a historical
timestamp — verify that in the first hour by printing `min`/`max` of `Stime`
once you have `archive/`. Everything else follows arithmetically.

**Reviewer value:** **High.** Reviewers reward a clearly characterised
failure mode with a clean fix and a measured before/after. It reframes your
project from "another IDS" into "a methodology finding about how these
systems are evaluated." It is also honest — you found it in your own code.

---

### N2. Ablation of an epistemic-control stack for LLM hypothesis generation
**Reuses:** `graph/nodes.py`, `graph/builder.py`, `graph/runner.py`,
`domain/hypothesis.py`, and all 49 existing graph tests.

**Claim.** LLM-generated hypotheses in a security-reasoning loop converge
prematurely and over-confidently without explicit epistemic controls. We
isolate four such controls — a permanent non-prunable UNKNOWN hypothesis,
a deterministic structural sanity gate, asymmetric confidence decay, and a
sustained-dominance persistence requirement — and quantify each one's
contribution to premature-convergence rate and to abstention on ambiguous
evidence.

**Why this is reachable.** The ablation switches **already exist** and are
already plumbed (EVAL_STATUS §4): remove the UNKNOWN injection block
(`nodes.py:201-214`), drop the sanity-gate node from the topology
(`builder.py:48,56-57`), toggle the ×1.5 asymmetric decay
(`nodes.py:383-385`), and set `convergence_persistence` via a runner
parameter (`runner.py:57`). You would be writing a config sweep, not new
mechanisms.

**Experiment.**
1. **Prerequisite:** fix belief inertia (EVIDENCE §D2) so the fourth control
   actually exists — 6 h, GAPS G10. Without this you would be ablating a
   no-op and a reviewer opening the artifact would catch it.
2. Construct 3 evidence regimes: sparse (1-2 signals), ambiguous (5+ signals,
   flat anomaly scores), and clear (10+ signals, high anomaly, ideally
   multi-source once G9 is done).
3. Run 2⁴ = 16 configurations × 50 situations × 3 repeats, using a **real**
   Gemini call (this also discharges GAPS G14).
4. Metrics: premature-convergence rate (converged with < 3 evidence items),
   abstention rate on the ambiguous regime, mean iterations to termination,
   final dominant confidence, LLM fallback rate.
5. Expected: removing UNKNOWN collapses abstention to near zero and drives
   premature convergence sharply up; the persistence requirement is the
   second-largest effect.

**Baseline it beats.** "Raw LLM hypothesis generation with a simple
confidence threshold" — i.e. all four controls off. This is a strong,
honest, and easily-understood baseline.

**Effort:** 26 h (6 h fixing G10, 8 h harness, 6 h runs including API cost,
6 h analysis).

**Risk of a negative result:** **Medium (~35%).** The controls might turn out
to be individually negligible, or the effect might be dominated by prompt
temperature. Two mitigations: (a) a negative result is still publishable if
framed as "these plausible controls did not help, and here is why," which
mid-tier venues do accept; (b) the UNKNOWN-hypothesis ablation is very likely
to show a large effect on its own, because the convergence function
structurally requires beating UNKNOWN by ≥ 0.15 (`nodes.py:511-517`), so at
minimum you will have one significant result.

**Reviewer value:** **High.** LLM-in-the-loop security reasoning is a hot
topic, most papers in it have no ablation at all, and abstention/calibration
is an active concern. A clean 4-factor ablation is exactly what this area is
missing.

---

### N3. Constrained, non-hallucinating explanation generation with a
### fail-closed integrity gate
**Reuses:** `explain/builder.py` (705 lines), `domain/explanation.py`, and 62
existing tests.

**Claim.** Deterministic, whitelist-validated explanation generation gives a
verifiable no-hallucination guarantee that LLM-generated security
explanations cannot provide, at the cost of expressiveness. We formalise the
guarantee, implement it as a fail-closed integrity gate over a fixed field
whitelist, and compare determinism, field-attribution correctness, and
analyst-rated usefulness against direct LLM explanation of the same
reasoning state.

**Why this is reachable.** The mechanism is fully built. `KNOWN_FIELDS`
(`builder.py:43-51`) is the whitelist; `validate_explanation_integrity`
(`builder.py:664-704`) raises on any section referencing a field outside it,
on any empty section, and on any out-of-bounds contribution or counterfactual
delta. The LLM comparator is *also* already written and currently unused —
`ExplanationFormatter._format_with_llm` (`formatter.py:73-90`). You have both
arms of the experiment sitting in the repo.

**Experiment.**
1. Sample 100 completed reasoning states.
2. Generate explanations via three paths: (a) deterministic builder,
   (b) `ExplanationFormatter.format` LLM rephrasing of the builder output,
   (c) direct LLM explanation from the raw reasoning state, no builder.
3. Metrics: **determinism** (identical output across 5 repeats — (a) is 1.0
   by construction, measure (b) and (c)); **unsupported-claim rate** (count
   of factual assertions not traceable to a whitelisted field, annotated by
   two raters); **integrity-gate rejection rate** when (c) is passed through
   the validator; **usefulness**, 5-point Likert from 3 raters.
4. Expected: (a) determinism 1.0, unsupported-claim rate 0, usefulness
   lowest; (c) determinism low, unsupported-claim rate materially > 0,
   usefulness highest. The finding is the trade-off curve, not a winner.

**Baseline it beats.** Direct LLM explanation. Note carefully: it does **not**
beat it on usefulness, and you must say so. The claim is about verifiability.

**Effort:** 22 h (4 h harness, 6 h runs, 8 h annotation with raters, 4 h
analysis). The annotation step needs 2-3 people for a few hours each.

**Risk of a negative result:** **Low-medium (~25%).** The determinism result
is guaranteed by construction. The risk is that the unsupported-claim rate
for the LLM arm turns out to be low, weakening the motivation — but a
low-but-nonzero rate on security explanations is itself a reportable finding.
The real risk is logistical: you need annotators.

**Reviewer value:** **Medium-high.** Fits squarely in the XAI-for-security
conversation and matches your working title better than anything else here.
Slightly weakened by being a system-design comparison rather than a new
technique.

---

### N4. Cross-domain entity-anchored fusion under an adversarial
### timing-desynchronisation model
**Reuses:** `adapters/network.py`, `adapters/auth.py`, `adapters/video.py`
(all implemented and unit-tested, all currently unused),
`store/correlation.py`, `api/ws_raw_signal.py`.

**Claim.** Entity-anchored correlation across heterogeneous detector domains
recovers multi-stage incidents that per-domain alerting misses, but degrades
predictably as inter-domain arrival skew grows; we characterise the
degradation and the skew tolerance of TTL-based situation grouping.

**Why this is reachable.** The three unused adapters are the missing
producers. Writing three synthetic emitters that hit `/ws/raw-signal`
(`ws_raw_signal.py:38-86`) with entity identifiers that deliberately collide
with the network source IPs would make `EntityCorrelation`
(`correlation.py:48-51`) genuinely fuse across domains for the first time.
This is the angle that would make the working title honest.

**Experiment.**
1. Define *K* = 50 synthetic multi-stage incidents, each spanning 3 domains
   with a known ground-truth entity and a known signal membership.
2. Inject them into background traffic at varying inter-domain skew
   (0 s, 30 s, 5 min, 20 min, 45 min) relative to the 30-minute TTL
   (`config.py:12`).
3. Metrics: incident-recovery rate (fraction of incidents whose signals land
   in one situation), grouping purity and completeness, and alert-volume
   reduction versus flat per-signal alerting.
4. Baselines: flat alerting (1 alert per signal); `DefaultCorrelation`
   grouping by `(signal_type, entity)` (`correlation.py:26-35`) — already
   implemented, a free second baseline.
5. Expected: sharp recovery-rate cliff as skew approaches the TTL; large
   alert-volume reduction.

**Baseline it beats.** Flat alerting, decisively, on volume. And
`DefaultCorrelation` on recovery rate for multi-vector incidents.

**Effort:** **38 h** (12 h synthetic producers, 8 h ground-truth incident
generator, 6 h harness, 6 h runs, 6 h analysis). Highest effort of the five.

**Risk of a negative result:** **High (~50%) — but not in the usual sense.**
The result will almost certainly come out *positive*, because entity-anchored
grouping obviously recovers same-entity incidents. **That is the problem:
it is close to tautological.** You built the ground truth to share an entity
key, and then measured whether a system that groups by entity key recovers
it. A sharp reviewer will say so. The skew-degradation curve is the part that
carries actual information — build the paper around that, not around the
recovery rate.

**Reviewer value:** **Medium.** It fixes the title's honesty problem, which
is worth a lot. But entirely synthetic incidents with no real multi-domain
telemetry is a well-known weakness, and the core mechanism is a dictionary
lookup.

---

### N5. The confidence-formula sensitivity and calibration study
**Reuses:** `core/reasoning_engine.py`, `config.py:21-28`, and 21 existing
reasoning tests.

**Claim.** Hand-tuned linear-aggregation confidence scores, ubiquitous in
deployed SIEM correlation rules, are poorly calibrated and highly sensitive
to weight choice; we quantify sensitivity across the weight simplex on a
labelled situation set and show that a two-parameter logistic recalibration
fitted on held-out situations substantially improves reliability at no
runtime cost.

**Why this is reachable.** All five weights and three saturation points are
already environment-settable (`config.py:21-28`) and injected at
`main.py:41-60`. The sweep is a configuration loop. The recalibration is
`sklearn.linear_model.LogisticRegression` on two features.

**Experiment.**
1. Derive situation-level ground truth from UNSW-NB15 labels: a situation is
   "true positive" if a majority of its constituent flows are labelled
   attack. This is mechanical given the `Label` column.
2. Sweep the 5-dimensional weight simplex (Dirichlet sample, ~500 points) and
   the 3 saturation parameters; for each, compute AUC and Expected
   Calibration Error of `confidence_level` against situation-level truth.
3. Report the sensitivity range: how much do AUC and ECE move across
   plausible weightings?
4. Fit Platt scaling on held-out situations; report ECE before/after and a
   reliability diagram.

**Baseline it beats.** The uncalibrated default weights — i.e. the shipped
configuration. Optionally a learned logistic model over the same five raw
features, which would show how much the hand-tuning costs.

**Effort:** 24 h (6 h ground-truth derivation, 6 h sweep harness, 4 h runs,
8 h analysis and figures).

**Risk of a negative result:** **Medium-high (~40%).** Two specific hazards:
(a) if AUC turns out to be insensitive to the weights, the sensitivity story
evaporates — though "these scores are robust to weighting" is still a
reportable, if duller, finding; (b) the situation-level ground truth is your
own construction, and a reviewer may contest the majority-vote definition.
Pre-register the definition and show robustness to the threshold.
Additionally, this angle inherits the `anomaly_score`-is-really-softmax-
confidence problem (GAPS G11), which must be fixed first or the study
measures the wrong thing.

**Reviewer value:** **Medium.** Calibration is a respected topic and the
"SIEM rules are uncalibrated" framing has practitioner appeal, but this reads
as a measurement study rather than a systems contribution.

---

## 3. Ranking by reviewer value ÷ effort

| Rank | Angle | Value | Effort (h) | Neg. risk | Value/Effort | Verdict |
|---|---|---|---|---|---|---|
| **1** | **N1 — Clock-domain separation** | High | **20** | **10%** | **Highest** | **Do this.** |
| **2** | **N2 — Epistemic-control ablation** | High | 26 | 35% | High | **Do this too.** |
| 3 | N3 — Non-hallucinating explanation | Med-high | 22 | 25% | Medium | Good third; needs annotators |
| 4 | N5 — Confidence calibration | Medium | 24 | 40% | Medium-low | Only if N1/N2 underdeliver |
| 5 | N4 — Cross-domain fusion | Medium | 38 | 50% (tautology risk) | Lowest | Skip unless the title is non-negotiable |

---

## 4. Recommendation

**Build the paper on N1 + N2. Combined: 46 h. Both reuse existing code and
require no new mechanisms.**

They compose into one coherent story rather than two disconnected results:

> *An LLM-in-the-loop situational-reasoning layer for streaming security
> telemetry. We identify a clock-domain conflation that silently collapses
> temporal reasoning in replay-based evaluation (N1), and we ablate four
> epistemic controls that govern when such a system should commit to a
> hypothesis and when it should abstain (N2).*

Both contributions are about **when a reasoning system should refuse to
conclude** — one from a systems/timing angle, one from an
epistemic/LLM angle. That is a single defensible thesis, it fits eight IEEE
pages, and neither claim depends on the MLP being good.

**Corollary — demote the ML layer.** The classifier becomes a *sensor*, not a
contribution. Report it in half a page with clean metrics (GAPS G1, G3, G6)
and state plainly that it is a standard baseline detector serving as the
signal source. This is not a retreat; it removes your weakest claim from the
firing line and reviewers respect papers that scope honestly.

**Retitle.** The current working title promises four things the system does
not do. Something closer to:

> *Knowing When Not to Conclude: Clock-Domain Separation and Epistemic
> Control in LLM-Assisted Situational Reasoning over Streaming Security
> Telemetry*

Drop "Cross-Layer," "Multi-Source," and "Real-Time" unless you fund GAPS G7
and G9 (22 h combined). "Cyber-Physical" should go regardless — there is no
physical-layer sensing anywhere in the three repos, and the one adapter that
would provide it (`adapters/video.py`) has no producer.
