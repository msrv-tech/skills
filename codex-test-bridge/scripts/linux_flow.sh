#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
COMMAND="${1:-}"
. "$ROOT/scripts/resolve_ibcmd_linux.sh"

usage() {
  local status="${1:-2}"
  cat >&2 <<'EOF'
Usage:
  linux_flow.sh doctor
  linux_flow.sh run

Required environment:
  CODEX_IBCMD                Exact ibcmd executable, or a 1C 8.5 version directory
                              containing exactly one of ibcmd or bin/ibcmd
  CODEX_1C_EXECUTABLE        Exact executable used for TestClient/TestManager
  CODEX_1C_DATABASE_PATH     Existing file infobase
  CODEX_1C_USERNAME          Existing test user (optional for a base without users)
  CODEX_1C_CONNECTION_FLAG  /F (this flow installs into a file infobase)
  CODEX_1C_CONNECTION_STRING Value for the connection flag
  CODEX_1C_WSAP_MODULE      Existing official wsap24.so module
  CODEX_1C_VRD_PATH          Existing publication default.vrd
  CODEX_1C_BRIDGE_URL        URL ending in /hs/codex-test

Optional environment:
  CODEX_1C_PASSWORD, CODEX_1C_BUILD_WORK, CODEX_1C_BUILD_DATA,
  CODEX_1C_CFE, CODEX_1C_ARTIFACT_DIR, CODEX_1C_WORKER_CONFIG,
  APACHECTL, SYSTEMCTL

The run command performs a real build, install, VRD update, Apache reload,
HTTP checks, and native Xvfb UI smoke. It never invokes sudo.
EOF
  exit "$status"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_env() {
  local name="$1"
  [ -n "${!name:-}" ] || fail "$name is required"
}

resolve_command() {
  local value="$1"
  local resolved
  if [[ "$value" == */* ]]; then
    [ -x "$value" ] || fail "required executable is missing or not executable: $value"
    printf '%s\n' "$value"
    return
  fi
  resolved="$(command -v "$value" 2>/dev/null)" ||
    fail "required command is not installed: $value"
  printf '%s\n' "$resolved"
}

resolve_ibcmd() {
  resolve_ibcmd_path "$CODEX_IBCMD"
}

check_http() {
  "$PYTHON" - "$CODEX_1C_BRIDGE_URL" <<'PY'
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def request(path, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {} if body is None else {"Content-Type": "application/json; charset=utf-8"}
    with opener.open(urllib.request.Request(base_url + path, data=body, headers=headers), timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("ok") is not True:
        raise RuntimeError(f"{path} returned an unsuccessful response: {result}")

request("/health")
request("/command", {"command": "health"})
print("HTTP health checks passed")
PY
}

[ "$#" -eq 1 ] || usage
case "$COMMAND" in
  -h|--help) usage 0 ;;
  doctor|run) ;;
  *) usage ;;
esac

for name in \
  CODEX_IBCMD CODEX_1C_EXECUTABLE CODEX_1C_DATABASE_PATH \
  CODEX_1C_CONNECTION_FLAG CODEX_1C_CONNECTION_STRING \
  CODEX_1C_WSAP_MODULE CODEX_1C_VRD_PATH CODEX_1C_BRIDGE_URL
do
  require_env "$name"
done

[ "$CODEX_1C_CONNECTION_FLAG" = "/F" ] ||
  fail "CODEX_1C_CONNECTION_FLAG must be /F for this file-infobase flow"
[ -d "$CODEX_1C_DATABASE_PATH" ] || fail "file infobase directory not found: $CODEX_1C_DATABASE_PATH"
[ -f "$CODEX_1C_WSAP_MODULE" ] || fail "official wsap24.so module not found: $CODEX_1C_WSAP_MODULE"
case "$(basename -- "$CODEX_1C_WSAP_MODULE")" in
  wsap24.so) ;;
  *) fail "CODEX_1C_WSAP_MODULE must point to wsap24.so" ;;
esac
[ -f "$CODEX_1C_VRD_PATH" ] || fail "VRD file not found: $CODEX_1C_VRD_PATH"
[ -f "$CODEX_1C_EXECUTABLE" ] || fail "1C executable not found: $CODEX_1C_EXECUTABLE"
[ -x "$CODEX_1C_EXECUTABLE" ] || fail "1C executable is not executable: $CODEX_1C_EXECUTABLE"

PYTHON="$(resolve_command python3)"
XVFB="$(resolve_command Xvfb)"
APACHECTL="$(resolve_command "${APACHECTL:-apache2ctl}")"
SYSTEMCTL="$(resolve_command "${SYSTEMCTL:-systemctl}")"
IBCMD="$(resolve_ibcmd)"
export IBCMD
export CODEX_1C_USERNAME="${CODEX_1C_USERNAME:-}"
export CODEX_1C_PASSWORD="${CODEX_1C_PASSWORD:-}"

"$IBCMD" --version
"$XVFB" -help >/dev/null 2>&1
"$APACHECTL" configtest
APACHE_MODULES="$("$APACHECTL" -M 2>&1)" ||
  fail "cannot list loaded Apache modules: $APACHE_MODULES"
[[ "$APACHE_MODULES" == *"_1cws_module"* ]] ||
  fail "Apache has not loaded the official 1C _1cws_module"
"$SYSTEMCTL" is-active --quiet apache2

WORKER_CONFIG="${CODEX_1C_WORKER_CONFIG:-$ROOT/ui-worker.example.json}"
[ -f "$WORKER_CONFIG" ] || fail "worker config not found: $WORKER_CONFIG"

if [ "$COMMAND" = "doctor" ]; then
  check_http
  "$PYTHON" "$ROOT/client.py" --base-url "$CODEX_1C_BRIDGE_URL" \
    doctor --worker-config "$WORKER_CONFIG"
  exit 0
fi

BUILD_WORK="${CODEX_1C_BUILD_WORK:-/tmp/codex-test-bridge-build}"
BUILD_DATA="${CODEX_1C_BUILD_DATA:-/tmp/codex-test-bridge-install-data}"
CFE="${CODEX_1C_CFE:-$ROOT/codex-test-bridge.cfe}"
ARTIFACT_DIR="${CODEX_1C_ARTIFACT_DIR:-$ROOT/artifacts/linux-smoke}"

WORK="$BUILD_WORK" OUT="$CFE" "$ROOT/scripts/build_cfe_linux.sh"
DATA="$BUILD_DATA" IB_PATH="$CODEX_1C_DATABASE_PATH" CFE="$CFE" \
  IB_USER="$CODEX_1C_USERNAME" IB_PASSWORD="${CODEX_1C_PASSWORD:-}" \
  "$ROOT/scripts/install_cfe_linux.sh"
"$PYTHON" "$ROOT/scripts/enable_vrd_linux.py" "$CODEX_1C_VRD_PATH"
"$APACHECTL" configtest
"$SYSTEMCTL" reload apache2
"$SYSTEMCTL" is-active --quiet apache2

check_http
"$PYTHON" "$ROOT/client.py" --base-url "$CODEX_1C_BRIDGE_URL" \
  doctor --worker-config "$WORKER_CONFIG"
"$PYTHON" "$ROOT/client.py" run-ui "$WORKER_CONFIG" \
  "$ROOT/examples/native-ui-smoke.ui.json" \
  --artifact-dir "$ARTIFACT_DIR" --report "$ARTIFACT_DIR/worker.json"
