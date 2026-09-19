#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python scripts/level9_ablation.py \
  --seed 42 \
  --llm real \
  --seeds 42,123,456,789,1024 \
  --thresholds 0.30,0.50,0.80 \
  --concurrency "${1:-40}" \
  --progress-seconds 300 \
  > /tmp/l9_run.out 2>/tmp/l9_run.err
echo "EXIT $?"
tail -20 /tmp/l9_run.out
