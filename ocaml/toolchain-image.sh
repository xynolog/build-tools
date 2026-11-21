#!/usr/bin/env bash
# toolchain-image.sh PROJECT...: hold each dune project to the OCaml
# toolchain's pins (check-toolchain.py), then tag the toolchain's image
# xynolog-ocaml-toolchain. The image is built only from this directory's
# Dockerfile and toolchain.json, so it is tagged by their digest too, and
# built from the pinned base only when no image has that tag: one an earlier
# run built, or a CI job loaded from its cache, is used as it is. Its
# apt packages are those of the build that made it, until the pins change.
#
# toolchain-image.sh --tag prints that tag.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd -P)"

image_tag() {
  python3 - "$HERE/Dockerfile" "$HERE/toolchain.json" <<'PYTHON'
import hashlib
import sys
digest = hashlib.sha256()
for path in sys.argv[1:]:
    digest.update(hashlib.sha256(open(path, 'rb').read()).digest())
print('xynolog-ocaml-toolchain:' + digest.hexdigest()[:16])
PYTHON
}

if [[ "$*" == --tag ]]; then
  image_tag
  exit
fi
if (($# == 0)) || [[ " $* " == *' --tag '* ]]; then
  echo 'Usage: toolchain-image.sh PROJECT... | --tag' >&2
  exit 2
fi

source "$HERE/../container-runtime.sh"
python3 "$HERE/check-toolchain.py" "$@"
RUNTIME="$(detect_container_runtime)"
IMAGE="$(image_tag)"
if ! "$RUNTIME" image inspect "$IMAGE" >/dev/null 2>&1; then
  "$RUNTIME" build --build-arg "BASE_IMAGE=$(python3 "$HERE/check-toolchain.py" --base-image)" \
    --tag "$IMAGE" --file "$HERE/Dockerfile" "$HERE"
fi
"$RUNTIME" image tag "$IMAGE" xynolog-ocaml-toolchain
