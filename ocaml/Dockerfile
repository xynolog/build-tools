# The OCaml toolchain's image: the pinned base, with the pinned opam repository
# and dune. toolchain-image.sh builds it, with this directory as its context,
# and tags it by a digest of this file and of each file it copies.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
RUN apt-get update && apt-get install --yes --no-install-recommends \
    python3 build-essential pkg-config libgmp-dev libssl-dev openssl ca-certificates git curl \
    && rm -rf /var/lib/apt/lists/*
USER opam
COPY --chown=opam:opam toolchain.json /tmp/xynolog-ocaml-toolchain.json
RUN python3 - <<'PYTHON'
import json
import subprocess
pins = json.load(open('/tmp/xynolog-ocaml-toolchain.json'))
actual = subprocess.check_output(['opam', 'exec', '--', 'ocamlc', '-version'], text=True).strip()
if actual != pins['ocaml']:
    raise SystemExit(f"OCaml compiler mismatch: expected {pins['ocaml']}, got {actual}")
subprocess.run(['opam', 'repository', 'set-url', '--yes', 'default',
    'git+https://github.com/ocaml/opam-repository.git#' + pins['opamRepository']], check=True)
subprocess.run(['opam', 'install', '--yes', 'dune.' + pins['dune']], check=True)
PYTHON
USER root
ENTRYPOINT ["opam", "exec", "--root", "/home/opam/.opam", "--"]
