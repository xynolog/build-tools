# build-tools

The build scripts the xynolog repositories share. Each repository pins this one
as a git submodule at `build-tools/`, beside `protocol/`, and runs the scripts
from there. A repository takes a fix by moving its pin.

| Script | What it does | How a repository uses it |
|---|---|---|
| `container-runtime.sh` | Picks a container engine that answers (Apple `container`, Docker, Podman, or `CONTAINER_RUNTIME`), without starting one or pulling an image | `source "$ROOT/build-tools/container-runtime.sh"`, then `detect_container_runtime` |
| `make-help.awk` | `make help`: the Makefile's `##` lines, aligned and wrapped | `awk [-v list="$(LIST)"] -f build-tools/make-help.awk Makefile Makefile` |
| `test_make_help.py` | Checks that `make help` lists every public target and nothing else | `python3 build-tools/test_make_help.py --root . [--list '<placeholder>=VARIABLE']` |
| `prepare-sdk-artifacts.sh` | Prints the SDK artifact bundle a product builds from: `SDK_ARTIFACTS` verified, or one resolved from the `SDK_REPO` checkout, against the repository's Protocol pin | `bash build-tools/prepare-sdk-artifacts.sh <language>...` |
| `advisories.py` | Fails on any published advisory for a dependency in a tracked lockfile (or one CI resolved) that `advisories.toml` does not ignore with a reason, and on an ignore that matched nothing | `python3 build-tools/advisories.py --root . [--lockfile PATH]`, with osv-scanner on PATH |
| `install-osv-scanner.sh` | Installs the osv-scanner release `advisories.py` runs, checked against its recorded SHA-256 | `bash build-tools/install-osv-scanner.sh <directory>` |

Only what at least two repositories run belongs here. `tests/` holds the
scripts' own tests; CI runs them, `tests/live_osv_scanner.py` against the real
scanner, and `test_make_help.py` against the consumer Makefile in
`tests/consumer/`.
