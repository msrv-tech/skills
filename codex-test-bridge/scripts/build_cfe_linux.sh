#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WORK="${WORK:-/tmp/codex-test-bridge-build}"
OUT="${OUT:-$ROOT/codex-test-bridge.cfe}"
IBCMD="${IBCMD:-${CODEX_IBCMD:-}}"
. "$ROOT/scripts/resolve_ibcmd_linux.sh"

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

IBCMD="$(resolve_ibcmd_path "$IBCMD")"
[ -d "$ROOT/src" ] || fail "bridge sources not found: $ROOT/src"
[ "$WORK" != "/" ] || fail "WORK cannot be /"

WORK="$(mkdir -p "$(dirname -- "$WORK")" && cd -- "$(dirname -- "$WORK")" && pwd)/$(basename -- "$WORK")"
OUT_DIR="$(mkdir -p "$(dirname -- "$OUT")" && cd -- "$(dirname -- "$OUT")" && pwd)"
OUT="$OUT_DIR/$(basename -- "$OUT")"

rm -rf "$WORK"
mkdir -p "$WORK/data"

"$IBCMD" --version
"$IBCMD" infobase create --database-path "$WORK/ib"
"$IBCMD" extension --database-path "$WORK/ib" create \
  --name=CodexTestBridge --name-prefix=CTB --purpose=add-on
"$IBCMD" config --data "$WORK/data" --database-path "$WORK/ib" import \
  --extension=CodexTestBridge "$ROOT/src"
"$IBCMD" config --data "$WORK/data" --database-path "$WORK/ib" check \
  --extension=CodexTestBridge --force
"$IBCMD" config --data "$WORK/data" --database-path "$WORK/ib" save \
  --extension=CodexTestBridge "$OUT"

[ -s "$OUT" ] || fail "ibcmd completed without creating a non-empty CFE: $OUT"
printf '%s\n' "$OUT"

