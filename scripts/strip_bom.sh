#!/usr/bin/env bash
PROJ="/mnt/f/XAI Project"
cd "$PROJ"

stripped=0
while IFS= read -r -d '' file; do
  if head -c 3 "$file" | od -An -tx1 | tr -d ' \n' | grep -qi '^efbbbf'; then
    sed -i '1s/^\xEF\xBB\xBF//' "$file"
    echo "stripped BOM: $file"
    stripped=$((stripped + 1))
  fi
done < <(find Enigma-ML-Layer Enigma-AIAgent scripts -name '*.py' -not -path '*/.venv/*' -print0)

echo "total stripped: $stripped"
