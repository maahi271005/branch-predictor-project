#!/bin/bash
# Build every binary used by the multi-trace evaluation (stage M_*).
# Same configuration and flags as the previous 10-trace study
# (see README.md): build.sh is unchanged.
#
#   ChampSim default predictors : bimodal gshare perceptron hashed_perceptron
#   proposed (TFL-TAGE-SC-L)    : tsl_proposed  = tagescl -DTSL_IMHIST -DTSL_BHIST  (== branch/tfl_tage_scl.bpred)
#   project reference baselines : tsl_base      = tagescl -DTSL_NO_IMLI           (== branch/tage_scl.bpred)
#                                 tage          = tagescl -DTSL_NO_SC -DTSL_NO_LOOP (== branch/tage.bpred)
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
B="$ROOT/experiments/scripts/build.sh"
LOG="$ROOT/build/logs"
mkdir -p "$LOG"

# Shared core objects first (avoids several builds compiling them at once).
"$B" bimodal bimodal > "$LOG/bimodal.log" 2>&1 || { echo "FAIL bimodal"; exit 1; }
echo "ok   bimodal"

build() {
    name=$1; shift
    if "$B" "$name" "$@" > "$LOG/$name.log" 2>&1; then echo "ok   $name"; else echo "FAIL $name (see $LOG/$name.log)"; fi
}
build gshare gshare &
build perceptron perceptron &
build hashed_perceptron hashed_perceptron &
build tsl_proposed tagescl -DTSL_IMHIST -DTSL_BHIST &
build tsl_base tagescl -DTSL_NO_IMLI &
build tage tagescl -DTSL_NO_SC -DTSL_NO_LOOP &
wait
