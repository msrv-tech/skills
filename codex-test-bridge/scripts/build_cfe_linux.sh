#!/usr/bin/env bash
set -eu

PLATFORM="${PLATFORM:-/opt/1cv8/x86_64/8.3.27.1859}"
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WORK="${WORK:-/tmp/codex-test-bridge-build}"
OUT="${OUT:-$ROOT/codex-test-bridge.cfe}"

rm -rf "$WORK"
mkdir -p "$WORK"

"$PLATFORM/ibcmd" infobase create --database-path "$WORK/ib"
"$PLATFORM/ibcmd" extension --database-path "$WORK/ib" create \
  --name=CodexTestBridge --name-prefix=CTB --purpose=add-on
"$PLATFORM/ibcmd" config import --database-path "$WORK/ib" \
  --extension=CodexTestBridge "$ROOT/src"
"$PLATFORM/ibcmd" config check --database-path "$WORK/ib" \
  --extension=CodexTestBridge --force
"$PLATFORM/ibcmd" config save --database-path "$WORK/ib" \
  --extension=CodexTestBridge "$OUT"

echo "$OUT"

