#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WORK="${WORK:-/tmp/codex-ui-test-fixtures-build}"
OUT="${OUT:-$ROOT/codex-ui-test-fixtures.cfe}"
IBCMD="${IBCMD:-${CODEX_IBCMD:-}}"
. "$ROOT/scripts/resolve_ibcmd_linux.sh"

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

IBCMD="$(resolve_ibcmd_path "$IBCMD")"
[ -d "$ROOT/src" ] || fail "fixture extension sources not found: $ROOT/src"
[ "$WORK" != "/" ] || fail "WORK cannot be /"

WORK="$(mkdir -p "$(dirname -- "$WORK")" && cd -- "$(dirname -- "$WORK")" && pwd)/$(basename -- "$WORK")"
OUT_DIR="$(mkdir -p "$(dirname -- "$OUT")" && cd -- "$(dirname -- "$OUT")" && pwd)"
OUT="$OUT_DIR/$(basename -- "$OUT")"

rm -rf "$WORK"
mkdir -p "$WORK/data"

"$IBCMD" --version
"$IBCMD" infobase create --database-path "$WORK/ib"
"$IBCMD" extension --database-path "$WORK/ib" create \
  --name=CodexUITestFixtures --name-prefix=CTF --purpose=add-on
"$IBCMD" config --data "$WORK/data" --database-path "$WORK/ib" import \
  --extension=CodexUITestFixtures "$ROOT/src"
"$IBCMD" config --data "$WORK/data" --database-path "$WORK/ib" check \
  --extension=CodexUITestFixtures --force
"$IBCMD" config --data "$WORK/data" --database-path "$WORK/ib" save \
  --extension=CodexUITestFixtures "$OUT"

[ -s "$OUT" ] || fail "ibcmd completed without creating a non-empty CFE: $OUT"
printf '%s\n' "$OUT"
