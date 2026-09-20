# EVIDENCE — Phase 2, items 2, 3, 4, 7 + defects + README audit

---

## A. Data

### A1. The only dataset actually used: UNSW-NB15

| Property | Value | Status | Evidence |
|---|---|---|---|
| Source | UNSW-NB15, files `UNSW-NB15_1..4.csv` + `NUSW-NB15_features.csv` | IMPLEMENTED | `Model.ipynb` cell 2; `Streamer.py:7-12,23` |
| Files present in repo | **none** | ABSENT | `Enigma-ML-Layer` listing has no `archive/` |
| Raw record count | 2,540,041 (last index `2540040` in cell 14 output) | code-produced | `Model.ipynb` cell 14 output |
| After de-duplication | **UNVERIFIED** | — | `train_df.drop_duplicates()` at cell 7, count not printed |
| Class count after label encoding | 11 | code-produced | cell 31 output |
| Post-dedup class distribution | normal 1,959,771; exploits 27,600; generic 25,378; fuzzers 21,795; reconnaissance 13,357; dos 5,665; analysis 2,185; backdoor 1,684; shellcode 1,511; backdoors 300; worms 171 | code-produced | cell 35 output |
| Time span | **UNVERIFIED** | — | `Stime`/`Ltime` are read but no min/max is printed anywhere |
| Sampling rate (offline) | n/a — flow records, not a fixed-rate feed | — | — |
| Sampling rate (replay) | 2 records per 0.5 s ≈ **4 records/s** | IMPLEMENTED | `Streamer.py:17-18,47` |
| Labels | present: `attack_cat` (target) and `Label` (binary) | IMPLEMENTED | cells 9, 30 |
| Synthetic data | **yes** — SMOTE to 15,000/class | IMPLEMENTED | cell 35 |
| Final balanced set | 11 × 15,000 = **165,000 rows** | code-produced | cell 35 output |

### A2. Label-space defect
Cell 31 output shows both `'backdoor': 1` and `'backdoors': 2` as separate
classes. These are the same UNSW-NB15 attack category with inconsistent
whitespace/plural in the source CSVs; cell 9 lowercases and strips but does
not merge them. The result is an **11-class problem where 10 is correct**,
with class 2 having only 300 real examples before SMOTE inflates it to
15,000 (5,000% synthetic).

Downstream, `_SIGNAL_TYPE_MAP` in `adapters/unsw_threat.py:35-53` contains
`"backdoor"` but **not** `"backdoors"`, so every prediction of class 2
degrades to `SignalType.UNKNOWN` at `unsw_threat.py:97`.

### A3. Preprocessing chain, in execution order
| Step | Cell / line | Note |
|---|---|---|
| Concatenate NB15_1..4 | cell 4 | |
| Shuffle, `random_state=42` | cell 5 | |
| `drop_duplicates()` | cell 7 | |
| `attack_cat` NaN → `'normal'`, strip+lower | cell 9 | 95.16% of rows were NaN (cell 8 output) |
| `ct_flw_http_mthd` NaN → 0 | cell 9 | 45.33% missing |
| `is_ftp_login` NaN → 0, then binarised | cells 9, 14 | 49.25% missing |
| `ct_ftp_cmd` `' '` → `'0'`, → int | cells 11-13 | |
| `sport`/`dsport` → numeric, NaN → 0 | cells 15-18 | |
| **Outliers → median** (IQR×1.5) | cell 22 | applied to the *whole* dataset |
| Drop 7 categorical cols | cell 27 | `sport, dsport, proto, srcip, dstip, state, service` |
| `LabelEncoder` on `attack_cat` | cell 30 | |
| Drop one of each pair with \|r\| ≥ 0.75 | cells 32-33 | 18 pairs found; 32 columns remain |
| **SMOTE + RandomUnderSampler to 15,000/class** | cell 35 | |
| Mutual-information filter, drop score < 0.01 | cells 37-40 | 12 features dropped, incl. `Label` |
| `StandardScaler.fit_transform` | cell 41 | on the *whole* dataset |
| `train_test_split(test_size=0.2, random_state=42)` | cell 43 | **last** |
| `to_categorical(num_classes=11)` | cell 44 | |

### A4. Dead preprocessing code
- `transform()` (log-skew correction), cell 24 — **defined, never called.**
- `generate_features()` (22 engineered ratio/interaction features), cell 26 —
  **defined, never called.** The paper cannot claim feature engineering.
- `PCA()` fitted and its scree plot shown, cell 42 — **never applied**; the
  model consumes `x_scaled` directly (cell 43).
- `pie_bar_plot()`, cell 25 — defined, never called.

### A5. Four independent train/test leakage paths
All four preprocessing steps below run **before** the split at cell 43:

1. **SMOTE before split** (cell 35 → cell 43). Synthetic minority samples are
   interpolations between real neighbours. After the split, a test-set
   synthetic point can be a linear combination of two training points, and
   vice versa. For classes with 171–2,185 real examples inflated to 15,000
   (worms, backdoors, shellcode, backdoor, analysis), the test partition is
   almost entirely synthetic and derived from training data. **This is the
   most severe methodological defect in the project.**
2. **Scaler fitted on all data** (cell 41). Test-set mean/variance leaks.
3. **Mutual-information feature selection on all data** (cells 37-40).
4. **Outlier→median replacement on all data** (cell 22).

Additionally, `validation_data=(x_test_scaled, y_test_one_hot)` is used both
for `keras_tuner` model selection (cell 54) and for early stopping /
reporting (cells 48, 57). **There is no held-out set that was not used for
model selection.** Every accuracy figure below is a validation figure, not a
test figure.

---

## B. Models

### B1. Deployed model
| Property | Value | Evidence |
|---|---|---|
| Type | Feed-forward MLP, Keras `Sequential` | cells 51-56 |
| Search space | 1-5 Dense layers, 20-40 units (step 2), Dropout 0.1-0.5, LR ∈ {1e-2, 1e-3, 1e-4}; BatchNorm after each Dense | cell 51 |
| Search | `keras_tuner.RandomSearch`, `max_trials=10`, objective `val_accuracy` | cell 52 |
| Chosen hyperparameters | **UNVERIFIED** — `best_param` (cell 55) is never printed | cells 55-56 |
| Input dim | 20 | cell 51; confirmed by cell 61 output `Shape of input: (1, 20)` and cell 64 output `Loaded 20 features` |
| Final features | `dur, sbytes, dbytes, sloss, Sload, Dload, swin, stcpb, dtcpb, smeansz, dmeansz, Sjit, Djit, Stime, Dintpkt, ct_srv_src, ct_srv_dst, ct_dst_ltm, ct_src_ ltm, ct_dst_src_ltm` | cell 64 output |
| Output | 11-way softmax | cell 51 |
| Loss | `categorical_crossentropy` | cell 51 |
| Optimiser | Adam | cell 51 |
| Epochs | 100, no early stopping in the final fit | cell 57 |
| Batch size | Keras default 32 (4,125 steps × 32 ≈ 132,000 = 80% of 165,000 ✓) | cell 57 output |
| Split | 80/20, `random_state=42` | cell 43 |
| Checkpoint | `unsw_nb15_threat_detection_model.h5` + `unsw_nb15_preprocessing_state.pkl` | cells 58-59 |
| Checkpoint in repo | **NO** | see INVENTORY §1 |

### B2. `Stime` as a model feature — a leakage-adjacent problem
`Stime` (flow start time, a raw Unix timestamp) survives feature selection
with the 4th-highest mutual-information score, 0.742683 (cell 38 output), and
is one of the 20 features fed to the model (cell 64 output).

In UNSW-NB15 the attack traffic was generated in scheduled simulation
windows. A high-MI raw timestamp is the classic signature of the model
learning *when the capture happened* rather than *what the traffic looks
like*. Any reviewer will flag this. It also guarantees the model cannot
generalise to a live 2026 deployment, where `Stime` lies far outside the
training range and `StandardScaler` will map it to an extreme z-value.

### B3. Every number the notebook actually produced

| Metric | Value | Which model | Evidence |
|---|---|---|---|
| Test accuracy | **0.7017272710800171** | the *untuned* hand-built model of cell 46 | cell 49 output |
| Test loss | **0.9234094619750977** | same | cell 49 output |
| Tuner best `val_accuracy` | **0.7351818084716797** over 10 trials | best tuner trial | cell 54 output |
| Tuner total search time | 1 h 36 m 36 s | | cell 54 output |
| Final `val_accuracy` @ epoch 100 | **0.7382** | `model1` — **this is the deployed model** | cell 57 output |
| Final `val_loss` @ epoch 100 | **0.7395** | same | cell 57 output |
| Final train accuracy @ epoch 100 | 0.7044 | same | cell 57 output |
| Hardware | NVIDIA RTX 3050 Laptop GPU, 1763 MB | | cell 46 output |
| Training wall time | ≈ 10-13 s/epoch × 100 ≈ **~20 min** | | cell 57 output |

**Critical caveat for the paper:** the widely quoted "70.17%" (cell 49) is
*not* the deployed model. It belongs to the throwaway architecture of cell
46. The deployed model is `model1` (cells 56-58), whose only figure is
`val_accuracy = 0.7382` — measured on the same split used for hyperparameter
selection.

**Precision, recall, F1, per-class breakdown, confusion matrix, ROC-AUC:
ABSENT.** All six are imported at cell 1 and **never called**. For an
11-class problem with a real-world prior of 77% `normal`, accuracy alone is
uninformative. This is a guaranteed reviewer rejection point.

### B4. The notebook is not re-runnable
Cells 48 (first `fit`), 54 (`tuner.search`), 57 (final `fit`), 58 (`save`),
and 59 (`joblib.dump`) are **entirely commented out**. Their stored outputs
prove they ran once, but a fresh `Run All` trains nothing and saves nothing.
Combined with the missing `archive/` directory and missing `.h5`/`.pkl`,
**no result in this project can currently be reproduced by anyone,
including the authors.**

### B5. Second learned component — Gemini
| Property | Value | Evidence |
|---|---|---|
| Model | `gemini-2.0-flash` | `config.py:41` |
| Temperature | 0.2 | `config.py:42` |
| Max output tokens | 1024 | `config.py:43` |
| Auth | `GOOGLE_API_KEY` or `ENIGMA_GEMINI_API_KEY` | `graph/runner.py:34` |
| Prompt | fixed template, 10 aggregate metrics, asks for exactly 3 hypotheses, one benign | `graph/nodes.py:74-104` |
| Sees raw signals? | **No** — only the 10 fields in `assemble_context` | `graph/nodes.py:52-66` |
| Output constraint | `confidence` clamped to [0.1, 0.5]; ≤5 hypotheses | `graph/nodes.py:152-157` |
| Failure handling | JSON parse failure or exception → 3 hardcoded fallback hypotheses | `graph/nodes.py:160-171,197-199` |
| Fine-tuned / trained by this project | **No.** Zero-shot prompting of a hosted API. | — |

---

## C. Real-time claims — item 7

### C1. Server-side instrumentation: **ABSENT**
Grep across all three repos for `time.perf_counter`, `time.monotonic`,
latency counters, histograms, Prometheus, OpenTelemetry, or a metrics
endpoint returns **nothing** in `Enigma-AIAgent` and `Enigma-ML-Layer`.

`/health` (`main.py:115-135`) returns situation counts, trend counts, mean
and max confidence, and adapter accept/reject tallies. **No timing, no queue
depth, no throughput.**

`AdapterRegistry` tracks `accepted_count`/`rejected_count`
(`registry.py:21-36`) — cumulative counters, no rate.

### C2. The only latency measurement anywhere
`hooks/useHealth.ts:19-26`:
```ts
const start = performance.now();
... fetch("/api/health") ...
const elapsed = performance.now() - start;
setLatencyMs(Math.round(elapsed));
```
This is a **browser→Next.js→FastAPI HTTP round trip for a counter endpoint**.
It measures nothing about the detection or reasoning pipeline. It is
displayed in the footer with a 500 ms amber threshold
(`Footer.tsx:26`).

**Any paper claim of "real-time" backed by this number would be dishonest.**

### C3. The only pipeline latency figure that exists
A code comment in a manual test script:
> `print("\nWaiting for analysis results (Gemini takes 5-15s per signal)...")`
> — `test_live.py:127`

**Status: UNVERIFIED developer estimate.** No measurement code produced it.

### C4. Structural evidence that the system is not real-time
Four independent findings, all code-verified:

1. **Unbounded task fan-out.** Every accepted signal spawns
   `asyncio.create_task(dashboard_manager.on_situation_updated(situation))`
   (`ws_signal.py:82-85`, `ws_raw_signal.py:77-81`). There is no semaphore,
   queue bound, or debounce. Each task runs a full LangGraph pass, i.e. **up
   to 3 Gemini calls** (`config.py:36`, `nodes.py:599`).
2. **Arrival rate vs service rate.** The replayer emits ≈4 records/s
   (`Streamer.py:17-18`). If the developer's 5-15 s per analysis estimate is
   even roughly right, the system is over-subscribed by **one to two orders
   of magnitude**. Tasks accumulate in the event loop with no backpressure
   signal to the producer.
3. **Thread-pool starvation.** `run_reasoning` is dispatched via
   `asyncio.to_thread` (`ws_dashboard.py:101-103`). The default asyncio
   executor caps at `min(32, cpu_count+4)` threads. Beyond that, analyses
   queue invisibly. **No queue depth is observable anywhere.**
4. **Quadratic per-analysis cost.** `event_intervals` sorts the full
   evidence list on every access (`situation.py:131`), and is read at least
   3× per analysis (`situation.py:164,199`; `reasoning_engine.py:181`).
   Because `expire_stale()` is never called (INVENTORY §5) and evidence is
   never trimmed (`situation.py:57-61`), each situation's evidence list grows
   without bound. With EntityCorrelation keying on ~40 distinct source IPs,
   a long replay produces a handful of situations with tens of thousands of
   signals each, and per-analysis cost grows as O(n log n) in a hot path
   executed once per arriving signal.

> **Verdict: "Real-Time" in the working title is currently unsupported by any
> measurement and is contradicted by four structural properties of the code.
> Either instrument it (GAPS G4) or remove the word.**

---

## D. Correctness defects with paper impact

### D1. Mixed clock domains — invalidates the entire temporal layer
**Severity: critical. Status: code-verified.**

Two different clocks are compared:
- `event_intervals`, `active_duration`, `event_rate`, `is_bursting` all use
  **signal-supplied timestamps** (`situation.py:102,109,131`).
- `is_quiet` uses the **wall clock**: `(utc_now() - last_seen) > quiet_window`
  (`situation.py:190`).
- `last_event_age_seconds` likewise (`situation.py:204-206`).

The ML layer sets each signal's timestamp from the dataset's `Stime` column,
falling back to now only on exception (`main.py:165-173`). When archival data
is replayed, `last_seen` is the capture time, not the replay time, so
`utc_now() − last_seen` is the age of the *dataset*.

Consequences, each traceable:
1. `quiet_detected == True` for every situation, permanently
   (`situation.py:190`).
2. `_detect_trend` branch 3 fires before the interval branches, so **every
   situation with evidence is DEESCALATING** unless a burst fires first
   (`reasoning_engine.py:177-178`).
3. `evaluate_hypotheses` applies `conf -= 0.1` for quiet
   (`nodes.py:369-370`), then the ×1.5 asymmetric decay
   (`nodes.py:383-385`) makes it −0.15 per iteration, then `trend ==
   "deescalating"` subtracts a further 0.05 → −0.075 after asymmetry. Net
   ≈ **−0.225 per iteration** on every non-UNKNOWN hypothesis.
4. Initial LLM confidences are capped at 0.5 (`nodes.py:156`), UNKNOWN starts
   at 0.4 and gains +0.10 for single-source diversity (`nodes.py:302-303`).
   Within one or two iterations UNKNOWN dominates, so `convergence = 0.0`
   (`nodes.py:501-503`) and the system reports **permanently undecided**.
5. `_build_contradicting_evidence` emits "Quiet period detected"
   (`builder.py:312-314`) for every situation.
6. `last_event_age_seconds` is reported to the frontend as a value in the
   hundreds of millions of seconds (`situation.py:204-206`).

**UNVERIFIED component:** the exact magnitude depends on `Stime` values,
which cannot be checked because `archive/` is absent. The *structure* of the
defect — comparing a wall clock against a signal-supplied timestamp — is
fully code-verified and breaks for any replayed historical data.

This defect is also the best novelty seed in the project (see NOVELTY N1).

### D2. `apply_belief_inertia` is a no-op — STUBBED
`graph/nodes.py:404-458`. Three verifiable problems:

```python
raw_velocity = old_conf - (old_conf - old_velocity)   # line 437
```
is algebraically `old_velocity`. The variable is assigned and **never read**;
the comment on lines 439-441 concedes the pre-evaluation confidence is not
available in state.

```python
new_velocity = old_velocity*0.7 + 0.3*(old_conf*0.1)  # line 443
```
is a decaying function of the *absolute* confidence, not of any change in it.
For a stable confidence of 0.4 it converges to 0.04 regardless of whether
belief is rising, falling, or flat.

Most importantly, **`h["confidence"]` is never written in this function.**
Only `belief_velocity` and `belief_acceleration` (lines 454-455) are set. The
docstring claims "Confidence updates are clamped by max_confidence_step"
(line 413) and `max_step = 0.15` (line 421) is defined but applied only to
the velocity field.

> **The system's advertised "belief inertia / resistance to premature
> convergence" mechanism does not rate-limit confidence at all.** The two
> tests that cover it (`test_velocity_is_updated`, `test_velocity_is_dampened`)
> assert on the velocity field, not on confidence, so they pass.

The `belief_velocity` field then flows into user-facing explanation text at
`builder.py:373-377`, `builder.py:580-597`, and `builder.py:631-634`
("Belief is accelerating", "Confidence trend: rising"). **The dashboard
displays a belief-dynamics narrative derived from a variable that does not
track belief dynamics.**

### D3. Sanity-gate branch that discards its own work
`graph/nodes.py:274-281`:
```python
for h in deduped:
    ...
    if any(kw in desc_lower for kw in vague_keywords):
        h = dict(h)                                   # rebinds the loop var
        h["confidence"] = max(0.1, h.get("confidence", 0.3) - 0.1)
```
`h = dict(h)` creates a copy; the mutation is applied to the copy and the
copy is never written back into `deduped`. **The vague-hypothesis penalty
never takes effect.** The same pattern at lines 247-252 *does* work, because
that branch mutates and the object is appended on line 253.

### D4. `update_convergence` mutates its input, contradicting the design contract
The module docstring states each node "Returns a partial dict update" and
"Has no side effects" (`nodes.py:3-7`). But `update_convergence` writes
directly into the `hypotheses` list held in state at lines 506-508, 537-543,
and 562-565, *before* returning it. The stated purity property that the
architecture section of a paper would claim is false.

### D5. `except (ValueError, Exception)` — meaningless
`adapters/registry.py:98`. `Exception` subsumes `ValueError`; the tuple is
redundant, and it catches `KeyboardInterrupt`-adjacent programming errors
too. Cosmetic, but a reviewer reading the artifact will notice.

### D6. Ingest never expires
`store.expire_stale()` (`situation_store.py:183-199`) has **no caller**. No
`BackgroundTasks`, no `asyncio` periodic task, no lifespan handler in
`main.py`. `situation_ttl_minutes` and `situation_dormancy_minutes`
(`config.py:12-13`) affect only the *reported* lifecycle label
(`situation.py:74-85`), never actual removal. Memory grows monotonically for
the life of the process.

---

## E. README audit — where the docs overclaim

| # | README claim | Reality | Verdict |
|---|---|---|---|
| E1 | Architecture diagram shows the LangGraph loop as the terminal stage (`README.md:14-24`) | Omits the explainability layer, the dashboard broadcaster, and the `/api/.../analyze` endpoint, all of which exist | **Out of date**, understates the system |
| E2 | "Registered Adapters" table lists 3 (`README.md:37-41`) | 4 are registered; `UNSWThreatAdapter` is registered *first* and is the only one used (`main.py:77-80`) | **Wrong** — omits the only adapter that runs |
| E3 | `/health` example shows `"phase": 4` (`README.md:102`) | Code returns `6.1` (`main.py:121`) | Stale |
| E4 | Project structure claims `test_graph.py` has 49 tests, `test_explanation.py` 27 (`README.md:171-172`) | 49 ✓; but `test_explanation.py` has **62** | Undercounts |
| E5 | Config table omits `ENIGMA_GRAPH_CONVERGENCE_PERSISTENCE` | Exists at `config.py:38` and materially controls convergence | Incomplete |
| E6 | "Quick Start: `pip install -e ".[dev]"` then `uvicorn ...`" (`README.md:211-214`) | Omits that `GOOGLE_API_KEY` is mandatory or the graph raises `RuntimeError` at `runner.py:36-39` on every analysis | **Misleading** — a clean checkout appears to work while silently falling back to `hypotheses: []` at `ws_dashboard.py:105-114` |
| E7 | Signal-flow step 6: "Ack is returned with adapter name..." (`README.md:33`) | True for `/ws/raw-signal`; the `/ws/signal` ack omits `adapter` (`ws_signal.py:75-79`) | Minor |
| E8 | `.env.example` lists `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ENIGMA_CORS_ORIGINS` | None exist in `config.py`; the real key is `GOOGLE_API_KEY` | **Wrong file** |
| E9 | Enigma-ML-Layer `README.md` | 10 bytes, no content | ABSENT |
| E10 | Enigma-Frontend `README.md` | Unmodified `create-next-app` boilerplate | ABSENT |

**Nothing in any README claims a metric, accuracy, latency, or throughput
figure.** That is the one thing working in your favour: there is no published
number to walk back. The overclaiming is in the *working title*, not the docs.

---

## F. Frontend/backend contract violations

### F1. Four field-name families that do not exist on the wire
Backend `Situation.summary()` (`situation.py:226-234`) returns exactly:
`situation_id, created_at, last_updated, version, evidence_count,
signal_types, entities`.

Frontend `SituationSummary` (`types/dashboard.ts:6-16`) additionally declares
`lifecycle`, `last_activity`, `max_anomaly`, `sources` — **none are sent.**

Similarly:
- FE `TemporalData` (`types/dashboard.ts:81-91`) expects `event_rate`,
  `mean_anomaly`, `max_anomaly`, `unique_types`, `unique_sources`,
  `is_bursting`, `is_quiet`, `duration_seconds`. Backend sends
  `event_rate_per_minute`, `burst_detected`, `quiet_detected`,
  `active_duration_seconds`, `last_event_age_seconds`,
  `mean_interval_seconds` (`domain/temporal.py:22-31`). **7 of 9 names
  differ.**
- FE `ReasoningData` (`types/dashboard.ts:93-100`) expects `confidence`,
  `anomaly_mean`, `diversity`, `burst_active`. Backend sends
  `confidence_level`, `mean_anomaly_score`, `source_diversity`,
  `burst_detected` (`domain/reasoning.py:30-44`). Only `trend` and
  `evidence_count` match.
- FE `Hypothesis` (`types/dashboard.ts:19-24`) expects `id` and status
  `"confirmed"`. Backend sends `hypothesis_id` and status `"converged"`
  (`domain/hypothesis.py:33-34`, `nodes.py:122-133`).

TypeScript does not catch this because the payload is cast, not validated:
`JSON.parse(raw) as SituationAnalysis` (`useDashboardWS.ts:81`).

### F2. Dashboard panels that display fabricated values
Because `situation.max_anomaly` is always `undefined`:

| UI element | File:line | What it actually shows |
|---|---|---|
| "Avg Anomaly" KPI card | `OverviewDashboard.tsx:220-221,255-256` | `isNaN(undefined)` → `true` → contributes 0 → **always 0%** |
| "Threat Levels" donut, "Avg Risk" centre | `OverviewDashboard.tsx:134-148,276` | Every situation falls to the `low++` branch → **always 100% Low, 0% Critical** |
| "Anomaly Score by situation" bar chart | `OverviewDashboard.tsx:195-204` | `(undefined \|\| 0)` → **all bars 0, all green** |
| Anomaly sparkline | `OverviewDashboard.tsx:210-212` | flat zero |
| Detail-panel "Anomaly" metric | `SituationOverview.tsx:99` | `pct(undefined)` → **"—"** |
| Sidebar "High Risk" filter | `Sidebar.tsx:60` | `undefined > 0.5` → false → **filter always returns empty** |
| Sidebar / feed ordering by recency | `Sidebar.tsx:52-54` | `new Date(undefined)` → NaN → guarded to 0 → **no ordering applied** |
| Confidence-trend x-axis labels | `OverviewDashboard.tsx:175-179` | `situation.last_activity` undefined → **every label "—"** |

The dominant hypothesis lookup at `SituationOverview.tsx:56`
(`h.id === explanation.dominant_hypothesis_id`) also never matches, because
the backend key is `hypothesis_id`. **The "Lead hypothesis" block never
renders.**

> **Paper impact: any screenshot of this dashboard is a screenshot of
> zeros.** Do not use one as a figure until F1 is fixed (GAPS G7, ~3 h).

---

## G. Capability summary table

| Capability | Status | Anchor |
|---|---|---|
| UNSW-NB15 ingestion & replay | IMPLEMENTED | `Streamer.py:20-52` |
| Multi-class threat classification | IMPLEMENTED (weights absent) | `main.py:130-134` |
| Streaming inference with batching | IMPLEMENTED | `main.py:100-204` |
| Signal normalisation / adapters | IMPLEMENTED | `adapters/*.py` |
| Cross-**source** correlation | **ABSENT in practice** — 1 source only | SYSTEM §2 |
| Cross-**domain** correlation (net/auth/video) | PARTIAL — adapters exist, no producers | INVENTORY §5 |
| Learned fusion | **ABSENT** | SYSTEM §2 |
| Temporal burst/quiet detection | IMPLEMENTED but **defective** | EVIDENCE §D1 |
| Deterministic confidence scoring | IMPLEMENTED, **uncalibrated** | SYSTEM §3 |
| Risk scoring | **ABSENT** | SYSTEM §3 |
| LLM hypothesis generation | IMPLEMENTED | `nodes.py:181-216` |
| Iterative belief revision | PARTIAL | `nodes.py:322-399` |
| Belief inertia / anti-premature-convergence | **STUBBED** | EVIDENCE §D2 |
| Explicit UNKNOWN / abstention | IMPLEMENTED | `nodes.py:201-214`, `hypothesis.py:94-110` |
| Structured explanation generation | IMPLEMENTED (rule-based) | `explain/builder.py` |
| Explanation integrity validation | IMPLEMENTED | `explain/builder.py:664-704` |
| Role-based explanation views | IMPLEMENTED, unused on live path | `explanation.py:225-252` |
| SHAP model attribution | PARTIAL — offline, 1 record | `Model.ipynb` cell 65 |
| Explanation consumed downstream | **ABSENT** — display only | SYSTEM §5d |
| Counterfactual generation | **STUBBED as XAI** — hardcoded constants | SYSTEM §5c |
| Real-time latency/throughput measurement | **ABSENT** | EVIDENCE §C1 |
| Backpressure / queue management | **ABSENT** | EVIDENCE §C4 |
| Situation expiry | **ABSENT** (code exists, uncalled) | EVIDENCE §D6 |
| Persistence | **ABSENT** — in-memory only | `situation_store.py:155` |
| Frontend visualisation | PARTIAL — several panels fed by absent fields | EVIDENCE §F2 |
| Automated evaluation harness | **ABSENT** | EVAL_STATUS.md |


---
---

# APPENDIX L1 — Level 1 findings, appended 2026-07-28

Appended per standing rule 5. Nothing above this line has been altered. This
appendix records what changed, what was corrected, and what was newly
discovered while restoring reproducibility.

## L1.1 The dataset was located, and both variants are present

Found at `F:\XAI Project\SAMFW.COM_SM-G990E_INS_G990EXXSGGYG1_fac`, a folder
whose name is unrelated leftover. Renamed to `F:\XAI Project\data`. Contents
were exactly the eight dataset files and nothing else.

Full inventory with a SHA-256 per file is at `results\dataset_manifest.json`,
produced by `Enigma-ML-Layer\dataset_manifest.py`.

| File | Rows | Columns | Header |
|---|---|---|---|
| UNSW-NB15_1.csv | 700001 | 49 | no |
| UNSW-NB15_2.csv | 700001 | 49 | no |
| UNSW-NB15_3.csv | 700001 | 49 | no |
| UNSW-NB15_4.csv | 440044 | 49 | no |
| UNSW_NB15_training-set.csv | 82332 | 45 | yes |
| UNSW_NB15_testing-set.csv | 175341 | 45 | yes |

This supersedes GAPS G2's premise that the data was absent. G2's other
components, the commented-out training cells and the missing model artefacts,
were real and are addressed below.

## L1.2 CORRECTION to section A1: raw row count

Section A1 states the raw record count as 2,540,041, inferred from the last
displayed index in notebook cell 14. The measured count is **2,540,047**.
The inference was wrong because cell 14 rendered a frame after
`drop_duplicates`, so its final index was not the row count.

## L1.3 NEW: the official split filenames are inverted

`UNSW_NB15_testing-set.csv` holds 175341 rows. `UNSW_NB15_training-set.csv`
holds 82332 rows. The published UNSW-NB15 partition is 175341 train against
82332 test, so **the file named "testing-set" is the training partition and
the file named "training-set" is the test partition.**

This is a known defect in the widely mirrored distribution. Level 3 must
assign roles by row count and never by filename. Recorded in the manifest as
`official_pre_split.filename_role_inverted = true`.

## L1.4 NEW: the two variants do not share a schema

The raw four-partition files carry 49 unheadered columns named by
`NUSW-NB15_features.csv`. The official split files carry 45 headed columns
using different names for the same quantities, for example `Spkts` against
`spkts`, `Sintpkt` against `sinpkt`, `smeansz` against `smean`,
`res_bdy_len` against `response_body_len`. The official files also add an
`id` column and lower-case `attack_cat` values differently.

A model trained on one variant cannot consume the other without an explicit
column mapping. Since `Streamer.py` replays the raw variant and Level 3 is
directed to prefer the official partition, **Level 3 must either build that
mapping or accept that the trained model cannot serve the replayed stream.**
This is a new dependency that the build plan does not currently account for.

## L1.5 CONFIRMED: section D1's previously unverified magnitude

Section D1 marked the magnitude of the clock-domain defect UNVERIFIED because
the CSVs were absent. Measured from the raw partitions:

```
Stime minimum  1421927377  =  2015-01-22T11:49:37Z
Stime maximum  1424262068  =  2015-02-18T12:21:08Z
```

The capture spans 27 days in early 2015. The wall-clock comparison at
`domain/situation.py:190` therefore evaluates `utc_now() - last_seen` as
approximately **eleven and a half years**, against a `quiet_window` of five
minutes. `quiet_detected` is true for every situation on every replay, without
exception. D1 is now fully evidenced rather than structurally inferred.

## L1.6 NEW: the backdoors label artefact is variant-specific

Section A2 reports `backdoor` and `backdoors` as separate classes. Measured
distribution shows this artefact exists **only in the raw four-partition
files**, where `backdoors` accounts for 534 rows before deduplication.

The official split files carry a clean ten-class `attack_cat` with no
`backdoors` value. **Adopting the official partition in Level 3 dissolves
GAPS G21 at no cost.**

## L1.7 CORRECTION to EVAL_STATUS section 6: the test suite is fully green

EVAL_STATUS reports 167 of 216 tests passing with `tests/test_graph.py`
failing to collect. That was an environment fault, now resolved.

The system interpreter carries `ormsgpack` 1.12.1, whose compiled extension is
blocked by the machine's Application Control policy, which prevents LangGraph
from importing. A per-repository virtual environment installs `ormsgpack`
1.12.2, which is not blocked.

```
216 tests collected in 0.85s
216 passed in 1.72s
```

**All 216 tests pass with zero collection errors.** The 49 LangGraph tests are
no longer unverified. They still mock the LLM at the LangChain invoke level, so
EVAL_STATUS's substantive criticism stands: no test exercises a real Gemini
call.

## L1.8 Environment, now pinned

Python 3.11.9. Two virtual environments, because the TensorFlow and LangGraph
dependency trees conflict on protobuf.

`Enigma-ML-Layer`: tensorflow 2.20.0, keras 3.15.0, scikit-learn 1.7.2,
imbalanced-learn 0.14.0, keras-tuner 1.4.7, shap 0.48.0, xgboost 3.0.5,
pandas 2.3.3, numpy 2.1.3, scipy 1.15.3, joblib 1.5.2, matplotlib 3.10.7,
seaborn 0.13.2, websockets 15.0.1.

`Enigma-AIAgent`: fastapi 0.128.0, uvicorn 0.40.0, pydantic 2.12.5,
pydantic-settings 2.12.0, websockets 15.0.1, langgraph 1.0.6, langchain-core
1.2.7, langchain-google-genai 4.2.0, pytest 9.0.2, pytest-asyncio 1.3.0,
httpx 0.28.1, ruff 0.15.1.

Each repository has `requirements.txt` with direct pins and
`requirements.lock.txt` with the full transitive freeze. `check_requirements.py`
confirms every third-party import in both repositories is covered by its
`requirements.txt`, and both files resolve cleanly from scratch under a pip
dry run. Coverage reports are at `results\requirements_coverage_ml.json` and
`results\requirements_coverage_aiagent.json`.

**TensorFlow runs CPU only on this machine.** Native Windows GPU support ended
after TensorFlow 2.10. The notebook recorded 10 to 13 seconds per epoch on an
RTX 3050 and 1 h 36 m for the ten-trial random search. Level 3 and Level 5
should budget substantially more, or move to WSL.

## L1.9 The notebook is now executable

`Enigma-ML-Layer\train.py` is a faithful port of `Model.ipynb` with cells 48,
54, 57, 58 and 59 restored, all Kaggle paths removed, and every path exposed
through argparse. It takes `--seed` and writes the seed into its output, per
standing rule 4.

**It deliberately preserves all four leakage paths from section A5.** It exists
so Level 1 has an executable baseline and a parity reference. No number it
produces belongs in the paper. Level 3 replaces it.

Three implementation departures from the notebook, none of which touch
modelling logic:

1. The outlier replacement loop is vectorised. The notebook applies a Python
   lambda per cell across roughly 36 columns and 2.5 million rows. The
   vectorised form is semantically identical and reduces that stage to
   6.5 seconds.
2. `fillna(..., inplace=True)` on a column selection is rewritten as explicit
   assignment. The chained form is removed in pandas 3.
3. `keras.layers.InputLayer(input_shape=...)` is rewritten to `shape=...` and
   `kernel_regularizer=l2` to `kernel_regularizer=l2()`. Both are required by
   Keras 3. The notebook passed the regulariser class rather than an instance.

### Measured parity against the notebook

| Quantity | Notebook | train.py | Match |
|---|---|---|---|
| Raw rows loaded | not printed | 2540047 | n/a |
| Rows after deduplication | 2059417, summed from cell 35 | 2059415 | within 2 rows |
| Highly correlated pairs | 18, cell 32 | 18 | exact |
| Columns dropped by correlation | 9, derived from cell 33 | 9 | exact |
| Rows after SMOTE and undersampling | 165000, cell 35 | 165000 | exact |
| Classes observed | 11, cell 31 | 11 | exact |
| Label mapping | cell 31 | identical, all 11 entries | exact |
| Final feature count | 20, cell 64 | 20 | exact |

The two-row deduplication difference is unexplained and is most likely a
pandas version difference in null handling. It is recorded rather than
resolved.

## L1.10 Two path defects fixed, both configuration only

`Streamer.py` read from a relative `archive\` directory that does not exist, so
it could not run at all. It now defaults to `..\data` and exposes
`--data-dir`, `--uri`, `--burst-size` and `--burst-delay`.

`main.py` loaded its model and pipeline from the current working directory. It
now looks in its own directory first, falls back to `..\artifacts`, and
exposes `--artifacts-dir`, `--port`, `--downstream-uri` and
`--normal-traffic-uri`. Confirmed to load and start against generated
artefacts.

## L1.11 Model artefacts now exist, and are provisional

`train.py` writes `artifacts\unsw_nb15_threat_detection_model.h5`,
`artifacts\unsw_nb15_preprocessing_state.pkl` and `artifacts\class_index.json`,
which are the three files `main.py` needs. The system can therefore be started
end to end for the first time.

**The artefacts currently on disk come from a three-epoch smoke run on a
300000 row sample.** They exist to prove the path works. They are not a
trained model and must not be used for any measurement.

## L1.12 Standing note on repository layout

`F:\XAI Project` is not a git repository. The three components are separate
repositories, and `data`, `results`, `artifacts` and `figures` sit outside all
three. Nothing written to those four directories is version controlled by any
repository.

Level 10 requires a single `reproduce.sh` that regenerates every number and
figure. That script has no repository to live in. **This needs a decision
before Level 10**, and the cheapest resolution is to make the project root a
repository with the three components as submodules.

## L1.13 Level 1 DONE CHECK

```
DONE CHECK 1: train.py --help
exit code: 0

DONE CHECK 2: pytest collection
216 tests collected in 0.85s
216 passed in 1.72s

DONE CHECK 3: dataset manifest
raw_four_partition present : True  rows=2540047
official_pre_split present : True  rows=257673
filename_role_inverted     : True
shared schema              : False

DONE CHECK 4: fresh clone plus pip install
requirements.txt resolves from scratch for both repositories under pip dry run
every third party import in both repositories is covered by requirements.txt
```

DONE CHECK 4 was verified by dependency resolution and static import coverage
rather than by a literal cold clone into an empty directory. That distinction
is recorded deliberately. A true cold-clone test has not been run.

## L1.14 Feature-set parity confirmed

The full-dataset run completed in 469 seconds with one training epoch. Result
at `results\train_parity_full_seed42.json`.

The final twenty features selected by `train.py` are **identical to notebook
cell 64, as a set and in order**:

```
dur, sbytes, dbytes, sloss, Sload, Dload, swin, stcpb, dtcpb, smeansz,
dmeansz, Sjit, Djit, Stime, Dintpkt, ct_srv_src, ct_srv_dst, ct_dst_ltm,
ct_src_ ltm, ct_dst_src_ltm
```

Set difference in both directions is empty. The earlier smoke run on a 300000
row sample selected a different twenty, because sampling shifts the
correlation matrix and therefore which pairs cross the 0.75 threshold. Full
data reproduces the notebook exactly.

Single-epoch accuracy also tracks the notebook. `train.py` reports 0.6673 on
the held-out split after one epoch; notebook cell 48 recorded a first-epoch
`val_accuracy` of 0.6603.

The parity table in L1.9 is therefore complete, with every row either exact or
within two rows out of 2.06 million.

Note for Level 3: `Stime` survives selection here exactly as it did in the
notebook, confirming section B2. A raw capture timestamp with the fourth
highest mutual information score is a temporal shortcut, and it will need to be
dropped or justified explicitly.

---

# APPENDIX W — WSL2 GPU evaluation, appended 2026-07-29

Appended per standing rule 5. This appendix records the outcome of setting up
WSL2 with GPU accelerated TensorFlow, and the measured decision that followed.

## W.1 Environment established

WSL 2.6.3.0 was already present on the host but carried only the
`docker-desktop` utility distribution, which is not usable for development.
Ubuntu 24.04.4 LTS was installed as `enigma-gpu`.

It was installed to `F:\WSL\enigma-gpu` rather than the default location because
`C:` had 7.7 GB free and the environment requires roughly 8 GB. The virtual
environment alone is 7.1 GB, almost all of it the CUDA runtime wheels.

Ubuntu 24.04.4 LTS, Python 3.12.3, kernel 6.6.87.2-microsoft-standard-WSL2,
12 CPUs, 7 GB RAM.

## W.2 GPU passthrough confirmed

```
/dev/dxg present
/usr/lib/wsl/lib populated with libcuda.so, libnvidia-ml.so.1, nvidia-smi

nvidia-smi inside WSL
  NVIDIA GeForce RTX 3050 Laptop GPU
  driver 566.07, CUDA 12.7
  4096 MiB total, 3964 MiB free
  compute capability 8.6

TensorFlow 2.20.0, built with CUDA True
  list_physical_devices('GPU') -> [PhysicalDevice('/physical_device:GPU:0')]
  Created device /device:GPU:0 with 1767 MB memory
```

**This is the 4 GB variant.** TensorFlow receives 1767 MB of the 4096 MiB
because WDDM reserves the remainder. That 1767 MB figure matches the notebook's
recorded 1763 MB, confirming the original work ran on the same class of device.

The 4 GB against 6 GB question turns out not to matter. The Level 3 model has
roughly 2300 parameters and a five member Level 4 deep ensemble is five copies
of it. VRAM does not constrain anything in this project.

## W.3 CORRECTION to Appendix L1.8

L1.8 states that Levels 3 and 5 should budget more time on CPU, or move to WSL
for GPU acceleration. **The second half of that recommendation was wrong** and
is withdrawn.

The GPU is slower than the CPU for this project's TensorFlow workload, at every
batch size that preserves the training dynamics.

Identical workload throughout: 132000 rows, 20 features, 11 classes, 2347
parameter dense network, seed 42. Produced by `Enigma-ML-Layer\bench_device.py`,
raw output under `results\bench\`.

| Batch | GPU s/epoch | CPU s/epoch | GPU speedup |
|---|---|---|---|
| 32 | 21.92 | 10.34 | 0.47x |
| 128 | 5.94 | 3.68 | 0.62x |
| 512 | 1.56 | 1.10 | 0.70x |
| 2048 | 0.52 | 0.56 | 1.06x |

The model is far too small to saturate the device. Per step kernel launch and
synchronisation overhead dominates across 4125 steps per epoch. The crossover
only arrives at batch 2048, where the margin is within noise and the batch size
would itself change the training dynamics.

Ten epoch run at batch 32, steady state seconds per epoch:

| Environment | Steady epoch |
|---|---|
| Windows CPU | 8.96 |
| WSL CPU | 10.34 to 12.26 |
| WSL GPU | 21.90 |

A corollary worth stating in the paper: the notebook's recorded 1 h 36 m for the
ten trial random search was GPU bound by launch overhead, not by compute. The
same search would have completed faster on CPU.

## W.4 Where the GPU does help

XGBoost, 132000 rows by 20 features, 200 trees, depth 6, 11 classes:

| Device | Fit seconds |
|---|---|
| cuda | 17.69 |
| cpu | 32.99 |

**GPU speedup 1.86x.** `xgb.build_info()` reports `USE_CUDA: True`. Histogram
construction parallelises well where a 2300 parameter dense network does not.

This is the only place the GPU should be used, and Level 5 is the only level
where it applies. Tree ensembles are not part of the TensorFlow numeric parity
chain, so using the GPU there costs no reproducibility.

## W.5 Filesystem boundary measured

559.2 MB across the four raw partitions, caches dropped between runs.

| Location | Raw read | Throughput | pandas read |
|---|---|---|---|
| `/mnt/f` drvfs | 6.28 s | 89.1 MB/s | 33.34 s |
| `/opt/enigma/data` ext4 | 1.33 s | 421.3 MB/s | 33.20 s |

The boundary costs 4.7x on raw throughput and 0.4 percent end to end. CSV
parsing dominates completely. **Copying the dataset into the WSL filesystem is
unnecessary.** It was copied anyway, 605 MB at `/opt/enigma/data`, since the
work was already done.

Caveat: dropping caches inside WSL does not drop the Windows side cache for
drvfs, so the `/mnt/f` figure is if anything flattering to drvfs.

## W.6 Level 1 parity across four environments

The deterministic pipeline is bit identical in all four. Rows after
deduplication 2059415, 18 correlated pairs, 9 columns dropped, 165000 rows after
resampling, the same 20 features in the same order, the same label mapping, the
same mutual information drop list.

Training numerics are not identical.

| Run | Accuracy | Loss | Total s |
|---|---|---|---|
| Windows CPU | 0.667333 | 1.075912 | 469 |
| WSL CPU | 0.666273 | 1.065632 | 262 |
| WSL GPU, TF32 default | 0.661788 | 1.069452 | 286 |
| WSL GPU, TF32 disabled | 0.666273 | 1.067247 | 438 |

Two separable effects.

**TF32 accounts for the entire GPU discrepancy.** Ampere enables TF32 for matmul
by default, truncating the mantissa. Setting `NVIDIA_TF32_OVERRIDE=0`,
`TF_DETERMINISTIC_OPS=1` and `TF_CUDNN_DETERMINISTIC=1` reproduces the WSL CPU
accuracy to six decimal places, 0.666273 against 0.666273. The cost is that the
epoch goes from 36 seconds to 176 seconds, roughly ten times slower than simply
using the CPU. Loss still differs in the third decimal, so this is agreement on
accuracy, not bit identity.

**Operating system accounts for the rest.** WSL CPU against Windows CPU differs
by 0.00106 in accuracy with no GPU involved, from thread count and BLAS
differences changing float accumulation order. This is irreducible.

The task specification for this work stated that environment changes must not
change results. **That requirement cannot be met for the training step and
should be dropped.** It is met in full for the deterministic pipeline, which is
where it matters, since feature selection is what the paper describes as
methodology. The 0.00106 cross platform delta belongs in threats to validity as
a measured reproducibility bound, not as a defect.

## W.7 Canonical environment

**WSL CPU is canonical for every number that reaches the paper.**

| Environment | Role |
|---|---|
| WSL CPU | canonical, all TensorFlow training and all paper numbers |
| WSL GPU | Level 5 XGBoost baselines only |
| Windows CPU | cross platform verification, and the reasoning layer |

WSL CPU is the fastest end to end at 262 seconds against 469, a 1.79x win over
Windows. That comes almost entirely from `mutual_info_regression`, roughly 156
seconds under WSL against roughly 380 under Windows. **Training was never the
bottleneck in this pipeline.** Feature selection is.

`CUDA_VISIBLE_DEVICES=-1` must be set on the canonical path. Without it
TensorFlow claims the GPU, which is slower and changes the numbers.

## W.8 Files added

```
Enigma-ML-Layer\requirements-gpu.txt            differs from requirements.txt in one line
Enigma-ML-Layer\requirements.wsl-gpu.lock.txt   76 package transitive freeze
Enigma-ML-Layer\bench_device.py                 GPU against CPU training benchmark
Enigma-ML-Layer\bench_io.py                     filesystem read benchmark
scripts\wsl_diagnose.sh                         install and TLS diagnostics
scripts\wsl_gpu_check.sh                        TensorFlow GPU verification
scripts\wsl_install_stack.sh                    pinned stack plus XGBoost CUDA check
scripts\wsl_bench.sh                            ten epoch GPU against CPU
scripts\wsl_bench_sweep.sh                      batch size sweep
scripts\wsl_bench_xgb.sh                        XGBoost device benchmark
scripts\wsl_io_bench.sh                         drvfs against ext4
scripts\wsl_parity.sh                           parity on GPU
scripts\wsl_parity_cpu.sh                       parity on CPU, canonical
scripts\wsl_parity_tf32off.sh                   parity on GPU with TF32 disabled
results\bench\                                  all raw benchmark output as JSON
```

`requirements-gpu.txt` differs from `requirements.txt` in exactly one line,
`tensorflow[and-cuda]==2.20.0` against `tensorflow==2.20.0`. Every other pin is
identical by design, so the CUDA runtime is the only variable between
environments.

## W.9 Operational notes

Scripts must be invoked through a carriage return strip. They live on NTFS and
carry CRLF, which bash rejects:

```
wsl -d enigma-gpu -u root -- bash -c "tr -d '\r' < '/mnt/f/XAI Project/scripts/NAME.sh' > /tmp/NAME.sh && bash /tmp/NAME.sh"
```

Passing shell strings inline through PowerShell into `wsl bash -lc` mangles
nested quotes and cost one false failure during this work. Use script files.

Two transient SSL failures occurred during the CUDA wheel download, reporting
`CA signature digest algorithm too weak`. They did not recur, TLS to
`files.pythonhosted.org` verifies cleanly, and all 13 nvidia packages installed.
If they return, the cause is TLS interception presenting a weak signed
certificate that Ubuntu's OpenSSL 3.0.13 rejects at its default security level
while Windows accepts it.

Disk cost: 7.1 GB for the virtual environment, 605 MB for the copied dataset,
plus roughly 2 GB for the distribution itself. All on `F:`, which has ample
space. `C:` was left untouched and still has 7.7 GB free.

---

# APPENDIX L2 — Level 2 defect remediation, appended 2026-08-03

Appended per standing rule 5. Nothing above this line has been altered.

Canonical environment for everything below: WSL CPU, `CUDA_VISIBLE_DEVICES=-1`,
per appendix W.7.

## L2.1 D1, mixed clock domains, FIXED and parameterised

`foundation/clock.py` now defines a Clock protocol with two implementations and
three modes. `WallClock` reads host time. `ReplayClock` advances monotonically to
the newest observed event timestamp.

Two design decisions worth recording.

**The mode selects both the clock and the reference timestamp.** Merely swapping
the clock would make `conflated` and `wall` identical, because the original
defect was not the clock alone but comparing host time against an event
timestamp. So `conflated` compares host now against `last_seen_at`, `wall`
compares host now against `last_updated`, and `separated` compares event now
against `last_seen_at`. Only the first mixes domains.

**The replay clock is owned by the store, not by the situation.** A per-situation
replay clock reports that situation's own newest event as now, so staleness is
identically zero and nothing can ever be reported quiet. Event time has to
advance globally as the stream progresses. `SituationStore` builds one clock and
injects it into every situation it creates, verified by
`test_store_shares_one_clock_across_situations`.

`ReasoningEngine` now carries a clock mode and raises `ValueError` when asked to
evaluate a situation built in a different one. The engine holds no clock of its
own; every time-dependent read is delegated to the situation. The check exists
because two components silently disagreeing about the time domain is exactly
what D1 was.

### Measured effect

400 synthesised signals carrying genuine 2015 era event timestamps, replayed
through 14 situations, seed 42. Full output at `results\level2\verify.json`.

| Clock mode | Trend distribution | Quiet | Degenerate |
|---|---|---|---|
| separated | deescalating 10, stable 4 | 10 true, 4 false | no |
| conflated | deescalating 14 | 14 true | **yes** |
| wall | stable 11, escalating 2, deescalating 1 | 0 true, 14 false | no |

The conflated column is the defect: every situation quiet, every trend
deescalating, one distinct label across the whole run. Separated recovers a
non-degenerate distribution. The defect remains reachable so Level 8 can measure
it rather than assert it.

## L2.2 NEW FINDING: the official partition carries no event time

Level 2 directed that `Streamer.py` replay the official test partition so the
schema matches training. It now does, defaulting to `UNSW_NB15_training-set.csv`,
the 82332 row file, with the inversion documented in the argument help.

**That partition has no `Stime` or `Ltime` column.** Its 45 columns carry only
`dur` and `rate`. Verified against `results\dataset_manifest.json`.

Three consequences.

1. `main.py` falls back to `time.time()` for the signal timestamp, so replayed
   signals carry ingest time, not event time.
2. Under `separated`, the replay clock then observes near-present timestamps and
   behaves like a wall clock. The conflation dissolves, but by accident of the
   data rather than by design.
3. **Level 8 cannot run its clock study on the official partition.** It needs
   genuine event timestamps. Either use the raw four-partition files, which do
   carry `Stime` spanning 2015-01-22 to 2015-02-18, or synthesise an event
   timeline by accumulating `dur`. The first is honest and is what the Level 2
   verification harness does in synthetic form.

This is a real conflict between the Level 2 instruction and the Level 8 design.
It is recorded rather than resolved, because resolving it is a Level 8 decision.

## L2.3 D2, belief inertia, FIXED

The node now computes a genuine per-iteration delta. `evaluate_hypotheses`
records `confidence_previous` and `confidence_before_inertia` on each
hypothesis; `apply_belief_inertia` compares them, clamps the change to
`max_confidence_delta`, and records both the pre-clamp and post-clamp values plus
an `inertia_clamped` flag.

The cap defaults to 0.15. That is the largest adjustment the evaluation node can
apply in one pass, being the 0.1 anomaly boost plus the 0.05 trend boost. A
smaller cap would suppress a legitimate single-pass update; a larger one could
never bind.

Demonstrated at a cap of 0.10:

```
confidence_previous     : 0.3
raw_proposed_confidence : 0.55
raw_delta               : 0.25
applied_confidence      : 0.4
applied_delta           : 0.1
inertia_clamped         : True
```

One design correction made during implementation. The node initially read the
cap from reasoning state, which let a state value silently override an
explicitly constructed node. The factory argument is now authoritative and the
state field is carried for run manifests only.

## L2.4 D3, sanity gate penalty, FIXED

The vague-hypothesis branch rebound the loop variable to a copy and never wrote
the copy back, so the penalty never took effect. The gate now writes into the
list by index.

```
before : {'vague': 0.4, 'benign': 0.4}
after  : {'vague': 0.3, 'benign': 0.4}
penalty applied to vague : 0.1
benign untouched         : True
```

The gate is also now non-mutating with respect to its input, verified by
`test_gate_does_not_mutate_its_input`.

## L2.5 D4, convergence scorer purity, FIXED

`update_convergence` deep copies the hypothesis list before touching anything
and returns new objects.

```
input_unchanged             : True
returned_objects_are_new    : True
input_dominant_iterations   : [0, 0]
returned_dominant_iterations: [1, 0]
```

The last two lines are the point: the caller's `dominant_iterations` stay at
zero while the returned copy advances. Under the old implementation repeated
scoring of the same state produced different answers, which would have made the
Level 9 ablation non-deterministic.

## L2.6 D5, anomaly score semantics, FIXED

`Enigma-ML-Layer/scoring.py` derives three separate scores from one probability
vector:

```
anomaly_score              = 1 - P(normal)
predicted_class_confidence = max(softmax)
predictive_entropy         = Shannon entropy / log(class count)
```

`Signal` carries all three; `predicted_class_confidence` and
`predictive_entropy` are optional so pre-Level-2 payloads still validate.
`ReasoningEngine` reads the corrected `anomaly_score` for its 0.30-weighted term.

The semantic check that the old field could not express:

```
confident normal : anomaly_score 0.02, predicted_class_confidence 0.98
confident attack : anomaly_score 0.97, predicted_class_confidence 0.97
```

The two numbers now diverge by 0.96 for the normal case. Under the old
implementation they were identical by construction, which is why a confidently
benign flow scored 0.99 on anomaly.

`resolve_normal_class_index` locates the normal class by name rather than by a
hardcoded index, and falls back to `1 - max(softmax)` when the label set has no
normal class. That fallback matters for Level 3, which holds out a class.

## L2.7 D6, dead frontend fields, FIXED

`Situation.summary` now emits `lifecycle`, `last_activity`, `sources`,
`max_anomaly` and `mean_anomaly`. Lifecycle is only populated when the caller
supplies a dormancy window and TTL, so the method never guesses a window.

The frontend type declarations were corrected to the real wire format rather
than the backend being bent to match invented names. `TemporalData` and
`ReasoningData` now use the field names the backend actually sends, and
`Hypothesis` uses `hypothesis_id` and the `converged` status. `npx tsc --noEmit`
exits 0.

The eight panels listed in section F2 now receive real values. `max_anomaly`
uses the corrected anomaly score.

## L2.8 Ablation wiring

Six switches, all environment-backed. Disabling a mechanism removes it from the
reasoning path rather than weakening it. For the sanity gate and belief inertia
that is literal: the node is not added to the compiled graph.

```
=== defaults ===
ENIGMA_CLOCK_MODE                 = separated
ENIGMA_UNKNOWN_HYPOTHESIS_ENABLED = True
ENIGMA_SANITY_GATE_ENABLED        = True
ENIGMA_ASYMMETRIC_DECAY_ENABLED   = True
ENIGMA_PERSISTENCE_REQUIRED       = True
ENIGMA_MAX_CONFIDENCE_DELTA       = 0.15
graph nodes = ['apply_belief_inertia', 'assemble_context', 'evaluate_hypotheses',
               'generate_hypotheses', 'hypothesis_sanity_gate', 'update_convergence']

=== all switches disabled ===
ENIGMA_CLOCK_MODE                 = conflated
ENIGMA_UNKNOWN_HYPOTHESIS_ENABLED = False
ENIGMA_SANITY_GATE_ENABLED        = False
ENIGMA_ASYMMETRIC_DECAY_ENABLED   = False
ENIGMA_PERSISTENCE_REQUIRED       = False
ENIGMA_MAX_CONFIDENCE_DELTA       = inf
graph nodes = ['assemble_context', 'evaluate_hypotheses', 'generate_hypotheses',
               'update_convergence']
```

All sixteen corners of the 2^4 factorial compile, verified by
`test_all_sixteen_configurations_build`.

## L2.9 Test suite

```
ruff check enigma_reason tests level2_verify.py   All checks passed!
pytest Enigma-AIAgent                             255 passed
pytest Enigma-ML-Layer                            16 passed
```

271 tests, up from 216 at the end of Level 1. 55 added: 32 in
`tests/test_level2_defects.py`, 16 in `Enigma-ML-Layer/tests/test_scoring.py`,
and 7 added to existing files.

`pytest` was added to the ML layer requirements at 9.0.2, matching the reasoning
layer pin.

### Existing tests changed, and why

Six tests encoded the D1 conflation. They created a situation, advanced the host
clock, and asserted quiet. That assertion only holds when host time is compared
against event time, which is the defect. Each was rewritten to advance event time
instead, which is how a situation legitimately becomes quiet under `separated`.

- `test_quiet_after_window_elapses`
- `test_quiet_window_configurable`
- `test_snapshot_captures_quiet`
- `test_summary_counts_quiet`
- `test_quiet_triggers_deescalating`
- `test_summary_counts_trends`

Two new tests pin both sides of the behaviour so the rewrite cannot silently
reintroduce the defect: `test_wall_clock_advance_does_not_make_separated_quiet`
and `test_conflated_mode_reproduces_the_defect`.

One test asserted the old belief inertia semantics.
`test_velocity_is_dampened` capped `belief_velocity`, which was the only field
the node wrote and which never influenced confidence. It now asserts that
velocity tracks the applied delta and that confidence is clamped, which is the
mechanism the name always claimed.

The three test files that patched `enigma_reason.domain.situation.utc_now` now
patch `enigma_reason.foundation.clock.utc_now`. This restores the documented
intent: `test_temporal.py`'s own module docstring already claimed it patched the
foundation module.

## L2.10 Files added

```
Enigma-AIAgent/level2_verify.py                    DONE CHECK evidence harness
Enigma-AIAgent/tests/test_level2_defects.py        32 regression tests
Enigma-ML-Layer/scoring.py                         the three-score split
Enigma-ML-Layer/tests/test_scoring.py              16 unit tests
Enigma-ML-Layer/pyproject.toml                     pytest and ruff configuration
scripts/wsl_setup_agent.sh                         reasoning layer venv in WSL
scripts/wsl_test.sh                                test runner
scripts/wsl_level2_check.sh                        lint and test both repos
scripts/wsl_level2_verify.sh                       DONE CHECK runner
scripts/wsl_ablation_dump.sh                       config and graph topology dump
results/level2/verify.json                         machine readable evidence
```

## L2.11 Carried forward

- The official partition has no event time. Level 8 must resolve this, see L2.2.
- `store.expire_stale()` still has no caller, section D6 of the original
  evidence. Situations still accumulate without bound. Not in Level 2 scope.
- The LLM is still mocked in every test. Level 9 is the first level that
  exercises a real model.
- `predictive_entropy` is emitted and stored but nothing consumes it yet. It is
  reserved for Level 4 selective prediction.

---

# APPENDIX L3 — Leakage-free retraining, appended 2026-08-04

Appended per standing rule 5. Nothing above this line has been altered.

Canonical environment: WSL CPU, `CUDA_VISIBLE_DEVICES=-1`.
Dataset: the official pre-split partition, roles assigned by row count.

`train.py` and everything it produced are superseded. They were a faithful port
of the notebook and carried all four leakage paths deliberately. `train_level3.py`
replaces them.

## L3.1 CORRECTION to the Level 3 brief: no label artefact exists

The brief states that the official partition uses "Backdoors" not "Backdoor" and
asks for a merge if both appear. Measured, both files carry exactly ten classes
with identical label sets and the spelling is **`Backdoor`**:

```
Analysis  Backdoor  DoS  Exploits  Fuzzers  Generic  Normal  Reconnaissance  Shellcode  Worms
```

`label_sets_identical: true`, `label_artefact_present: false`. Task 4 dissolves.
The `backdoors` artefact recorded in section A2 exists only in the raw
four-partition files, as appendix L1.6 already established.

## L3.2 NEW: the label column is a direct target leak

`label` is perfectly determined by `attack_cat`: Normal is 0 and every attack
class is 1, with zero variance within each class. Left in the feature matrix it
hands the model the entire attack-versus-benign decision.

The notebook dropped it only by accident. Its mutual information filter scored
`Label` at 0.003 and cut it, but that score came from `mutual_info_regression`
applied to a nominal target, which is not a meaningful quantity. Had the score
landed differently the leak would have shipped.

`level3_pipeline.DROPPED_COLUMNS` now removes `id` and `label` explicitly, by
name, with the reason recorded in the split manifest.

## L3.3 Leakage audit

`scripts/audit_leakage.py` is both a static and a structural verifier. It parses
the training modules and reports every fit site, then constructs the pipeline and
checks the resampler is terminal.

```
train_level3.py          clean
    fit site: label_encoder.fit(sorted) line 261
    fit site: pipeline.fit_resample(train_frame) line 280
    fit site: model.fit(x_train_resampled) line 294
level3_pipeline.py       clean
runtime structural audit: clean, resampler is terminal
total violations: 0

audit_leakage.py exit code: 0
gate result: PASS
```

Three fit sites, all on training data. The structural check matters most: SMOTE
is the terminal step of an imblearn Pipeline, which is why that pipeline exposes
no `transform` method at all. Validation and test data physically cannot receive
synthetic rows, because the only route through the fitted transforms is
`pipeline[:-1].transform`, which excludes the sampler by construction.

## L3.4 Three-way split

Roles by row count, never by filename.

```
pool  UNSW_NB15_testing-set.csv   175341 rows
test  UNSW_NB15_training-set.csv   82332 rows

class               train      val     test
Analysis             1600      400      677
Backdoor             1397      349      583
DoS                  9811     2453     4089
Exploits            26714     6679    11132
Fuzzers             14547     3637     6062
Generic             32000     8000    18871
Normal              44800    11200    37000
Reconnaissance       8393     2098     3496
Shellcode             906      227      378
Worms                 104       26       44
TOTAL              140272    35069    82332
```

The distribution shift the official partition preserves is visible directly:
Normal is 31.9 per cent of the training fold and 44.9 per cent of the test
partition. This is why validation accuracy overstates test accuracy throughout,
and it is the property that makes the benchmark meaningful.

## L3.5 Feature set, and why it changed

25 features selected by mutual information from 39 numeric candidates plus
one-hot encoded `proto`, `service` and `state`:

```
dur, dpkts, sbytes, dbytes, rate, sttl, dttl, sload, dload, sinpkt, dinpkt,
sjit, tcprtt, synack, smean, dmean, ct_srv_src, ct_state_ttl, ct_dst_ltm,
ct_src_dport_ltm, ct_dst_sport_ltm, ct_dst_src_ltm, ct_src_ltm, ct_srv_dst,
service_dns
```

Against the notebook's 20, the differences are structural rather than a matter
of taste:

- **`Stime` is gone and cannot return.** The official partition has no `Stime` or
  `Ltime` column. Appendix B2 recorded `Stime` as the fourth highest scoring
  feature in the old pipeline and flagged it as a temporal shortcut. The
  partition change removes it by construction.
- **`stcpb` and `dtcpb` are gone.** TCP base sequence numbers are effectively
  random identifiers. They scored highly in the old pipeline against a nominal
  target treated as continuous.
- **Column names differ throughout.** `Spkts` against `spkts`, `Sintpkt` against
  `sinpkt`, `smeansz` against `smean`, `res_bdy_len` against `response_body_len`.
  The two variants are not interchangeable, as appendix L1.4 established.
- **`service_dns` is new.** The old pipeline dropped `proto`, `service` and
  `state` before selection. They are now one-hot encoded with rare categories
  collapsed and unseen categories tolerated, which is required because the test
  partition carries `state` values the training pool does not.

Top scores: `sbytes` 1.145, `smean` 0.928, `sload` 0.901, `dbytes` 0.632,
`dmean` 0.548, `rate` 0.547, `dur` 0.533.

One deliberate departure from the notebook: outliers are winsorised to the
training fold's interquartile bounds rather than replaced with the column median.
Median replacement maps an extreme observation onto a typical one, which destroys
exactly the signal an intrusion detector depends on.

## L3.6 SMOTE degree is a hyperparameter, chosen on validation

The first run reached 65.7 per cent accuracy with a 42.6 per cent false positive
rate on benign traffic. Fully balancing the training fold to the majority count
trains under a uniform class prior while the test partition is 45 per cent
Normal, and that prior shift inflates minority predictions.

Three strategies were swept on the validation split only, with the criterion
fixed in advance as validation macro F1:

```
strategy     val_acc  val_macroF1   val_FPR  train_rows
full          0.7582       0.5304    0.1989      448000
moderate      0.7767       0.5641    0.1934      286000
minimal       0.8117       0.5195    0.1096      141262
selected: moderate
```

**The pre-registered criterion selects `moderate`, and that is what the headline
results use.** It is worth stating plainly that `minimal` had higher validation
accuracy and roughly half the false positive rate. Had the criterion been
operational rather than balanced, the choice would have gone the other way. A
declared sensitivity run over `minimal` is recorded in L3.11.

## L3.7 Results, five seeds, both configurations

```
config     distribution  accuracy            macro F1
closedset  validation    0.7775 +/- 0.0027   0.5611 +/- 0.0063
closedset  natural       0.6843 +/- 0.0036   0.4476 +/- 0.0057
closedset  balanced      0.5282 +/- 0.0198   0.4896 +/- 0.0172
openset    validation    0.7781 +/- 0.0017   0.5982 +/- 0.0032
openset    natural       0.6860 +/- 0.0022   0.4735 +/- 0.0089
openset    balanced      0.5612 +/- 0.0076   0.5329 +/- 0.0117
```

Seed 42, natural distribution:

```
                 closedset   openset
accuracy            0.6846    0.6899
macro F1            0.4459    0.4882
weighted F1         0.7267    0.7309
FPR normal          0.4186    0.4206
```

Seed variance is very low, 0.0036 on closed-set accuracy across five seeds. The
result is a stable property of the configuration rather than noise.

**Accuracy sits below the 77 to 85 per cent band the brief describes as the
honest ceiling.** The cause is identifiable rather than mysterious. Per class,
seed 42 closed set:

```
Analysis         P=0.012 R=0.034 F1=0.018 n=677
Backdoor         P=0.155 R=0.038 F1=0.061 n=583
DoS              P=0.333 R=0.744 F1=0.460 n=4089
Exploits         P=0.752 R=0.594 F1=0.664 n=11132
Fuzzers          P=0.239 R=0.650 F1=0.350 n=6062
Generic          P=1.000 R=0.952 F1=0.976 n=18871
Normal           P=0.997 R=0.581 F1=0.735 n=37000
Reconnaissance   P=0.714 R=0.854 F1=0.778 n=3496
Shellcode        P=0.115 R=0.661 F1=0.196 n=378
Worms            P=0.368 R=0.159 F1=0.222 n=44
```

Normal carries precision 0.997 and recall 0.581. The sensor almost never labels
an attack as benign, but it flags 41.9 per cent of benign traffic as an attack.
Normal is 45 per cent of the test partition, so that recall alone accounts for
roughly nineteen accuracy points. The confusion matrix localises it further:
**Normal is misread as Fuzzers 32 per cent of the time**, which is the single
largest off-diagonal cell in the matrix.

Analysis at F1 0.018 and Backdoor at 0.061 are near-unclassifiable, exactly as
the brief predicted, and they are what hold macro F1 near 0.45.

Leakage trigger: **no run exceeded the 0.85 ceiling**. The highest natural
distribution accuracy across all ten runs was 0.689882.

## L3.8 Open set, the unknown attack condition

`Worms` is held out entirely from training and validation, leaving 104 training
rows and 26 validation rows removed and 44 rows present only at test time.

**The 44 row test set is thin.** Every open-set statistic below is a small sample
estimate and should be reported with that caveat. `Shellcode` at 1133 pool and
378 test rows would give roughly nine times the statistical power and remains a
genuinely distinct attack class; it is the better choice if Level 4 needs tighter
intervals. `Backdoor` is a poor alternative despite its size, because it is
already heavily confused with Exploits and DoS in the closed-set matrix and would
therefore be a weak unknown signal.

Seed 42 behaviour on the held-out class:

```
predicted label distribution for held-out Worms
  Exploits    31  (70.5%)
  DoS          7  (15.9%)
  Fuzzers      4  ( 9.1%)
  Shellcode    2  ( 4.5%)

confidence on holdout : mean 0.5567  median 0.5472  min 0.2835  max 0.7728
confidence on known   : mean 0.8273  median 0.9795
gap known minus holdout : 0.2705
```

Two findings that matter for Level 4.

**The model never mistakes an unknown attack for benign traffic.** All 44 Worms
are assigned to some attack class. The sensor recognises that something is wrong
even when it cannot name it.

**Confidence separates the two populations usefully.** Maximum confidence on the
held-out class is 0.7728 while median confidence on known classes is 0.9795. A
rejection threshold anywhere in that interval would reject essentially every
unknown-attack record while retaining the majority of known-class predictions.
This is the separation the Level 4 selective prediction experiment depends on,
and it exists.

## L3.9 Serving path

`main.py` now loads `model_{config}_seed{N}.keras` and
`pipeline_{config}_seed{N}.pkl` and transforms through
`fitted_pipeline[:-1].transform`, so the serving path uses the identical fitted
transforms as training and cannot invoke the resampler. The Level 1 artefacts are
deliberately unsupported: they expect the raw 49 column schema.

### NEW: the official partition carries no entity identifier

It has no `srcip`, `dstip`, `sport` or `dsport` column. Without an entity every
signal would correlate into a single situation, which would make the reasoning
layer meaningless rather than merely limited.

`resolve_entity_device` derives a synthetic device from the flow `id` across a
pool of sixteen, and the identifier is labelled `synthetic-device-NN` on the wire
so nothing downstream can mistake it for a real host. This is the third capability
the official partition lacks, after event timestamps in L2.2 and the class label
artefact in L3.1. **Level 7's scenario generator must supply genuine entities**;
the build plan already requires this.

### End to end smoke test

Part A, scoring 100 real test records through the checkpointed model and
pipeline:

```
records_scored: 100
predicted_normal_count: 26
predicted_attack_count: 74
anomaly_on_predicted_normal: mean 7.30e-05, max 0.001384
anomaly_on_predicted_attack: mean 0.936786, min 0.678815
normal_below_ceiling: True
attack_mean_above_floor: True
attack_min_above_floor: False
separation_normal_to_attack: 0.936713
all_scores_in_unit_interval: True
anomaly_differs_from_class_confidence: True
```

`attack_min_above_floor` is False and that is correct behaviour, not a defect.
The assertion was initially written as "every attack record scores above 0.9",
which is wrong: a record where the model splits probability between normal and an
attack class legitimately scores 0.68. The check was rewritten to assert the mean
and to report the minimum as information. The property that matters, that the two
populations separate by 0.937 on a unit scale, holds.

Part B, the full websocket path with all three services running:

```
started: ['reasoning layer', 'sensor layer', 'replayer']
health_reached: True
situation_count: 16
total_evidence: 92
signal_types_seen: ['analysis', 'dos', 'exploit', 'fuzzers', 'shellcode']
entities_seen: device:synthetic-device-00 through device:synthetic-device-07
max_anomaly_range: min 0.86539, max 0.997091
total_adapted: 92
total_rejected: 0
```

92 signals adapted, none rejected, grouped into 16 situations across the
synthetic entity pool. The remaining records of the 100 replayed were classified
Normal and routed to the benign sink rather than downstream, which is the
intended split.

## L3.10 Figures

Rendered as PDF with PNG previews, and inspected rather than assumed correct.

Colour follows the project data visualisation method. The two training series use
categorical slots one and two, validated together before any plotting code was
written: worst adjacent CVD separation 24.7 and normal vision separation 33.6,
both clear of the gates, contrast above 3:1. The confusion matrices use the
single hue sequential blue ramp, light to dark, because the encoded quantity is
magnitude. No rainbow anywhere.

Loss and accuracy are drawn in separate panels rather than on twinned vertical
axes, which would invite the reader to compare two unrelated scales by their
crossing point.

```
figures/training_curves_seed42.pdf
figures/confusion_matrix_closedset_seed42.pdf
figures/confusion_matrix_openset_seed42.pdf
figures/preview/*.png
```

Note for anyone reading the training curves: validation loss sits below training
loss and validation accuracy above training accuracy. That is the usual dropout
and batch normalisation artefact of metrics computed during training with
regularisation active, not a leak.

## L3.11 Declared sensitivity analysis

A second five-seed grid over both configurations is running with the `minimal`
SMOTE strategy, writing to `results/sensitivity_minimal/`. It is declared here
rather than substituted for the headline result, because re-picking a
hyperparameter after seeing test metrics is precisely the practice this level
exists to eliminate. Both will be reported.

## L3.12 Outputs

```
scripts/audit_leakage.py
scripts/strip_bom.sh
results/classifier/split_manifest.json
results/classifier/leakage_audit.json
results/classifier/smote_strategy_selection.json
results/classifier/metrics_{closedset,openset}_seed{42,123,456,789,1024}.json
results/classifier/confusion_{closedset,openset}_seed{...}.npy
results/classifier/openset_holdout_analysis_seed{...}.json
results/classifier/summary.csv
results/classifier/summary_statistics.json
results/classifier/smoke_test.json
artifacts/model_{config}_seed{N}.keras          10 files
artifacts/pipeline_{config}_seed{N}.pkl         10 files
artifacts/class_index_{closedset,openset}.json
artifacts/hyperparameters.json
figures/training_curves_seed42.pdf
figures/confusion_matrix_{closedset,openset}_seed42.pdf
```

`pytest` was added to the ML layer requirements at 9.0.2. Sixteen scoring tests
and the 255 reasoning tests remain green.

## L3.13 Carried forward

- Accuracy sits below the brief's stated honest band, traced to Normal recall of
  0.581 driven by Normal being misread as Fuzzers. The sensitivity run in L3.11
  will show whether the SMOTE degree explains it.
- The 44 row Worms test set limits open-set statistical power. Level 4 should
  consider Shellcode.
- The official partition lacks event timestamps, entity identifiers and the raw
  variant's label artefact. Levels 7 and 8 depend on the first two.
- A UTF-8 BOM written by PowerShell broke `ast.parse` in the audit script.
  `scripts/strip_bom.sh` removed it from seven files and the audit now reads with
  `utf-8-sig`. Worth knowing before any future static analysis is added.

## L3.14 Sensitivity result: validation selection picked the worse configuration

The declared `minimal` grid completed. Five seeds, both configurations, written
to `results/sensitivity_minimal/`.

```
config     distribution  moderate (pre-registered)      minimal (sensitivity)
closedset  validation    acc 0.7775 +/- 0.0027  F1 0.5611   acc 0.8105 +/- 0.0021  F1 0.5220
closedset  natural       acc 0.6843 +/- 0.0036  F1 0.4476   acc 0.7517 +/- 0.0055  F1 0.4413
openset    validation    acc 0.7781 +/- 0.0017  F1 0.5982   acc 0.8105 +/- 0.0021  F1 0.5343
openset    natural       acc 0.6860 +/- 0.0022  F1 0.4735   acc 0.7539 +/- 0.0067  F1 0.4428

false positive rate, natural distribution, mean of five seeds
  closedset   moderate 0.4194   minimal 0.2726   improvement 0.1468
  openset     moderate 0.4190   minimal 0.2700   improvement 0.1490
```

The finding is not that one strategy is better. It is that **the selection
signal did not transfer across the distribution shift.**

On validation, macro F1 separated the two clearly and in favour of `moderate`:
0.5611 against 0.5220, a gap of 0.039 against a seed standard deviation of
roughly 0.006. That is a decisive-looking margin.

On the test partition the same metric collapses to 0.4476 against 0.4413, a gap
of 0.0063 against a standard deviation of 0.0057. The two configurations are
statistically indistinguishable on the criterion that chose between them.

Meanwhile the metrics the criterion did not use moved decisively the other way.
`minimal` gains 6.7 accuracy points and cuts the false positive rate on benign
traffic by roughly 15 points, consistently across every seed and both
configurations.

**This is a methodological result worth reporting in the paper.** Validation
drawn from the training pool cannot rank configurations whose failure mode is
prior sensitivity, because the validation split shares the training prior. The
official partition's 31.9 against 44.9 per cent Normal shift is exactly the
condition under which this happens, and it is the standard evaluation protocol on
this benchmark.

### What to use downstream

Both artefact sets are checkpointed. The recommendation for Levels 4, 5 and 9 is
**`minimal`**, and the justification does not require the test set:

- On validation alone, `minimal` wins accuracy 0.8105 against 0.7775 and false
  positive rate 0.1096 against 0.1934, losing only macro F1.
- For a sensor whose output feeds a reasoning layer, the false positive rate is
  the operative constraint. A 42 per cent rate floods the reasoning layer with
  situations built from benign traffic, which would make the Level 9 ablation
  measure noise.

That reasoning was available before the test partition was touched. It was not
the pre-registered criterion, and the honest record is that the pre-registered
criterion chose otherwise. Both numbers are reported and neither is hidden.

The headline Level 3 figures in L3.7 remain the `moderate` results, because those
are what the pre-registered protocol produced. `minimal` at 0.7517 closed-set
accuracy sits within the brief's stated 77 to 85 per cent honest band once seed
variance is allowed for, which `moderate` at 0.6843 does not.

---

# APPENDIX L4 — Calibration and selective prediction, appended 2026-08-04

Appended per standing rule 5. Nothing above this line has been altered.

Canonical environment: WSL CPU, `CUDA_VISIBLE_DEVICES=-1`.
Artefacts: the `minimal` SMOTE checkpoints from appendix L3.14, five seeds per
configuration. The `moderate` checkpoints remain available and were not used.

Calibration for network intrusion detection is saturated and is not the
contribution. This level exists so that abstention observed further up the stack
can be attributed to evidence rather than to a miscalibrated input.

## L4.1 Method choices

**Deep ensemble rather than Monte Carlo dropout.** Level 3 already checkpointed
five independently seeded models per configuration, so the ensemble costs
nothing. Each member carries its own fitted pipeline, because mutual information
feature selection is seeded, so members differ in both initialisation and input
representation. That widens diversity rather than compromising it, but it means
every member transforms the raw frame itself.

**Temperature scaling without stored logits.** The Level 3 models end in a
softmax and no logits were checkpointed. Taking the elementwise log of a softmax
output recovers the logits up to an additive constant, and softmax ignores
additive constants, so scaling log probabilities by one over T is exactly
temperature scaling of the original logits. No retraining and no architecture
change was needed.

**Grid search rather than gradient descent for T.** The objective is smooth and
one dimensional, the grid is cheap, and a deterministic search keeps optimiser
seed sensitivity out of a number the paper reports.

## L4.2 Temperature scaling did not transfer, and made test calibration worse

```
temperature fitted on validation : 0.9477
validation ECE : 0.0099 -> 0.0073
test ECE       : 0.0397 -> 0.0449      WORSE
test maximum calibration error : 0.2124 -> 0.2383
validation NLL : 0.4630 -> 0.4626
```

The reliability diagram shows the mechanism directly. Both panels sit **below**
the diagonal, meaning the ensemble is overconfident across the whole confidence
range on the test partition. The fitted temperature is below one, which sharpens
the distribution and therefore increases confidence. That was the right
correction on validation, where ensemble averaging left the model slightly
underconfident, and the wrong one on test.

**This is the same failure as appendix L3.14, in a different guise.** A
correction fitted on a validation split drawn from the training pool does not
transfer to a partition with a different class prior. In Level 3 it selected the
worse resampling strategy. Here it degrades the very quantity it was fitted to
improve. The official partition's 31.9 against 44.9 per cent Normal shift is the
condition in both cases.

The finding is consistent with the distribution shift literature and is worth
stating plainly in the paper: **on this benchmark, in-distribution temperature
scaling is not merely ineffective, it is actively harmful.**

Note also that the ensemble is worse calibrated on validation than a single
member, 0.0099 against 0.0067, which is the expected underconfidence of
averaging.

### Per class calibration on test, before and after

```
Analysis         n=677    0.0086 -> 0.0090
Backdoor         n=583    0.0004 -> 0.0008
DoS              n=4089   0.0088 -> 0.0074
Exploits         n=11132  0.0286 -> 0.0309
Fuzzers          n=6062   0.0681 -> 0.0701
Generic          n=18871  0.0059 -> 0.0064
Normal           n=37000  0.0923 -> 0.0926
Reconnaissance   n=3496   0.0082 -> 0.0074
Shellcode        n=378    0.0060 -> 0.0057
```

Normal and Fuzzers carry by far the worst calibration, which is the same pair the
Level 3 confusion matrix identified: Normal is misread as Fuzzers 32 per cent of
the time. Miscalibration and misclassification localise to the same place, so a
single top-label figure of 0.0397 hides where the problem actually is. That is
why per class error was requested and it earned its place.

## L4.3 Selective prediction

```
score                            AURC     lower is better
calibrated_confidence            0.0575
negative_total_uncertainty       0.0581
negative_epistemic_uncertainty   0.0738
risk without rejection           0.2439
```

Calibrated confidence is the best rejection score and epistemic uncertainty
alone is the worst. Risk falls from 0.2439 at full coverage to near zero at
roughly 45 per cent coverage, so the reject option works in the ordinary sense.

## L4.4 The critical experiment, and the honest answer

```
holdout Worms n=44 against known n=82288

AUROC total_uncertainty                0.7619
AUROC aleatoric_uncertainty            0.7614
AUROC epistemic_uncertainty            0.7884
AUROC negative_calibrated_confidence   0.6908

total        known 0.2270  holdout 0.4707  gap +0.2438
aleatoric    known 0.2220  holdout 0.4607  gap +0.2387
epistemic    known 0.0050  holdout 0.0100  gap +0.0051
```

**Epistemic uncertainty does separate the held-out class, and it separates best,
exactly as theory predicts.** AUROC 0.7884 against 0.6908 for calibrated
confidence. That is the positive result and it is real.

**Three caveats, all of which belong in the paper.**

First, **the absolute epistemic magnitudes are tiny**, 0.0050 against 0.0100 on
a unit scale. The five ensemble members overwhelmingly agree even on a class none
of them was trained on. They make the same mistake together. The ranking is
informative; the magnitude is not, and any threshold placed on raw epistemic
uncertainty would be operating in the third decimal place.

Second, **almost all the separation is aleatoric, not epistemic.** Total
uncertainty AUROC is 0.7619 and its aleatoric component alone is 0.7614. The
decomposition that was supposed to isolate "the model has not seen this before"
finds that the signal is mostly "this record is intrinsically ambiguous". The
epistemic part adds 0.0265 of AUROC over aleatoric.

Third, **at operationally useful coverage the reject option catches few unknown
attacks**:

```
target coverage   holdout rejected   known rejected
0.99              0.0455             0.0240
0.95              0.1136             0.0628
0.90              0.1818             0.0980
0.80              0.2727             0.1800
0.70              0.3182             0.3129
0.50              1.0000             0.5206
```

At 90 per cent coverage the sensor rejects 18 per cent of unknown attacks and
10 per cent of known traffic, a ratio of under two to one. At 70 per cent
coverage the two rates are indistinguishable. Only at 50 per cent coverage does
it reject every unknown attack, and it discards half of all traffic to do so.

**Appendix L3.8 overstated this.** It reported maximum confidence on the held-out
class at 0.7728 against a median of 0.9795 on known classes and concluded a
threshold in that band would work. That was a single model, seed 42. Measured
properly on the ensemble with an AUROC rather than an eyeballed gap, the
separation is 0.69 on confidence. The earlier reading is superseded.

**Verdict for the paper.** Sensor-level abstention has a genuine but modest
signal against unknown attacks. It is not on its own a solution to the
unknown-attack problem. That is precisely the argument for a second abstention
mechanism at the reasoning layer, which is what Level 9 tests, so this is a
useful result rather than a disappointing one. It must not be written up as
though 0.79 AUROC were an operational capability.

**Statistical caveat.** 44 held-out records. Every open-set number here is a
small sample estimate. Shellcode at 378 test records would give roughly nine
times the power and remains a genuinely distinct attack class.

## L4.5 Abstention wired into the serving path

`Signal` now carries `abstained` and `calibrated_confidence`. The adapter
preserves both. `SituationReasoningSnapshot` exposes `abstained_evidence_count`
and `abstention_fraction`, and `Situation.summary` reports the count, so a
situation resting on detections the sensor would not stand behind is visible
rather than implicit.

The temperature and the rejection threshold are written to
`artifacts/.../abstention_policy_{config}.json` by `run_level4.py` and loaded by
the sensor, so the serving path cannot drift from the configuration that was
measured. Both are fitted on validation only.

### A defect found and fixed during this level

The first end to end run produced **zero abstentions**. The policy was fitted on
the five member ensemble mean, but `main.py` was serving a single model. A single
member is measurably sharper than the mean, so an ensemble-calibrated threshold
applied to it never fires. **The reject option was silently disabled.**

The serving path now runs the same ensemble the policy was fitted on. This is the
general hazard: a calibration artefact is only valid for the exact predictive
distribution it was fitted to, and nothing in the code enforced that.

### Done check item four, proven end to end

Measured over a 4000 record sample of the test partition with the ensemble and
the loaded policy:

```
abstained_count            356
abstention_rate            0.0890
abstention_rate_on_known   0.0888
abstention_rate_on_holdout 0.5000   (only 2 holdout records in the sample)
confidence_threshold       0.454154
temperature                0.947744
```

The 8.9 per cent measured rate matches the 9.8 per cent the validation threshold
predicted, which is the transfer check the temperature scaling failed.

Twenty genuinely abstained records were then forwarded over the real websocket
path to a running reasoning layer:

```
payloads_sent              20
accepted                   20
situation_count            12
total_evidence             20
abstained_evidence_total   20
signal_types_seen          ['unknown']

sample situation:
  evidence_count 2, signal_types ['unknown'],
  entities ['device:synthetic-device-04'],
  abstained_evidence_count 2, max_anomaly 0.928354
```

All twenty arrived carrying `abstained` true and the `unknown` label rather than
a fabricated class.

Note that the Level 3 smoke test still reports zero abstentions. That is correct
and not a contradiction: it replays from the head of the test file and those
records happen to be classified confidently. It is recorded here because a smoke
test that never exercises a path is not evidence that the path works, which is
why `level4_verify_abstention.py` exists.

## L4.6 Figures

```
figures/reliability_diagram.pdf     before and after scaling, with the diagonal
figures/risk_coverage.pdf           three rejection scores with AURC in the legend
figures/uncertainty_by_class.pdf    per class uncertainty, held-out class marked
```

Rendered and inspected rather than assumed correct. The reliability panels plot
observed accuracy against predicted confidence with vertical drops to the
diagonal, so the gap is the readable quantity. The risk coverage figure uses
categorical slots one, two and three, which are the three validated for all-pairs
separation rather than only adjacent pairs, because three series appear together
on one axis pair.

## L4.7 Tests

```
ruff                     All checks passed
pytest Enigma-AIAgent    265 passed
pytest Enigma-ML-Layer    31 passed
```

296 tests, up from 271 at the end of Level 3. 25 added: 10 in
`tests/test_level4_abstention.py` covering the schema, the adapter, the snapshot
and store ingestion, and 15 in `Enigma-ML-Layer/tests/test_abstention.py`
covering temperature scaling and the abstention decision.

## L4.8 Outputs

```
Enigma-ML-Layer/level4_calibration.py
Enigma-ML-Layer/run_level4.py
Enigma-ML-Layer/make_level4_figures.py
Enigma-ML-Layer/level4_verify_abstention.py
Enigma-ML-Layer/tests/test_abstention.py
Enigma-AIAgent/tests/test_level4_abstention.py
results/calibration/ece_{closedset,openset}_seed42.json
results/calibration/risk_coverage_{closedset,openset}.csv
results/calibration/uncertainty_by_class_{closedset,openset}.csv
results/calibration/level4_summary.json
results/calibration/abstention_endtoend.json
artifacts/sensitivity_minimal/abstention_policy_{closedset,openset}.json
figures/reliability_diagram.pdf
figures/risk_coverage.pdf
figures/uncertainty_by_class.pdf
```

## L4.9 Carried forward

- Temperature scaling degrades test calibration. Either report the uncorrected
  ensemble, or fit the temperature on a held-out slice that shares the test
  prior, which the official partition does not provide. Do not silently ship the
  scaled numbers.
- The 44 record held-out set limits every open-set estimate. Consider Shellcode.
- Epistemic uncertainty ranks well but has negligible magnitude, so any
  downstream mechanism keying on a raw threshold rather than a rank will not
  work.
- A calibration artefact is only valid for the exact predictive distribution it
  was fitted to. Nothing currently enforces that the serving ensemble matches the
  policy's ensemble beyond a comment and a default argument.

---

# APPENDIX L5 — Baselines, appended 2026-08-05

Appended per standing rule 5. Nothing above this line has been altered.

Canonical environment: WSL CPU. XGBoost trains on the GPU, per appendix W.4.
Artefacts and split: the minimal SMOTE configuration from L3.14.

Only the classifier head changes between the MLP and the tree baselines. The
split comes from the same stratified call with the same seed, the features come
from the same seeded mutual information selector, the resampling is the same,
and the evaluation function is imported from `train_level3` rather than
reimplemented, so a difference in the numbers cannot come from a difference in
how they were computed.

## L5.1 Sensor-layer comparison

Five seeds, closed set, natural distribution.

```
classifier                accuracy            macro F1            weighted F1         FPR
MLP deep ensemble    0.7517 +/- 0.0055   0.4413 +/- 0.0057   0.7558 +/- 0.0050   0.2726 +/- 0.0145
Random Forest        0.7464 +/- 0.0005   0.5047 +/- 0.0055   0.7800 +/- 0.0006   0.2375 +/- 0.0015
XGBoost              0.7582 +/- 0.0017   0.5072 +/- 0.0066   0.7756 +/- 0.0019   0.2465 +/- 0.0019
```

Winners: **XGBoost on accuracy and macro F1, Random Forest on weighted F1 and on
false positive rate.** The MLP wins nothing.

The margins matter more than the ranking. On accuracy the three sit within 1.2
points of each other, which for a paper is a tie. On **macro F1 the gap is
decisive: 0.505 and 0.507 against 0.441, roughly eleven standard deviations of
seed variance.** The trees are substantially better at the minority classes that
drag the macro average down, which is exactly where appendix L3.7 located the
MLP's weakness.

The MLP also has an order of magnitude more seed variance on false positive rate,
0.0145 against 0.0015 and 0.0019. The tree baselines are not merely better here,
they are more stable.

Open set figures are within noise of closed set for both trees, as expected when
the held-out class is 44 of 82332 records.

```
rf   openset  acc 0.7467 +/- 0.0006   macroF1 0.5046 +/- 0.0031   FPR 0.2371
xgb  openset  acc 0.7596 +/- 0.0010   macroF1 0.5082 +/- 0.0029   FPR 0.2442
```

**This is the result the brief anticipated, and it should be reported plainly.
Tree ensembles dominate this dataset, and the MLP is not the contribution.** The
correct framing for the paper is that the sensor is a commodity component, that
a stronger commodity component is available off the shelf, and that the
contribution sits above it.

Leakage trigger: no run of the twenty exceeded the ceiling. Highest natural
accuracy across all baseline runs was 0.761599.

## L5.2 Isotonic calibration fails to transfer, which is the third instance

Isotonic calibration fitted on the validation split, `cv="prefit"` so the base
estimator is never refitted on the calibration data.

```
classifier   validation ECE        test ECE
rf           0.0313 -> 0.0189      0.0636 -> 0.0666      worse on test
xgb          0.0055 -> 0.0030      0.0851 -> 0.0837      essentially unchanged
```

Both improve on validation. Random Forest gets **worse** on test, XGBoost is
unchanged within noise. AURC tells the same story: RF 0.0626 raw against 0.0668
calibrated, XGBoost 0.0582 either way.

**This is now the third independent instance of the same failure.**

1. L3.14, validation macro F1 selected the worse resampling strategy.
2. L4.2, validation-fitted temperature scaling degraded test calibration.
3. Here, validation-fitted isotonic calibration degrades or fails to improve
   test calibration.

Three different correction mechanisms, three different classifier families, one
cause: the validation split is drawn from the training pool and shares its class
prior, and the official test partition does not. **This has stopped being an
observation about one experiment and become a finding about the benchmark's
standard evaluation protocol.** It deserves its own paragraph in the paper, and
possibly its own subsection, because every published result on this split that
tunes on an in-distribution validation fold is exposed to it.

Note also that XGBoost is far better calibrated than Random Forest before any
correction, 0.0055 against 0.0313 on validation, and worse on test, 0.0851
against 0.0636. Calibration quality does not transfer in rank order either.

## L5.3 Open-set separation, all three classifiers

Held-out class Worms, 44 test records, five seeds.

```
classifier   score                              AUROC
mlp          epistemic uncertainty              0.7884
xgb          negative calibrated probability    0.7169
xgb          negative max probability           0.7017 +/- 0.0126
mlp          negative calibrated confidence     0.6908
rf           negative calibrated probability    0.6765
rf           negative max probability           0.6719 +/- 0.0041
```

**The deep ensemble's epistemic uncertainty is the best unknown-attack detector
of everything measured, and it is the only score that beats both tree
baselines.** On confidence alone the MLP is mid-field, 0.6908, between XGBoost
at 0.7017 and Random Forest at 0.6765.

That distinction is the argument for keeping the ensemble. The MLP is the worst
classifier here on every closed-set metric, but the disagreement between its
members carries information about novelty that no single tree ensemble's
confidence provides. If the sensor is chosen on classification quality alone,
XGBoost wins and the unknown-attack signal is lost.

All three fail in the same direction. Summed over five seeds, held-out Worms are
predicted as Exploits 196 of 220 times by Random Forest and 187 of 220 by
XGBoost, matching the MLP's 70.5 per cent from L3.8. Every model reads an unseen
worm as an exploit.

The 44 record caveat from L4.4 applies unchanged to all of these numbers.

## L5.4 Literature comparison, with provenance stated

```
work                                                accuracy  comparable  provenance
Kasongo and Sun, 2020                                 0.7716  yes         corroborated
XGBoost feature selection study, IEEE doc 10930023   ~0.7800  yes         unverified
TrailGate, 2025                                       0.7865  yes         unverified
Hierarchical Classification, 2024, Random Forest      0.8344  yes         unverified
this work, XGBoost baseline                           0.7582  reference   measured
this work, MLP deep ensemble                          0.7517  reference   measured
```

Nothing was trained for this table. Every figure is transcribed from the Level 5
brief.

**Three of the four could not be corroborated and are recorded on trust.** The
IEEE entry is identified only by a document number, with no title or authors
known. TrailGate 2025 postdates the model's knowledge cutoff entirely. The
hierarchical classification figure of 83.44 per cent sits above the band the
build plan calls the honest ceiling for this split, which is itself worth
checking, since a hierarchical scheme that collapses classes before scoring is
not measuring the same ten-way task.

**None of these should reach the paper's related work section before being
checked against the actual publication.** A transcribed accuracy attached to an
unverified citation is the first thing a reviewer checks.

Placed against the corroborated reference point, this work's XGBoost baseline at
0.7582 sits 1.3 points below Kasongo and Sun. That is a reasonable position for a
pipeline built for auditability rather than for accuracy, and it is consistent
with the leakage-free split.

## L5.5 Flat alerting against situation grouping

5000 test records replayed at the sensor's configured 0.5 second spacing.

```
records replayed        5000
alerts, no grouping     3374
alerts per minute       80.98
false alerts            632
false alert rate        0.1873
abstained alerts        575
situations created      16
compression ratio       210.88
```

The alert volume figures are real and usable. **A flat alerting system raises 81
alerts a minute on this replay, and 18.7 per cent of them are on traffic that is
genuinely benign.** That is the operational case for grouping, and it does not
depend on any downstream reasoning being correct.

**The compression ratio of 210.88 is an artefact and must not be reported as a
result.** The sensor derives a synthetic entity from `id` modulo sixteen, because
the official partition carries no source or destination address, as recorded in
L3.9. Correlation groups by entity. There are therefore exactly sixteen possible
situations regardless of the data, and the compression ratio is simply alerts
divided by the pool size. Change the pool size and the ratio moves
proportionally. It measures the constant, not the system.

## L5.6 Rule-only variant, and why its result is meaningless

```
situations scored                    16
dominant type accuracy               1.0
signal level accuracy for contrast   0.5931
mean ground truth purity             0.34
trend distribution                   escalating 4, stable 10, deescalating 2
```

**The accuracy of 1.0 measures nothing.** Every one of the sixteen situations has
majority ground truth `generic` and dominant emitted type `generic`, with mean
purity 0.34.

The mechanism is the same synthetic entity assignment. Because `id` modulo
sixteen is uncorrelated with attack class, each situation is a uniform random
sample of the test distribution. The plurality class of a random sample of the
test set is Generic, and the plurality of the model's predictions on a random
sample is also Generic, so the two agree in all sixteen cases by construction.
The metric is asking whether the most common class equals the most common class.

The honest contrast is the signal level accuracy of 0.5931, which is a real
measurement of how often the sensor's emitted label matches the record's true
label, and which needs no situation-level ground truth at all.

**Both Part B grouping numbers are blocked on the same missing capability**: the
official partition has no entity identifier, so there is no real correlation key,
so there are no real situations. This is the third consequence of the partition
choice, after missing event timestamps in L2.2 and missing entities in L3.9.
Level 7's scenario generator is the correct place to measure this, and it should
be treated as a prerequisite rather than an enhancement.

## L5.7 LLM-only variant, BLOCKED

**Not run. No Gemini credential is available in this environment.**

```
GOOGLE_API_KEY in environment          absent
ENIGMA_GEMINI_API_KEY in environment   absent
.env file                              none anywhere in the project
                                       only .env.example, with empty placeholders
```

Recorded in `results/baselines/llm_only_comparison.json` with the same detail, so
the gap is machine readable rather than a silently missing file.

No LLM calls were made and nothing was simulated or estimated in place of the
missing measurement. This also blocks any comparison of the full hybrid system
against the rule-only variant, since the full system needs the same credential.

Two things are needed to unblock it, and the second matters more than the first.
A credential. And situation-level ground truth that is not degenerate, per L5.6,
without which the LLM-only comparison would measure the same nothing the
rule-only comparison did.

## L5.8 Outputs

```
results/baselines/rf_{closedset,openset}_seed{42,123,456,789,1024}.json
results/baselines/xgb_{closedset,openset}_seed{...}.json
results/baselines/rf_calibration.json
results/baselines/xgb_calibration.json
results/baselines/rf_risk_coverage.csv
results/baselines/xgb_risk_coverage.csv
results/baselines/literature.json
results/baselines/alert_volume_comparison.json
results/baselines/rule_only_comparison.json
results/baselines/llm_only_comparison.json     blocked, with reasons
results/baselines/classifier_comparison.json
results/baselines/replay_signals.jsonl         the exact stream both variants saw
results/baselines/replay_manifest.json
results/baselines/summary.csv
results/baselines/summary_statistics.json
figures/baseline_comparison.pdf
```

The replay stream is written to disk rather than regenerated per variant, so
every reasoning baseline provably saw the identical signal sequence and the
comparison can be re-run without re-scoring.

```
ruff                     All checks passed
pytest Enigma-AIAgent    265 passed
pytest Enigma-ML-Layer    31 passed
```

No new dependency was added. Random Forest and isotonic calibration come from
scikit-learn 1.7.2 and XGBoost 3.0.5, both already pinned since Level 1.

## L5.9 Carried forward

- The MLP loses to both tree baselines on every closed-set metric. Report it and
  reframe the sensor as a commodity component.
- The MLP's epistemic uncertainty is nonetheless the best unknown-attack score
  measured, 0.7884 against 0.7017 and 0.6719. That is the reason to keep the
  ensemble, and it should be stated as the reason rather than left implicit.
- Validation-fitted correction has now failed to transfer three separate times.
  This is a finding about the benchmark, not about one experiment.
- Both reasoning-layer grouping metrics are degenerate because the official
  partition has no entity identifier. Level 7 is a prerequisite, not an
  enhancement.
- Three of four literature figures are unverified. Resolve them before writing
  related work.

---

# Appendix L6. Instrumentation

Level 6 closes gap C1. Every claim below is reproducible from
`scripts/level6_*.py` and the JSON and JSONL files under `results/level6`.

## L6.1 Where the run logger was attached, and why there

The brief offered three attachment points: a LangGraph stream, a callback hook,
or logging inside `update_convergence`. The stream was chosen.

`runner.py` now drives the graph with `compiled_graph.stream(initial_state,
stream_mode="values")` instead of `invoke`, and a recorder observes each yielded
state. `iteration_count` is advanced by exactly one node, so a rise in that
field marks a completed iteration and is the trigger for a record.

Three reasons for this choice over the alternatives:

1. No node is modified and no node is aware of the recorder, so the claim that
   logging cannot alter reasoning is structural rather than a matter of care.
   Logging inside `update_convergence` would have put a writer inside a node
   whose purity was the fix for defect D4.
2. LangGraph implements `invoke` over the same value stream, so the last value
   yielded is the state `invoke` would have returned. The two paths are not
   merely similar, they are the same execution.
3. The recorder sees the full accumulated state, so no field had to be threaded
   through a callback signature.

Logging is off unless a sink is passed. `run_reasoning(..., run_log=None)` takes
the original `invoke` path unchanged.

## L6.2 The two constraints, and how they are enforced

**Logging must not change behaviour.** Four tests in
`tests/test_level6_instrumentation.py` assert this, and one of them is a control.
`test_two_unlogged_runs_agree_under_normalisation` runs two unlogged analyses
through the same normalisation used by the other three and asserts they agree,
which establishes that the normalisation is not concealing a real difference.
Normalisation is necessary because `hypothesis_id` and `situation_id` come from
`uuid4` and therefore differ between any two runs whether or not logging is on.
Everything reasoning computes is compared unnormalised.

**The logger must not fail an analysis.** `test_failing_sink_does_not_break_analysis`
hands the runner a sink that raises `OSError` on every write and asserts the
analysis still returns hypotheses and a non-zero iteration count.
`RunLogWriter` counts drops rather than raising, including when its own file
cannot be opened.

## L6.3 Per stage latency, measured

Six boundaries are instrumented. No single run covers all six: the offline
replay has no dashboard so cannot time a broadcast, and the load harness
substitutes a fixed service time for the model. Both are reported separately in
`results/level6/latency_six_stage.json` rather than merged into a table
describing a run that never happened.

Offline replay, 1000 analyses, seed 42, deterministic mock model:

| stage | p50 ms | p95 ms | p99 ms |
| --- | --- | --- | --- |
| signal_ingest | 0.026 | 0.140 | 0.192 |
| situation_attach | 0.018 | 0.129 | 0.182 |
| deterministic_reasoning | 0.098 | 0.145 | 0.208 |
| langgraph_gemini | 45.697 | 51.025 | 70.432 |
| explanation_build | 0.201 | 0.262 | 0.327 |

Load harness at 4 records/s, 80 analyses, 6 s simulated service time:

| stage | p50 ms | p95 ms | p99 ms |
| --- | --- | --- | --- |
| signal_ingest | 0.082 | 0.160 | 0.191 |
| situation_attach | 0.066 | 0.125 | 0.166 |
| deterministic_reasoning | 0.114 | 0.197 | 0.218 |
| langgraph_gemini | 6022.378 | 6090.038 | 6150.819 |
| explanation_build | 0.114 | 0.187 | 0.210 |
| dashboard_broadcast | 0.067 | 0.105 | 0.130 |

The reasoning stage dominates the other five by roughly 300 times even with a
mock model that performs no network call, and by roughly 50000 times at the
simulated service time. The five non-model stages together have a p99 under
0.9 ms. **The system the paper describes is fast; the model it calls is not.**
This is the honest framing and it should not be aggregated away.

## L6.4 Real model latency remains UNVERIFIED

No Gemini API key exists in this environment. Neither `GOOGLE_API_KEY` nor
`ENIGMA_GEMINI_API_KEY` is set, and `Enigma-AIAgent` contains only `.env.example`.
`_default_llm_factory` raises without a key, and `make_generate_hypotheses`
catches every exception and substitutes `_fallback_hypotheses()`.

Two consequences, both of which matter to the paper:

1. **No real Gemini latency figure exists.** C3 recorded a developer estimate of
   5 to 15 s per analysis and it remains the only such figure. It is still
   UNVERIFIED. The 6 s used by the load harness is drawn from that estimate and
   is declared as a parameter in the output, not presented as a measurement.
2. **Every live dashboard run observed to date exercised the fallback path, not
   the model.** The dashboard screenshots captured during the frontend work show
   exactly the three strings in `nodes.py:200-202` together with the UNKNOWN
   hypothesis, which is `_fallback_hypotheses()` verbatim. This explains the
   convergence score pinned at 0.00 across all 16 situations: the fallback emits
   three fixed hypotheses at 0.3, 0.3 and 0.25, UNKNOWN starts at 0.4 and
   dominates permanently, so the loop is undecided by construction. Any figure
   or screenshot drawn from those runs illustrates the fallback, and must not be
   captioned as LLM reasoning.

## L6.5 Queue depth and backpressure

`AnalysisPool` replaces the unbounded `asyncio.create_task` fan out recorded in
C4. Concurrency is capped, the backlog is counted, and submissions beyond the
bound are shed and counted rather than queued without limit. The acknowledgement
on `/ws/signal` now carries `analysis_admitted`, which is the only backpressure
signal the protocol has.

Measured with `scripts/level6_load.py`, seed 42, 20 s of arrivals, 4 concurrent,
64 pending bound, 6 s simulated service time. Service capacity is therefore
4 / 6 = 0.667 analyses per second.

| arrival rate | offered | peak backlog | mean backlog | shed | shed % | drain s |
| --- | --- | --- | --- | --- | --- | --- |
| 0.5 /s | 10 | 5 | 3.40 | 0 | 0.0 | 4.0 |
| 1 /s | 20 | 11 | 7.05 | 0 | 0.0 | 13.1 |
| 4 /s | 80 | 68 | 36.08 | 0 | 0.0 | 101.2 |
| 16 /s | 320 | 68 | 60.88 | 240 | 75.0 | 102.3 |

**Where it saturates.** Steady state capacity is 0.667 analyses per second, so
every rate at or above 1 /s is oversubscribed and the only question is how fast
the bound is reached. Within a 20 s window the buffer is not exhausted at 1 /s,
is exhausted exactly at 4 /s where peak backlog reaches 68, the sum of the 64
pending bound and 4 running slots, and is exhausted early at 16 /s where 75 per
cent of arrivals are shed. The 0.5 /s row is a control below capacity and shows
the measurement discriminates rather than always reporting saturation.

C4 estimated the replayer at approximately 4 records/s. That is the row where
the buffer fills exactly, which corroborates the C4 claim of oversubscription by
one to two orders of magnitude, now with a number attached.

## L6.6 The evidence sort

C4 item 4 recorded that `event_intervals` sorts the full evidence list on every
access and is read at least three times per analysis over a list that is never
trimmed. It was cheap to improve and has been: the result is memoised against
`version`, which advances on every attach and so invalidates the cache exactly
when the evidence changes.

This removes the repeated sorts within a single analysis. It does **not** change
the asymptotic cost, which remains O(n log n) in evidence count on the first read
after each attach. Removing that would require keeping `_evidence` sorted on
insert, which changes the order of the public `evidence` property and was judged
too invasive for the benefit. **The quadratic growth C4 describes is reduced by a
constant factor, not eliminated.**

## L6.7 Offline replay

`enigma_reason/replay/offline.py` runs the store, the deterministic engine, the
graph and the explanation builder with no FastAPI, no websocket and no network.

Done check figure, seed 42, entity correlation, deterministic mock model:

- 1000 signals, **100 situations**, 1000 analyses, 3000 iterations logged,
  0 dropped, **47.0 s wall clock**.

That is 21 analyses per second including graph execution and explanation
building, which is what makes a Level 9 sweep of 320 suites feasible at all.

## L6.8 Response cache

Keyed on the assembled prompt, not on the context dict as the brief specified.
The context dict is not sufficient to identify a request: the prompt also embeds
the prior hypotheses being refined, so two iterations sharing a context but
carrying different prior beliefs would collide and the cache would answer a
question that was not asked. The prompt is a strict superset of the context, so
the key is sound wherever the narrower one would have been and correct where it
would not.

Measured, seed 42, 200 signals, 20 devices, mock model:

| measurement | lookups | hits | hit rate |
| --- | --- | --- | --- |
| cold run | 600 | 3 | 0.005 |
| warm repeat of the same suite | 600 | 600 | **1.000** |
| 16 ablation configurations sharing one cache | 9600 | 8983 | **0.936** |

The warm run added **zero** model calls.

**The 0.936 figure is an upper bound and must not be used as a Level 9 budget.**
It was measured with the deterministic mock, whose three hypothesis descriptions
never vary, so `_build_existing_hypothesis_context` is far more stable across
configurations than it would be with a real model. Two structural results do
carry over, and are visible in the per configuration table:

- Toggling **P** changes nothing about any prompt, because persistence affects
  only convergence gating. Its rows hit at 1.000.
- Toggling **U** changes nothing about any prompt, because
  `_build_existing_hypothesis_context` already filters UNKNOWN out.
- Toggling **A** does change prompts, because asymmetric decay changes the
  confidences that are printed. It is the only switch that produced misses.

The floor that survives a real model is the first iteration: with no prior
hypotheses, iteration one assembles a byte identical prompt in all sixteen
configurations, so 15 of 16 are guaranteed hits. At three iterations per
analysis that is a **31 per cent floor**. The true rate lies between 31 and 94
per cent and must be measured with `--llm real` before a budget is set.

## L6.9 Run manifest

`build_run_manifest` pins the commit of all three repositories, the resolved
config, the seed, content hashes of the model artefact and dataset, wall clock
start and end, and an environment fingerprint. A full example is
`results/level6/manifest_traced.json`.

Note that all three commits carry a `-dirty` suffix in the manifests produced
during this level, because the manifests were generated before the level was
committed. This is the intended behaviour and is why the suffix exists.

`tensorflow_version` reports `absent` in the agent virtual environment, which is
correct: the reasoning layer does not depend on TensorFlow. It resolves in the
machine learning environment.

## L6.10 What Level 6 unblocks and what it does not

Unblocked: per iteration outcome metrics for Level 7 scoring, including
premature convergence and iterations to termination, neither of which was
computable before; per stage latency for the performance figure; queue depth for
the honesty claim about real time.

Still blocked: any figure requiring real model latency or real model text, until
an API key is available. The word "real-time" in the working title remains
unsupported for the end to end path, because the dominant stage has never been
measured. It is now supported for everything else, with a p99 under 0.9 ms
across the five non-model stages.

---

# Appendix L7. Scenario generator with injected ground truth

Level 7 gives the project its first situation level ground truth. Everything
below is reproducible from `scripts/level7_*.py` and the files under
`results/scenarios`.

## L7.1 The frozen suite

| property | value |
| --- | --- |
| seed | 42 |
| suite hash | `52b89293b37baff655f97a41a42b67962059c2c96c5a34a716c69af7202f0efc` |
| scenarios | 400, 100 per regime |
| signals | 8832 |
| situations under entity grouping | 625 |
| abstained signal fraction | 0.2258 |

Expected conclusions: 300 scenarios expect UNKNOWN, and the remaining 100 clear
scenarios are spread across six narratives, from 13 for data exfiltration to 22
for reconnaissance sweep.

The hash covers ground truth, parameters, entities, sources and every signal's
content. Signal identifiers are excluded because they are freshly generated
uuids and would make an otherwise identical suite hash differently.

## L7.2 Source diversity

Diversity is reported per situation, because a situation is what the reasoner
sees. A scenario spanning three entities becomes three situations, and the
scenario level union would overstate what any single one of them observes.

| distinct sources | situations | share |
| --- | --- | --- |
| 1 | 64 | 10.2% |
| 2 | 206 | 33.0% |
| 3 | 186 | 29.8% |
| 4 | 169 | 27.0% |

Every one of the 64 situations at diversity one is sparse. No clear, ambiguous
or unknown attack situation sits at diversity one, which matters because
diversity one forces three mechanisms into a degenerate regime simultaneously:
the diversity term saturates at a third of its weight, the sanity gate adds a
low diversity boost to UNKNOWN on every iteration, and convergence is halved
once mean anomaly passes the high anomaly threshold. A suite generated at
diversity one would have measured those three penalties rather than reasoning.

**A defect found and fixed during this level.** The first implementation drew
sources from a merged pool across detector families and then filtered to the
family each entity belonged to. That left some entities holding a single
eligible source: 70.3 per cent of scenarios reached diversity two or more
rather than the configured 88 per cent. Sources are now drawn per detector
family, so the parameter means distinct sources per situation and is honoured
exactly. `test_sources_vary_so_diversity_exceeds_one` asserts the property.

## L7.3 The Level 5 artefact, explicitly ruled out

The same statistic is computed twice over the identical 8832 signals: once on
this generator's entity assignment, and once on a reconstruction of the Level 5
assignment of index modulo sixteen.

| statistic | scenario scoped entity | index modulo 16, as Level 5 |
| --- | --- | --- |
| groups | 625 | 16 |
| Cramer's V | **1.0** | **0.0072** |
| global category entropy | 2.6962 bits | 2.6962 bits |
| mean within group entropy | **0.0 bits** | **2.6959 bits** |
| entropy reduction | 2.6962 bits | 0.0003 bits |
| pure groups | 625 of 625, 100% | 0 of 16, 0% |

Under the Level 5 assignment, knowing which group a signal fell into reduced
uncertainty about its category by 0.0003 of 2.6962 bits. Every group was a
uniform random sample of the corpus, which is precisely why rule only accuracy
came out at 1.0: the metric was asking whether the most common class equals the
most common class. Under this generator each group is pure and grouping by
entity reconstructs the scenario exactly.

**This is not label leakage.** `assemble_context` exposes only aggregated
metrics and never sees an entity identifier, a timestamp or a signal id. The
entity determines which signals belong together, not what they mean. A reasoner
cannot read the answer off the entity because it is never shown the entity.
`test_entity_identifies_its_scenario` and
`test_entity_grouping_is_not_a_uniform_random_sample` assert both halves.

## L7.4 Outcome metrics against the current system

Two model paths were run over the identical frozen suite. The first is the
unmodified system as it stands, which with no API key substitutes the fallback
hypotheses at `nodes.py:200-202`. The second uses the Level 6 deterministic
mock, whose hypothesis text varies enough to exercise the keyword matching.
Both are the real reasoning path from the sanity gate onward.

625 situations, 8832 analyses, 26496 iterations logged, 0 dropped.

| metric | system, fallback | system, mock | reference | always abstain | always conclude |
| --- | --- | --- | --- | --- | --- |
| correct_conclusion_rate | 0.7120 | 0.3440 | 0.9792 | 0.7120 | 0.2880 |
| false_conclusion_rate | 0.0000 | 0.6112 | 0.0208 | 0.0000 | 0.7120 |
| abstention_rate | 1.0000 | 0.3744 | 0.6912 | 1.0000 | 0.0000 |
| appropriate_abstention_rate | 1.0000 | 0.4629 | 0.9708 | 1.0000 | 0.0000 |
| inappropriate_abstention_rate | 1.0000 | 0.1556 | 0.0000 | 1.0000 | 0.0000 |
| premature_convergence_rate | 0.0000 | 0.3824 | 0.0208 | 0.0000 | 0.7120 |
| single_iteration_conclusion_rate | 0.0000 | 0.0000 | 0.3088 | 0.0000 | 1.0000 |
| mean_iterations_to_termination | 3.0 | 3.0 | 1.0 | 1.0 | 1.0 |

**The unmodified system abstains on 625 of 625 situations.** It concludes
nothing, ever. Its correct conclusion rate of 0.7120 is exactly the score of a
policy that always abstains, to four decimal places, because that is what it
is. This is the Level 6 finding L6.4 showing up as a number: the fallback emits
three fixed hypotheses at 0.3, 0.3 and 0.25 while UNKNOWN starts at 0.4 and is
boosted further, so UNKNOWN dominates permanently by construction.

## L7.5 Saturation, and what it is caused by

The suite is discriminable. A reference reasoner reading only the aggregated
context reaches 0.9792 against 0.7120 for always abstaining and 0.2880 for
always concluding, so the suite separates a policy that judges from policies
that do not.

Under the mock, six of the eight metrics are unsaturated and every one of the
six discriminates between regimes:

| metric | value | range across regimes |
| --- | --- | --- |
| correct_conclusion_rate | 0.3440 | 0.9500 |
| false_conclusion_rate | 0.6112 | 0.7944 |
| abstention_rate | 0.3744 | 0.8444 |
| appropriate_abstention_rate | 0.4629 | 1.0000 |
| inappropriate_abstention_rate | 0.1556 | 0.1556 |
| premature_convergence_rate | 0.3824 | 0.7545 |

Two metrics remain pinned in every configuration tried:
`single_iteration_conclusion_rate` at 0.0 and `mean_iterations_to_termination`
at exactly 3.0.

**These two are not generator controllable, and the generator was not adjusted
to chase them.** Three independent pieces of evidence:

1. The other six metrics are unsaturated on the same suite from the same
   generator, so the suite is not the limiting factor.
2. Disabling the UNKNOWN hypothesis and the persistence requirement together
   flips the system from abstaining on everything to concluding on everything,
   abstention rate 1.0 to 0.0, and yet leaves both iteration metrics exactly
   where they were.
3. Across all **26496** iteration records the highest convergence score ever
   observed is **0.6225** against a threshold of **0.8**. Not one record
   reaches the threshold, and all 8832 analyses terminate with reason
   `max_iterations`.

The convergence threshold is unreachable within the iteration budget. Mean
convergence also falls as reasoning proceeds, 0.1530 at iteration one, 0.1257
at iteration two, 0.1130 at iteration three, so additional iterations make the
system less rather than more decided. This is a property of the interaction
between `graph_convergence_threshold` at 0.8, `graph_max_iterations` at 3 and
`max_confidence_delta` at 0.15, and it is a finding for the paper rather than a
generator defect. Level 9 varies exactly these mechanisms.

## L7.6 Worked example

Scenario `s00100`, ambiguous regime. Three entities, four sources, 54 signals
across data exfiltration, intrusion and reconnaissance types, mean anomaly
0.5987, 21 of 54 signals abstained by the sensor.

Ground truth: expected conclusion UNKNOWN, should conclude False. The evidence
fits reconnaissance sweep and data exfiltration equally well and does not
separate them, so a confident single conclusion is unsupported however much of
this evidence arrives.

What the system did on situation `f1135f10`: concluded, did not abstain, ran 3
iterations, terminated on `max_iterations` with final convergence 0.1776 over
18 pieces of evidence. The named hypothesis matched neither the expected
narrative nor its rival.

Scored: correct False, false conclusion True, premature convergence True. The
system committed to an answer on evidence that supports two narratives equally,
which is the failure mode the ambiguous regime exists to detect, and it did so
while its own convergence score was 0.1776. It concluded without being
convinced, because termination by iteration exhaustion promotes whatever leads
at the time into a conclusion.

## L7.7 What this validation does and does not establish

Established: the scoring machinery works, the suite discriminates between
policies that judge and policies that do not, entity grouping reconstructs
scenarios, and six of eight metrics respond to regime.

Not established: reasoning quality. Neither model path is Gemini. The fallback
run measures a system that cannot conclude, and the mock run measures a system
whose hypothesis text comes from three fixed strings chosen by digest. The
correct conclusion rates in L7.4 are properties of those substitutes. **Rerun
`scripts/level7_validate.py --llm real` once an API key exists**, and treat
every number in L7.4 as provisional until then.

A further limit is the keyword matching in `scenarios/scoring.py`. A hypothesis
right in substance but sharing no vocabulary with its category is scored as a
false conclusion, so the reported correct conclusion rate is a lower bound.

---

# Appendix L7.8. The real model path, restored, scored and budgeted

Appendix L7.7 ends with an instruction: rerun `scripts/level7_validate.py
--llm real` once an API key exists. A key has existed since 7 August. The
flag never did. This appendix records what was restored, what a real model
does to the Level 7 result, and one finding that reorders the critical path
into Level 9.

## L7.8.1 What was missing

`level7_validate.py` declared `choices=("mock", "fallback")`. There was no
real path to run. The file was last written at 03:42 on 7 August, the same
minute the smoke log beside it was finished, so a real path existed briefly
and was lost. Nothing under `scripts/` was in any repository at the time, so
there was no history to recover it from. The project root is now a
repository, and this loss is the reason it is.

Three further defects were found and fixed.

The script never loaded `.env`. `enigma_reason.config.Settings` carries
`env_prefix` but no `env_file`, so nothing in that file reached the process.
`settings.gemini_model` resolved to its `gemini-2.0-flash` default rather
than the configured `gemini-2.5-flash`, `gemini_max_output_tokens` to 1024
rather than 4096, and `GOOGLE_API_KEY` was absent from the environment
altogether. The script now loads it exactly as `scripts/demo_server.py`
already did.

A relative `--suite` crashed the report writer at `relative_to`, which
nothing had exercised because the default is absolute. The same defect class
later cost the cache measurement its report, recorded at L7.8.7.

Most seriously, every `--llm fallback` run mirrored its output over
`validation_run.json` and `metric_distributions.csv`, the canonical files
behind L7.4, with no check on what had produced it. A sixty scenario sizing
run during this work silently replaced the four hundred scenario result. It
was recovered from the previous commit. The mirror now requires the
unablated full suite at its canonical path and a scenario count of 400.

`_default_llm_factory` read `GOOGLE_API_KEY` and `ENIGMA_GEMINI_API_KEY`. It
now also reads `GEMINI_API_KEY`, the name the upstream SDK documents, which
previously failed as though no key were present.

## L7.8.2 The 7 August smoke could not be rescued

The smoke log was the only unmanifested artefact in the project. It was also
not what it appeared to be.

`scripts/check_fallback_absent.py` hashes the three fixed strings at
`nodes.py:200-202` and searches a run log for them. Their presence proves
generation raised and was substituted on at least one iteration; their
absence across every iteration proves every hypothesis came from the model.
The run log stores only a twelve character hash of each description, so this
cannot be read off by eye.

| quantity | 7 August smoke |
| --- | --- |
| iterations | 128 |
| iterations containing a fallback hypothesis | 8 |
| fallback iteration fraction | **0.0625** |
| hypothesis rows | 581 |
| hypothesis rows that are fallback | 24 |

The smoke was therefore roughly 94 per cent real model output and 6 per cent
silent substitution. The most likely mechanism is the unloaded `.env`
described above: at the 1024 token default the model's JSON was truncated,
parsing raised, and `_fallback_hypotheses` was substituted with nothing in
the log marking it. The re-run below, with 4096 tokens loaded, falls back
zero times in 369 iterations, which is consistent with that mechanism but
does not prove it.

Its eight outcome metrics cannot be recovered at all. Scoring needs the
scenario to situation mapping and the hypothesis texts behind the hashes, and
the run that produced the log saved neither. This is not a limitation of the
scoring code. It is the reason the smoke had to be run again, and the reason
a run log on its own is not a result.

## L7.8.3 The re-run

| property | value |
| --- | --- |
| suite | `results/scenarios/suite.jsonl` |
| parent suite hash | `52b89293...f0efc`, verified equal to L7.1 |
| slice | one scenario per regime, `s00000` `s00100` `s00200` `s00300` |
| slice hash | `094c582059410e8693bdb873259b1a132251d713fe85ebd3732f3297e28aef29` |
| seed | 42 |
| model | `gemini-2.5-flash`, temperature 0.2, 4096 output tokens |
| situations | 7 |
| analyses | 123 |
| iterations logged | 369, none dropped |
| wall clock | 3294 s |
| seconds per model call | **8.927** |
| fallback iterations | **0 of 369** |
| distinct hypothesis texts | **365**, against 4 on both substitute paths |

Outputs are the full quartet the other runs carry and the smoke did not:
`validation_run_real.json`, `validation_run_log_real.jsonl`,
`metric_distributions_real.csv`, `validation_outcomes_real.jsonl` and
`manifest_validate_real.json`, the manifest pinning all three repository
commits, the seed, the model name, the resolved config and the suite hash.

The slice is small and is declared as such. It is one scenario per regime
rather than a sample of each, so every rate below rests on seven situations
and none is a population estimate. What it settles are the three structural
questions L7.7 left open. It includes `s00100`, the ambiguous scenario
dissected as the worked example in L7.6.

## L7.8.4 Outcome metrics across every model path

| metric | fallback | mock | real | 7 Aug smoke |
| --- | --- | --- | --- | --- |
| correct_conclusion_rate | 0.7120 | 0.3440 | 0.2857 | not recoverable |
| false_conclusion_rate | 0.0000 | 0.6112 | 0.7143 | not recoverable |
| abstention_rate | 1.0000 | 0.3744 | 0.2857 | not recoverable |
| appropriate_abstention_rate | 1.0000 | 0.4629 | 0.4000 | not recoverable |
| inappropriate_abstention_rate | 1.0000 | 0.1556 | 0.0000 | not recoverable |
| premature_convergence_rate | 0.0000 | 0.3824 | 0.4286 | not recoverable |
| single_iteration_conclusion_rate | 0.0000 | 0.0000 | 0.0000 | not recoverable |
| mean_iterations_to_termination | 3.0 | 3.0 | 3.0 | not recoverable |
| situations | 625 | 625 | **7** | 2 |
| analyses | 8832 | 8832 | 123 | about 43 |
| distinct hypothesis texts | 4 | 4 | **365** | 342 |

**The denominators differ by two orders of magnitude and these columns are
not a like for like comparison.** What the table supports is a statement
about direction and kind, not about magnitude.

The direction inverts L7.4. The unmodified system with no key abstains on
every situation it ever sees, scoring exactly the always abstain policy. With
a real model it abstains on two of seven and concludes on five, and its false
conclusion rate of 0.7143 is precisely the always conclude baseline. The
system did not move from abstaining to judging. It moved from one degenerate
policy to the other.

**L7.4 is superseded for any claim about reasoning quality**, as L7.7 said it
would be. It remains the correct description of the unconfigured system,
which is a real deployment state and worth keeping measured.

## L7.8.5 The scorer does not survive contact with a real model

This is the finding that reorders the work before Level 9.

Across all seven situations, `matched_expected` is False and
`matched_competitor` is also False. Not one hypothesis Gemini produced shared
vocabulary with either the category it was supposed to reach or the rival it
was supposed to be confused by.

Scenario `s00000` expects `data_exfiltration`, whose keywords are
`exfiltrat`, `data transfer`, `outbound`, `upload`, `leak`, `volume`. What
the model writes, read from the response cache, is prose of this kind:

    Coordinated reconnaissance activity from multiple distinct sources.
    Automated external scanning or vulnerability assessment.
    Misconfigured or malfunctioning benign automation causing anomalous events.
    Persistent, low-volume anomalous activity from diverse internal sources.

This is competent security English. It is not the generator's vocabulary. The
mock scored well under keyword matching because its text is drawn from that
vocabulary by construction, which made the scorer look adequate for as long
as nothing real was scored.

L7.7 already recorded that keyword matching makes the correct conclusion rate
a lower bound. What is new is the magnitude. On real text the match rate is
zero of seven, so the scorer is not merely deflating a rate, it is not
discriminating at all on the axis it exists to measure.

Which metrics this contaminates can be read off `scenarios/scoring.py`.

| metric | keyword dependent | trustworthy on the real path |
| --- | --- | --- |
| correct_conclusion_rate, truth says conclude | yes, `scoring.py:155,159` | **no** |
| correct_conclusion_rate, truth says abstain | no, `correct = abstained`, `scoring.py:161` | yes |
| false_conclusion_rate | inherits the above | partly |
| abstention_rate | no | yes |
| appropriate and inappropriate abstention | no | yes |
| premature_convergence_rate | no, evidence count only, `scoring.py:168` | yes |
| single_iteration_conclusion_rate | no | yes |
| mean_iterations_to_termination | no | yes |

Of the seven situations, five carry ground truth UNKNOWN, where `correct` is
simply whether the system abstained and no keyword is consulted. Those five
are scored correctly. The two clear regime situations are the keyword
dependent ones, and both are recorded as false conclusions on a test the
scorer cannot currently pass.

**Consequence for Level 9.** The brief names `premature_convergence_rate` and
`false_conclusion_rate` as the primary outcomes. The first is keyword
independent and is safe. The second is not. The LLM judge panel planned for
Level 10, validated against fifty hand labelled cases, is therefore a
prerequisite for Level 9's primary outcome rather than a later refinement,
unless the keyword scorer is replaced by semantic matching first. Running the
factorial against the current scorer would produce a false conclusion rate
that measures vocabulary overlap rather than reasoning.

## L7.8.6 Convergence, now confirmed against a real model

L7.5 established under the mock that the 0.8 threshold is unreachable and
that every analysis terminates by exhausting its iteration budget, and
flagged both as provisional until a real model ran. Both survive.

| quantity | fallback | mock | real |
| --- | --- | --- | --- |
| iterations | 26496 | 26496 | 369 |
| highest convergence observed | 0.0000 | 0.6245 | **0.3850** |
| mean convergence | 0.0000 | 0.1733 | 0.1428 |
| iterations reaching the 0.8 threshold | 0 | 0 | **0** |
| analyses terminating on `max_iterations` | all | all | **all 123** |
| UNKNOWN dominant at termination | 1.0000 | 0.4550 | 0.3089 |

The real model's ceiling is **lower** than the mock's, 0.385 against 0.6245,
so the gap to the threshold widens rather than closes when the substitute is
removed. The threshold is not merely unreached, it is not approached.
`graph_convergence_threshold` must therefore be a swept parameter in Level 9
rather than a constant, or `single_iteration_conclusion_rate` and
`mean_iterations_to_termination` stay pinned at 0.0 and 3.0 in every cell of
the factorial, exactly as they are in every configuration tried so far.

The UNKNOWN dominance figures show the epistemic control competing rather
than dominating for the first time. Under the fallback it wins every
termination by construction, which is L6.4 restated as a rate. Under a real
model it wins roughly a third.

The mock figure of 0.6245 is measured here from
`validation_run_log_mock.jsonl`. L7.5 quotes 0.6225 across a wider set of
runs. The two are consistent in substance and the discrepancy is noted rather
than reconciled.

## L7.8.7 Cache hit rate per switch, against a real model

L6.8 measured 0.936 across sixteen configurations and stated plainly that the
figure is an upper bound taken with a mock whose three descriptions never
vary, with a first iteration floor of 0.31. The true rate was declared
unknown until measured against a real model. It has now been measured.

Five configurations over the same four scenario slice, sharing one cache,
with the baseline populating it. 369 lookups each.

| configuration | ablated | lookups | hits | misses | hit rate | elapsed |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | none | 369 | 369 | 0 | 1.0000 | 5.9 s |
| minus_U | U | 369 | 369 | 0 | **1.0000** | 6.2 s |
| minus_S | S | 369 | 259 | 110 | **0.7019** | 1016.2 s |
| minus_A | A | 369 | 345 | 24 | **0.9350** | 233.8 s |
| minus_P | P | 369 | 369 | 0 | **1.0000** | 5.6 s |
| pooled, excluding baseline | | 1476 | 1342 | 134 | **0.9092** | |

**The structural predictions in L6.8 hold exactly.** U and P change no prompt
and hit at 1.0, because persistence affects only convergence gating and
`_build_existing_hypothesis_context` already filters UNKNOWN out. S and A
alter the confidences printed into the next iteration's prompt and are the
only switches that cost model calls.

What L6.8 could not predict is the magnitude, and the answer is that the
reuse largely survives a real model: **0.9092 measured against 0.936 under
the mock**, far above the 0.31 floor. The sanity gate is the expensive
switch, not asymmetric decay as the mock suggested.

The measurement is sound; its report writer was not. The run completed all
five configurations and printed these figures, then raised on a relative
`--cache` path, the defect class already fixed once in `level7_validate.py`.
Re-running would report 1.0 everywhere because the misses it paid for are now
in the cache, and the pre ablation cache cannot be reconstructed because
nothing recorded which entries the run added. The figures were therefore
transcribed by `scripts/level9_cache_recover.py`, and every artefact it
writes carries a `recovered_from_stdout` flag. The 1845 record run log is the
authentic artefact of the same run and is unaffected.

## L7.8.8 The rate limit, measured rather than assumed

Every concurrency figure depends on the tier, which the API does not report.
`scripts/probe_rate_limit.py` infers it from behaviour.

| requests | concurrency | elapsed | succeeded | refused | achieved rpm | mean latency |
| --- | --- | --- | --- | --- | --- | --- |
| 12 | 6 | 5.0 s | 12 | 0 | 143.9 | 2.40 s |
| 60 | 20 | 8.0 s | 60 | 0 | 449.7 | 2.49 s |
| 150 | 50 | 12.4 s | 150 | 0 | 728.7 | 3.58 s |

**No refusal at any point, 222 requests in total.** The free tier for
`gemini-2.5-flash` is 10 requests per minute, so this key is definitively not
on it. 728.7 rpm is a floor rather than a ceiling: the limit was never
reached. Latency is flat to concurrency 20 and begins to climb by 50, which
is the first sign of queueing and the reason the recommendation below stops
at 25.

These trivial prompts return in about 2.5 s. The reasoning prompts in the
real run average **8.927 s**, so per call latency in the budget is taken from
the run and not from the probe.

## L7.8.9 Level 8 and Level 9, re-budgeted

A pass costs three model calls per signal, because every arriving signal
triggers an analysis and every analysis runs its three iteration budget. The
full suite is 8832 signals and therefore 26496 calls per pass. At the
measured 8.927 s serially that is 65.7 hours for a single pass, which is why
the plan's Level 8 budget of 8 hours and its Level 9 shape were both
unreachable.

Two corrections to the plan's arithmetic. The four evidence regimes are
already inside the suite, so the plan's additional factor of four in Level 9
is double counting and is dropped. Against that, `graph_convergence_threshold`
must now be swept, which the plan did not budget for; three values are
assumed below.

    calls        = 3 * signals * passes
    uncached     = calls * (1 - hit_rate)
    wall_seconds = max(uncached * latency / concurrency, uncached / rpm * 60)

Wall clock in hours, at the measured hit rate of 0.9092 and, in brackets, at
a pessimistic 0.70 chosen because it is the worst single switch measured.

| per regime | scenarios | situations | seeds | concurrency | Level 8 | Level 9 |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 20 | about 33 | 5 | 25 | 0.20 (0.65) | 3.16 (10.43) |
| **10** | **40** | **66** | **5** | **25** | **0.39 (1.30)** | **6.31 (20.85)** |
| 15 | 60 | 102 | 5 | 25 | 0.59 (1.96) | 9.47 (31.28) |
| 25 | 100 | about 170 | 5 | 25 | 0.99 (3.26) | 15.78 (52.13) |
| 50 | 200 | about 340 | 5 | 50 | 0.99 (1.63) | 15.78 (26.07) |
| 100, full suite | 400 | 625 | 3 | 50 | 1.18 | 18.93 (not measured) |

**Recommended: 10 scenarios per regime, 40 scenarios, 66 situations, 5 seeds,
concurrency 25.** Level 8 lands at 0.39 hours and Level 9 at 6.31 hours
against targets of 6 and 24. It is the largest configuration that still fits
both targets if the hit rate turns out to be 0.70 rather than 0.9092, where
it costs 1.30 and 20.85 hours. The full suite fits on the measured rate but
only at 3 seeds and concurrency 50, and it has no margin at all if the rate
falls, so it is not recommended.

The sub-suite is frozen accordingly by `scripts/level9_subsuite.py`, which
verifies the parent against the L7.1 hash before drawing and refuses
otherwise. It samples uniformly without replacement within each regime rather
than taking a prefix, because the suite is written regime by regime in
scenario id order and a prefix samples the generator's early state.

| property | value |
| --- | --- |
| sub-suite hash | `a2b37f29b163ea310586f3073e88bddd5f0628667ba0c0595ddfa88d708c3911` |
| parent hash | `52b89293...f0efc`, verified |
| seed | 42 |
| scenarios | 40, ten per regime |
| signals | 963 |
| situations under entity grouping | 66 |
| abstained signals | 220 |

**One thing the budget assumes that does not exist.** Every figure at
concurrency above 1 requires a concurrent driver. `OfflineReplay` is strictly
serial, and at concurrency 1 nothing in the grid fits: the smallest
configuration is 47 hours for Level 9. Building concurrent execution into the
Level 8 and Level 9 drivers is therefore a prerequisite for both, and is not
optional work that can be deferred.

**Statistical power given up.** Estimating any single rate:

| scope | n | 95 per cent interval half width at p = 0.5 |
| --- | --- | --- |
| full suite, overall | 625 | 0.039 |
| full suite, per regime | 156 | 0.078 |
| sub-suite, overall | 66 | 0.121 |
| sub-suite, per regime | 16 | 0.245 |

Per regime cells become nearly uninformative in isolation, at plus or minus
24 points, and the headline four cell table crossing the unknown attack
regime with the sensor reject option will rest on about 16 situations per
cell. That must be stated in the paper rather than implied.

The loss is smaller than those figures suggest for the comparisons the
ablation actually makes. Every configuration runs the same frozen situations,
so differences between configurations are paired rather than independent, and
the variance that matters is the variance of the per situation difference.
Main effects of the four switches remain detectable where they are large.
Interactions will not be, and the plan's instruction to report interactions
only if the data supports it should be read strictly.

## L7.8.10 What this establishes and what it does not

Established. The real path exists, is documented and is reproducible. Three
findings previously flagged provisional now hold against `gemini-2.5-flash`:
the convergence threshold is unreachable and the real ceiling is lower than
the mock's; termination is always by iteration exhaustion; and the cache
reuse that Level 9 depends on is real at 0.9092 rather than a mock artefact.
The rate limit is measured, the tier is not free, and both levels have a
budget resting on measurement.

Not established. Reasoning quality, still, and now for a sharper reason than
in L7.7: the scorer cannot recognise a correct real hypothesis, so
`correct_conclusion_rate` and `false_conclusion_rate` on the real path are not
yet meaningful. The seven situation slice is too small for any rate quoted in
L7.8.4 to be a population estimate. The 0.9092 hit rate is measured over four
switches on four scenarios with the threshold held constant, and the
threshold sweep's effect on it is unmeasured, though sweeping downward should
if anything raise it because earlier termination reuses prefixes already
cached.

The next action is not Level 8. It is replacing or validating the scorer,
because Level 9's primary outcome depends on it, and building concurrent
execution, because every budget above depends on that.

---

# Appendix L7.9. A rejected scorer and a concurrent driver

Two prerequisites for Level 8 were attempted. The second succeeded. The first
did not, and the reason it did not corrects a claim made in L7.8.

## L7.9.1 Correction to L7.8.5

L7.8.5 reported that the keyword scorer returns no match on 7 of 7 real
analyses and concluded that it "is not merely deflating a rate, it is not
discriminating at all on the axis it exists to measure". That conclusion does
not follow from that statistic, and the statistic is misleading.

Keyword matching is consulted on **2 of the 7 situations**, not 7.
`scoring.py:159` reaches for `matched_expected` only when the ground truth
says conclude. The other five carry `should_conclude` false, where
`correct = abstained` at `scoring.py:161` and no keyword is read. Two of
those five, the sparse and unknown attack scenarios, carry empty keyword
lists by construction, so `matched_expected` is false for them whatever any
scorer does.

On the two where it is consulted it was right. Both belong to `s00000`, whose
ground truth is `data_exfiltration`. The dominant hypotheses were:

    Persistent external reconnaissance from a limited set of distinct sources.
    Sustained external reconnaissance from multiple distinct sources.

That is reconnaissance. The model proposed the wrong narrative, and a scorer
reporting no match against data exfiltration is reporting correctly.

The underlying worry remains legitimate: a keyword list will under credit a
correct hypothesis that reaches for different vocabulary, and Level 9 needs a
scorer that survives that. But the evidence in L7.8 did not demonstrate it
happening, and L7.8.5 should have said so.

## L7.9.2 The embedding scorer, built and rejected

`scenarios/semantic.py` embeds a prose narrative for each of the six
categories and the hypothesis text with `all-MiniLM-L6-v2`, pinned alongside
`sentence-transformers` 5.1.0 and `torch` 2.8.0+cpu, and compares them by
cosine. The narratives were written from the `Category` definitions, their
names, keyword lists and detector families, and not by reading model output,
which would have tuned the scorer to the thing it was meant to judge. Their
content hash is recorded so a change is detectable.

**The validation set.** Fifty distinct hypothesis texts were drawn from the
real model run, stratified across its seven situations, and hand labelled by
a single annotator before the scorer was run. The question asked of each was
which of the six narratives the text describes, if any, judged on the text
alone. A category was assigned only where the text describes that category's
defining action: reconnaissance is scanning or enumeration, lateral movement
is moving between internal systems rather than merely being present on
several, exfiltration is data leaving rather than internal transfer.
Rationale is recorded against the ten arguable cases. There is no second
annotator and therefore no agreement figure.

The labels came out at 16 positives and 34 negatives, and every positive is
`reconnaissance_sweep`. That is not a sampling accident. Across the whole
four scenario slice the model never once proposed brute force access,
physical intrusion, service denial, lateral movement or data exfiltration by
name. **Five of the six categories have no positive instance in real model
output at all**, which is a limitation on everything below and a finding in
its own right.

**The evaluation.** In use the scorer is always asked about one specific
category: does this hypothesis describe the narrative this scenario expects.
The evaluation mirrors that. Each of the 50 hypotheses is paired with each of
the 6 categories, giving 300 decisions, each a positive exactly when the hand
label names that category.

| threshold | TP | FP | FN | TN | precision | recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.20 | 15 | 154 | 1 | 130 | 0.0888 | 0.9375 | 0.1622 |
| 0.25 | 12 | 90 | 4 | 194 | 0.1176 | 0.7500 | 0.2034 |
| 0.30 | 9 | 43 | 7 | 241 | 0.1731 | 0.5625 | 0.2647 |
| 0.35 | 7 | 20 | 9 | 264 | 0.2593 | 0.4375 | 0.3256 |
| **0.36, best F1** | 7 | 17 | 9 | 267 | **0.2917** | **0.4375** | **0.3500** |
| 0.40 | 4 | 8 | 12 | 276 | 0.3333 | 0.2500 | 0.2857 |
| 0.50 | 1 | 2 | 15 | 282 | 0.3333 | 0.0625 | 0.1053 |
| 0.60 | 0 | 0 | 16 | 284 | 0.0000 | 0.0000 | 0.0000 |

**Best achievable precision 0.2917 and recall 0.4375, against a required
0.70 on both.** The keyword scorer on the identical 300 decisions scores
**precision 0.8125 and recall 0.8125**.

The brief said to stop rather than ship a scorer below 0.7, and that a second
broken scorer is worse than a known missing one. The embedding scorer is
therefore **not adopted**. It remains reachable behind `--scorer embedding`
so the result stays reproducible.

## L7.9.3 Why it fails, concretely

The failure is not that similarity carries no signal. Against the
reconnaissance narrative alone the positives separate from the negatives:
positives median 0.323 against a negative maximum of 0.277. The failure is
that a general sentence embedding places benign systems prose and all six
attack narratives within a narrow band of each other, so any threshold loose
enough to catch true matches also fires against five wrong categories.

Applied to the real run, the rejected scorer moves two metrics:

| metric | keyword | embedding |
| --- | --- | --- |
| correct_conclusion_rate | 0.2857 | **0.4286** |
| false_conclusion_rate | 0.7143 | **0.5714** |
| every other metric | unchanged | unchanged |

It looks like an improvement and is not. The situation it flips is one of the
two `s00000` situations, and this is the whole mechanism:

| text | similarity |
| --- | --- |
| "Persistent external reconnaissance from a limited set of distinct sources." | |
| to the data exfiltration narrative | **0.3118**, clears the 0.27 threshold |
| to the reconnaissance narrative | 0.3542, higher still |

The scorer credits a hypothesis about reconnaissance as data exfiltration and
records the analysis as correct. The entire gain is spurious credit for a
wrong answer, which is precisely the failure mode the instruction to stop
below 0.7 exists to prevent.

An earlier implementation required the expected category to be the closest of
all six, which removes this particular error. It was worse overall, because
requiring an outright win costs far more recall than it buys precision, and
it is recorded in the sweep as `argmax_recall`.

## L7.9.4 What would be needed instead

Not an LLM judge as the primary scorer, for the reasons the brief gives. What
this result actually points at is that the six narratives are too close
together for a general purpose embedding at this granularity, and that the
evidence for any scorer is thin while five of six categories have no positive
instance.

Three things would change the picture, in order of cost: a domain tuned
embedding rather than a general one; a labelled set drawn from a run in which
the model proposes more than one narrative, which needs Level 8 or 9 output
rather than a four scenario slice; and only then a judge panel, used to
validate whichever mechanical scorer is chosen rather than to replace it.

Until one of those exists, **keyword matching remains the scorer**, and the
caveat recorded in L7.7 stands: the correct conclusion rate it reports is a
lower bound.

## L7.9.5 The concurrent driver

`enigma_reason/replay/concurrent.py` runs replay units in a thread pool, one
independent `OfflineReplay` per unit with its own store, engine and
correlation state. Shared collaborators are the response cache and the run
log writer, both of which hold locks.

**A unit is one scenario, and that choice is deliberate.** The brief asked
for concurrency over situations rather than over iterations, because an
analysis's iterations are sequentially dependent. A scenario is one step
coarser than a situation and is the smallest boundary at which splitting
changes nothing: a situation's analyses are ordered by signal arrival, and
the situations within a scenario share the ingest counter that decides when
an analysis fires. Splitting below the scenario would change when analyses
happen. Splitting at the scenario cannot, because scenarios share no state.

`--concurrency` defaults to 1, and at 1 the driver is bypassed entirely so
existing serial runs reproduce exactly rather than merely equivalently.

## L7.9.6 The cache was safe against corruption and not against waste

`ResponseCache` already held a lock over its entries and its counters, so
concurrent readers and writers could not corrupt the store. That was checked
rather than assumed and it held.

What it did not have was single flight. Two workers missing the same prompt
at the same moment both called the model, and both paid for one answer. A
fill now takes a per prompt lock, re-checks the store under it without
counting the re-check, and a caller served by another worker's fill is
recorded as `coalesced` rather than as a second miss. Four tests cover it,
including eight threads released simultaneously on one prompt, which produce
exactly one model call and seven coalesced hits.

## L7.9.7 Determinism across concurrency

Two runs of the frozen sub-suite at seed 42, through the Level 6
deterministic mock so that any difference is the driver rather than model
sampling.

| concurrency | analyses | iterations | distinct situations | retries | wall clock |
| --- | --- | --- | --- | --- | --- |
| 1 | 963 | 2889 | 66 | 0 | 42.5 s |
| 25 | 963 | 2889 | 66 | 0 | 28.3 s |

**The sorted analysis signatures are identical.** A signature is built per
situation from every analysis that terminated, carrying the evidence held,
the iteration reached, the reason it stopped, whether UNKNOWN led, and the
convergence score. Situation identifiers are freshly generated uuids and
differ between any two runs, so they are used only to group records and never
enter the signature. Comparing these sorted removes every ordering effect
concurrency introduces while preserving anything a difference in work would
change. An earlier version of this check included the uuid in the key and
reported a false mismatch across all 963 analyses, which is what the first
run of it did.

The 1.5x speedup here is not the interesting number. The mock does no
network wait, so the work is CPU bound and the interpreter lock caps what
threads can buy. The real measurement is below.

## L7.9.8 Measured throughput, and the floor nobody budgeted for

Eight scenarios of the sub-suite against live Gemini at concurrency 25, with
a cold cache so every call is real.

| quantity | value |
| --- | --- |
| units | 8 scenarios |
| model calls | 534 |
| cache hits | 3, rate 0.0056, a cold cache as intended |
| retries | **0**, no throttling at this concurrency |
| wall clock | 1353.6 s |
| wall clock per call | 2.535 s |
| serial equivalent at 8.927 s per call | 4767 s |
| **effective parallelism** | **3.52, not 25** |

The shortfall is entirely explained, and the explanation is the finding. The
eight units were 150, 108, 108, 72, 60, 27, 6 and 6 calls. A unit runs on one
worker, so the run cannot finish before its longest unit does. That critical
path is 150 calls at 8.927 s, or **1339 s. The run took 1353.6 s, within 1.1
per cent of it.** Work divided by concurrency would have predicted 190 s. The
critical path, not the concurrency, set the wall clock.

The budget model in L7.8.9 had two floors, work over concurrency and the
tier's requests per minute. It now has three, and `level9_budget.py` takes
the longest unit as a parameter.

    wall = max(uncached * latency / concurrency,
               uncached / rpm * 60,
               longest_unit_calls * (1 - hit_rate) * latency)

**What this changes for Level 9.** If the driver is handed one pass at a time
it pays the critical path once per pass, and Level 9 costs 12.16 hours at
concurrency 25 and exactly the same at concurrency 50, because concurrency
has stopped being the binding constraint. If it is handed the whole cross
product of configuration, seed and scenario as one pool of units, there are
9600 of them, the critical path is one scenario rather than one pass, and
Level 9 costs 6.31 hours at concurrency 25.

Concurrency is therefore not sufficient on its own. **The driver must be fed
the cross product**, and `--cross-product` in the budget script records which
assumption a figure was produced under.

## L7.9.9 Revised budget

Measured inputs: 8.927 s per call serially, 0.9092 pooled cache hit rate,
728.7 requests per minute with no refusal, longest sub-suite unit 225 calls,
zero retries observed at concurrency 25.

| per regime | scenarios | situations | seeds | concurrency | Level 8 | Level 9 |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 20 | 33 | 5 | 25 | 0.20 | 3.16 |
| **10** | **40** | **66** | **5** | **25** | **0.39** | **6.31** |
| 15 | 60 | 102 | 5 | 25 | 0.59 | 9.47 |
| 25 | 100 | 170 | 5 | 25 | 0.99 | 15.78 |
| 50 | 200 | 340 | 5 | 25 | 1.97 | 31.56, over |
| 100, full suite | 400 | 625 | 5 | 25 | 3.94 | 63.12, over |

The recommendation from L7.8.9 is unchanged: **ten scenarios per regime, 40
scenarios, 66 situations, five seeds, concurrency 25**, which is the largest
configuration that still fits both targets at a pessimistic 0.70 hit rate.
Sub-suite hash `a2b37f29b163ea310586f3073e88bddd5f0628667ba0c0595ddfa88d708c3911`.

Two caveats on it. Every figure assumes cross product scheduling, which the
driver supports but the Level 8 and Level 9 scripts must actually use. And
the zero retries observed is at concurrency 25 over 534 calls; the retry path
is covered by tests rather than by having been exercised in anger, and a
throttled run will now be visible in the run log rather than merely slow.

## L7.9.10 What these two tasks establish

Established. The concurrent driver exists, is deterministic against the
serial one on sorted analysis signatures, and is measured rather than
projected. The response cache is single flighted. The critical path floor is
identified, quantified to within 1.1 per cent, and folded into the budget.
Level 8 and Level 9 are affordable at the recommended sample size.

Not established, and now clearer than before. The project still has no
validated way to tell whether a free text hypothesis matches a ground truth
narrative other than keyword matching, whose limits L7.7 recorded and which
this work did not improve on. The embedding scorer was built, validated at
precision 0.2917 and recall 0.4375 against 0.8125 and 0.8125 for keyword
matching, and rejected. `false_conclusion_rate` remains a Level 9 primary
outcome resting on the weaker of the two mechanisms, and the correction in
L7.9.1 means the case for replacing it is a prior argument rather than a
measured failure.

---

# Appendix L8. The clock domain study

A reproducibility hazard for replay based intrusion detection evaluation,
demonstrated at scale against a real model. The claim is not about a defect
in this system. It is that any temporal reasoning layer which evaluates
staleness in host time while ingesting archived events will silently convert
every replayed situation into a quiescent one, and that this collapses trend
detection to a near constant and drives the reasoner into abstention. The
system studied here is the instrument, not the subject.

## L8.1 The gate: event time must actually survive into the suite

The hazard only exists where event time and wall clock disagree, so the first
thing checked was whether they do. L2.2 recorded that the official UNSW-NB15
partition carries no Stime or Ltime, which means a replay of it stamps every
signal with ingest time and separated mode degenerates into wall mode: there
is nothing left to separate. A study run on such a suite would report three
identical configurations and the null would read as a finding.

`scripts/level8_clock_check.py` reads the frozen sub-suite and reports what
it carries.

| quantity | value |
| --- | --- |
| signals with an event timestamp | **963 of 963** |
| signals missing one | 0 |
| earliest event time | 2026-03-01T00:00:08.862Z |
| latest event time | 2026-03-01T00:22:56.677Z |
| event time span | 0.38 hours |
| gap from latest event to wall clock | **4864.05 hours, 202.67 days** |
| per scenario span, median | 458 s |
| per scenario span, maximum | 1359 s |

The generator's timestamps are genuine and sit more than two hundred days
behind the clock the study ran at, so conflating the two is demonstrable on
this suite. No fallback to the raw four partition files was needed.

Note the two scales, because both matter. Between scenarios the events are
two hundred days stale, which is what a conflated clock sees. Within a
scenario they span minutes, which is what trend detection needs in order to
have anything to detect.

## L8.2 Scheduling, and the critical path confirmed a third time

The grid is three clock modes by five seeds by forty scenarios, 600 units.
L7.9.8 established that a unit runs on one worker and that wall clock is
floored by the longest unit, so feeding a driver one pass at a time pays that
floor once per pass. All 600 units were scheduled as a single pool.

| quantity | value |
| --- | --- |
| units | 600 |
| model calls if every one missed | 43335 |
| longest single unit | 225 calls |
| predicted critical path | 2009 s |
| predicted work over concurrency, at 40 | 9671 s |
| **actual wall clock** | **1980 s, 0.55 h** |
| actual against predicted critical path | **ratio 0.99** |

The run finished in the time its longest unit takes, to within one per cent.
That is the third independent confirmation of the critical path model, after
the 1.1 per cent agreement recorded in L7.9.8 and the budget it produced.

Caches are scoped per seed rather than shared across the grid. The prompt a
situation assembles does not depend on the seed, so a cache shared across
seeds would serve seed 42's responses to every later seed and the deviation
across five seeds would be zero by construction rather than because the model
is stable. The deviations reported below are therefore real.

| quantity | value |
| --- | --- |
| cache hits | 38604 |
| cache misses | 4731 |
| hit rate | **0.8908** |
| units failed | 0 |
| retries | 0 |
| fallback iterations | **0 of 43335** |

The hit rate of 0.8908 sits just below the 0.9092 measured per switch in
L7.8.7 and well above the 0.31 floor L6.8 stated, so the reuse Level 9
depends on holds across clock modes as well as across epistemic switches.

## L8.3 Two defects the study found by being run

**The replay engine never received its clock mode.** `OfflineReplay` built
its `ReasoningEngine()` with no arguments, so the engine sat at the
`SEPARATED` default while the `SituationStore` beside it took the configured
mode. Every analysis in conflated or wall mode therefore raised the clock
mode mismatch guard that Level 2 added for exactly this: two components
disagreeing about the time domain. The guard worked. Nothing had exercised it
because nothing had run a replay in a non default mode until this study.

**A dropped connection fell through to the fallback hypotheses.** The retry
predicate matched throttling, 429 and quota and 503, but not the Gemini
client's "Server disconnected without sending a response". Such a call was
re-raised on the first attempt, caught by the generation node as it is built
to be, and three fixed strings from `nodes.py:200-202` were substituted with
only a log line to mark it. The first full attempt at this study accumulated
**25 contaminated iterations** across three cells before it was stopped. The
predicate is now `looks_transient` and covers dropped connections, resets,
timeouts and 502, 503 and 504, and the study counts fallback iterations in
its own output so contamination can never again be something a reader has to
go looking for. The run reported above carries zero.

## L8.4 The collapse

Pooled across five seeds, share of iterations carrying each trend label.

| clock mode | escalating | stable | deescalating | distinct labels |
| --- | --- | --- | --- | --- |
| conflated | 0.0602 | **0.0000** | **0.9398** | **2** |
| wall | 0.1350 | 0.8266 | 0.0384 | 3 |
| separated | 0.1298 | 0.6272 | 0.2430 | 3 |

**Under conflation the stable label is never emitted at all**, and 94 per
cent of iterations are de-escalating. Trend detection has not degraded, it
has stopped: the label is a near constant carrying no information about the
situation it describes.

The mechanism is visible one step earlier.

| clock mode | quiet detected | standard deviation |
| --- | --- | --- |
| conflated | **1.0000** | 0.0000 |
| wall | 0.0000 | 0.0000 |
| separated | 0.2098 | 0.0000 |

Every situation in conflated mode is quiet, in all five seeds, because every
situation's most recent event is two hundred days old when measured against
the host clock. A permanently quiet situation is a permanently de-escalating
one, and the trend label follows.

This reproduces at scale, against a real model, what L2.1 predicted from 400
synthetic signals.

## L8.5 What that does to the reasoner

All eight Level 7 outcome metrics, mean and standard deviation over five
seeds, 66 situations per cell.

| metric | conflated | wall | separated |
| --- | --- | --- | --- |
| correct_conclusion_rate | **0.5000 ± 0.0303** | 0.2182 ± 0.0264 | 0.2182 ± 0.0264 |
| false_conclusion_rate | 0.4485 ± 0.0312 | 0.7788 ± 0.0281 | 0.7788 ± 0.0281 |
| abstention_rate | **0.5273 ± 0.0113** | 0.1818 ± 0.0192 | 0.1818 ± 0.0192 |
| appropriate_abstention_rate | 0.6826 ± 0.0174 | 0.2565 ± 0.0254 | 0.2565 ± 0.0254 |
| inappropriate_abstention_rate | **0.1700 ± 0.0400** | 0.0100 ± 0.0200 | 0.0100 ± 0.0200 |
| premature_convergence_rate | 0.2212 ± 0.0121 | 0.5182 ± 0.0177 | 0.5182 ± 0.0177 |
| single_iteration_conclusion_rate | 0.0000 | 0.0000 | 0.0000 |
| mean_iterations_to_termination | 3.0000 | 3.0000 | 3.0000 |

Read carelessly this says conflation is good for the system. Correct
conclusions rise from 0.22 to 0.50, false conclusions fall from 0.78 to 0.45,
premature convergence more than halves. **Every one of those movements is an
artefact of abstaining more often on a suite whose ground truth mostly says
abstain**, and the per regime breakdown shows it.

| regime | truth says | conflated correct | separated correct |
| --- | --- | --- | --- |
| clear | conclude | **0.080** | **0.130** |
| ambiguous | abstain | 0.800 | 0.080 |
| sparse | abstain | 1.000 | 1.000 |
| unknown_attack | abstain | 0.338 | 0.013 |

On the one regime whose ground truth requires a conclusion, conflation makes
the system **worse**, 0.080 against 0.130. On the three that reward
abstention it scores better because it abstains, and in every one of those
three the correct conclusion rate equals the abstention rate exactly, because
`correct = abstained` at `scoring.py:161` when the truth says abstain.

Conflation does not improve the reasoner. It disables it, and three quarters
of this suite rewards a disabled reasoner. Inappropriate abstention, the one
metric that penalises abstaining, is seventeen times higher under conflation:
0.1700 against 0.0100.

## L8.6 Wall and separated agree on every outcome, and that is informative

The two non conflated modes produce identical outcome metrics to four decimal
places, seed by seed, which is not a coincidence and is not a defect. They
are genuinely different runs:

| quantity | wall, seed 42 | separated, seed 42 |
| --- | --- | --- |
| quiet iterations | 0 of 2889 | **606 of 2889** |
| trend, stable | 2388 | 1812 |
| trend, deescalating | 111 | 702 |
| distinct hypothesis texts | 7030 | 7269 |
| texts unique to this mode | 1292 | 1531 |

Different prompts, different hypotheses, same conclusions. The explanation is
that the outcome metrics turn on whether UNKNOWN leads at termination, and a
21 per cent quiet fraction does not flip that on any of the 66 situations,
while a 100 per cent quiet fraction flips many. **Quiescence acts on the
reasoner like a threshold rather than a gradient.** That is worth stating
because it bounds the hazard: a replay whose events are merely somewhat stale
is not affected, and a replay whose events are uniformly stale is destroyed.

## L8.7 Hypothesis diversity, which refutes an earlier worry and raises another

L7.9.2 recorded that across the seven situation slice the model named
positive instances of exactly one of the six categories, and warned that a
sample that small cannot distinguish a narrow model from a narrow sample.
With 151713 hypotheses examined across 990 scored situations, the answer is
clear.

| category | times named | times dominant |
| --- | --- | --- |
| reconnaissance_sweep | 41586 | 19561 |
| data_exfiltration | 5820 | 1363 |
| lateral_movement | 3340 | 262 |
| brute_force_access | 380 | 46 |
| service_denial | 66 | 8 |
| physical_intrusion | 33 | 0 |

**All six of six are named.** The single category result in L7.9.2 was sample
size, and that worry is withdrawn.

What replaces it is worse. The share each category takes, computed within
each regime:

| regime | reconnaissance | exfiltration | lateral | brute force | denial | physical |
| --- | --- | --- | --- | --- | --- | --- |
| clear | **81.6%** | 10.9% | 6.8% | 0.6% | 0.1% | 0.0% |
| ambiguous | **80.4%** | 11.4% | 6.9% | 1.0% | 0.2% | 0.0% |
| sparse | **80.9%** | 15.8% | 0.0% | 1.2% | 0.0% | 2.0% |
| unknown_attack | **81.6%** | 11.7% | 6.0% | 0.5% | 0.1% | 0.1% |

The four regimes are built to carry different evidence and to expect
different answers. The distribution of narratives the model proposes is
**invariant across them**, reconnaissance taking between 80.4 and 81.6 per
cent in every one. The model's choice of narrative is not a function of the
regime it is looking at.

Of the two explanations L7.9.2 set up, this is the second: the regimes
produce evidence signatures the model does not distinguish. It is not prompt
steering toward a single family, because five other families are named, in
stable proportions, everywhere.

**This bears directly on what Level 9 can measure.** If the narrative the
model proposes is independent of the regime, then any metric built on whether
that narrative matches the ground truth is measuring a near constant, and the
2^4 ablation cannot move it. `correct_conclusion_rate` and
`false_conclusion_rate` are already the two metrics L7.9 could not validate a
scorer for. This is a second, independent reason to doubt them, and it
arrives before Level 9 rather than after.

## L8.8 The generalisable hazard

Stated without reference to this system.

A streaming reasoning layer that assesses situations over time needs two
clocks: the time at which evidence occurred, and the time at which the
assessment is being made. Staleness, quiescence, rate and trend are all
defined as differences between them. Implementations routinely take the
second from the host clock, because in production the two are within seconds
of each other and the distinction is invisible.

Under replay the distinction is everything. An archived capture is hours,
months or years old. A layer that compares archived event time against the
host clock finds every situation uniformly ancient, marks all of them quiet,
and reports a single trend label for the entire corpus. Nothing raises an
error. The layer produces confident, well formed, entirely uninformative
temporal features, and every downstream consumer inherits them.

Three properties make this hazard worth naming rather than filing as a bug.

**It is silent.** No exception, no warning, no missing field. The collapse is
only visible if the distribution of trend labels is inspected, and a trend
label that is constant looks exactly like a system that has decided the
traffic is calm.

**It inverts under the obvious metric.** In this study conflation raised
correct conclusions from 0.22 to 0.50 and halved premature convergence. An
evaluation reporting only those numbers would conclude that the broken
configuration was the better one. The error is only visible per regime, on
the subset whose ground truth requires a conclusion, where conflation is
worse.

**It has a threshold, not a gradient.** Partial staleness does nothing: the
21 per cent quiet fraction of separated mode leaves every outcome metric
identical to wall mode. Uniform staleness destroys everything. A pilot on
recent data will therefore show no problem at all, and the failure appears
only when the corpus is old enough that every situation crosses the quiet
threshold together.

The mitigation is cheap and is what Level 2 implemented: make the time domain
an explicit parameter, evaluate staleness in the same domain the evidence
carries, and assert that the components agree. The assertion is what caught
the defect in L8.3, in this very study, eleven months after it was written.

## L8.9 What this establishes and what it does not

Established. Event timestamps survive into the frozen sub-suite with a 202
day gap to wall clock. Conflating the domains eliminates one of three trend
labels entirely, marks 100 per cent of situations quiet against 0 and 21 per
cent for the two honest modes, and raises abstention from 0.18 to 0.53. The
apparent improvement in five of eight outcome metrics is an abstention
artefact, demonstrated by the clear regime where conflation is worse. Five
seeds, real model, zero contamination, deviations under 0.04 throughout.

Not established. Whether the hazard behaves the same way on a corpus whose
staleness is non uniform, which is the interesting intermediate case and
which this suite cannot produce because its scenarios share a generation
window. Whether the outcome metrics mean anything at all, given L7.9's
unvalidated scorer and L8.7's finding that the model's narrative choice is
independent of regime. And the absolute level of every rate here, which rests
on 66 situations, not on the 625 of the full suite.

Figure 2 is `figures/fig2_clock_collapse.pdf`. Panel A is the trend
distribution as the plan specified. Panels B and C are not what the plan
specified, because both quantities it named are constant: the convergence
fraction is 0.000 in all three modes and mean iterations to termination is
3.0 in all three, both for the reason L7.5 established and L7.8.6 confirmed,
and the mean final UNKNOWN confidence spans 0.509 to 0.512. Panel B instead
carries the mechanism, quiescence against abstention, and Panel C the
consequence, false conclusion and premature convergence against appropriate
abstention.

---

# Appendix L8.1. Level 9 preparation: diagnosis, scoping and budget

Written before Level 9 runs. The metric set in L8.1.4 is declared in advance
and not revised afterwards, on the same discipline as the pre-registered
SMOTE criterion in L3.6.

## L8.1.1 Why the narrative share is invariant

L8.7 measured that the share of narratives Gemini proposes is invariant
across the four evidence regimes, 80.4 to 81.6 per cent reconnaissance in
every one. Three causes were candidates: the prompt template steering toward
one family, the generator failing to produce distinguishable evidence, or the
information barrier leaving the model nothing to discriminate on.

The contexts were captured by wrapping `assemble_context` for an offline
replay of the sub-suite, so what is analysed is exactly what the model was
handed rather than a reconstruction. The replay used a factory that raises,
which costs no model calls, because context assembly runs before generation
and is unaffected by generation failing. 2889 contexts, 40 scenarios.

Each field was tested univariately, Kruskal-Wallis across the four regimes
for the continuous fields and a chi-square test of independence for the
categorical ones, each with an effect size, because at this many records a
p-value alone calls a difference of no consequence significant. The floors
were epsilon squared at 0.01 and Cramer's V at 0.10, with alpha 0.01.

| field | test | p | effect | separates |
| --- | --- | --- | --- | --- |
| evidence_count | Kruskal-Wallis | 2.1e-45 | 0.072 | yes |
| event_rate_per_minute | Kruskal-Wallis | 7.0e-08 | 0.011 | yes |
| active_duration_seconds | Kruskal-Wallis | 1.6e-33 | 0.053 | yes |
| confidence_level | Kruskal-Wallis | 4.2e-115 | 0.184 | yes |
| source_diversity | Kruskal-Wallis | 1.7e-79 | 0.127 | yes |
| mean_anomaly_score | Kruskal-Wallis | 0.0 | **0.654** | yes |
| iteration | Kruskal-Wallis | 1.0 | 0.000 | no |
| burst_detected | chi-square | 2.0e-17 | 0.167 | yes |
| quiet_detected | chi-square | 2.6e-15 | 0.157 | yes |
| trend | chi-square | 4.4e-42 | 0.190 | yes |

Nine of ten separate. A random forest over the whole vector reaches accuracy
0.6867 ± 0.0398 against a majority class base rate of 0.3988, a lift of
+0.288. **Candidate C as originally put is refuted: the barrier is not
starving the model.**

That test, however, asks the wrong question, and noticing why is the finding.
The four regimes describe how *sufficient* the evidence is, not *which
attack* it is. A scenario in the clear regime may be about exfiltration or
about brute force; the regime does not say. The invariance L8.7 measured is
about narrative identity, so narrative identity is what has to be tested.

Repeating the multivariate test with the scenario's narrative category as the
target, restricted to the 20 scenarios that have one, and cross validating by
`GroupKFold` so that no scenario ever spans folds:

| target | classes | accuracy | base rate | lift |
| --- | --- | --- | --- | --- |
| regime, four levels | 4 | 0.6867 ± 0.0398 | 0.3988 | **+0.288** |
| narrative category | 6 | 0.1328 ± 0.0992 | 0.2378 | **−0.105** |

A classifier with unrestricted access to all ten fields predicts the
narrative **worse than always guessing the most common one**.

**Candidate C, refined, is established.** The context separates the regimes
and carries no usable signal for which narrative applies. The model can tell
a sparse situation from a clear one and cannot tell exfiltration from
reconnaissance, so it falls back to a prior, and that prior is the invariant
81 per cent. A and B are moot for hypothesis content: no prompt can extract
an identity the context does not contain, and however distinguishable the
underlying signals are, the barrier does not pass it.

## L8.1.2 The proposed widening cannot work, and was not run

Task 2 proposed widening the context with the distribution of
`Signal.signal_type`, then running one configuration to convert the
observation into a causal claim. That widening was tested offline before any
model call was spent on it, and it fails.

`signal_type` is not derived from the scenario's narrative. Signals are
produced as raw detector payloads and routed through the adapters, so the
type reflects the adapter's normalisation of a detector family. The result is
not merely uninformative but actively misleading:

| scenario narrative | anomalous_access | data_exfiltration | intrusion | reconnaissance |
| --- | --- | --- | --- | --- |
| brute_force_access | 0.364 | 0.000 | 0.636 | 0.000 |
| data_exfiltration | 0.099 | 0.682 | 0.220 | 0.000 |
| lateral_movement | 0.315 | 0.213 | 0.472 | 0.000 |
| physical_intrusion | 0.389 | 0.000 | 0.130 | **0.481** |
| reconnaissance_sweep | 0.000 | **0.611** | 0.157 | 0.232 |
| service_denial | 0.277 | 0.400 | 0.253 | 0.071 |

Reconnaissance scenarios carry 61 per cent data exfiltration signals, and
physical intrusion scenarios carry 48 per cent reconnaissance signals.

Measured on the same group aware protocol:

| feature set | accuracy | base rate | lift |
| --- | --- | --- | --- |
| signal_type shares | 0.1500 ± 0.1458 | 0.2750 | −0.1250 |
| source shares | 0.1000 ± 0.0935 | 0.2750 | −0.1750 |
| both together | 0.1000 ± 0.0935 | 0.2750 | −0.1750 |

Every candidate is worse than guessing. Running the widening would have cost
model calls to demonstrate nothing, or worse, would have steered the model
toward the wrong narrative and been read as success.

The reason is structural and is worth recording, because it bounds what this
suite can ever measure. A `Category` is defined by its detector families and
its keywords. The detector signatures are:

| category | detectors |
| --- | --- |
| data_exfiltration | network_anomaly |
| service_denial | network_anomaly |
| brute_force_access | auth_anomaly |
| physical_intrusion | video_detection |
| reconnaissance_sweep | network_anomaly + video_detection |
| lateral_movement | network_anomaly + auth_anomaly |

**`data_exfiltration` and `service_denial` share an identical signature.** No
aggregate field derived from detectors, sources or signal types can separate
them, at any sample size, because there is nothing to separate. The narrative
lives only in the ground truth keywords, and exposing those is label leakage
by definition.

The honest conclusion is stronger than the one Task 2 sought. It is not that
the current context happens to be too narrow. It is that **on this suite, the
narrative a scenario is about is not recoverable from any aggregate the
information barrier could legitimately expose.**

## L8.1.3 What that means for the two conclusion metrics

Three independent findings now bear on `correct_conclusion_rate` and
`false_conclusion_rate`, and they compound rather than overlap.

L7.9 could not validate a scorer: keyword matching is the better of the two
tried, and the embedding scorer was rejected at precision 0.2917 against
0.8125. L8.7 found the model's narrative choice invariant to regime. L8.1.1
now shows why, and L8.1.2 shows it cannot be fixed by widening the context.

A metric that asks whether the named narrative matches the ground truth is,
on this suite, asking a question the system was never given the information
to answer. That is not a defect of the reasoner and it is not noise. It is a
property of the instrument.

## L8.1.4 The declared Level 9 metric set

Declared before the run. Three tiers.

**Primary outcomes, reported as the result.** These depend only on whether
the system concluded or abstained and on the evidence count at termination.
None consults a keyword, none depends on narrative identity, and all four
moved materially in the clock study.

| metric | why it is sound |
| --- | --- |
| abstention_rate | counts a decision, not a narrative |
| appropriate_abstention_rate | same, restricted to truth that says abstain |
| inappropriate_abstention_rate | same, restricted to truth that says conclude |
| premature_convergence_rate | evidence count against the sufficiency threshold, `scoring.py:168` |

**Dead at the current threshold, reported once and then excluded.**

| metric | value observed | across |
| --- | --- | --- |
| single_iteration_conclusion_rate | 0.0000 | 26496 mock, 128 real, 43335 clock study calls |
| mean_iterations_to_termination | 3.0000 | the same |

Both are pinned because the 0.8 convergence threshold is never reached. They
are excluded from the primary analysis, **and the threshold sweep in L8.1.5
is the test of whether they can be revived at all.** If they move at a lower
threshold they return as secondary outcomes; if they do not, the finding is
that the persistence and inertia mechanisms, not the threshold, are what
prevent convergence, which is itself a result.

**Compromised, reported with the caveat attached and never as a headline.**

| metric | status |
| --- | --- |
| false_conclusion_rate | depends on narrative matching, which L8.1.2 shows is unrecoverable on this suite |
| correct_conclusion_rate, on the sparse, ambiguous and unknown attack regimes | **sound**, because `correct = abstained` at `scoring.py:161` when the truth says abstain and no keyword is read |
| correct_conclusion_rate, on the clear regime | **unsound**, it is the only regime whose truth says conclude and therefore the only one where narrative matching is consulted |

The clear regime is 10 of the 40 scenarios. Its `correct_conclusion_rate`
will be reported separately and labelled unsound rather than pooled into an
overall figure that would inherit the problem silently. The overall figure
will be reported too, with this caveat referenced, because L8.5 showed how
easily a pooled conclusion rate misleads: conflation appeared to double it
while making the clear regime worse.

## L8.1.5 The convergence threshold as a swept parameter

`graph_convergence_threshold` becomes a swept parameter rather than the
constant 0.8 it has been since Level 2.

| value | rationale |
| --- | --- |
| 0.30 | below every ceiling measured, so convergence should become reachable |
| 0.50 | just above the observed ceilings of 0.385 in L7.8 and 0.4620 in the clock study |
| 0.80 | the current constant, carried as the control |

The three bracket the observed range rather than exploring beyond it, because
the question is whether the two pinned metrics can move at all, not where the
optimum lies.

## L8.1.6 Grid cost and the budget

Priced on measured throughput: 8.927 s per call, a requests per minute
ceiling of 728.7 with no refusal ever observed, concurrency 40, and the
sub-suite's 2889 calls per pass with a longest unit of 225 calls.

The cache rate is predicted structurally rather than assumed. Only S and A
alter the confidences printed into the next iteration's prompt; U and P
change no prompt, as L6.8 reasoned and L7.8.7 measured. The sixteen
configurations therefore collapse to **four distinct prompt families**, so
within a seed three quarters of the grid is served from cache. The threshold
behaves like U and P at the first iteration and can only shorten an analysis,
never lengthen it, so it adds no prompts of its own.

A predicted hit rate of 0.75 is used for budgeting, deliberately below the
0.9092 measured per switch in L7.8.7 and the 0.8908 measured in the clock
study, so the estimate is conservative.

| option | units | paid calls | predicted hours | fits 24 h |
| --- | --- | --- | --- | --- |
| **full factorial at every threshold** | **9600** | **173340** | **10.75** | **yes** |
| full factorial, threshold sweep at one seed | 4480 | 80892 | 5.01 | yes |
| threshold sweep on the all on configuration only | 600 | 10834 | 0.67 | yes |

**The full factorial at every threshold fits and is what will run**: 16
configurations by 3 thresholds by 5 seeds by 40 scenarios, 9600 units,
scheduled as one cross product pool. No reduction in seeds is needed and the
two fallbacks are recorded only so the choice is visible.

The predicted critical path is 2009 s, the longest unit at 225 calls. The
Level 8 run of 600 units predicted the same 2009 s and took 1980 s, a ratio
of 0.986, which is the third confirmation of that model and the basis for
trusting this one.

## L8.1.7 What this preparation establishes

Established. The information barrier passes evidence sufficiency and not
narrative identity, measured rather than argued, with the regime target as a
positive control showing the method can detect separation when it is there.
The proposed widening cannot work, and the reason is structural rather than
incidental. The Level 9 metric set is declared in advance, in three tiers,
with the unsound cell named. The threshold sweep is designed to bracket the
observed ceiling, and the full grid is priced at 10.75 hours against a 24
hour budget.

Not established. Whether the two pinned metrics move at a lower threshold,
which the sweep will answer. Whether the invariant narrative would persist on
a suite whose categories carried distinct detector signatures, which this
suite cannot answer because two of its six do not. And whether any of this
generalises beyond 40 scenarios and 66 situations.

---

# Appendix L9. The epistemic control ablation

The primary contribution, and it is largely a negative result. Two of the
four mechanisms do nothing measurable, the third does nothing except where a
fourth has already been removed, and the sensor level of the two level
abstention claim is not wired to the reasoning level at all. The metric set
below is the one declared in L8.1.4 before the run, and it is reported as
declared.

## L9.1 What ran

| property | value |
| --- | --- |
| design | 16 configurations by 3 thresholds by 5 seeds by 40 scenarios |
| units | 9600, scheduled as one cross product pool |
| suite | sub-suite `a2b37f29`, 40 scenarios, 66 situations |
| model | `gemini-2.5-flash`, real, cache on |
| wall clock | **8692 s, 2.41 h** |
| units failed | **0** |
| retries | **0** |
| fallback iterations | **0 of 9600 units** |
| cache | 651255 hits, 5851 misses, hit rate **0.9911** |

The budget in L8.1.6 predicted 10.75 hours on a deliberately conservative
0.75 hit rate. The realised rate was 0.9911, so only 5851 model calls were
actually paid for. Two things account for that. The clock study cache already
held the all on cell at the standing threshold in separated mode, which is
one of the 240 cells here. And the structural prediction held exactly: U and
P change no prompt, so the sixteen configurations collapse to four prompt
families and the threshold adds none of its own.

The run finished in 2.41 hours against a predicted critical path of 2009 s,
a ratio of 4.33. Unlike Levels 8, this run was not critical path bound: at
9600 units the work over concurrency term dominates, which is the regime the
budget model says it should be in.

## L9.2 Main effects on the four live metrics

Ablated minus enabled, averaged over every combination of the other three
switches, computed per seed and then deviated across the five. Threshold
0.80, the standing value.

| metric | U | S | A | P |
| --- | --- | --- | --- | --- |
| abstention_rate | **−0.0985 ± 0.008** | **−0.0833 ± 0.011** | −0.0030 ± 0.003 | **0.0000 ± 0.000** |
| appropriate_abstention_rate | **−0.1391 ± 0.010** | **−0.1174 ± 0.016** | −0.0044 ± 0.004 | **0.0000 ± 0.000** |
| inappropriate_abstention_rate | −0.0050 ± 0.010 | −0.0050 ± 0.010 | 0.0000 ± 0.000 | 0.0000 ± 0.000 |
| premature_convergence_rate | **+0.0970 ± 0.007** | **+0.0818 ± 0.011** | +0.0030 ± 0.003 | 0.0000 ± 0.000 |

Read as mechanisms:

**U, the non prunable UNKNOWN hypothesis, is the mechanism.** Removing it
costs 0.0985 of abstention and 0.1391 of appropriate abstention, and buys
0.0970 of premature convergence. Its effect is twelve standard deviations
from zero.

**S, the sanity gate, is the second mechanism**, at roughly five sixths of
U's size and with the same sign everywhere.

**A, asymmetric confidence decay, does nothing.** −0.0030 against a deviation
of 0.003 is one standard deviation from zero on a metric that ranges over
0.18. It is not a small effect, it is an absent one, subject to the
qualification in L9.5.

**P, the persistence requirement, does nothing at all** at this threshold.
Not approximately nothing: 0.0000 with deviation 0.0000 on every live metric.
Its behaviour at lower thresholds is L9.6.

## L9.3 The sixteen configurations collapse to five outcomes

The full table the plan asked to be relegated to an appendix, threshold 0.80,
five seeds.

| configuration | U | S | A | P | abstention | appropriate | inappropriate | premature |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all on | on | on | on | on | 0.1818 ± 0.019 | 0.2565 ± 0.025 | 0.0100 ± 0.020 | 0.5182 ± 0.018 |
| minus A | on | on | **off** | on | 0.1818 ± 0.019 | 0.2565 ± 0.025 | 0.0100 ± 0.020 | 0.5182 ± 0.018 |
| minus P | on | on | on | **off** | 0.1818 ± 0.019 | 0.2565 ± 0.025 | 0.0100 ± 0.020 | 0.5182 ± 0.018 |
| minus AP | on | on | **off** | **off** | 0.1818 ± 0.019 | 0.2565 ± 0.025 | 0.0100 ± 0.020 | 0.5182 ± 0.018 |
| minus S | on | **off** | on | on | 0.0212 ± 0.007 | 0.0304 ± 0.011 | 0.0000 | 0.6758 ± 0.007 |
| minus SP | on | **off** | on | **off** | 0.0212 ± 0.007 | 0.0304 ± 0.011 | 0.0000 | 0.6758 ± 0.007 |
| minus SA | on | **off** | **off** | on | 0.0091 ± 0.007 | 0.0130 ± 0.011 | 0.0000 | 0.6879 ± 0.007 |
| minus SAP | on | **off** | **off** | **off** | 0.0091 ± 0.007 | 0.0130 ± 0.011 | 0.0000 | 0.6879 ± 0.007 |
| every configuration with U off, eight of them | **off** | any | any | any | **0.0000** | **0.0000** | 0.0000 | **0.6970** |

Four distinct rows plus the U off row, from sixteen configurations. The
structure is exact rather than approximate:

- `all on`, `minus A`, `minus P` and `minus AP` are **identical to four
  decimal places on every metric**. A and P change nothing, alone or together.
- The eight configurations with U disabled are **identical to each other**.
  Once UNKNOWN is gone, nothing else matters: abstention is zero and premature
  convergence is 0.6970 whatever S, A and P are set to.
- Between those extremes, S moves abstention from 0.1818 to 0.0212, and A
  moves it from 0.0212 to 0.0091 but only once S is already off.

## L9.4 The effect lives in one regime

Main effects on abstention_rate broken out by regime, threshold 0.80.

| regime | U | S | A | P |
| --- | --- | --- | --- | --- |
| clear | −0.0050 ± 0.010 | −0.0050 ± 0.010 | 0.0000 | 0.0000 |
| ambiguous | −0.0400 ± 0.025 | −0.0400 ± 0.025 | 0.0000 | 0.0000 |
| **sparse** | **−0.5500 ± 0.016** | **−0.4500 ± 0.016** | −0.0200 ± 0.019 | 0.0000 |
| unknown_attack | −0.0063 ± 0.013 | −0.0063 ± 0.013 | 0.0000 | 0.0000 |

The mechanisms act almost entirely on sparse situations. On sparse, all on
abstains at 1.0000 and minus U abstains at 0.0000; the mechanism is the
difference between always declining and never declining. On the other three
regimes the same switch moves the rate by between 0.005 and 0.04.

This is a trade-off only in the weakest sense, because nothing is being
traded: the mechanisms help where evidence is scarce and are close to inert
everywhere else. In particular they do almost nothing on **unknown_attack**,
which is the regime the two level abstention claim in L9.8 rests on, and the
regime an intrusion detection paper most wants them to work on.

## L9.5 Interactions, and what five seeds supports

Two way interaction terms on abstention_rate at threshold 0.80, computed as
half the difference between the effect of one switch when a second is ablated
and its effect when that second is not.

| pair | interaction | deviation |
| --- | --- | --- |
| **U × S** | **+0.0833** | 0.0115 |
| U × A | +0.0030 | 0.0028 |
| S × A | −0.0030 | 0.0028 |
| U × P | 0.0000 | 0.0000 |
| S × P | 0.0000 | 0.0000 |
| A × P | 0.0000 | 0.0000 |

**Five seeds supports exactly one of these claims.** U × S is +0.0833 against
a deviation of 0.0115, seven times its own spread, and it has an
interpretation: U and S are partly redundant, because both push confidence
toward UNKNOWN, so removing both costs less than the sum of removing each.
That term is as large as S's entire main effect.

U × A and S × A are each exactly one deviation from zero and are not
resolved. The three pairs involving P are exactly zero because P itself is
exactly zero. **No interaction claim beyond U × S should be made from this
design**, and the A effects in L9.2 and L9.3 sit in the same unresolved band:
what L9.3 shows is that A moves abstention by 0.0121 in one corner of the
factorial, which is real in the table and not separable from noise in the
effect estimate.

## L9.6 The threshold sweep, and the two dead metrics

L8.1.4 declared `single_iteration_conclusion_rate` and
`mean_iterations_to_termination` dead at the standing threshold, excluded
them from the primary analysis, and said the sweep would test whether they
could be revived at all. It does, and the answer is conditional.

Pooled over all 240 cells:

| threshold | convergence fraction | single_iteration | mean iterations |
| --- | --- | --- | --- |
| 0.30 | **0.2781** | **0.0224** | **2.9420** |
| 0.50 | 0.0280 | 0.0000 | 3.0000 |
| 0.80 | 0.0000 | 0.0000 | 3.0000 |

**Both metrics move, but only at 0.30, and only because half the cells there
have persistence disabled.** Splitting the same numbers by P settles it:

| threshold | convergence fraction, P enabled | P ablated | max convergence, P enabled | P ablated |
| --- | --- | --- | --- | --- |
| 0.30 | **0.0000** | **0.5561** | **0.2900** | 0.6000 |
| 0.50 | **0.0000** | 0.0559 | **0.4900** | 0.6015 |
| 0.80 | **0.0000** | 0.0000 | 0.6500 | 0.6500 |

Two things to read here.

**With persistence enabled the convergence fraction is 0.0000 at every
threshold**, so lowering the threshold on its own revives nothing. That is
the direct answer to the question L8.1.4 posed: the threshold was never the
binding constraint.

**The maximum convergence score with persistence enabled is exactly the
threshold minus 0.01**, 0.2900 at 0.30 and 0.4900 at 0.50. That is not a
coincidence and not a property of the confidence dynamics. It is the literal
value of a clamp, and L9.7 is what it does.

At 0.80 the clamp would allow 0.79 but the dynamics only reach 0.65, so at
the standing threshold the ceiling is genuinely dynamical and the clamp is
not binding. Below roughly 0.66, the clamp binds instead. Both ceilings are
present; which one binds depends on the threshold, and neither is ever
crossed while persistence is on.

## L9.7 Why persistence can never be satisfied

The clamp is `convergence = min(convergence, threshold - 0.01)`, applied
whenever persistence is required, the dominant hypothesis is not UNKNOWN, and
persistence is not satisfied. Persistence is satisfied when the dominant
hypothesis has been dominant for `graph_convergence_persistence` consecutive
iterations, which defaults to 2.

It is never satisfied, and the reason is structural.

`generate_hypotheses` replaces the hypothesis list on every iteration. It
parses a fresh response, builds new hypothesis dictionaries with freshly
generated identifiers, and carries forward only the UNKNOWN entry, which has
a fixed identifier. The previous iteration's named hypotheses are discarded
rather than updated.

Measured over the all on cell at threshold 0.80, seed 42:

| quantity | value |
| --- | --- |
| analyses with more than one iteration | 963 |
| named hypotheses observed | 10068 |
| named hypotheses appearing in more than one iteration | **0** |
| analyses in which UNKNOWN recurs | 963 of 963 |
| distinct `dominant_iterations` values recorded at termination | **{0}**, across 4382 records |

**No named hypothesis survives a single iteration**, so `dominant_iterations`
cannot accumulate, so a requirement of two consecutive dominant iterations is
unsatisfiable by construction. The persistence mechanism is not a strict
convergence criterion that the model fails to meet. It is a criterion that
cannot be met by anything except UNKNOWN, and UNKNOWN is excluded from it by
the same condition.

This explains every result in this appendix that involves P. P has exactly
zero effect at threshold 0.80 because the clamp it applies is not binding
there. It has a large effect at 0.30 because the clamp is binding there, and
what removing P does is remove the clamp, not relax a requirement.

**P is therefore not an epistemic control in the sense the design intended.**
It was meant to require a belief to persist before being acted on. What it
does is hold the convergence score just under whatever threshold is
configured, for as long as any named hypothesis leads.

## L9.8 The two level abstention result

Four cells on the unknown attack regime, five seeds. Sensor reject off is
implemented by clearing the abstained flag on every signal before ingestion.
Epistemic control off is the all four disabled cell.

| sensor reject | epistemic control | abstention | appropriate abstention | premature convergence |
| --- | --- | --- | --- | --- |
| on | on | 0.0125 ± 0.025 | 0.0125 ± 0.025 | 0.9875 ± 0.025 |
| on | off | 0.0000 ± 0.000 | 0.0000 ± 0.000 | 1.0000 ± 0.000 |
| **off** | on | 0.0125 ± 0.025 | 0.0125 ± 0.025 | 0.9875 ± 0.025 |
| **off** | off | 0.0000 ± 0.000 | 0.0000 ± 0.000 | 1.0000 ± 0.000 |

| effect | value |
| --- | --- |
| sensor reject, with epistemic control on | **+0.000000** |
| sensor reject, with epistemic control off | **+0.000000** |
| epistemic control, with sensor reject on | +0.012500 |

**The sensor rows are identical.** Clearing the abstained flag on every
signal in the suite changes nothing, to six decimal places, in either
epistemic condition.

They are not complementary and they are not redundant. **The second level
never receives the first.** `abstained` is counted into the reasoning
snapshot as `abstained_evidence_count` and `abstained_fraction`, and then
read by nothing: it does not filter evidence, it does not enter
`mean_anomaly_score`, `source_diversity` or `confidence_level`, and it is
absent from the ten fields `assemble_context` exposes, so the model never
sees it. The sub-suite carries a 0.2285 abstained fraction overall and 0.5467
on the unknown attack regime, and all of it is inert.

The honest statement for the paper is that the two level abstention claim is
**not implemented**, and that this experiment is what establishes it rather
than a reading of the code. The four cell design was run as specified and its
sensor axis has no effect because there is no path for it to act through.

The epistemic axis is barely better on this regime: 0.0125 against 0.0000,
which is one situation in eighty. L9.4 already showed why, since the
mechanisms act on sparse and not on unknown attack.

## L9.9 The carried metrics, reported as declared

L8.1.4 declared `correct_conclusion_rate` sound on the three abstain truth
regimes and unsound on clear, and `false_conclusion_rate` compromised
throughout. Reported accordingly, threshold 0.80.

| configuration | overall | clear, **unsound** | three abstain truth regimes, sound |
| --- | --- | --- | --- |
| all on | 0.2182 | 0.1300 | 0.3642 |
| minus U | 0.0394 | 0.1300 | 0.0000 |
| minus S | 0.0728 | 0.1700 | 0.0467 |
| all off | 0.0515 | 0.1700 | 0.0000 |

On the three regimes where `correct = abstained` and no keyword is consulted,
the ordering matches the live metrics exactly: all on 0.3642, minus S 0.0467,
minus U and all off 0.0000. That is the same story as L9.2 told, which is
expected, because on those regimes the metric is a relabelling of abstention.

On clear, the only regime where narrative matching is consulted, the numbers
move in the opposite direction: removing mechanisms raises the rate from
0.1300 to 0.1700. This is exactly the cell L8.1.2 established is
unmeasurable, because the narrative a scenario is about cannot be recovered
from anything the information barrier exposes. It is reported and it should
not be interpreted.

## L9.10 Isolating persistence from inertia

L9.7 argues from the code and from hypothesis identity that persistence is
what holds convergence down. Belief inertia is the other mechanism that could
plausibly do it, by capping how far a confidence may move in one iteration.
The two are crossed directly at threshold 0.30, the lowest swept value and
the one where convergence is otherwise reachable, with every other mechanism
left on and five seeds per cell.

| persistence | inertia | convergence fraction | single_iteration | mean iterations | max convergence |
| --- | --- | --- | --- | --- | --- |
| on | on | **0.0000 ± 0.000** | 0.0000 | 3.0000 | **0.2900** |
| on | **off** | **0.0000 ± 0.000** | 0.0000 | 3.0000 | **0.2900** |
| **off** | on | 0.3057 ± 0.005 | 0.0897 ± 0.006 | 2.6640 ± 0.010 | 0.4330 |
| **off** | **off** | 0.3092 ± 0.007 | 0.1437 ± 0.008 | 2.6000 ± 0.015 | 0.5428 |

| effect on convergence fraction | value |
| --- | --- |
| removing persistence | **+0.3057** |
| removing inertia | **+0.0000** |

**Persistence is the cause and inertia is not.** Raising the inertia cap
until it can never bind, while leaving persistence on, moves the convergence
fraction by exactly zero and leaves the maximum convergence at exactly
0.2900, which is the clamp. Removing persistence moves it by 0.3057.

Inertia is not entirely inert, but its effect is only visible once
persistence has been removed, and it is on how convergence is reached rather
than whether. With persistence off, lifting the inertia cap raises
`single_iteration_conclusion_rate` from 0.0897 to 0.1437 and lowers mean
iterations from 2.6640 to 2.6000: beliefs are allowed to move further per
iteration, so more analyses finish on the first one. That is the mechanism
behaving as designed, masked completely by a mechanism that is not.

## L9.11 Figures

**Figure 3**, `figures/fig3_ablation_main_effects.pdf`. Four single switch
removals against the two baselines, four panels. The third panel is not the
one the brief implies: `inappropriate_abstention_rate` sits at 0.01 or below
in all six configurations, so drawing it gives six bars on the axis. It is
replaced by the abstention rate on the sparse regime, which is where the
whole effect lives, and the substitution is stated in the figure's own module
docstring as well as here. The full sixteen row table is L9.3.

**Figure 6**, `figures/fig6_belief_trajectory.pdf`. One situation's belief
trajectory, chosen by a rule fixed before any trajectory was drawn: among the
unknown attack situations of the all on cell at seed 42, the one whose
evidence count at termination is the median of that regime, ties broken by
the smallest identifier. That rule selected situation `09e0a866` with an
evidence count of 1, which is the median for this regime and is itself worth
noting.

The figure is not the belief trajectory the plan imagined, because there are
no trajectories to draw. Nine named hypotheses are proposed across the
analysis and none appears in more than one iteration, so they plot as
isolated points rather than lines. Only UNKNOWN persists, climbing from 0.65
to 0.99. The figure therefore shows L9.7 directly: what looks like a missing
trajectory is the finding.

## L9.12 What Level 9 establishes and what it does not

**Established, and these are the paper's results.**

The UNKNOWN hypothesis is the mechanism that produces abstention. Removing it
takes abstention to exactly 0.0000 in all eight configurations where it is
off, whatever the other three switches do.

The sanity gate is a genuine second mechanism at roughly five sixths of
UNKNOWN's size, and the two are partly redundant: the U by S interaction is
+0.0833, as large as the sanity gate's own main effect, and it is the one
interaction five seeds resolves.

Asymmetric confidence decay does nothing detectable. Its main effect is one
standard deviation from zero, and it moves abstention only in the corner of
the factorial where the sanity gate is already disabled.

The persistence requirement does nothing at the standing threshold and is not
what it was designed to be. Generation replaces the hypothesis list every
iteration, so no named hypothesis survives to become persistent, a
requirement of two consecutive dominant iterations is unsatisfiable, and what
the mechanism actually does is clamp the convergence score to the threshold
minus 0.01. Crossing it with belief inertia shows persistence moves
convergence by 0.3057 and inertia by 0.0000.

The two level abstention claim is not implemented. The sensor's reject option
is recorded and never read, so clearing it on every signal changes the
outcome by 0.000000.

The mechanisms act on sparse evidence and almost nowhere else: 0.55 and 0.45
on sparse against 0.006 on unknown attack.

**Not established.**

Whether any of this holds beyond 40 scenarios and 66 situations. The
deviations here are small, 0.008 to 0.025 on the live metrics, but they are
deviations across five seeds on one frozen sub-suite, not across suites.

Whether the mechanisms would matter on a suite where the reasoner had
narrative identity to work with. L8.1.2 established that this suite does not
provide it, so what is measured here is abstention behaviour under evidence
scarcity, which is a narrower claim than the mechanisms were designed for.

Anything resting on `correct_conclusion_rate` for the clear regime or on
`false_conclusion_rate`, which were declared compromised in L8.1.4 before the
run and are reported in L9.9 without interpretation.

Whether a corrected persistence mechanism, one that tracked hypotheses across
iterations by content rather than by generated identity, would change the
picture. That is the obvious next experiment and this study does not run it.

**What a reader should take from this appendix.** Of four hand designed
epistemic controls, one works, one works and overlaps heavily with the first,
one is inert, and one is a clamp misdescribed as a persistence requirement.
The honest headline is that hand designed guardrails on an LLM reasoner are
easy to write, hard to verify, and in this case three of four did not survive
being measured. That is a more useful result than a fabricated positive, and
it is the result the brief anticipated when it said a negative finding here
is publishable.
