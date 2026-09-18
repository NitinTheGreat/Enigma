#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python scripts/level9_subsuite.py \
  --seed "${2:-42}" --per-regime "${1:-15}" 2>/dev/null
