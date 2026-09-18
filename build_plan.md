# Ten-Level Build Plan

Target paper: *Two-Level Abstention in LLM-Assisted Security Triage: Calibrated
Sensor Rejection and Epistemic Control Under Unknown Attacks*

Primary contribution: composition of sensor-level selective prediction with
reasoner-level epistemic control, plus a four-factor ablation of the epistemic
mechanisms under a genuine unknown-attack condition.

Estimated total: 115 to 130 hours. Levels 1 to 6 are infrastructure and produce
no paper claims. Levels 7 to 10 produce every number in the paper.

## Dependency order

```
L1 Environment
 └─ L2 Defects ──────────────┐
 └─ L3 Retraining            │
      └─ L4 Calibration      │
           └─ L5 Baselines   │
                             ├─ L6 Instrumentation
                             │    └─ L7 Scenarios
                             │         ├─ L8 Clock study
                             │         └─ L9 Ablation
                             │              └─ L10 Harness and figures
```

L3 through L5 can run in parallel with L2 and L6 if you have help. L7 gates
everything downstream and is the single highest-risk item.

## Rules for every level

Give Claude Code these standing instructions once, at the start of each session.

```
STANDING RULES for this project.

1. No comments in code. Names carry the meaning.
2. Plain British English in all prose, docs and commit messages. No em dashes.
3. Every experiment writes machine-readable output to results/ as JSONL or CSV.
   Never print a number that is not also written to disk.
4. Every experiment script takes --seed and writes the seed into its output.
5. Never modify a file under paper/ except to append. Those are the evidence
   files and they are the audit trail.
6. If you find that a task is impossible as specified, stop and say so. Do not
   substitute a weaker version silently.
7. Before claiming a level is complete, run the DONE CHECK stated in the task
   and paste its actual output.
8. Pin every dependency you add. Update requirements.txt in the same commit.
```

---

## Level 1 — Environment and reproducibility

**Goal:** all three repos run from a clean clone. 6 hours.

```
LEVEL 1 — Restore reproducibility.

The dataset is now present. The trained model is not, and the notebook's
training cells are commented out, so nothing in this project currently runs
end to end.

TASKS
1. Inventory the dataset. Confirm which UNSW-NB15 variant is present: the four
   full CSVs (~2.54M records) or the official pre-split partition
   (175,341 train / 82,332 test). Report exact row counts, column counts,
   column names and class distribution per file. Write to
   results/dataset_manifest.json.
2. Pin the environment. Produce requirements.txt with exact versions for
   Enigma-ML-Layer and Enigma-AIAgent. Record Python version. The notebook was
   authored on Kaggle, so remove all Kaggle-specific paths.
3. Convert Model.ipynb into a runnable script at
   Enigma-ML-Layer/train.py. Uncomment cells 48, 54, 57, 58, 59. Parameterise
   paths via argparse. Do not change any modelling logic yet, this level is
   purely about making the existing pipeline executable.
4. Resolve the ormsgpack import failure blocking tests/test_graph.py. If it is
   the Windows Application Control policy, document the workaround rather than
   vendoring the package.
5. Get the full test suite collecting and running. Report pass and fail counts.
6. Create a Makefile or tasks.md documenting how to start each of the three
   services and in what order.

DO NOT retrain yet. Do not fix any modelling defect yet.

DONE CHECK
  - python train.py --help succeeds
  - pytest collects 216 tests with zero collection errors
  - results/dataset_manifest.json exists and states the exact variant
  - a fresh clone plus pip install -r requirements.txt reproduces the above
```

---

## Level 2 — Defect remediation

**Goal:** the reasoning stack stops sitting in a degenerate regime. 10 hours.

This level is non-negotiable and must precede every experiment. Four of your
mechanisms currently do not do what their names say, and one of them is a
factor in your headline ablation.

```
LEVEL 2 — Fix the five defects documented in paper/EVIDENCE.md sections D and F.

Read paper/EVIDENCE.md and paper/SYSTEM.md first. Do not re-derive the
analysis, it is already done.

D1 — MIXED CLOCK DOMAINS, domain/situation.py:190
  is_quiet uses the wall clock while every other temporal metric uses signal
  timestamps. On replayed archival data every situation is permanently quiet,
  therefore permanently DEESCALATING, therefore hypotheses decay and UNKNOWN
  dominates by construction rather than by evidence.

  Fix: introduce an explicit clock abstraction. A Clock protocol with two
  implementations, WallClock and ReplayClock, where ReplayClock advances from
  the latest observed signal timestamp. Inject it into Situation and
  ReasoningEngine. Every temporal computation must read from the same clock.

  CRITICAL: keep the old behaviour reachable behind a flag named
  clock_mode with values "conflated", "wall", "separated". Level 8 needs to run
  all three configurations. Do not delete the bug, parameterise it.

D2 — BELIEF INERTIA IS A NO-OP, graph/nodes.py:404-458
  It writes belief_velocity and belief_acceleration but never writes
  confidence, so it rate-limits nothing. Its output nonetheless drives
  "belief is accelerating" text on the dashboard.

  Fix: make it actually damp confidence change. Cap the per-iteration
  confidence delta at a configurable maximum. Expose the cap via config so it
  can be set to infinity to disable the mechanism, which is how Level 9 will
  ablate it.

D3 — DISCARDED PENALTY BRANCH in the sanity gate, graph/nodes.py:223-317
  Fix the no-op branch. Same requirement, make the mechanism ablatable via
  config rather than via code deletion.

D4 — CONVERGENCE SCORER MUTATES ITS INPUT, graph/nodes.py:463-578
  Make it pure. Return new hypothesis objects.

SEMANTIC DEFECT — anomaly_score, Enigma-ML-Layer/main.py:190
  anomaly_score is currently max softmax probability, which is classifier
  confidence, not anomalousness. A flow confidently labelled "generic" scores
  0.99. This value is the 0.30-weighted dominant term in the downstream
  confidence formula.

  Fix: emit three distinct fields.
    predicted_class_confidence  = max softmax, unchanged, renamed honestly
    anomaly_score               = 1 - P(normal)
    predictive_entropy          = normalised Shannon entropy of the softmax
  Update the adapter, the Signal schema and every consumer. Add tests. Keep
  anomaly_score as the field ReasoningEngine reads, so the weighted sum now
  measures something defensible.

F1 — DEAD FRONTEND FIELDS
  Eight dashboard panels read max_anomaly, last_activity, lifecycle and
  sources, none of which the backend sends. Either send them or remove the
  panels. Do not leave panels displaying zeros.

CONSTRAINTS
  Every mechanism touched here must end up switchable via config.py and
  environment variable, because Level 9 ablates all four.
  Add a regression test per defect that fails against the old behaviour.

DONE CHECK
  - a replayed run produces a non-degenerate distribution of trend labels
    under clock_mode=separated, paste the distribution
  - test suite green, new tests included
  - grep confirms no consumer of the old anomaly_score semantics remains
```

---

## Level 3 — Leakage-free retraining

**Goal:** one honest, reproducible classifier. 12 hours.

```
LEVEL 3 — Rebuild the training pipeline without leakage.

The existing pipeline has four leakage paths documented in
paper/EVIDENCE.md section A5. SMOTE, the StandardScaler, the mutual-information
selector and outlier replacement are all fitted before the train/test split.
Additionally there is no untouched test set, the same 20% split drove
keras_tuner selection, early stopping and final reporting.

TASKS
1. Three-way split. Train, validation, test. Stratified. The test set is
   touched exactly once, at the very end. If the official 175k/82k partition is
   present, use it and report that you did, because it preserves the
   train/test distribution shift that makes the benchmark meaningful.
2. Move every fitted transform inside a sklearn Pipeline so it fits on the
   training fold only. SMOTE goes inside an imblearn Pipeline, applied to the
   training fold only, never to validation or test.
3. Merge the backdoor and backdoors label artefact into one class. Document
   the row counts before and after.
4. HOLD OUT ONE ATTACK CLASS ENTIRELY from training. Recommended: Worms, it
   has 171 real examples and is unclassifiable anyway. This class appears only
   at test time and constitutes the unknown-attack condition that the whole
   paper depends on. Make it a parameter, --holdout-class, so you can run
   both a closed-set and an open-set configuration.
5. Call the metrics that were imported at cell 1 and never used. Accuracy,
   macro-F1, weighted-F1, per-class precision/recall/F1 with support,
   normalised confusion matrix, and false positive rate. FPR is the number an
   IDS reviewer looks for first.
6. Evaluate on BOTH the class-balanced test set and the natural distribution
   test set. Report both. The natural distribution is what an operator sees.
7. Five seeds. Report mean and standard deviation for every headline metric.
8. Checkpoint everything: model weights, the fitted pipeline, the class index
   mapping, and a JSON of all hyperparameters. Commit the artefacts or store
   them with a documented retrieval path. The class index mapping is what the
   serving path needs to turn a softmax index into a class name.

EXPECTATIONS
  Do not tune for accuracy. The honest published ceiling on the official split
  is 77 to 85% multiclass, and macro-F1 of 0.4 to 0.6 is normal because
  Analysis, Backdoor and Worms are near-unclassifiable. If you land above 85%,
  stop and hunt for leakage. A high number here is a bug, not a result.

OUTPUTS
  results/classifier/metrics_{seed}.json
  results/classifier/confusion_{seed}.npy
  artifacts/model_{config}.keras, artifacts/pipeline_{config}.pkl,
  artifacts/class_index.json

DONE CHECK
  - a leakage audit script confirms no transform sees test data before fitting
  - metrics reported for closed-set and open-set, balanced and natural
  - five seeds, standard deviations reported
```

---

## Level 4 — Calibration and selective prediction

**Goal:** the sensor becomes a trustworthy, abstaining input. 14 hours.

This is the first half of your contribution.

```
LEVEL 4 — Make the sensor calibrated and give it a reject option.

Read the research context: calibration for NIDS alone is saturated, so this
level is not the contribution by itself. It exists to make sensor confidence
trustworthy enough that reasoner-level abstention can be attributed to
evidence rather than to noise.

TASKS
1. Measure calibration before any correction. Expected Calibration Error with
   15 bins, plus a reliability diagram. Report ECE per class as well as
   overall, because minority-class miscalibration is the mechanism your
   downstream sanity gate is supposed to absorb.
2. Apply temperature scaling, fitted on the validation set only, per Guo et
   al. 2017. Report ECE before and after. Export the reliability diagram at
   publication size as PDF.
3. Add an epistemic uncertainty estimate. Choose one and justify it:
   Monte Carlo dropout with 50 forward passes, or a deep ensemble of five
   models. Deep ensemble is stronger and you already need five seeds from
   Level 3, so it is close to free. Report predictive entropy and mutual
   information, which separates aleatoric from epistemic uncertainty.
4. Implement a reject option. The classifier abstains when its calibrated
   confidence falls below a threshold. Sweep the threshold and produce a
   risk-coverage curve and AURC, per the SelectiveNet evaluation convention.
5. The critical experiment for this level: compare uncertainty on the
   held-out unknown class against uncertainty on known classes. Report the
   separation. If epistemic uncertainty does not separate them, say so
   plainly, it is a negative result you must report rather than hide.
6. Wire the reject decision into the serving path. A rejected record emits a
   Signal with an explicit abstained flag rather than a class label. The
   downstream reasoner must handle it.

OUTPUTS
  results/calibration/ece_{config}_{seed}.json
  results/calibration/risk_coverage_{config}.csv
  results/calibration/uncertainty_by_class_{config}.csv
  figures/reliability_diagram.pdf, figures/risk_coverage.pdf

DONE CHECK
  - ECE before and after temperature scaling, both reported
  - AURC computed
  - uncertainty separation between known and held-out classes quantified
  - a rejected record flows through to the reasoner with abstained=true
```

---

## Level 5 — Baselines

**Goal:** the comparison table. 8 hours.

```
LEVEL 5 — Baselines on the identical split.

Currently zero baselines exist and sklearn's tree modules are not even
imported.

TASKS
1. Random Forest and XGBoost on the exact same split and pipeline as Level 3.
   Expect them to beat the MLP. Report it. Tree ensembles dominate this
   dataset and pretending otherwise will be caught.
2. Calibrate the tree baselines too, so the calibration comparison is fair.
   Isotonic or Platt for the trees.
3. Two or three published UNSW-NB15 multiclass results from the literature,
   cited, with a clear note on which split each used. Kasongo and Sun 2020 is
   the standard official-split reference at 77.16% multiclass.
4. A flat-alerting strawman for the reasoning layer: every non-normal
   prediction becomes its own alert, no situation grouping, no hypothesis
   loop. This is the baseline your architecture argues against and you need
   its alert volume for the paper.
5. A rule-only reasoning variant with the LLM removed, and an LLM-only variant
   with the deterministic reasoning removed. These two matter more than the
   classifier baselines, because they isolate what the hybrid buys you.

OUTPUTS
  results/baselines/{model}_{seed}.json
  results/baselines/alert_volume_comparison.csv

DONE CHECK
  - Table I is producible: your MLP versus RF versus XGBoost versus cited
    literature, macro-F1 and weighted-F1 with seed variance
  - alert volume for flat alerting versus situation grouping, reported
```

---

## Level 6 — Instrumentation

**Goal:** nothing that happens in the reasoner goes unrecorded. 12 hours.

Every figure except the architecture diagram is blocked on this.

```
LEVEL 6 — Add telemetry to the reasoning stack.

Currently there is zero server-side instrumentation. Every value the paper
needs already exists in the returned state, but only the final state is
returned and nothing writes it to disk.

TASKS
1. A structured run logger. Every analysis writes one JSONL record per
   reasoning iteration, not just per analysis. Fields:
     run_id, situation_id, iteration, timestamp,
     trend, convergence_score, evidence_count, source_diversity,
     mean_anomaly, burst_detected, is_quiet,
     hypotheses[{id, text_hash, confidence, is_unknown}],
     dominant_iterations, terminated, termination_reason
   This requires either a LangGraph stream or callback hook, or logging
   inside update_convergence. Currently runner.py:103 returns only the final
   state.
2. Per-stage latency. Instrument six boundaries: ingest, situation attach,
   deterministic reasoning, LangGraph plus Gemini, explanation build,
   broadcast. Record p50, p95, p99. Expect Gemini to dominate by one to two
   orders of magnitude and report that honestly.
3. Queue depth and backlog. Every signal currently spawns an unbounded
   asyncio.create_task running up to three Gemini calls, against a 4 records
   per second arrival rate. Instrument the backlog and add a bounded
   semaphore so the system degrades measurably rather than silently.
4. A run manifest per experiment: git commit hash, config dict, seed,
   model artefact hash, dataset hash, wall clock start and end.
5. An offline replay mode that runs the reasoning stack over a fixed list of
   Signal objects without any network service, so experiments are
   deterministic and fast. This is what Levels 8 and 9 will drive.

CONSTRAINTS
  Logging must not change reasoning behaviour. Add a test that asserts
  identical final state with logging on and off, given the same seed and a
  mocked LLM.

DONE CHECK
  - a single replayed run produces a JSONL with one row per iteration
  - latency percentiles reported per stage
  - offline replay mode runs 100 situations with a mocked LLM in under 10s
```

---

## Level 7 — Scenario generator

**Goal:** situation-level ground truth, which currently does not exist. 16 hours.

This is the highest-risk level and the one that unlocks every downstream claim.
Without it you cannot measure whether the reasoner concluded correctly, only
that it concluded.

```
LEVEL 7 — Build a scenario generator with injected ground truth.

The project has no situation-level ground truth, so no component downstream of
the classifier can currently be evaluated. Since you generate the scenario, you
know the correct conclusion.

DESIGN
  A scenario is a list of Signal objects plus a ground-truth label stating
  what a correct reasoner should conclude, including "insufficient evidence,
  correct answer is UNKNOWN".

  Four evidence regimes, per paper/FIGURES.md Fig 3:
    CLEAR       strong consistent evidence, one correct hypothesis
    AMBIGUOUS   evidence consistent with two hypotheses, correct answer is
                either abstention or a low-confidence pair
    SPARSE      too little evidence to conclude, correct answer is UNKNOWN
    UNKNOWN_ATTACK  signals derived from the held-out class from Level 3,
                correct answer is UNKNOWN, no known hypothesis is right

  Parameters per scenario: signal count, arrival pattern including burst and
  quiet, source diversity from 1 to 4, anomaly score distribution, entity
  count, and whether abstained signals from Level 4 are present.

TASKS
1. Implement the generator. Deterministic given a seed.
2. Generate a suite of at least 400 scenarios, balanced across the four
   regimes, and freeze it with a hash. The frozen suite is what every
   experiment runs against.
3. USE MULTIPLE SOURCES. Set Signal.source to different values so
   source_diversity exceeds 1. Currently it is hardcoded to one string, which
   pins three mechanisms into a degenerate regime. The three implemented but
   unused adapters, network.py, auth.py and video.py, define the schemas you
   need. This is the only place a limited multi-source claim becomes
   defensible, and it must be framed as controlled synthetic evaluation, not
   as real cross-domain fusion.
4. Define the outcome metrics precisely and implement scoring:
     correct_conclusion_rate
     false_conclusion_rate      concluded, and wrong
     abstention_rate            terminated with UNKNOWN dominant
     appropriate_abstention     abstained when ground truth says UNKNOWN
     premature_convergence_rate concluded before evidence sufficed
     single_iteration_conclusion_rate
     mean_iterations_to_termination
5. Validate the generator. Run the unmodified system against it and confirm
   the scores are neither at floor nor at ceiling. A generator that is too
   easy or too hard measures nothing.
6. Ship the generator in the artifact. Reviewers will ask, and a released
   generator converts the main weakness of this evaluation into a
   contribution.

DONE CHECK
  - 400+ frozen scenarios with a manifest hash
  - all seven metrics computed against the current system, values pasted
  - source_diversity distribution across the suite, pasted
  - scores are mid-range, not saturated
```

---

## Level 8 — Clock-domain study

**Goal:** N1, now a section rather than a paper. 8 hours.

```
LEVEL 8 — The clock-conflation experiment.

Level 2 preserved the defect behind clock_mode with three values. Run all
three across the frozen scenario suite.

TASKS
1. For each of conflated, wall, separated, run the full suite. Five seeds.
2. Report per configuration:
     distribution of trend labels
     fraction of situations reaching convergence
     mean final UNKNOWN confidence
     mean iterations to termination
     all seven Level 7 outcome metrics
3. Produce Fig 2 as a three-panel grouped bar chart.
4. Write the finding as a reproducibility hazard for replay-based IDS
   evaluation generally, not merely as a bug report about your system. The
   generalisable claim is that conflating wall-clock and event-time in a
   temporal reasoning layer silently converts every replayed situation into a
   quiescent one, which collapses trend detection to a constant.

OUTPUTS
  results/clock_study/{mode}_{seed}.jsonl
  figures/fig2_clock_collapse.pdf

DONE CHECK
  - three configurations, five seeds each
  - the collapse is quantified, not asserted
```

---

## Level 9 — Epistemic control ablation

**Goal:** the paper. 20 hours.

```
LEVEL 9 — Ablate the four epistemic control mechanisms.

This is the primary contribution. Four mechanisms, each independently
switchable after Level 2:

  U  non-prunable UNKNOWN hypothesis        nodes.py:201-214
  S  sanity gate doubt boost                nodes.py:223-317
  A  asymmetric confidence decay            nodes.py:322-399
  P  persistence requirement                runner.py convergence_persistence

TASKS
1. Full 2^4 factorial, 16 configurations, across all four evidence regimes
   from Level 7, five seeds. That is 320 runs of the suite. Use the offline
   replay mode from Level 6 and a real LLM, not a mock, because the point is
   LLM overconfidence. Budget the Gemini calls and cache aggressively.
2. Primary outcome: premature_convergence_rate and false_conclusion_rate.
   Secondary: appropriate_abstention on SPARSE and UNKNOWN_ATTACK regimes.
3. The headline analysis is the UNKNOWN_ATTACK regime crossed with the
   Level 4 sensor reject option. Four cells:
     sensor rejects on, epistemic control on
     sensor rejects on, epistemic control off
     sensor rejects off, epistemic control on
     sensor rejects off, epistemic control off
   This is the two-level abstention claim. If the two levels are
   complementary rather than redundant, that is the result the paper turns on.
   If they are redundant, report that, it is still publishable and more honest
   than most of the literature.
4. Report main effects and, if the data supports it, interactions. Sixteen
   bars will be unreadable in one column, so plan a main-effects plot with the
   four single-factor removals plus the all-off baseline, and put the full
   16-row table in an appendix.
5. Statistical treatment. Five seeds, report mean and standard deviation, and
   state plainly that this is not a significance test unless you run enough
   seeds to justify one.

RISK
  If no configuration differs meaningfully from any other, the mechanisms do
  nothing and that is the finding. Report it. A negative result on whether
  hand-designed epistemic guardrails actually constrain an LLM reasoner is
  publishable at your target venues and is more useful than a fabricated
  positive.

OUTPUTS
  results/ablation/{config}_{regime}_{seed}.jsonl
  results/ablation/summary.csv
  figures/fig3_ablation_main_effects.pdf
  figures/fig6_belief_trajectory.pdf

DONE CHECK
  - 16 configurations x 4 regimes x 5 seeds complete
  - the four-cell two-level abstention table, populated
  - main effects plot produced
```

---

## Level 10 — Evaluation harness, figures, artifact

**Goal:** everything a reviewer will ask for. 16 hours.

```
LEVEL 10 — Evaluation harness, figure export, artifact packaging.

TASKS
1. LLM-judge panel for reasoning quality, where the scenario ground truth
   cannot reach. Three judges, different model families if possible, frozen
   prompt, evaluating whether a hypothesis is plausible given the evidence.
   Validate the panel against a human-annotated subset of at least 50 cases
   that you label yourself. Report agreement, Pearson r or MAE.
2. Deterministic trace checks alongside the judges. Assert directly from the
   Level 6 logs whether UNKNOWN was retained, whether termination required
   more than one iteration, whether the persistence requirement was actually
   satisfied. Reviewers increasingly know that LLM judges score unverified
   trajectories far too generously, so trace checks are what make the judging
   credible.
3. Export all figures at publication size as PDF. Nothing in this project is
   currently exported, only rendered in notebooks.
     Fig 1  architecture and data flow, drawn honestly, mark the LLM
            information barrier as a selling point, grey the three unused
            adapters rather than omitting them
     Fig 2  clock collapse, from Level 8
     Fig 3  ablation main effects, from Level 9
     Fig 4  confusion matrix and per-class F1, from Level 3
     Fig 5  reliability diagram and risk-coverage, from Level 4
     Fig 6  belief trajectory case study, from Level 9
   Latency by stage becomes a table rather than a figure unless Level 6
   produced something interesting.
4. Tables.
     Table I   baseline comparison from Level 5
     Table II  component status and threats to validity, condensed from
               paper/EVIDENCE.md section G
     Table III full 16-configuration ablation for the appendix
5. Reproducibility package. A single script that regenerates every number and
   every figure from the frozen scenario suite and the checkpointed model.
   A README stating exact versions, seeds, hardware and expected runtime.
6. Threats to validity section, written honestly. It must state: the
   evaluation is predominantly synthetic; the multi-source condition is
   constructed, not observed; the LLM is non-deterministic and only five seeds
   were run; the classifier is a sensor and not a contribution; no real
   deployment or operator study was conducted.
7. Update paper/EVIDENCE.md with everything that changed, so the audit trail
   stays accurate.

DONE CHECK
  - reproduce.sh regenerates every figure from scratch
  - judge panel validated against 50 human-labelled cases
  - all six figures exported as PDF
```

---

## What to watch for

**The pivot trigger.** If Level 9 shows the four mechanisms are indistinguishable,
do not manufacture a difference. Rewrite the paper around the negative result and
the two-level abstention comparison from Level 4, which will still hold.

**The leakage trigger.** If Level 3 produces above 85% multiclass accuracy on the
official split, something is wrong. Stop and audit before proceeding.

**The scenario trigger.** If Level 7 cannot produce a generator whose scores sit
in mid-range, the whole downstream evaluation is measuring nothing. Fix it there,
not later.

**The re-check.** LLM-SOC papers appeared monthly through 2025 and 2026. Run a
targeted literature search immediately before submission to confirm nobody has
published the epistemic-control ablation while you were building it.