#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python scripts/level8_clock_study.py \
  --seed 42 \
  --llm real \
  --seeds 42,123,456,789,1024 \
  --concurrency "${1:-25}" \
  > /tmp/l8_run.out 2>/tmp/l8_run.err
echo "EXIT $?"
cat /tmp/l8_run.out
