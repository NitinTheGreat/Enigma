# Enigma

A three layer system for network threat detection with explicit reasoning about
uncertainty. A sensor scores flows and abstains when it is not confident, a
reasoning layer accumulates those scores into situations and argues about what
they mean, and a dashboard shows the argument as it happens.

| Directory | What it holds |
| --- | --- |
| `Enigma-ML-Layer` | The sensor. Trains and serves the UNSW-NB15 classifier ensemble, applies temperature scaling and the abstention policy, and emits signals. |
| `Enigma-AIAgent` | The reasoning layer. Correlates signals into situations, runs the LangGraph hypothesis loop, and broadcasts explanations. |
| `Enigma-Frontend` | The dashboard. Next.js, live websocket feed. |
| `paper` | Evidence trail and gap analysis. Append only. |
| `scripts` | Launchers, experiment drivers and diagnostics. |
| `results` | Machine readable experiment output. |
| `artifacts` | Trained model checkpoints and fitted policies. |

## What has to be running

Four servers and one client, five processes in total.

| Process | Repository | Port | Role |
| --- | --- | --- | --- |
| Reasoning agent | `Enigma-AIAgent` | 8000 | FastAPI and websockets |
| Sensor | `Enigma-ML-Layer` | 8765 | Websocket server, scores arriving flows |
| Normal traffic sink | `Enigma-ML-Layer` | 9000 | Receives flows the sensor judged benign |
| Dashboard | `Enigma-Frontend` | 3000 | Next.js development server |
| Streamer | `Enigma-ML-Layer` | none | Client, replays UNSW-NB15 into port 8765 |

Signals flow left to right:

```
Streamer  ->  8765 sensor  ->  8000 agent  ->  3000 dashboard
                   |
                   +-------->  9000 normal traffic sink
```

## Environment

The canonical runtime is WSL2 on CPU. The distribution is `enigma-gpu`, which is
not the default distribution on this machine, so every WSL command needs
`-d enigma-gpu` or it will run inside `docker-desktop` and fail to find bash.

Two virtual environments live outside the repositories so that a checkout never
carries them:

- `/opt/enigma/.venv-agent` for the reasoning layer
- `/opt/enigma/.venv-gpu` for the machine learning layer

`CUDA_VISIBLE_DEVICES=-1` is set by every launcher. The model is a twenty
feature dense network and the GPU gains nothing on it. XGBoost is the one
exception and sets its own device where it is used.

The launcher scripts are stored with Windows line endings, so each command below
strips carriage returns before running the script. Invoking them directly will
fail with a confusing `bad interpreter` error.

## Starting everything

Run each block in its own terminal, in this order.

### 1. Reasoning agent, port 8000

```powershell
wsl -d enigma-gpu -e /bin/bash -lc "tr -d '\r' < '/mnt/f/XAI Project/scripts/wsl_start_agent.sh' > /tmp/a.sh && bash /tmp/a.sh"
```

### 2. Sensor, port 8765

```powershell
wsl -d enigma-gpu -e /bin/bash -lc "tr -d '\r' < '/mnt/f/XAI Project/scripts/wsl_start_sensor.sh' > /tmp/s.sh && bash /tmp/s.sh"
```

Wait for the five ensemble members to finish loading before starting the
streamer. Starting the streamer early drops the first few hundred flows.

### 3. Normal traffic sink and streamer, port 9000

```powershell
wsl -d enigma-gpu -e /bin/bash -lc "tr -d '\r' < '/mnt/f/XAI Project/scripts/wsl_start_stream.sh' > /tmp/t.sh && bash /tmp/t.sh"
```

This single script starts two of the five processes: `Frontend_listener.py` in
the background, then `Streamer.py` in the foreground.

### 4. Dashboard, port 3000

```powershell
cd "F:\XAI Project\Enigma-Frontend\enigma-fe"; npm run dev
```

Then open <http://localhost:3000>.

The dashboard reads its backend address from `enigma-fe/.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000/ws/dashboard
```

That file is gitignored and is not in a fresh checkout. Without it the dashboard
falls back to a hardcoded deployment address rather than your machine, connects
to nothing, and shows an empty feed while reporting no error.

## Checking it is alive

```powershell
Invoke-WebRequest http://localhost:8000/health  -UseBasicParsing
Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing
Invoke-WebRequest http://localhost:3000/api/situations -UseBasicParsing
```

`/health` reports situation counts and adapter tallies. `/metrics` reports per
stage latency percentiles and the analysis backlog. `/api/situations` proves the
dashboard can reach the agent through its own proxy, which is the failure that
an empty feed usually turns out to be.

The first analysis push reaches the browser roughly ten seconds after the
streamer starts, because a situation is only broadcast once a full reasoning
pass has finished. A dashboard that looks empty for the first few seconds is
behaving correctly.

## Stopping everything

```powershell
wsl -d enigma-gpu -e /bin/bash -lc "pkill -f 'uvicorn enigma_reason' ; pkill -f 'main.py --artifacts-dir' ; pkill -f Streamer.py ; pkill -f Frontend_listener.py ; echo stopped"
```

The dashboard stops with Ctrl+C in its own terminal.

## Which processes are up

```powershell
wsl -d enigma-gpu -e /bin/bash -lc "ps aux | grep -E 'uvicorn|main.py|Streamer|Frontend_listener' | grep -v grep"
```

## Running the tests

```powershell
wsl -d enigma-gpu -e /bin/bash -lc "cd '/mnt/f/XAI Project/Enigma-AIAgent' && CUDA_VISIBLE_DEVICES=-1 /opt/enigma/.venv-agent/bin/python -m pytest -q"
```

```powershell
cd "F:\XAI Project\Enigma-Frontend\enigma-fe"; npx tsc --noEmit; npx eslint .
```

## Offline experiments

The experiments do not need any of the five processes. The reasoning stack runs
in process with no transport, which is what makes a Level 9 sweep feasible.

```powershell
wsl -d enigma-gpu -e /bin/bash -lc "cd '/mnt/f/XAI Project' && CUDA_VISIBLE_DEVICES=-1 /opt/enigma/.venv-agent/bin/python scripts/level6_replay.py --seed 42 --tag mock --signals 400"
```

Output lands in `results/level6` as a per iteration run log, per stage latency
percentiles, a run manifest pinning the commit of all three repositories, and a
summary. Pass `--llm real` to drive Gemini instead of the deterministic mock,
and `--cache results/level6/gemini_cache.json` to reuse responses across runs.
