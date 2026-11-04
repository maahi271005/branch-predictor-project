#!/bin/bash
# Post-experiment pipeline for the 50-trace evaluation:
#   raw ChampSim outputs -> CSVs -> figures -> report values/tables -> workbook -> PDF -> verification
#
#   bash experiments/scripts/finalize_50trace.sh
#
# PY   python with the standard library (default: python3, or python on Windows)
# VPY  python with matplotlib, openpyxl and pymupdf (default: build/venv)
# TECTONIC  LaTeX engine (default: build/tools/tectonic(.exe), else tectonic on PATH)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
PY=${PY:-$(command -v python3 || command -v python)}
if [ -z "${VPY:-}" ]; then
    for c in build/venv/Scripts/python build/venv/bin/python; do [ -x "$c" ] && VPY=$c && break; done
fi
if [ -z "${TECTONIC:-}" ]; then
    for c in build/tools/tectonic.exe build/tools/tectonic; do [ -x "$c" ] && TECTONIC=$ROOT/$c && break; done
    TECTONIC=${TECTONIC:-tectonic}
fi
S=experiments/scripts

echo "== analysis";  "$PY" -I $S/analyze_50trace.py
echo "== figures";   "$VPY" $S/make_figures_50trace.py
echo "== report values, tables"; "$PY" -I $S/make_report_50trace.py
echo "== workbook";  "$VPY" $S/make_workbook_50trace.py
echo "== PDF"
( cd report_50trace && "$TECTONIC" -k main.tex 2>&1 | grep -iE "error|overfull|undefined" || true )
cp report_50trace/main.pdf report_50trace/TFL-TAGE-SC-L_50trace_Report.pdf
echo "== verification"; "$VPY" -W ignore $S/verify_report_50trace.py
