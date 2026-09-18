#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python scripts/level7_validate.py \
  --seed 42 --llm fallback \
  --suite results/scenarios/sub_suite.jsonl \
  --tag subsuite_sizing \
  > /tmp/subsize.out 2>/dev/null
head -2 /tmp/subsize.out
grep -E "^model calls|^termination" /tmp/subsize.out || true
