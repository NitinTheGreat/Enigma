#!/usr/bin/env bash
cd "/mnt/f/XAI Project/Enigma-AIAgent"
export CUDA_VISIBLE_DEVICES=-1
export PYTHONUNBUFFERED=1
/opt/enigma/.venv-agent/bin/python - <<'PY'
import enigma_reason.main
import enigma_reason.replay
import enigma_reason.observability
print("imports ok")
PY
