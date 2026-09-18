#!/usr/bin/env bash
PROJ="/mnt/f/XAI Project"
FE="$PROJ/Enigma-Frontend/enigma-fe"

/opt/enigma/.venv-agent/bin/python "$PROJ/scripts/repair_mojibake.py" \
  "$FE/components/dashboard/HypothesesPanel.tsx" \
  "$FE/components/dashboard/LiveFeed.tsx" \
  "$FE/components/dashboard/SituationOverview.tsx" \
  "$FE/types/dashboard.ts" \
  "$@"

echo
echo "=== remaining non-ascii lines ==="
grep -nP '[^\x00-\x7F]' "$FE/components/dashboard/HypothesesPanel.tsx" \
  "$FE/components/dashboard/LiveFeed.tsx" \
  "$FE/components/dashboard/SituationOverview.tsx" | head -12
