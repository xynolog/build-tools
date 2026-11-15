#!/usr/bin/env bash
# Install the osv-scanner release advisories.py runs, checked against the
# SHA-256 GitHub records for that release's asset, into the directory named.
#
#   bash build-tools/install-osv-scanner.sh "$RUNNER_TEMP/bin"
#
# A new version is a change here: the version and every platform's checksum.
set -euo pipefail

VERSION=v2.7.0

[[ $# -eq 1 ]] || { echo 'Usage: install-osv-scanner.sh <directory>' >&2; exit 2; }
destination="$1"

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) asset=osv-scanner_linux_amd64 sha256=160c6253e2922e9e0a6a9771c5c4c40a4b3c6090b34a3cdd5e80c96cc2e4218b ;;
  Linux-aarch64) asset=osv-scanner_linux_arm64 sha256=4061ef4c021ed3c47f203b818f337e351336cc5cd67c0274fc36bd1dfc728dd7 ;;
  Darwin-x86_64) asset=osv-scanner_darwin_amd64 sha256=e82c5df7ab0a42dff29a1cd0660711447b56b4c0483ff66ad8634df10fd81a45 ;;
  Darwin-arm64) asset=osv-scanner_darwin_arm64 sha256=d4926ef8da134332543be276dff157e4c170f99ad91fc48e89448a8816bdf70b ;;
  *) echo "No osv-scanner $VERSION release for $(uname -s) $(uname -m)." >&2; exit 2 ;;
esac

mkdir -p "$destination"
download="$(mktemp "${TMPDIR:-/tmp}/osv-scanner.XXXXXX")"
trap 'rm -f "$download"' EXIT
curl --fail --silent --show-error --location --output "$download" \
  "https://github.com/google/osv-scanner/releases/download/$VERSION/$asset"
actual="$(shasum -a 256 "$download" | awk '{print $1}')"
[[ "$actual" == "$sha256" ]] || {
  echo "osv-scanner $VERSION $asset has SHA-256 $actual, not the $sha256 recorded here." >&2
  exit 1
}
install -m 0755 "$download" "$destination/osv-scanner"
