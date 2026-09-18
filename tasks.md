# Running the system

Project root is `F:\XAI Project`. It is not itself a git repository. It contains
three independent repositories plus four shared working directories.

```
F:\XAI Project\
  Enigma-ML-Layer\      git repo, sensor and training
  Enigma-AIAgent\       git repo, reasoning and explanation
  Enigma-Frontend\      git repo, dashboard
  data\                 UNSW-NB15, not tracked by any repo
  results\              machine readable experiment output
  artifacts\            model weights, fitted pipelines, tuner state
  figures\              publication figures
  paper\                evidence files, append only
```

`data`, `results`, `artifacts` and `figures` are shared across the three
repositories and are deliberately outside all of them. Every script that writes
to them takes an explicit path argument, so nothing depends on the working
directory.

## Which environment is canonical

There are three usable environments. **The canonical environment for every
number that reaches the paper is WSL CPU.** This is a measured decision, not a
preference. See the benchmark section below.

| Environment | Role |
|---|---|
| WSL CPU, `enigma-gpu` distro | **canonical.** All TensorFlow training, all paper numbers |
| WSL GPU, same distro | Level 5 XGBoost baselines only. Never for TensorFlow |
| Windows CPU | cross-platform verification, and the reasoning layer |

The GPU is genuinely worse for this project's TensorFlow workload. It is 1.8 to
2.4 times slower than the CPU at every realistic batch size, and it silently
changes results unless TF32 is disabled, which makes it ten times slower again.
It is 1.86 times faster for XGBoost, which is the only place it should be used.

## First time setup, Windows

Python 3.11.9. Each Python repository has its own virtual environment because
the TensorFlow and LangGraph dependency trees conflict on protobuf.

```
cd "F:\XAI Project\Enigma-ML-Layer"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

cd "F:\XAI Project\Enigma-AIAgent"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

cd "F:\XAI Project\Enigma-Frontend\enigma-fe"
npm install
```

`requirements.txt` holds the direct dependencies. `requirements.lock.txt` holds
the full transitive freeze and is what to use when an exact reproduction is
needed.

Do not install into the system Python. The system interpreter has an
`ormsgpack` build that is blocked by the machine's Application Control policy,
which prevents LangGraph from importing and stops 49 tests from collecting. The
virtual environment installs a build that is not blocked.

## First time setup, WSL

The distribution is named `enigma-gpu` and lives on `F:\WSL\enigma-gpu`, not on
`C:`, because `C:` had 7.7 GB free and this environment needs roughly 8 GB.

```
wsl --install Ubuntu-24.04 --location "F:\WSL\enigma-gpu" --name enigma-gpu --no-launch
wsl -d enigma-gpu -u root -- bash -lc "apt-get update && apt-get install -y python3-venv python3-pip python3-dev build-essential"
wsl -d enigma-gpu -u root -- bash -lc "mkdir -p /opt/enigma && cd /opt/enigma && python3 -m venv .venv-gpu"
wsl -d enigma-gpu -u root -- bash -lc "/opt/enigma/.venv-gpu/bin/python -m pip install -r '/mnt/f/XAI Project/Enigma-ML-Layer/requirements-gpu.txt'"
```

Ubuntu 24.04.4 LTS, Python 3.12.3, kernel 6.6.87.2-microsoft-standard-WSL2, 12
CPUs, 7 GB RAM by default. Everything runs as root inside the distribution,
which is why there was no interactive user creation step. The virtual
environment sidesteps the PEP 668 externally managed environment restriction.

`requirements-gpu.txt` differs from `requirements.txt` in exactly one line,
`tensorflow[and-cuda]==2.20.0` instead of `tensorflow==2.20.0`. Every other pin
is identical, deliberately, so that the only variable between environments is
the CUDA runtime. `requirements.wsl-gpu.lock.txt` is the full transitive freeze,
76 packages.

To run anything, use scripts rather than inline commands. Passing shell strings
through PowerShell into `wsl bash -lc` mangles nested quotes. The scripts in
`scripts\` are written for this and are invoked as:

```
wsl -d enigma-gpu -u root -- bash -c "tr -d '\r' < '/mnt/f/XAI Project/scripts/NAME.sh' > /tmp/NAME.sh && bash /tmp/NAME.sh"
```

The `tr -d '\r'` is required. The scripts live on an NTFS volume and carry CRLF
line endings, which bash will not accept.

### GPU state, measured

```
nvidia-smi inside WSL
  NVIDIA GeForce RTX 3050 Laptop GPU
  driver 566.07, CUDA 12.7
  4096 MiB total, 3964 MiB free
  compute capability 8.6

TensorFlow
  tf.config.list_physical_devices('GPU') -> [PhysicalDevice('/physical_device:GPU:0')]
  Created device /device:GPU:0 with 1767 MB memory
```

This is the 4 GB variant, not the 6 GB one. TensorFlow only receives 1767 MB of
the 4096 MiB because WDDM reserves the remainder for the Windows compositor.
1767 MB is the number that actually constrains anything.

It constrains nothing in this project. The Level 3 model has roughly 2300
parameters and the Level 4 deep ensemble is five copies of it. That is
kilobytes. VRAM is not a limiting factor here and the 4 GB against 6 GB question
turns out not to matter.

## Benchmarks

Identical workload throughout: 132000 rows, 20 features, 11 classes, 2347
parameter dense network, seed 42. Produced by `Enigma-ML-Layer\bench_device.py`,
raw output in `results\bench\`.

### Batch size sweep, seconds per epoch, WSL

| Batch | GPU | CPU | GPU speedup |
|---|---|---|---|
| 32 | 21.92 | 10.34 | 0.47x |
| 128 | 5.94 | 3.68 | 0.62x |
| 512 | 1.56 | 1.10 | 0.70x |
| 2048 | 0.52 | 0.56 | 1.06x |

The GPU never meaningfully wins. The model is far too small to saturate it, so
per-step kernel launch and synchronisation overhead dominates across 4125 steps
per epoch. The crossover only arrives at batch 2048, where the margin is within
noise, and that batch size would change training dynamics.

### Ten epoch run at batch 32, seconds per epoch

| Environment | Steady epoch |
|---|---|
| Windows CPU | 8.96 |
| WSL CPU | 10.34 to 12.26 across runs |
| WSL GPU | 21.90 |

### XGBoost, 132000 rows, 200 trees, depth 6

| Device | Fit seconds |
|---|---|
| cuda | 17.69 |
| cpu | 32.99 |

GPU speedup 1.86x. This is the one place the GPU is worth using, and Level 5 is
the one place it applies.

### Filesystem boundary

| Location | Raw read | Throughput | pandas read |
|---|---|---|---|
| `/mnt/f` drvfs | 6.28 s | 89.1 MB/s | 33.34 s |
| `/opt/enigma/data` ext4 | 1.33 s | 421.3 MB/s | 33.20 s |

559.2 MB across the four raw partitions, caches dropped between runs.

The boundary costs 4.7x on raw throughput, which sounds decisive and is not.
CSV parsing dominates so completely that the end to end difference is 0.4
percent. **Copying the dataset into the WSL filesystem is not necessary.** It
has been copied anyway, to `/opt/enigma/data`, 605 MB, because it was already
done and costs nothing further. Delete it if you want the space back.

The caveat worth knowing: dropping caches inside WSL does not drop the Windows
side cache for drvfs, so the `/mnt/f` figure is if anything flattering.

## Level 1 parity across environments

The deterministic part of the pipeline is bit identical everywhere. Rows after
deduplication 2059415, 18 correlated pairs, 9 columns dropped, 165000 rows after
resampling, the same 20 features in the same order, the same label mapping, the
same mutual information drop list. All four runs agree exactly.

Training numerics do not agree.

| Run | Accuracy | Loss | Total s |
|---|---|---|---|
| Windows CPU | 0.667333 | 1.075912 | 469 |
| WSL CPU | 0.666273 | 1.065632 | 262 |
| WSL GPU, TF32 default | 0.661788 | 1.069452 | 286 |
| WSL GPU, TF32 disabled | 0.666273 | 1.067247 | 438 |

Two separate effects.

**TF32.** Ampere enables TF32 for matmul by default, which truncates the
mantissa. That alone accounts for the entire GPU discrepancy. Setting
`NVIDIA_TF32_OVERRIDE=0`, `TF_DETERMINISTIC_OPS=1` and `TF_CUDNN_DETERMINISTIC=1`
reproduces the WSL CPU accuracy to six decimal places. The cost is that the
epoch goes from 36 seconds to 176 seconds, roughly ten times slower than simply
using the CPU. Loss still differs in the third decimal, so this is agreement on
accuracy, not bit identity.

**Operating system.** WSL CPU against Windows CPU differs by 0.00106 in accuracy
with no GPU involved. Different thread counts and different BLAS produce
different float accumulation order. This is irreducible and should be reported
in the threats to validity section rather than hidden.

WSL CPU is also the fastest end to end, 262 seconds against 469, a 1.79x win.
That comes almost entirely from `mutual_info_regression`, which takes about 156
seconds under WSL and about 380 under Windows. Training is not the bottleneck in
this pipeline and never was.

## Dataset

`data\` holds both UNSW-NB15 variants.

| File | Rows | Columns | Header |
|---|---|---|---|
| UNSW-NB15_1.csv | 700001 | 49 | no |
| UNSW-NB15_2.csv | 700001 | 49 | no |
| UNSW-NB15_3.csv | 700001 | 49 | no |
| UNSW-NB15_4.csv | 440044 | 49 | no |
| UNSW_NB15_training-set.csv | 82332 | 45 | yes |
| UNSW_NB15_testing-set.csv | 175341 | 45 | yes |

Two warnings that will otherwise cost you a day.

**The official split filenames are inverted.** The file named
`UNSW_NB15_testing-set.csv` holds 175341 rows and is the official *training*
partition. The file named `UNSW_NB15_training-set.csv` holds 82332 rows and is
the official *test* partition. This is a known defect in the widely mirrored
distribution of this dataset. Level 3 must map roles by row count, never by
filename.

**The two variants do not share a schema.** The raw four-partition files carry
49 unheadered columns named by `NUSW-NB15_features.csv`. The official split
files carry 45 headed columns using different names for the same quantities,
for example `Spkts` against `spkts`, `Sintpkt` against `sinpkt`, `smeansz`
against `smean`, `res_bdy_len` against `response_body_len`. A model trained on
one variant cannot consume the other without an explicit column mapping.

Regenerate the inventory at any time:

```
cd "F:\XAI Project\Enigma-ML-Layer"
.\.venv\Scripts\python.exe dataset_manifest.py
```

Writes `results\dataset_manifest.json`, including a SHA-256 per file.

## Training

`train.py` is a faithful port of `Model.ipynb`, including its four leakage
paths. It exists so Level 1 has an executable baseline. It is not the honest
pipeline. Level 3 replaces it.

Canonical, WSL CPU, via `scripts\wsl_parity_cpu.sh` or directly:

```
wsl -d enigma-gpu -u root -- bash -lc "CUDA_VISIBLE_DEVICES=-1 /opt/enigma/.venv-gpu/bin/python '/mnt/f/XAI Project/Enigma-ML-Layer/train.py' --data-dir /opt/enigma/data --results-dir '/mnt/f/XAI Project/results' --artifacts-dir /opt/enigma/artifacts --run-name notebook_parity"
```

Windows, for cross-checking:

```
cd "F:\XAI Project\Enigma-ML-Layer"
.\.venv\Scripts\python.exe train.py --skip-tuning --baseline-epochs 1 --sample-rows 300000 --run-name smoke
.\.venv\Scripts\python.exe train.py --run-name notebook_parity
```

`CUDA_VISIBLE_DEVICES=-1` is not optional on the canonical path. Without it
TensorFlow will take the GPU, which is slower and changes the numbers.

The full run includes the ten-trial random search. Budget accordingly: the
notebook recorded 1 h 36 m for the search alone on an RTX 3050, and that figure
was itself GPU bound by launch overhead rather than compute. On CPU at batch 32
expect roughly the same order.

Outputs:

```
results\train_{run_name}_seed{seed}.json
artifacts\unsw_nb15_threat_detection_model_{run_name}_seed{seed}.keras
artifacts\unsw_nb15_threat_detection_model.h5
artifacts\unsw_nb15_preprocessing_state.pkl
artifacts\class_index.json
```

The `.h5` and `.pkl` filenames are fixed because `main.py` loads them by name.

## Running the three services

Start in this order. Each needs its own terminal.

**1. Reasoning layer, port 8000.**

```
cd "F:\XAI Project\Enigma-AIAgent"
$env:GOOGLE_API_KEY = "<key>"
.\.venv\Scripts\python.exe -m uvicorn enigma_reason.main:app --host 0.0.0.0 --port 8000
```

Without `GOOGLE_API_KEY` the service still starts and still accepts signals,
but every LangGraph pass raises and falls back to an empty hypothesis list at
`api/ws_dashboard.py:105-114`. The dashboard then shows permanently undecided
situations. The failure is silent, so check the logs.

**2. Sensor layer, port 8765.**

```
cd "F:\XAI Project\Enigma-ML-Layer"
.\.venv\Scripts\python.exe main.py
```

Requires `unsw_nb15_threat_detection_model.h5` and
`unsw_nb15_preprocessing_state.pkl`. It looks in its own directory first, then
falls back to `artifacts\`. Override with `--artifacts-dir`. Exits with code 1
if either is missing.

Forwards non-normal predictions to `ws://localhost:8000/ws/signal` and normal
traffic counts to `ws://localhost:9000`. Both are overridable with
`--downstream-uri` and `--normal-traffic-uri`.

**3. Optional normal-traffic sink, port 9000.**

```
cd "F:\XAI Project\Enigma-ML-Layer"
.\.venv\Scripts\python.exe Frontend_listener.py
```

Prints to stdout only. Nothing consumes it. If it is not running, `main.py`
retries the connection every five seconds and logs the failure, which is noisy
but harmless.

**4. Replayer.**

```
cd "F:\XAI Project\Enigma-ML-Layer"
.\.venv\Scripts\python.exe Streamer.py
```

Defaults to `..\data`, two records every 0.5 seconds, looping the dataset
forever. Override with `--data-dir`, `--uri`, `--burst-size`, `--burst-delay`.

**5. Dashboard, port 3000.**

```
cd "F:\XAI Project\Enigma-Frontend\enigma-fe"
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
$env:NEXT_PUBLIC_WS_URL = "ws://localhost:8000/ws/dashboard"
npm run dev
```

Both variables default to a hardcoded EC2 address, `13.233.93.2`, so they must
be set for local use.

## Tests

```
cd "F:\XAI Project\Enigma-AIAgent"
.\.venv\Scripts\python.exe -m pytest -q
```

216 tests, all passing, zero collection errors.

`Enigma-ML-Layer` and `Enigma-Frontend` have no tests.

`test_live.py` in the AIAgent root is a manual end to end script against the
hardcoded EC2 host. It is not part of the suite.

## Level 2 configuration switches

Six environment variables control the mechanisms Level 8 and Level 9 vary. All
carry the `ENIGMA_` prefix and are read by `enigma_reason/config.py`.

| Variable | Default | Effect when changed |
|---|---|---|
| `ENIGMA_CLOCK_MODE` | `separated` | `conflated` restores the D1 defect for the Level 8 study. `wall` evaluates staleness entirely in host time |
| `ENIGMA_UNKNOWN_HYPOTHESIS_ENABLED` | `True` | `false` never creates the permanent UNKNOWN hypothesis |
| `ENIGMA_SANITY_GATE_ENABLED` | `True` | `false` removes the sanity gate node from the compiled graph |
| `ENIGMA_ASYMMETRIC_DECAY_ENABLED` | `True` | `false` applies negative adjustments at face value |
| `ENIGMA_PERSISTENCE_REQUIRED` | `True` | `false` allows convergence on the first dominant iteration |
| `ENIGMA_MAX_CONFIDENCE_DELTA` | `0.15` | `inf` removes the belief inertia node from the compiled graph |

Disabling a mechanism removes it from the reasoning path rather than weakening
it. For the sanity gate and belief inertia this is literal: the node is not
added to the graph. Verify with `scripts\wsl_ablation_dump.sh`, which prints the
compiled node list under both configurations.

Reproduce the Level 2 evidence with:

```
wsl -d enigma-gpu -u root -- bash -c "tr -d '\r' < '/mnt/f/XAI Project/scripts/wsl_level2_verify.sh' > /tmp/v.sh && bash /tmp/v.sh"
```

Output lands in `results\level2\verify.json`.

## Known blockers carried into later levels

These are recorded in full in `paper\EVIDENCE.md`. They are listed here only so
nobody is surprised while running the system.

- Replaying archival data makes every situation permanently quiet, therefore
  permanently de-escalating, therefore permanently undecided. The dataset
  manifest confirms the raw capture spans 2015-01-22 to 2015-02-18, so the
  wall-clock comparison at `domain/situation.py:190` is roughly eleven years
  out. Level 2 fixes it.
- Eight dashboard panels read backend fields that are never sent, so they show
  zeros. Level 2 fixes it.
- `anomaly_score` emitted by `main.py` is the maximum softmax probability, not
  an anomaly measure. Level 2 replaces it.
- `.env.example` in `Enigma-AIAgent` names `OPENAI_API_KEY` and
  `ANTHROPIC_API_KEY`. Neither is used. The key that matters is
  `GOOGLE_API_KEY`.
- `train.py` deliberately preserves the four leakage paths so Level 1 has an
  executable baseline. Do not quote any number it produces in the paper.
  Level 3 replaces it.
