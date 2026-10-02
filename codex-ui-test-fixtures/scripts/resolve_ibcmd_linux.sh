#!/usr/bin/env bash

resolve_ibcmd_path() {
  local value="${1:-}"
  local root_candidate
  local bin_candidate

  if [ -z "$value" ]; then
    printf '%s\n' "Error: set IBCMD or CODEX_IBCMD to an ibcmd executable or 1C version directory" >&2
    return 1
  fi
  case "$value" in
    */) value="${value%/}" ;;
  esac

  if [ -d "$value" ]; then
    root_candidate="$value/ibcmd"
    bin_candidate="$value/bin/ibcmd"
    if [ -e "$root_candidate" ] && [ -e "$bin_candidate" ]; then
      printf 'Error: both ibcmd layouts exist in %s; specify the exact executable path\n' "$value" >&2
      return 1
    fi
    if [ -e "$root_candidate" ]; then
      value="$root_candidate"
    elif [ -e "$bin_candidate" ]; then
      value="$bin_candidate"
    else
      printf 'Error: ibcmd not found; checked %s and %s\n' "$root_candidate" "$bin_candidate" >&2
      return 1
    fi
  fi

  if [ ! -f "$value" ]; then
    printf 'Error: ibcmd not found: %s\n' "$value" >&2
    return 1
  fi
  if [ ! -x "$value" ]; then
    printf 'Error: ibcmd is not executable: %s\n' "$value" >&2
    return 1
  fi
  printf '%s\n' "$value"
}
