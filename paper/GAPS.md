# GAPS — Phase 3

Target calibration: **mid-tier applied security venue, 8 pages, IEEE
format** (IEEE TrustCom / ARES / IEEE CSR / DSN industry track class).

Reviewer profile assumed: 3 reviewers, at least one an ML-security
specialist who knows UNSW-NB15 well, at least one a systems person. This
community accepts strong systems papers with **one** solid empirical
contribution, but rejects on methodology defects without discussion.

Ordered by **P(rejection if unaddressed)**. Hours are for one competent
person already familiar with this codebase.

---

## Tier 0 — Desk-reject / immediate-reject territory

### G1. Train/test leakage invalidates every reported number
**P(rejection) ≈ 0.95.** Effort: **10 h.**

SMOTE runs at cell 35, the split at cell 43 (EVIDENCE §A5). The scaler, the
mutual-information selector, and the outlier→median replacement are all
fitted on the full dataset. Additionally the "test" set doubles as the
`keras_tuner` selection set and the early-stopping monitor, so nothing is
held out.

Any UNSW-NB15 reviewer will catch SMOTE-before-split within thirty seconds —
it is the single most common flaw in papers on this dataset and reviewers are
primed for it.

**Fix:**
1. Split first, stratified, into train / val / test (60/20/20).
2. Fit scaler, MI selector, and outlier bounds on **train only**; transform
   val and test.
3. Apply SMOTE to **train only**.
4. Use val for tuning and early stopping; touch test **once**.
5. Report the new accuracy honestly. **Expect it to drop.** Balanced-class
   accuracy of 0.7382 with leakage plausibly becomes 0.60-0.70 macro-F1 on a
   clean split. A lower, defensible number is worth far more than a higher,
   indefensible one.

Blocked on G2.

### G2. Nothing is reproducible
**P(rejection) ≈ 0.9.** Effort: **6 h.**

Missing: `archive/` CSVs, `unsw_nb15_threat_detection_model.h5`,
`unsw_nb15_preprocessing_state.pkl`. Cells 48, 54, 57, 58, 59 are commented
out, so `Run All` trains and saves nothing. `Enigma-ML-Layer/README.md` is
10 bytes. No `requirements.txt`, no Python version pin, no seeds beyond two
`random_state=42`.

**Fix:** download script or documented dataset path; uncomment and
parameterise the training cells; `requirements.txt` with pinned versions
(TF, sklearn, imblearn, shap, keras-tuner); global seed function; a real
README with exact run commands; commit the `.h5` and `.pkl` (they are tiny —
1,484 parameters, ~6 KB) or provide a one-command retrain.

### G3. No baseline comparison
**P(rejection) ≈ 0.85.** Effort: **8 h.**

Zero baselines exist (EVAL_STATUS §3). A detection paper on a public dataset
without a baseline is not reviewable.

**Fix (minimum acceptable set):**
- Random Forest and XGBoost on the identical clean split — 3 h, and both
  will likely **beat** your MLP on UNSW-NB15 tabular data. Report it
  honestly; the paper's contribution is not "our MLP is best."
- Two or three published UNSW-NB15 multi-class results cited from the
  literature, with an explicit note that splits differ.
- A **flat-alerting baseline** for the reasoning layer: one alert per
  signal, no situation grouping. This is the strawman your architecture
  implicitly argues against and it costs ~2 h to instrument.

### G4. No evaluation of the actual contribution
**P(rejection) ≈ 0.85.** Effort: **20 h.**

The title promises cross-layer threat intelligence, behavioural analytics,
and real-time defence. The *only* evaluated component is a stock MLP on a
public dataset — which is the one part that is not novel. Correlation,
temporal reasoning, hypothesis generation, and explanation have **no metric
of any kind** (EVAL_STATUS §2).

**Fix:** pick one mechanism and evaluate it properly. See NOVELTY — N2
(ablation of the epistemic-control stack) is the cheapest credible option
because the ablation switches already exist (EVAL_STATUS §4).

---

## Tier 1 — Strong-reject on review

### G5. No defensible novelty claim
**P(rejection) ≈ 0.8.** Effort: 0 h to decide, 20-40 h to execute — see
NOVELTY.md.

Every component is off-the-shelf: Keras MLP, SHAP, LangGraph, Gemini,
FastAPI, Next.js. The integration is competent but integration is not a
contribution at this venue. Addressed in full in NOVELTY.md.

### G6. Accuracy is the only metric, on an 11-class imbalanced problem
**P(rejection) ≈ 0.75.** Effort: **4 h.**

No precision, recall, F1, confusion matrix, or FPR (EVAL_STATUS §2). For
intrusion detection, **false-positive rate is the metric reviewers care most
about** and it is entirely absent. Note that `worms` has 171 real examples
and `backdoors` 300 — per-class recall on these will be poor and must be
reported.

**Fix:** call the six sklearn functions already imported at cell 1. Report
macro-F1, weighted-F1, per-class P/R/F1, a confusion matrix, and FPR at the
operating threshold. Cheapest high-value item in this document.

### G7. Real-time claims are unsupported and structurally contradicted
**P(rejection) ≈ 0.7.** Effort: **12 h.**

No server-side instrumentation exists (EVIDENCE §C1). The only latency
number in the project is a browser HTTP round-trip to a counter endpoint
(`useHealth.ts:19-26`) and a code comment estimating 5-15 s per Gemini
analysis (`test_live.py:127`). Meanwhile the replayer emits ~4 records/s into
an unbounded `create_task` fan-out with no backpressure (EVIDENCE §C4).

**Fix, in priority order:**
1. Instrument four stage timings (ingest→signal, signal→situation,
   situation→reasoning-complete, reasoning→broadcast) with
   `time.perf_counter`, accumulate percentiles, expose on `/health` — 4 h.
2. Add a `asyncio.Semaphore` around the analysis task and expose queue depth
   — 3 h.
3. Run a sustained load test at 1, 4, 16, 64 records/s and report p50/p95/p99
   plus queue growth — 5 h.
4. **If the numbers are bad, change the title.** "Real-Time" is not load
   bearing; "Streaming" or "Online" is honest and costs you nothing with
   reviewers.

### G8. The mixed-clock defect makes the temporal layer inert
**P(rejection) ≈ 0.65** if a reviewer runs the artifact; lower otherwise.
Effort: **5 h to fix, 8 h to turn into a contribution.**

`is_quiet` compares wall clock against signal-supplied timestamps
(`situation.py:190`) while every other temporal metric uses signal
timestamps. Under replay of archival data, `quiet_detected` is permanently
true, every situation is DEESCALATING, hypotheses decay ~0.225/iteration, and
the system reports permanently undecided (EVIDENCE §D1).

**This means the entire reasoning stack currently operates in a degenerate
regime.** Any live demo or artifact evaluation exposes it.

**Fix:** introduce an explicit clock abstraction with `event_time` and
`ingest_time` on `Signal`; use `event_time` for intervals and `ingest_time`
for staleness; add a replay-clock mode that advances a virtual now. See
NOVELTY N1 — this fix is also the most defensible novelty angle available.

### G9. "Cross-layer / multi-source" is a single source
**P(rejection) ≈ 0.65.** Effort: **10 h.**

`Signal.source` is the constant `"unsw-threat-detector"` for every signal
(`main.py:193`), so `source_diversity == 1` always (SYSTEM §2). Three of the
four adapters have no producer (INVENTORY §5). The title's central claim is
not demonstrated.

**Fix, cheapest credible version:** add a second and third synthetic
producer that emit `auth_anomaly` and `video_detection` payloads to
`/ws/raw-signal` with entity identifiers that *deliberately collide* with the
network source IPs, so `EntityCorrelation` actually fuses across domains.
Label a set of injected multi-domain incidents and measure whether grouping
recovers them. Roughly 10 h, and it makes G4, G9, and the title all
simultaneously honest.

**Alternative if you cannot fabricate producers:** rewrite the title to drop
"Cross-Layer" and "Multi-Source." Free.

---

## Tier 2 — Major revision / weak reject

### G10. Two mechanisms in the "epistemic control" story do not work
**P(rejection) ≈ 0.5** if the paper claims them. Effort: **6 h.**

- `apply_belief_inertia` never writes `confidence`; it is a no-op on belief
  (EVIDENCE §D2). Its output nonetheless drives user-facing "belief is
  accelerating" text in the explanation (`builder.py:373-377,631-634`).
- The vague-hypothesis penalty in the sanity gate mutates a discarded copy
  (EVIDENCE §D3).

If the paper claims "belief inertia prevents premature convergence," a
reviewer who opens the artifact will find that claim false. **Either fix
both (6 h) or delete the claim.** Fixing is better — it is a prerequisite
for the N2 ablation.

### G11. `anomaly_score` is really classifier confidence
**P(rejection) ≈ 0.45.** Effort: **6 h.**

`main.py:190` sets `anomaly_score = max(softmax)`, and the same value is
copied into `confidence` (SYSTEM §3). The 0.30-weighted dominant term of the
confidence formula therefore measures classifier certainty, not
anomalousness. A confidently-classified benign-ish `generic` flow scores
0.99.

**Fix:** either (a) derive a genuine anomaly score — `1 − p(normal)`, or
predictive entropy, both one-liners on the existing softmax — and keep
`confidence` as `max(softmax)`; or (b) rename the field throughout and
justify the semantics in the paper. Option (a) is 2 h of code plus 4 h of
re-running downstream evaluation, and it makes the field name honest.

### G12. Confidence weights are unjustified magic numbers
**P(rejection) ≈ 0.45.** Effort: **8 h.**

The five weights (0.25/0.15/0.20/0.30/0.10) and three saturation points
(10/10/3) have no derivation, no citation, and no sensitivity analysis
(SYSTEM §3). A reviewer will ask "why these?"

**Fix:** a weight-sensitivity sweep. All eight are env-settable
(`config.py:21-28`), so this is a loop over configurations, not new code.
Report how the trend/confidence distribution moves. Even a one-figure
sensitivity plot converts a weakness into a defensible design discussion.

### G13. No threats-to-validity section, and plenty to declare
**P(rejection) ≈ 0.4** (reviewers often treat absence as a red flag rather
than a reject). Effort: **3 h.**

You must declare, at minimum: single-dataset evaluation; UNSW-NB15 is
synthetic lab traffic from 2015 and known not to represent modern
enterprise traffic; `Stime` as a feature risks temporal shortcut learning
(EVIDENCE §B2); SMOTE distorts the class prior; no adversarial or
evasion evaluation; LLM non-determinism and API dependence; in-memory-only
state; single-node deployment; simulated rather than deployed operation.

Writing this section honestly is *cheap* and it materially raises reviewer
trust. Do not skip it.

### G14. LLM component is entirely unevaluated and non-deterministic
**P(rejection) ≈ 0.4.** Effort: **10 h.**

Gemini 2.0 Flash at temperature 0.2 (`config.py:41-42`) generates the
hypotheses that the whole reasoning loop operates on, and **no test or
experiment uses a real LLM** — all 49 graph tests mock it
(`test_graph.py`). There is no measure of hypothesis quality, no
reproducibility analysis, no cost accounting, no fallback-rate statistic
(the fallback at `nodes.py:165-171` fires silently on any parse failure).

**Fix:** run N=50 situations × 5 repeats, log the fallback rate, measure
hypothesis-set stability across repeats (e.g. Jaccard over descriptions),
and have two people rate a 30-situation sample for plausibility. 10 h and it
gives you a real table.

### G15. Frontend displays fabricated zeros
**P(rejection) ≈ 0.35** — becomes near-certain if you include a dashboard
screenshot as a figure. Effort: **3 h.**

Eight dashboard panels read backend fields that are never sent
(EVIDENCE §F1-F2): "Avg Anomaly" is permanently 0%, the "Threat Levels"
donut is permanently 100% Low, all anomaly bars are zero and green, the
"High Risk" sidebar filter always returns empty, and the "Lead hypothesis"
block never renders because the key is `hypothesis_id` not `id`.

**Fix:** add `lifecycle`, `last_activity`, `max_anomaly`, and `sources` to
`Situation.summary()` (`situation.py:226-234`); align the `TemporalData`,
`ReasoningData`, and `Hypothesis` field names; replace the unchecked
`as SituationAnalysis` cast at `useDashboardWS.ts:81` with runtime
validation so the next drift is caught.

---

## Tier 3 — Weakens the paper, unlikely to be the stated reject reason

### G16. No adversarial or evasion evaluation
Effort: **16 h.** Expected at top-tier, optional at mid-tier. A simple
feature-perturbation robustness curve on the 20 input features would be a
cheap bonus. Consider only if time remains.

### G17. Unbounded memory growth
Effort: **3 h.** `expire_stale()` is never called (EVIDENCE §D6) and
evidence lists are never trimmed. Any long-run experiment for G7 will hit
this. Fix before running load tests, not after.

### G18. Explanation quality is unmeasured
Effort: **14 h.** No faithfulness, stability, or user study
(EVAL_STATUS §2). At a mid-tier venue an XAI-titled paper can survive with a
qualitative walkthrough plus a determinism argument (the builder *is*
deterministic — `builder.py:14-17` — and that is worth stating), but a small
stability experiment would be stronger.

### G19. Both LLM prompts are unversioned and untested
Effort: **2 h.** `_HYPOTHESIS_PROMPT` (`nodes.py:74-104`) and
`_FORMAT_PROMPT` (`formatter.py:27-48`) are inline string constants with no
version, no test, and no ablation. Extract, version, and include verbatim in
an appendix — reviewers increasingly demand this.

### G20. Documentation drift
Effort: **2 h.** Ten discrepancies catalogued in EVIDENCE §E, including a
`.env.example` that names the wrong provider entirely. Cheap; do it before
artifact submission.

### G21. `backdoor` / `backdoors` label split
Effort: **1 h.** An 11-class problem that should be 10 (EVIDENCE §A2), with
`backdoors` degrading to `SignalType.UNKNOWN` downstream
(`unsw_threat.py:35-53`). Merge the classes in cell 9. Fold into the G1
re-run.

### G22. No statistical significance or run-to-run variance
Effort: **4 h.** Every number is a single run at seed 42. Run 5 seeds,
report mean ± std. Fold into the G1 re-run for near-zero marginal cost.

---

## Effort summary

| Tier | Gaps | Hours |
|---|---|---|
| 0 — desk-reject | G1-G4 | **44** |
| 1 — strong reject | G5-G9 | **37** (G5 is decision + execution, counted in NOVELTY) |
| 2 — major revision | G10-G15 | **36** |
| 3 — weakening | G16-G22 | **42** |
| | **Total if everything is fixed** | **~159 h** |

### Minimum viable submission path — 78 h

The smallest set that makes an 8-page mid-tier submission defensible:

| Order | Gap | Hours | Why it is on the critical path |
|---|---|---|---|
| 1 | G2 reproducibility | 6 | Everything else is blocked on being able to re-run |
| 2 | G1 clean split | 10 | Every number is currently invalid |
| 3 | G21 label merge | 1 | Free, fold into the same re-run |
| 4 | G6 proper metrics | 4 | Highest value per hour in the whole document |
| 5 | G3 baselines | 8 | Non-negotiable for a detection paper |
| 6 | G22 seed variance | 4 | Near-zero marginal cost on top of 1-5 |
| 7 | G10 fix the two broken mechanisms | 6 | Prerequisite for the ablation |
| 8 | G8 clock-domain fix | 5 | Without it the reasoning stack is inert |
| 9 | G4/G5 one real contribution (NOVELTY N1 or N2) | 20 | The actual paper |
| 10 | G7 latency instrumentation | 12 | Or delete "Real-Time" from the title (0 h) |
| 11 | G13 threats to validity | 3 | Cheap trust |
| 12 | G20 doc drift | 2 | Artifact hygiene |
| | **Total** | **81 h** | ≈ two focused weeks |

Dropping G7 in favour of retitling brings this to **69 h**. That is the
honest floor.
