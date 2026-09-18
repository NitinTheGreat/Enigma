# SYSTEM — Phase 2, items 1, 5, 6

Architecture, correlation logic, and risk scoring, with citations.
Every component is marked **LEARNED** or **RULE-BASED** and given a status.

---

## 1. Component table

| # | Component | File:lines | Input | Output | Transformation | Nature | Status |
|---|---|---|---|---|---|---|---|
| C1 | Dataset replayer | `Streamer.py:20-52` | 4 UNSW-NB15 CSVs | JSON records over WS | Chunked read (2 rows), NaN→`""`, 0.5 s sleep | RULE-BASED | IMPLEMENTED |
| C2 | Batch collector | `main.py:107-122` | queued JSON records | list ≤128 | Wait for first item, then fill until 128 or 0.5 s | RULE-BASED | IMPLEMENTED |
| C3 | Preprocessor | `main.py:45-64` | record batch | scaled float matrix | Drop 7 categorical cols + saved drop list; fill missing expected cols with **0**; reorder to `expected_features`; `StandardScaler.transform` | RULE-BASED | IMPLEMENTED |
| C4 | Threat classifier | `main.py:130-134`, `Model.ipynb` cells 51-57 | 20-dim scaled vector | 11-class softmax | Keras MLP (tuned) | **LEARNED** | IMPLEMENTED (weights not in repo) |
| C5 | Traffic splitter | `main.py:145-198` | class name + softmax | route to one of two sockets | `if pred_name == 'normal'` → port 9000 else → port 8000 | RULE-BASED | IMPLEMENTED |
| C6 | SHAP explainer | `Model.ipynb` cell 65 | 1 record, 100-row background | per-feature attributions | `shap.DeepExplainer` | **LEARNED (post-hoc)** | PARTIAL — notebook only, see §5 |
| C7 | Signal adapter | `adapters/unsw_threat.py:78-155` | ML JSON envelope | canonical `Signal` | Field mapping + enum lookup + clamp to [0,1] | RULE-BASED | IMPLEMENTED |
| C8 | Adapter registry | `adapters/registry.py:73-109` | raw dict | `Signal` | First adapter whose `can_handle` is True | RULE-BASED | IMPLEMENTED |
| C9 | Situation store | `store/situation_store.py:160-176` | `Signal` | `Situation` | Find-or-create by correlation key, append evidence | RULE-BASED | IMPLEMENTED |
| C10 | Correlation strategy | `store/correlation.py:38-51` | `Signal` | tuple key | `(str(entity),)` or `(signal_type,)` | RULE-BASED | IMPLEMENTED — see §2 |
| C11 | Temporal snapshot | `domain/situation.py:192-217` | `Situation` | `SituationTemporalSnapshot` | Interval statistics, burst/quiet booleans | RULE-BASED | IMPLEMENTED (**defective, see EVIDENCE §D1**) |
| C12 | Reasoning engine | `core/reasoning_engine.py:97-130` | `Situation` | `SituationReasoningSnapshot` | Fixed 5-term weighted sum + 3-branch trend rule | RULE-BASED | IMPLEMENTED |
| C13 | Context assembler | `graph/nodes.py:46-69` | two snapshots | 10-field dict | Field selection (the "information barrier") | RULE-BASED | IMPLEMENTED |
| C14 | Hypothesis generator | `graph/nodes.py:181-216` | context dict | 3-5 hypothesis dicts | Gemini 2.0 Flash prompt → JSON parse → clamp conf to [0.1,0.5] | **LEARNED (LLM)** | IMPLEMENTED |
| C15 | Sanity gate | `graph/nodes.py:223-317` | hypotheses | hypotheses | Dedup by first 50 chars, keyword-inject a benign hypothesis, boost UNKNOWN on sparse/low-diversity/flat evidence | RULE-BASED | IMPLEMENTED (**one no-op branch, EVIDENCE §D3**) |
| C16 | Hypothesis evaluator | `graph/nodes.py:322-399` | hypotheses + snapshot | hypotheses | 5 additive threshold adjustments, ×1.5 asymmetric decay, prune below 0.1 | RULE-BASED | IMPLEMENTED |
| C17 | Belief inertia | `graph/nodes.py:404-458` | hypotheses | hypotheses | Writes `belief_velocity`/`belief_acceleration` | RULE-BASED | **STUBBED — does not affect confidence, see EVIDENCE §D2** |
| C18 | Convergence scorer | `graph/nodes.py:463-578` | hypotheses | `convergence_score`, statuses | Spread over mean + margin over UNKNOWN, flat/anomaly penalties, persistence requirement | RULE-BASED | IMPLEMENTED (**mutates input, EVIDENCE §D4**) |
| C19 | Loop controller | `graph/nodes.py:583-604` | state | `"end"`/`"loop"` | Threshold + max-iteration check | RULE-BASED | IMPLEMENTED |
| C20 | Explanation builder | `explain/builder.py:54-165` | final state + snapshots | `ExplanationSnapshot` | 7 template sections from ~25 `if` thresholds | RULE-BASED | IMPLEMENTED |
| C21 | Integrity validator | `explain/builder.py:664-704` | snapshot | raises or returns | Checks referenced field names ∈ `KNOWN_FIELDS`, bullets non-empty, scores bounded | RULE-BASED | IMPLEMENTED |
| C22 | Role filter | `domain/explanation.py:225-252` | snapshot + role | snapshot | Section-type allowlist per role | RULE-BASED | IMPLEMENTED (unused on WS path) |
| C23 | Plain formatter | `explain/formatter.py:104-131` | snapshot | text | String concatenation | RULE-BASED | IMPLEMENTED |
| C24 | LLM formatter | `explain/formatter.py:73-90` | snapshot | prose | Gemini rephrasing | **LEARNED (LLM)** | IMPLEMENTED, **never called** |
| C25 | Dashboard broadcaster | `api/ws_dashboard.py:182-199` | analysis dict | WS frames | `json.dumps(..., default=str)` fan-out | RULE-BASED | IMPLEMENTED |
| C26 | Frontend aggregator | `components/dashboard/OverviewDashboard.tsx:124-232` | analysis Map | chart series | Grouping and averaging | RULE-BASED | PARTIAL (**reads non-existent fields, EVIDENCE §F1**) |

### Count of learned vs rule-based
- **Learned components on the live path: 2.** The Keras MLP (C4) and the
  Gemini hypothesis generator (C14).
- **Learned components off the live path: 2.** SHAP (C6, notebook only) and
  the LLM formatter (C24, never called).
- **Everything else — 22 of 26 components — is hand-written rules,
  thresholds, and templates.**

---

## 2. Correlation logic — stated plainly

**It is a single-key hash grouping, not fusion of any kind.**

`main.py:67` injects `EntityCorrelation()`. Its entire implementation is:

```python
def get_key(self, signal: Signal) -> CorrelationKey:
    if signal.entity:
        return (str(signal.entity),)
    return (signal.signal_type.value,)
```
— `store/correlation.py:48-51`

`str(EntityRef)` is `f"{kind}:{identifier}"` (`domain/signal.py:34-35`). The
ML layer sets the device identifier to `record.get("srcip", "unknown_device")`
and hardcodes `user` to `"network_admin"` and `location` to
`"server_rack_1"` (`main.py:185-189`). The adapter picks `device` first
(`adapters/unsw_threat.py:113-117`). So in the running system the
correlation key is **exactly the source IP string**.

`SituationStore._find_or_create` (`situation_store.py:298-317`) looks the key
up in `self._key_index` and appends to the matching `Situation` or creates a
new one. There is no time window, no scoring, no graph, no learned
association, and no notion of a signal belonging to two situations.

Answering the question as posed:

> **This is not learned fusion. It is not a weighted rule set. It is not a
> threshold cascade. It is a dictionary keyed on source IP.**

The threshold cascade that *does* exist is downstream of grouping, in
`ReasoningEngine` (§3) and `evaluate_hypotheses` (`graph/nodes.py:355-386`),
and it operates on aggregates of an already-formed group.

### "Cross-layer" / "multi-source" is not currently demonstrated
`_source_diversity` counts distinct `Signal.source` strings
(`reasoning_engine.py:205-210`). The ML layer sets `source` to the constant
`"unsw-threat-detector"` for every signal (`main.py:193`, and the adapter's
default at `unsw_threat.py:144`). Therefore under the live feed
**`source_diversity == 1` for every situation, always.**

This has three consequences that propagate through the whole reasoning stack:
1. `diversity_contribution` is capped at `1/3` of its weight
   (`reasoning_engine.py:146`).
2. The sanity gate adds +0.10 to UNKNOWN every iteration
   (`graph/nodes.py:301-303`).
3. Convergence is halved whenever mean anomaly > 0.7
   (`graph/nodes.py:532-534`).

The three adapters that would supply a second and third domain
(`network.py`, `auth.py`, `video.py`) are implemented and unit-tested but
**have no producer** — see INVENTORY §5.

---

## 3. Risk scoring

**There is no risk score in this system.** Grep across all three repos for
`risk|severity` returns only: two CSS colour helpers in the frontend
(`Sidebar.tsx:29-34`, `OverviewDashboard.tsx:276`), and prose in docstrings
and explanation bullet text (`explain/builder.py:424,517`;
`domain/situation.py:5`; `domain/reasoning.py:5`). The last two are comments
explicitly stating that risk scoring is *out of scope*:

> "It carries no opinions, no risk scores, and no decisions" —
> `domain/situation.py:5`

**Status: ABSENT.**

The nearest analogue is `confidence_level`, which is *not* a risk score — it
measures how significant a situation looks, not how dangerous.

### The actual formula
`ReasoningEngine._compute_confidence` (`core/reasoning_engine.py:134-158`):

```
confidence = clamp₀¹(
    0.25 · min(evidence_count / 10, 1)
  + 0.15 · min(event_rate     / 10, 1)
  + 0.20 · min(source_diversity / 3, 1)
  + 0.30 · mean_anomaly_score
  + 0.10 · 𝟙[burst_detected]
)
```

| Property | Value | Evidence |
|---|---|---|
| Range | [0, 1], clamped | `reasoning_engine.py:158` |
| Weights | 0.25 / 0.15 / 0.20 / 0.30 / 0.10 | `reasoning_engine.py:50-54`, overridable via `ENIGMA_CONFIDENCE_WEIGHT_*` (`config.py:21-25`) |
| Saturations | 10 events, 10 events/min, 3 sources | `reasoning_engine.py:57-59` |
| Calibration | **none** | No fitting code, no calibration set, no reliability diagram anywhere in the three repos |
| Validation | **none** | `tests/test_reasoning.py` (21 tests) checks the arithmetic reproduces the formula and stays in bounds. It does not validate the weights against any ground truth. |
| Provenance of the weights | **UNVERIFIED** | No comment, commit message, or notebook justifies these five numbers. They are defaults in a dataclass. |

### What `mean_anomaly_score` actually is
`reasoning_engine.py:212-218` averages `Signal.anomaly_score`. That field is
populated by `unsw_threat.py:130` from the payload's `anomaly_score`, which
the ML layer sets at `main.py:190` to:

```python
confidence = float(np.max(predictions[i]))   # main.py:141
"anomaly_score": confidence,
"confidence": confidence,                     # main.py:190-191
```

**`anomaly_score` is the max softmax probability of the classifier.** It is a
classification-confidence value, not an anomaly measure. A record the model
confidently labels `generic` receives `anomaly_score ≈ 0.99`. The two fields
are also byte-identical, so `Signal.confidence` carries zero extra
information.

This is the single largest semantic defect in the pipeline: the 0.30-weighted
dominant term of the confidence formula measures **how sure the classifier
is**, not **how anomalous the traffic is**. Any paper claim that the
confidence score reflects threat severity is unsupported.

---

## 4. Trend detection

`ReasoningEngine._detect_trend` (`core/reasoning_engine.py:162-201`), in
evaluation order:

1. `evidence_count == 0` → STABLE
2. `burst` → ESCALATING
3. `quiet and evidence_count > 0` → **DEESCALATING**
4. `len(intervals) < 3` → STABLE
5. `recent_mean < overall_mean / 1.5` → ESCALATING
6. `recent_mean > overall_mean × 2.0` → DEESCALATING
7. else STABLE

Branch 3 dominates under the live feed because of the clock-domain defect
described in EVIDENCE §D1. Practical effect: the trend layer collapses to a
constant.

---

## 5. Where "XAI" actually lives

Two entirely separate things are called explainability in this codebase, and
**they are not connected**.

### 5a. SHAP — real XAI, offline only
`Model.ipynb` cell 65 builds `shap.DeepExplainer(loaded_model, background)`
with `background = x_train_scaled[:100]`, explains **one** record, and prints
the top-3 features. Output preserved in the notebook:

```
--- XAI Explanation for Class: backdoor ---
-> swin: This feature INCREASED the probability (Value: 0.7768)
-> sloss: This feature DECREASED the probability (Value: -0.3358)
-> sbytes: This feature INCREASED the probability (Value: 0.2423)
```

`shap` is imported nowhere else. Grep confirms it appears only in
`Model.ipynb`. **`main.py` does not import or call SHAP.** No attribution
value is ever transmitted downstream.

**Status: PARTIAL — a working single-instance demonstration, entirely
offline, with no path into the serving system.**

### 5b. What the serving path actually sends
`main.py:192` sets the `features` field to:

```python
"features": list(record.keys()),
```

That is the list of **CSV column names**, identical for every single signal,
carrying no per-instance information. It is stored on the `Signal`
(`unsw_threat.py:137-141`, `domain/signal.py:66-70`) and then **never read
by anything**. Grep for `.features` across `enigma_reason/` finds no
consumer.

### 5c. The "explainability layer" is a rule-based report generator
`explain/builder.py` (705 lines) emits 7 typed sections. Every bullet is a
literal string chosen by an `if` on a threshold — for example
`explain/builder.py:256-258`:

```python
if rs.burst_detected:
    bullets.append("Burst activity detected: supports escalation-related hypotheses")
    total_score += 0.2
```

The `contribution_score` values (0.2, 0.3, 0.15, 0.1 …) at
`builder.py:259-284` are hardcoded constants, not attributions computed from
the model. The `Counterfactual` deltas at `builder.py:500,514,528,541,551`
(+0.10, +0.15, +0.20, −0.10) are likewise hand-picked numbers that restate
thresholds appearing elsewhere in the code — they are **not** counterfactuals
in the Wachter/DiCE sense (no optimisation, no search over input space, no
verification that the stated delta would occur).

The file docstring is accurate about this: "NEVER uses an LLM / NEVER invents
facts" (`builder.py:14-16`). It is a faithful, auditable, deterministic
*report*. It is not a post-hoc explanation of a learned model.

**Status: IMPLEMENTED as a deterministic report generator; ABSENT as model
explainability.**

### 5d. Is any explanation consumed downstream?
No. `build_explanation` output goes to exactly two places:
`api/analyze.py:105` (HTTP response) and `api/ws_dashboard.py:117` (WS
broadcast). Nothing feeds back into hypothesis confidence, situation state,
or the classifier. The frontend renders it (`ExplanationSections.tsx`).

> **The explanation is display-only. Nothing acts on it.**

---

## 6. Honest one-line architecture summary

A Keras MLP classifies replayed UNSW-NB15 flows; non-`normal` predictions are
grouped by source IP into in-memory buckets; a fixed weighted sum and a
LangGraph loop around Gemini produce three natural-language hypotheses whose
confidences are then adjusted by hand-tuned threshold rules; a template
engine renders the resulting numbers as bullet points for a React dashboard.
