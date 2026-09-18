#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
IBCMD="${IBCMD:-${CODEX_IBCMD:-}}"
IB_PATH="${IB_PATH:?IB_PATH is required}"
CFE="${CFE:?CFE is required}"
EXTENSION_NAME="${EXTENSION_NAME:-CodexTestBridge}"
IB_USER="${IB_USER:-}"
IB_PASSWORD="${IB_PASSWORD:-}"
DATA="${DATA:?DATA is required and must name a dedicated ibcmd runtime directory}"
. "$SCRIPT_DIR/resolve_ibcmd_linux.sh"

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

IBCMD="$(resolve_ibcmd_path "$IBCMD")"
[ -d "$IB_PATH" ] || fail "file infobase directory not found: $IB_PATH"
[ -s "$CFE" ] || fail "CFE not found or empty: $CFE"
[ -n "$EXTENSION_NAME" ] || fail "EXTENSION_NAME cannot be empty"
mkdir -p "$DATA"

BASE_ARGS=(config --data "$DATA" "--database-path=$IB_PATH")
if [ -n "$IB_USER" ]; then
  BASE_ARGS+=(--user "$IB_USER")
fi
if [ -n "$IB_PASSWORD" ]; then
  BASE_ARGS+=(--password "$IB_PASSWORD")
fi

"$IBCMD" "${BASE_ARGS[@]}" load --extension="$EXTENSION_NAME" --force "$CFE"
"$IBCMD" "${BASE_ARGS[@]}" check --extension="$EXTENSION_NAME" --force
"$IBCMD" "${BASE_ARGS[@]}" extension update --name="$EXTENSION_NAME" --active=yes --safe-mode=no --unsafe-action-protection=no
"$IBCMD" "${BASE_ARGS[@]}" apply --extension="$EXTENSION_NAME" --force --dynamic=disable --session-terminate=force
"$IBCMD" "${BASE_ARGS[@]}" extension info --name="$EXTENSION_NAME"
