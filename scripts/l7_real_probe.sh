#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python - <<'PY'
import os
import sys
from pathlib import Path

root = Path("/mnt/f/XAI Project")
from dotenv import load_dotenv

load_dotenv(root / "Enigma-AIAgent" / ".env")
sys.path.insert(0, str(root / "Enigma-AIAgent"))

from enigma_reason.config import settings
from enigma_reason.graph.runner import _default_llm_factory

print("GOOGLE_API_KEY present:", bool(os.environ.get("GOOGLE_API_KEY")))
print("GEMINI_API_KEY present:", bool(os.environ.get("GEMINI_API_KEY")))
print("ENIGMA_GEMINI_API_KEY present:", bool(os.environ.get("ENIGMA_GEMINI_API_KEY")))
print("settings.gemini_model:", settings.gemini_model)
print("settings.gemini_max_output_tokens:", settings.gemini_max_output_tokens)

model = _default_llm_factory()
reply = model.invoke("Name one reconnaissance technique in under twelve words.")
print("GEMINI REPLY:", repr(reply.content))
PY
