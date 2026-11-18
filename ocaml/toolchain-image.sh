#!/usr/bin/env bash
# toolchain-image.sh PROJECT...: hold each dune project to the OCaml
# toolchain's pins (check-toolchain.py), then build the toolchain's image from
# the pinned base, tagged xynolog-ocaml-toolchain.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd -P)"
source "$HERE/../container-runtime.sh"
RUNTIME="$(detect_container_runtime)"

if (($# == 0)); then
  echo 'Usage: toolchain-image.sh PROJECT...' >&2
  exit 2
fi
python3 "$HERE/check-toolchain.py" "$@"
"$RUNTIME" build --build-arg "BASE_IMAGE=$(python3 "$HERE/check-toolchain.py" --base-image)" \
  --tag xynolog-ocaml-toolchain --file "$HERE/Dockerfile" "$HERE"
