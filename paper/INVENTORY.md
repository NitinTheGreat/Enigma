# INVENTORY — Phase 1

Scope: three repositories under `F:\XAI Project`, inspected 2026-07-27.
Target venue: mid-tier applied security venue (8 pages, IEEE format).

Capability legend used throughout: **IMPLEMENTED** (code exists and is
exercised), **PARTIAL** (code exists but only covers part of the claim),
**STUBBED** (code exists but does not do what its name says), **ABSENT**
(no code).

---

## 1. Enigma-ML-Layer

| Property | Value | Evidence |
|---|---|---|
| Language | Python 3 (no version pin) | no `pyproject.toml`, no `requirements.txt` |
| Framework | none — bare `asyncio` + `websockets` | `Enigma-ML-Layer/main.py:1-10` |
| Packaging | none | repo root listing: 5 files only |
| Entry points | `main.py` (WS server, port 8765), `Streamer.py` (replay client), `Frontend_listener.py` (print-only sink, port 9000) | `main.py:219-238`, `Streamer.py:54-74`, `Frontend_listener.py:34-44` |
| Runtime deps | `websockets`, `pandas`, `joblib`, `tensorflow.keras`, `numpy` | `main.py:1-10` |
| External services | none (no cloud, no DB, no broker) | — |
| README | 10 bytes, no content | `Enigma-ML-Layer/README.md` |
| Commits | 5, all 2026-02-15 | `git log` |

### Data sources
- UNSW-NB15 CSVs: `archive/UNSW-NB15_1..4.csv` plus
  `archive/NUSW-NB15_features.csv` for column names — `Streamer.py:7-12`, `Streamer.py:23-24`.
- Notebook additionally reads `UNSW_NB15_training-set.csv`,
  `UNSW_NB15_testing-set.csv`, `UNSW-NB15_LIST_EVENTS.csv` — `Model.ipynb` cell 2.
  **Neither of these two split files is used anywhere downstream**; the model
  is trained on the concatenation of `NB15_1..4` only (cell 4).

### Missing runtime artifacts — repo does not run as checked out
`main.py:29-30` loads `unsw_nb15_threat_detection_model.h5` and
`unsw_nb15_preprocessing_state.pkl`, and `main.py:37-38` calls `exit(1)` if
either is missing. Neither file is in the repository, nor is the `archive/`
directory. Directory listing of `Enigma-ML-Layer` contains exactly:
`.git`, `Frontend_listener.py`, `main.py`, `Model.ipynb`, `README.md`,
`Streamer.py`. **Status: repo is NOT reproducible.**

---

## 2. Enigma-AIAgent (`enigma_reason`)

| Property | Value | Evidence |
|---|---|---|
| Language | Python ≥3.11 | `pyproject.toml:5` |
| Framework | FastAPI + LangGraph | `pyproject.toml:6-15` |
| Entry point | `uvicorn enigma_reason.main:app` | `README.md:213`, `enigma_reason/main.py:93-97` |
| Runtime deps | fastapi, uvicorn, pydantic v2, pydantic-settings, websockets, langgraph, langchain-core, langchain-google-genai | `requirements.txt:1-11` |
| External services | Google Gemini (`gemini-2.0-flash`) via `GOOGLE_API_KEY` | `enigma_reason/graph/runner.py:30-46`, `config.py:41-43` |
| Persistence | none — in-memory dict only | `store/situation_store.py:154-156` |
| Commits | 14, 2026-02-13 → 2026-02-14 | `git log` |

### HTTP / WS surface
| Route | Kind | File |
|---|---|---|
| `/ws/signal` | WS ingest (canonical, adapter fallback) | `api/ws_signal.py:42-90` |
| `/ws/raw-signal` | WS ingest (adapter-only) | `api/ws_raw_signal.py:38-86` |
| `/ws/dashboard` | WS broadcast to frontends | `api/ws_dashboard.py:210-222` |
| `GET /api/situations` | list | `api/analyze.py:48-55` |
| `GET /api/situation/{id}/analyze` | full analysis | `api/analyze.py:57-180` |
| `GET /health` | aggregate counters | `main.py:115-135` |

### Tests
216 test functions across 8 files (`tests/`). On this machine **167 pass in
0.58 s**; `tests/test_graph.py` (49 tests) fails to *collect* because
`ormsgpack`, a transitive LangGraph dependency, is blocked by a local
Windows Application Control policy. That is an environment fault, not a code
fault — but it means the 49 LangGraph tests are **UNVERIFIED on this
machine**. LLM calls in those tests are mocked at the LangChain `invoke`
level (`tests/test_graph.py`, `_mock_llm_response`), so **no test exercises a
real Gemini call**.

| File | Tests |
|---|---|
| `test_explanation.py` | 62 |
| `test_graph.py` | 49 (not collected here) |
| `test_adapters.py` | 34 |
| `test_temporal.py` | 30 |
| `test_reasoning.py` | 21 |
| `test_signal.py` | 10 |
| `test_situation.py` | 5 |
| `test_store.py` | 5 |

`test_live.py` (repo root) is a manual end-to-end script against a hardcoded
EC2 host `13.233.93.2`, not part of the suite (`test_live.py:11-13`).

### Config drift
`.env.example` documents `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and
`ENIGMA_CORS_ORIGINS` (`.env.example:11-15`). None of these exist in
`config.py`; the code actually needs `GOOGLE_API_KEY`
(`graph/runner.py:34`). **The example env file is wrong.**

---

## 3. Enigma-Frontend (`enigma-fe`)

| Property | Value | Evidence |
|---|---|---|
| Language | TypeScript | `tsconfig.json` |
| Framework | Next.js 16.1.6, React 19.2.3, App Router | `package.json:12-16` |
| Charting | hand-rolled SVG (no chart library) | `components/charts/*.tsx` |
| Animation | framer-motion 12 | `package.json:12` |
| Entry point | `app/page.tsx` | `app/page.tsx:33` |
| Backend base URL | `http://13.233.93.2:8000` (hardcoded default) | `app/api/health/route.ts:3` |
| WS URL | `ws://13.233.93.2:8000/ws/dashboard` (hardcoded default) | `hooks/useDashboardWS.ts:6` |
| README | unmodified `create-next-app` boilerplate | `enigma-fe/README.md` |
| Tests | **none** | no test files, no test script in `package.json:5-10` |
| Commits | 10, 2026-02-13 → 2026-02-16 | `git log` |

`components/Hero.tsx` is a 0-byte file.

---

## 4. How the three repos relate

There is **no shared schema package, no message broker, and no code
dependency** between the repos. Coupling is entirely by hand-written JSON
over WebSockets, duplicated independently on each side.

### Wire contracts (three separate, unversioned, hand-maintained copies)
1. **ML → AIAgent.** Producer builds the dict at `main.py:177-195`. Consumer
   parses it at `adapters/unsw_threat.py:78-155`. Agreement verified by
   reading both.
2. **AIAgent → Frontend.** Producer at `api/ws_dashboard.py:120-180`.
   Consumer type declarations at `types/dashboard.ts:6-111`. **These do not
   agree** — see EVIDENCE.md §F1.
3. **ML → Frontend_listener.** Producer at `main.py:152-158` sends
   `{normal_count, timestamp}`; the listener at `Frontend_listener.py:21`
   reads `payload["inputs_for_xai_model"]["timestamp"]`, catches `KeyError`,
   and prints. It is a debug printer, not a component.

### Data-flow map

```
┌────────────────────────────────────────────────────────────────────┐
│ Enigma-ML-Layer                                                    │
│                                                                    │
│  archive/UNSW-NB15_{1..4}.csv   [NOT IN REPO]                      │
│         │  pd.read_csv chunksize=2                Streamer.py:33-36│
│         ▼                                                          │
│  Streamer.py ──── ws://localhost:8765 ────┐       Streamer.py:15   │
│    2 records / 0.5 s  ≈ 4 rec/s           │       Streamer.py:17-18│
│                                            ▼                       │
│                                   main.py handle_connection        │
│                                        main.py:208-215             │
│                                            │ asyncio.Queue         │
│                                            ▼      main.py:41       │
│                                   inference_worker                 │
│                                   batch ≤128 or 0.5 s              │
│                                        main.py:13-14, 107-122      │
│                                            │                       │
│                     preprocess_batch (drop 7 cols, align to 20     │
│                     expected_features, StandardScaler.transform)   │
│                                        main.py:45-64               │
│                                            │                       │
│                     Keras MLP .h5  → softmax over 11 classes       │
│                                        main.py:29, 130-134         │
│                                            │                       │
│                        ┌───────────────────┴──────────────────┐    │
│              pred == 'normal'                     pred != 'normal'│
│                        │                                       │   │
└────────────────────────┼───────────────────────────────────────┼───┘
                         │                                       │
         ws://localhost:9000                     ws://localhost:8000
         {normal_count, timestamp}                /ws/signal
              main.py:152-158                     main.py:177-198
                         │                                       │
                         ▼                                       ▼
        ┌──────────────────────────┐    ┌──────────────────────────────────┐
        │ Frontend_listener.py     │    │ Enigma-AIAgent                   │
        │ prints JSON to stdout.   │    │                                  │
        │ Terminal only — NOT      │    │ ws_signal.py:49-69               │
        │ connected to the Next.js │    │  Signal.model_validate, else     │
        │ app.                     │    │  AdapterRegistry fallback        │
        │ Frontend_listener.py:26-29│   │        │                         │
        └──────────────────────────┘    │  UNSWThreatAdapter               │
                                        │  unsw_threat.py:78-155           │
                                        │        │                         │
                                        │  SituationStore.ingest           │
                                        │  key = (entity,) EntityCorrelation│
                                        │  situation_store.py:160-176      │
                                        │  correlation.py:48-51            │
                                        │        │                         │
                                        │  asyncio.create_task(...)  ← per │
                                        │  signal, UNBOUNDED               │
                                        │  ws_signal.py:82-85              │
                                        │        ▼                         │
                                        │  DashboardManager._build_analysis│
                                        │  ws_dashboard.py:85-180          │
                                        │   1. temporal_snapshot           │
                                        │      situation.py:192-217        │
                                        │   2. ReasoningEngine.evaluate    │
                                        │      reasoning_engine.py:97-130  │
                                        │   3. run_reasoning → LangGraph   │
                                        │      → Gemini 2.0 Flash          │
                                        │      runner.py:103, nodes.py:193 │
                                        │   4. build_explanation           │
                                        │      explain/builder.py:54-165   │
                                        │        │                         │
                                        │  _broadcast to all WS clients    │
                                        │  ws_dashboard.py:182-199         │
                                        └────────┬─────────────────────────┘
                                                 │ ws /ws/dashboard
                                                 ▼
                            ┌──────────────────────────────────────┐
                            │ Enigma-Frontend                      │
                            │ useDashboardWS.ts:74-115             │
                            │  Map<situation_id, SituationAnalysis>│
                            │  feed capped at 200                  │
                            │  useDashboardWS.ts:18                │
                            │                                      │
                            │ Also polls, via Next route handlers: │
                            │  /api/health     → :8000/health      │
                            │  /api/situations → :8000/api/situations│
                            │  /api/situation/[id]/analyze         │
                            └──────────────────────────────────────┘
```

### Ports and hosts, as configured in code
| From | To | Address | Evidence |
|---|---|---|---|
| Streamer | ML | `ws://localhost:8765` | `Streamer.py:15` |
| ML | AIAgent | `ws://localhost:8000/ws/signal` | `main.py:18` |
| ML | listener | `ws://localhost:9000` | `main.py:21` |
| Frontend | AIAgent | `ws://13.233.93.2:8000/ws/dashboard` | `useDashboardWS.ts:6` |
| Frontend | AIAgent | `http://13.233.93.2:8000` | `app/api/health/route.ts:3` |

The ML layer points at `localhost`; the frontend points at a public EC2 IP.
The two halves are therefore configured for **different deployments** and
have not been run together as checked in. `git log` for Enigma-ML-Layer
records `5daa4f7 Change DOWNSTREAM_URI to localhost for testing`, confirming
the EC2 target was edited out.

---

## 5. Paths never exercised by the live system

| Component | Status | Note |
|---|---|---|
| `/ws/raw-signal` endpoint | IMPLEMENTED, unused | No producer sends `source_type`; ML uses `/ws/signal` (`main.py:18`) |
| `NetworkAnomalyAdapter` | IMPLEMENTED, unused | requires `source_type == "network_anomaly"` (`adapters/network.py:35`) — never sent |
| `AuthAnomalyAdapter` | IMPLEMENTED, unused | `adapters/auth.py:33` |
| `VideoDetectionAdapter` | IMPLEMENTED, unused | `adapters/video.py:34` |
| `ExplanationFormatter.format` (LLM path) | IMPLEMENTED, unused | Both callers use the deterministic `format_plain` instead (`api/analyze.py:116`, `api/ws_dashboard.py:118`) |
| `DefaultCorrelation` | IMPLEMENTED, unused | `main.py:67` injects `EntityCorrelation` |
| `filter_explanation_for_role` MANAGER/AUDITOR | IMPLEMENTED, unused on WS path | `ws_dashboard.py:117` never filters; only the REST route accepts `role` (`analyze.py:60`) |
| `store.expire_stale()` | IMPLEMENTED, **never called** | No scheduler, no background task references it (`situation_store.py:183-199`) |

The last row matters: situations are never expired in the running system.
Evidence lists grow without bound (`situation.py:57-61`).
