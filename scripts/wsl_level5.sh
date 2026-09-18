#!/usr/bin/env bash
ML_VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"

export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1

cd "$PROJ/Enigma-ML-Layer"
"$ML_VENV/bin/python" run_level5_baselines.py "$@"
