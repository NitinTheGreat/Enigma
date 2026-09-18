#!/usr/bin/env bash
ML_VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"

export CUDA_VISIBLE_DEVICES=-1
export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1

cd "$PROJ/Enigma-ML-Layer"
"$ML_VENV/bin/python" run_level3_experiments.py \
  --smote-strategy minimal \
  --results-dir "$PROJ/results/sensitivity_minimal" \
  --artifacts-dir "$PROJ/artifacts/sensitivity_minimal"
