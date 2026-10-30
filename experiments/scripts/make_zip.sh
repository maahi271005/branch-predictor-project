#!/bin/bash
# Package the complete ChampSim source, predictor, scripts, raw results and documents.
#
#   make_zip.sh [output.zip]
#
# Excludes traces, binaries, object files and other build artefacts.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${1:-$ROOT/submission/TFL_TAGE_SCL_ChampSim.zip}
NAME=TFL_TAGE_SCL_ChampSim
STAGE=$(mktemp -d)
PKG=$STAGE/$NAME
mkdir -p "$PKG"

# ChampSim tree (the repository directory name ends in a space; copy its contents)
tar -C "$ROOT/champsim/" \
    --exclude=./bin --exclude=./obj --exclude=./dpc3_traces --exclude='./results_*' \
    --exclude='./scripts/wget-log*' --exclude=./inc/champsim.h.bak \
    -cf - . | (mkdir -p "$PKG/champsim" && tar -C "$PKG/champsim" -xf -)

mkdir -p "$PKG/experiments"
cp -r "$ROOT/experiments/scripts" "$ROOT/experiments/harness" "$ROOT/experiments/results" "$PKG/experiments/"
cp "$ROOT"/experiments/*.md "$PKG/experiments/"
find "$PKG/experiments" -name '__pycache__' -prune -exec rm -rf {} +
cp -r "$ROOT/research" "$PKG/research"
cp -r "$ROOT/submission/results" "$PKG/results"
cp "$ROOT/submission/README.md" "$PKG/README.md"
cp "$ROOT/submission/Branch_Predictor_Report.docx" "$PKG/"
cp "$ROOT/Branch_Prediction_Assignment_Simple.docx" "$PKG/research/"

rm -f "$OUT"
(cd "$STAGE" && zip -qr "$OUT" "$NAME")
rm -rf "$STAGE"
echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
