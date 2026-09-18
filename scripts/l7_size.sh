#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python scripts/level7_validate.py \
  --seed 42 --llm fallback --limit "${1:-2}" --tag "sizing${1:-2}" \
  > /tmp/sizing.out 2>/dev/null
head -4 /tmp/sizing.out
grep -E "^model calls|^convergence max|^termination" /tmp/sizing.out || true
