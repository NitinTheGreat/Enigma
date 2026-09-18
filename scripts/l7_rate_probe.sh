#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python scripts/probe_rate_limit.py \
  --seed 42 --requests "${1:-12}" --concurrency "${2:-6}"
