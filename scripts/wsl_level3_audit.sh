#!/usr/bin/env bash
ML_VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"

export CUDA_VISIBLE_DEVICES=-1
export TF_CPP_MIN_LOG_LEVEL=2
cd "$PROJ/Enigma-ML-Layer"

"$ML_VENV/bin/python" "$PROJ/scripts/audit_leakage.py" --seed 42
