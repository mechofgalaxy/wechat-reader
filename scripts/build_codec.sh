#!/bin/sh
# Developer build; ordinary users receive this wheel in the macOS archive.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
: "${UV_BIN:?Set UV_BIN to the reviewed uv executable}"
: "${BUILD_PYTHON:?Set BUILD_PYTHON to Python 3.12 for macOS arm64}"
cd "$root"
export CFLAGS="-g0 -O2 -ffile-prefix-map=$HOME=. -ffile-prefix-map=/private/tmp=."
"$UV_BIN" --no-config --no-cache build --wheel --python "$BUILD_PYTHON" \
  --build-constraints requirements-voice.lock --out-dir bin/macos-arm64/wheels vendor/pilk-0.2.4.tar.gz
echo 'Before release: inspect wheel paths/licenses, hash the exact wheel and update its pilk hash in requirements-voice.lock.'
