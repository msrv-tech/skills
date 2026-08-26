#!/usr/bin/env bash
set -euo pipefail

IBCMD="${IBCMD:-ibcmd}"
IB_PATH="${IB_PATH:?IB_PATH is required}"
CFE="${CFE:?CFE is required}"
EXTENSION_NAME="${EXTENSION_NAME:-CodexTestBridge}"
IB_USER="${IB_USER:?IB_USER is required}"
IB_PASSWORD="${IB_PASSWORD:-}"

BASE_ARGS=(config "--database-path=$IB_PATH" --user "$IB_USER" --password "$IB_PASSWORD")

"$IBCMD" "${BASE_ARGS[@]}" load --extension="$EXTENSION_NAME" --force "$CFE"
"$IBCMD" "${BASE_ARGS[@]}" check --extension="$EXTENSION_NAME" --force
"$IBCMD" "${BASE_ARGS[@]}" extension update --name="$EXTENSION_NAME" --active=yes --safe-mode=no --unsafe-action-protection=no
"$IBCMD" "${BASE_ARGS[@]}" apply --extension="$EXTENSION_NAME" --force --dynamic=disable --session-terminate=force
"$IBCMD" "${BASE_ARGS[@]}" extension info --name="$EXTENSION_NAME" || true
