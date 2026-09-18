#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python scripts/level7_validate.py \
  --seed "${2:-42}" \
  --llm real \
  --limit "${1:-4}" \
  --cache results/scenarios/gemini_cache_real.json \
  --tag real \
  > /tmp/l7_real.out 2>/tmp/l7_real.err
echo "EXIT $?"
cat /tmp/l7_real.out
