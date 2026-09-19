#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python - <<'PY' 2>/dev/null
import sys

sys.path.insert(0, "Enigma-AIAgent")
from scenarios.semantic import EmbeddingMatcher

matcher = EmbeddingMatcher()
texts = [
    "Persistent external reconnaissance from a limited set of distinct sources.",
    "Sustained external reconnaissance from multiple distinct sources.",
]
for text in texts:
    scores = matcher.assign(text).similarities
    print(text)
    print("   data_exfiltration    %.4f" % scores["data_exfiltration"])
    print("   reconnaissance_sweep %.4f" % scores["reconnaissance_sweep"])
    print("   threshold            %.2f" % matcher.threshold)
    print("   scored as data_exfiltration:",
          matcher.matches_category(text, "data_exfiltration", ()))
    print()
PY
