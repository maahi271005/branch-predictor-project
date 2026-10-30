#!/bin/bash
# Out-of-tree ChampSim build for branch-predictor experiments.
#
#   build.sh <binary_name> <predictor> [extra compiler flags...]
#
#   <predictor>  name of branch/<predictor>.bpred
#   extra flags  e.g. -DTAGE_NO_LOOP=1 to build an ablation variant
#
# Equivalent configuration to:  ./build_champsim.sh <predictor> no no no no lru 1
# but it never touches the repository's bin/, obj/ or generated *.cc files,
# so several variants can be built side by side.
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <binary_name> <predictor> [extra flags...]"
    exit 1
fi

NAME=$1; BP=$2; shift 2
EXTRA="$*"

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
CS="$ROOT/champsim"
OUT="$ROOT/build"
CXX=${CXX:-g++}
CFLAGS="-Wall -O3 -std=c++11 -I$CS/inc"

[ -f "$CS/branch/$BP.bpred" ] || { echo "[ERROR] no branch/$BP.bpred"; exit 1; }
mkdir -p "$OUT/common" "$OUT/bp" "$OUT/bin"

# Predictor-independent objects (rebuilt only when core sources change).
COMMON_SRC=(
    "src/block.cc" "src/cache.cc" "src/dram_controller.cc" "src/main.cc" "src/ooo_cpu.cc" "src/uncore.cc"
    "prefetcher/no.l1i_pref" "prefetcher/no.l1d_pref" "prefetcher/no.l2c_pref" "prefetcher/no.llc_pref"
    "prefetcher/kpcp_util.cc"
    "replacement/base_replacement.cc" "replacement/lru.llc_repl"
)
OBJS=()
for s in "${COMMON_SRC[@]}"; do
    o="$OUT/common/$(echo "$s" | tr '/.' '__').o"
    OBJS+=("$o")
    if [ ! -f "$o" ] || [ "$CS/$s" -nt "$o" ] || [ -n "$(find "$CS/inc" -newer "$o" -name '*.h' | head -1)" ]; then
        $CXX $CFLAGS -x c++ -c "$CS/$s" -o "$o.tmp.$$" && mv "$o.tmp.$$" "$o"
    fi
done

$CXX $CFLAGS $EXTRA -x c++ -c "$CS/branch/$BP.bpred" -o "$OUT/bp/$NAME.o"
$CXX "${OBJS[@]}" "$OUT/bp/$NAME.o" -o "$OUT/bin/$NAME"

{
    echo "binary: $NAME"
    echo "predictor: branch/$BP.bpred"
    echo "predictor_sha256: $(sha256sum "$CS/branch/$BP.bpred" | cut -d' ' -f1)"
    echo "extra_flags: $EXTRA"
    echo "config: l1i=no l1d=no l2c=no llc=no repl=lru cores=1"
    echo "compiler: $($CXX --version | head -1)"
    echo "built: $(date -Iseconds)"
} > "$OUT/bin/$NAME.buildinfo"
echo "built $OUT/bin/$NAME"
