#!/bin/bash
# Integrity check of every file in a trace directory (run under Linux/WSL).
#
#   check_traces.sh <trace_dir> <out_file> [parallel=14]
#
# One line per file, sorted by name:
#   name|size_bytes|sha256|md5|xz_index|uncompressed_bytes|xz_test|seconds
# md5 is recorded because Zenodo publishes md5 checksums.
# xz_index : "xz -l" (reads the stream index; fails on truncated files)
# xz_test  : "xz -t" (decompresses the whole file and checks every CRC)
# ChampSim 2021 trace records are 64 bytes, so instructions = uncompressed / 64.
set -u
DIR=$1; OUT=$2; J=${3:-14}
cd "$DIR" || exit 1
check() {
  f=$1; t0=$(date +%s)
  sum=$(sha256sum -- "$f" | cut -d' ' -f1)
  md5=$(md5sum -- "$f" | cut -d' ' -f1)
  if lst=$(xz --robot -l -- "$f" 2>/dev/null); then
    idx=OK; unc=$(printf '%s\n' "$lst" | awk -F'\t' '$1=="totals"{print $5}')
  else
    idx=FAIL; unc=
  fi
  if msg=$(xz -t -- "$f" 2>&1); then st=OK; else st="FAIL:$(printf '%s' "$msg" | tr '\n|' '  ')"; fi
  echo "$f|$(stat -c %s -- "$f")|$sum|$md5|$idx|$unc|$st|$(( $(date +%s) - t0 ))"
}
export -f check
ls -1 | grep -v '^desktop.ini$' | xargs -d '\n' -P "$J" -I{} bash -c 'check "$1"' _ {} | sort > "$OUT"
