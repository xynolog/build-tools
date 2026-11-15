#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"
expected_protocol="$(git -C "$ROOT" ls-tree HEAD protocol | awk '{print $3}')"
actual_protocol="$(git -C "$ROOT/protocol" rev-parse HEAD 2>/dev/null || true)"
[[ -n "$expected_protocol" && "$actual_protocol" == "$expected_protocol" ]] || {
  echo "Protocol submodule does not match this repository's pin (${expected_protocol:-missing})." >&2
  exit 2
}
[[ -z "$(git -C "$ROOT/protocol" status --porcelain --untracked-files=all)" ]] || {
  echo 'Protocol submodule has local changes; pin the intended Protocol revision before building.' >&2
  exit 2
}
if [[ -n "${SDK_ARTIFACTS:-}" ]]; then
  verify_args=()
  for language in "$@"; do verify_args+=(--language "$language"); done
  python3 "$SDK_ARTIFACTS/tools/verify-artifact-bundle.py" "$SDK_ARTIFACTS" \
    --protocol-commit "$expected_protocol" "${verify_args[@]}" >/dev/null
  cd "$SDK_ARTIFACTS" && pwd -P
else
  [[ -n "${SDK_REPO:-}" ]] || {
    echo "Set SDK_REPO to an SDK checkout, or SDK_ARTIFACTS to an artifact bundle." >&2
    exit 2
  }
  [[ -d "$SDK_REPO/scripts" ]] || {
    echo "SDK checkout not found at $SDK_REPO; set SDK_REPO or SDK_ARTIFACTS." >&2
    exit 2
  }
  SDK_REPO="$(cd "$SDK_REPO" && pwd -P)"
  bundle="$(bash "$SDK_REPO/scripts/resolve-artifact-bundle.sh" "$@")"
  python3 "$SDK_REPO/scripts/verify-artifact-bundle.py" "$bundle" \
    --protocol-commit "$expected_protocol" >/dev/null
  printf '%s\n' "$bundle"
fi
