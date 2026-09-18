# EVAL_STATUS — Phase 2, item 8

What evaluation exists today, verbatim, with citations. Nothing here is
extrapolated.

---

## 1. Quantitative results that exist

**All of them come from stored outputs in `Enigma-ML-Layer/Model.ipynb`.
There is exactly one file in the entire project that has ever produced a
number, and its training cells are commented out.**

| # | Metric | Value | Model | Split | Evidence |
|---|---|---|---|---|---|
| R1 | Accuracy | 0.7017272710800171 | cell-46 hand-built MLP (**not deployed**) | 20% of the SMOTE-balanced 165k set | cell 49 output |
| R2 | Categorical cross-entropy loss | 0.9234094619750977 | same | same | cell 49 output |
| R3 | Best `val_accuracy` over 10 random-search trials | 0.7351818084716797 | best tuner trial | same | cell 54 output |
| R4 | Last trial `val_accuracy` | 0.5833636522293091 | trial 10 | same | cell 54 output |
| R5 | Tuner wall-clock | 1 h 36 m 36 s | — | — | cell 54 output |
| R6 | Final `val_accuracy` @ epoch 100 | **0.7382** | `model1` — **the deployed model** | same | cell 57 output |
| R7 | Final `val_loss` @ epoch 100 | **0.7395** | same | same | cell 57 output |
| R8 | Final train accuracy @ epoch 100 | 0.7044 | same | same | cell 57 output |
| R9 | Single-record softmax vector | `[0.3464, 0.4094, 0.00015, 0.1199, 0.0240, 0.0407, 0.0239, 0.00029, 0.0331, 0.0021, 0.00015]` | deployed | 1 record, `x.iloc[0:1]` | cell 62 output |
| R10 | Single-record SHAP top-3 | `swin +0.7768`, `sloss −0.3358`, `sbytes +0.2423` | deployed | 1 record, 100-row background | cell 65 output |
| R11 | Mutual-information scores, 32 features | `sbytes 1.2514` … `ct_src_dport_ltm 0.0000` | n/a | whole dataset (pre-split) | cell 38 output |
| R12 | Class distribution before/after SMOTE | 11 classes, 1,959,771 → 15,000 each | n/a | whole dataset | cell 35 output |
| R13 | Highly-correlated feature pairs (\|r\| ≥ 0.75) | 18 pairs | n/a | whole dataset | cell 32 output |

### Caveats attached to every number above
1. **R6/R7 are the only figures describing the deployed model**, and they are
   validation figures. The same split drove `keras_tuner` model selection
   (cell 54) and epoch-level monitoring (cell 57). There is **no untouched
   test set.**
2. R1/R2 (the "70.17%" most likely to be quoted) belong to a **discarded**
   architecture.
3. All of R1-R8 are measured on a **SMOTE-balanced** set where 9 of 11
   classes are majority-synthetic, so they do not estimate operational
   performance on real 77%-`normal` traffic.
4. All of R1-R8 are contaminated by the four leakage paths in EVIDENCE §A5.

> **Recommended framing if you must cite a number today:**
> "≈74% validation accuracy on a class-balanced 11-way UNSW-NB15 task,
> measured on the same split used for hyperparameter selection." Anything
> stronger is not defensible.

---

## 2. Metrics that do NOT exist

| Metric | Status | Note |
|---|---|---|
| Precision (any averaging) | **ABSENT** | imported at cell 1, never called |
| Recall | **ABSENT** | imported, never called |
| F1 (macro / micro / weighted) | **ABSENT** | imported, never called |
| Confusion matrix | **ABSENT** | imported, never called |
| `classification_report` | **ABSENT** | imported, never called |
| ROC-AUC / ROC curve | **ABSENT** | imported, never called |
| Per-class breakdown | **ABSENT** | — |
| False-positive rate | **ABSENT** | the single most important metric for an IDS paper |
| PR curves | ABSENT | — |
| Calibration / reliability diagram | ABSENT | — |
| Detection latency | ABSENT | EVIDENCE §C1 |
| Throughput (records/s sustained) | ABSENT | — |
| Queue depth / backlog | ABSENT | EVIDENCE §C4 |
| Memory profile over a long run | ABSENT | relevant given EVIDENCE §D6 |
| Explanation quality (any measure) | ABSENT | no faithfulness, stability, or human study |
| Hypothesis quality (any measure) | ABSENT | no annotation of whether Gemini's hypotheses are correct |
| Convergence-rate statistics | ABSENT | the field exists; nothing aggregates it |
| End-to-end system accuracy | ABSENT | no ground truth exists at the situation level |

Six of the seven sklearn metrics imported at `Model.ipynb` cell 1
(`recall_score, precision_score, f1_score, confusion_matrix,
classification_report, roc_auc_score, roc_curve`) are **never invoked
anywhere in the notebook.**

---

## 3. Baselines

**ABSENT — zero baselines of any kind.**

No comparison against:
- classical detectors on UNSW-NB15 (Random Forest, XGBoost, SVM, k-NN) —
  the standard comparison set for this dataset;
- published UNSW-NB15 results from the literature;
- a rule-only variant of the reasoning stack (no LLM);
- an LLM-only variant (no deterministic reasoning);
- a flat alerting baseline (no situation grouping) — the natural strawman
  the paper's own architecture argues against;
- any competing SIEM correlation approach.

`sklearn`'s ensemble and tree modules are **not even imported** at
`Model.ipynb` cell 1. No baseline was ever attempted.

---

## 4. Ablations

**ABSENT — zero ablations.**

The codebase has four cleanly separable mechanisms that are *designed* to be
ablatable, and none of them has been ablated:

| Mechanism | Ablation switch that already exists | File |
|---|---|---|
| UNKNOWN hypothesis | remove the injection block | `nodes.py:201-214` |
| Sanity gate | drop the node from the topology | `builder.py:48,56-57` |
| Belief inertia | drop the node | `builder.py:50,59` |
| Convergence persistence | `convergence_persistence` param, already plumbed to the runner | `runner.py:57,76,93` |
| Max iterations | `max_iterations` param | `runner.py:56,74` |
| Correlation strategy | `EntityCorrelation` ↔ `DefaultCorrelation`, injectable | `main.py:67`, `correlation.py:26-51` |
| Confidence weights | all five settable via env | `config.py:21-28` |

This is the most valuable thing in this document: **the ablation
infrastructure is already built.** See NOVELTY N2 and GAPS G3.

---

## 5. Plots and saved artifacts

| Artifact | Status | Evidence |
|---|---|---|
| Boxplots, 43 numerical features | rendered in notebook, **not exported** | cell 20 output `<Figure size 1800x4500 with 43 Axes>` |
| Histograms + skewness, 43 features | rendered, not exported | cell 23 output |
| PCA cumulative-variance scree plot | rendered, not exported | cell 42 output |
| Train/val loss curve | rendered, not exported | cell 50 output |
| Model checkpoint `.h5` | **not in repo** | INVENTORY §1 |
| Preprocessing state `.pkl` | **not in repo** | INVENTORY §1 |
| Keras-tuner directory `/kaggle/working/threat_detection_project` | **not in repo**, path is Kaggle-specific | cell 52 |
| Result logs, CSV, JSON | **none anywhere** | — |
| Any figure file (`.png`/`.pdf`/`.svg`) in any repo | **none** | file listing |

**No figure in this project is currently in an exportable state.** Every plot
would have to be regenerated, which requires the missing dataset and a
re-run of the commented-out training cells.

---

## 6. Test suite as evidence

216 test functions; **167 pass in 0.58 s** on this machine.
`tests/test_graph.py` (49 tests) does not collect here because `ormsgpack`,
a transitive LangGraph dependency, is blocked by a local Windows Application
Control policy — an environment fault, not a code fault.

| File | Tests | What it establishes |
|---|---|---|
| `test_explanation.py` | 62 | Section construction, integrity validation, role filtering |
| `test_graph.py` | 49 | Node behaviour with a **mocked** LLM |
| `test_adapters.py` | 34 | Field mapping and rejection paths for all 4 adapters |
| `test_temporal.py` | 30 | Interval maths, burst/quiet booleans |
| `test_reasoning.py` | 21 | Confidence arithmetic, trend branches |
| `test_signal.py` | 10 | Pydantic validation at the boundary |
| `test_situation.py` | 5 | Lifecycle transitions |
| `test_store.py` | 5 | Find-or-create, expiry helper |

**What the suite is:** thorough unit coverage of deterministic logic. It is
genuinely good engineering and is worth one honest sentence in the paper.

**What the suite is not:**
- It does not measure detection quality — no test asserts an accuracy,
  precision, or recall.
- It does not exercise a real LLM (`_mock_llm_response` in
  `test_graph.py` mocks at the LangChain `invoke` level).
- It does not exercise the ML layer at all — `Enigma-ML-Layer` has **zero
  tests**.
- It does not exercise the frontend — `Enigma-Frontend` has **zero tests**
  and no test script (`package.json:5-10`).
- It does not test the defects in EVIDENCE §D. In fact, three of them
  (D1 mixed clocks, D2 no-op inertia, D3 discarded penalty) survive
  precisely because the tests assert on the fields the buggy code *does*
  write, not on the behaviour the code is *supposed* to produce.

---

## 7. Evaluation protocol

**ABSENT.** There is no written protocol, no seed policy beyond
`random_state=42` in two places (cells 5, 43), no repeated-run variance, no
hardware/software manifest, and no defined success criterion for any
component other than the classifier's accuracy.

---

## 8. Bottom line

> **The project has produced exactly one defensible quantitative claim —
> ≈74% validation accuracy on a leakage-contaminated, class-balanced,
> 11-way UNSW-NB15 split — and it cannot currently be reproduced because the
> dataset, the model weights, and the executable training cells are all
> absent.**
>
> Every other component of the system (correlation, temporal reasoning,
> hypothesis generation, explanation, dashboard) has **no evaluation
> whatsoever**: no metric, no baseline, no ablation, no protocol, no saved
> output.
