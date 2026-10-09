#!/usr/bin/env bash
#
# Regenerates every figure and every reported number in the paper from the
# frozen sub-suite and the committed machine readable results.
#
# Stages 0 to 3 need no API key and no network. Every model response they
# depend on is already summarised in a committed artefact, so the numbers the
# paper quotes are recomputed here rather than copied.
#
# Stage 4 re-runs the experiments against the model. It needs either the
# response caches, which are 75 MB and documented rather than committed, or a
# key in Enigma-AIAgent/.env. It is skipped unless --full is passed, and the
# script reports what it skipped rather than failing silently.
#
# Usage:
#   ./reproduce.sh            offline, regenerates figures and tables
#   ./reproduce.sh --full     additionally re-runs the model experiments
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON="${ENIGMA_PYTHON:-/opt/enigma/.venv-agent/bin/python}"
export CUDA_VISIBLE_DEVICES=-1

FULL=0
[ "${1:-}" = "--full" ] && FULL=1

PASSED=0
SKIPPED=0
FAILED=0
SKIPPED_NAMES=""
FAILED_NAMES=""

say() { printf '\n== %s\n' "$1"; }

step() {
  local name="$1"; shift
  printf '  %-54s ' "$name"
  if "$@" > /tmp/reproduce_step.log 2>&1; then
    printf 'ok\n'
    PASSED=$((PASSED + 1))
  else
    printf 'FAILED\n'
    tail -4 /tmp/reproduce_step.log | sed 's/^/      /'
    FAILED=$((FAILED + 1))
    FAILED_NAMES="$FAILED_NAMES $name"
  fi
}

skip() {
  printf '  %-54s skipped, %s\n' "$1" "$2"
  SKIPPED=$((SKIPPED + 1))
  SKIPPED_NAMES="$SKIPPED_NAMES $1"
}

say "Stage 0  environment"
printf '  %-54s %s\n' "python" "$($PYTHON --version 2>&1)"
printf '  %-54s %s\n' "platform" "$(uname -srm)"
printf '  %-54s %s\n' "cpus" "$(nproc 2>/dev/null || echo unknown)"
printf '  %-54s %s\n' "working directory" "$ROOT"
printf '  %-54s %s\n' "api key present" \
  "$(grep -q 'GOOGLE_API_KEY=.' Enigma-AIAgent/.env 2>/dev/null && echo yes || echo no, not required for stages 0 to 3)"

HAVE_AGENT=0
if [ -d Enigma-AIAgent/enigma_reason ]; then
  HAVE_AGENT=1
  printf '  %-54s %s\n' "Enigma-AIAgent beside the root" "present"
else
  printf '  %-54s %s\n' "Enigma-AIAgent beside the root" "ABSENT"
  echo '      The reasoning layer is its own repository and is not tracked here.'
  echo '      Clone it beside this one to enable the stages that import it:'
  echo '        git clone https://github.com/NitinTheGreat/Enigma-AIAgent.git'
fi

say "Stage 1  frozen inputs verified by content hash"
if [ "$HAVE_AGENT" -eq 1 ]; then
  step "suite and sub-suite hashes" $PYTHON scripts/verify_hashes.py --seed 42
else
  skip "suite and sub-suite hashes" "needs Enigma-AIAgent beside the root"
fi

say "Stage 2  figures"
step "Figure 1  architecture" $PYTHON scripts/make_fig1_architecture.py --seed 42
if [ -f results/clock_study/study_seed42.json ]; then
  step "Figure 2  clock collapse" $PYTHON scripts/make_fig2_clock_collapse.py --seed 42
else
  skip "Figure 2  clock collapse" "results/clock_study/study_seed42.json absent"
fi
if [ -f results/ablation/cells_detail_seed42.json ]; then
  step "Figures 3 and 6  ablation and trajectory" \
    $PYTHON scripts/make_fig3_fig6.py --seed 42 --threshold 0.80
else
  skip "Figures 3 and 6" "results/ablation/cells_detail_seed42.json absent"
fi

say "Stage 3  tables and reported numbers"
step "paper numbers, recomputed from committed results" \
  $PYTHON scripts/reproduce_numbers.py --seed 42

say "Stage 4  model experiments"
if [ "$FULL" -eq 1 ]; then
  if [ "$HAVE_AGENT" -eq 1 ] && [ -f results/ablation/cache_seed42.json ]; then
    step "Level 9 ablation, served from cache" \
      $PYTHON scripts/level9_ablation.py --seed 42 --llm real --concurrency 40
    step "Level 10 repair, served from cache" \
      $PYTHON scripts/level10_repair.py --seed 42 --stage full
  else
    skip "Level 9 and Level 10 re-runs" "needs Enigma-AIAgent and the response caches, see README"
  fi
else
  skip "Level 8, 9 and 10 re-runs" "not requested, pass --full"
fi

say "Summary"
printf '  passed  %d\n' "$PASSED"
printf '  skipped %d%s\n' "$SKIPPED" "${SKIPPED_NAMES:+ ($SKIPPED_NAMES )}"
printf '  failed  %d%s\n' "$FAILED" "${FAILED_NAMES:+ ($FAILED_NAMES )}"
printf '\n'
if [ "$FAILED" -eq 0 ]; then
  printf 'REPRODUCED. Every stage that could run did run.\n'
  exit 0
fi
printf 'INCOMPLETE. %d stage(s) failed.\n' "$FAILED"
exit 1
