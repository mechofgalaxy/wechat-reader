#!/bin/sh
# Install only this application under a user-owned prefix. No sudo or system Python changes.
set -eu
umask 077
source_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
prefix=${WECHAT_READER_HOME:-"$HOME/.local/share/wechat-reader"}
flavor=core
while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix) prefix=$2; shift 2;;
    --with-voice) flavor=voice; shift;;
    --help) echo 'Usage: ./install.sh [--prefix DIRECTORY] [--with-voice]'; exit 0;;
    *) echo "Unknown option: $1" >&2; exit 2;;
  esac
done
case "$prefix" in /*) ;; *) echo 'Prefix must be an absolute path.' >&2; exit 2;; esac
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) uv_target=aarch64-apple-darwin; uv_sha=60fbd5c8a1ed681845eea28d9d622fcde03c51e91a43465b64a1e17db1ed3472;;
  Linux-x86_64) uv_target=x86_64-unknown-linux-gnu; uv_sha=f29c3e94ffabd7e6f3ba521dba169a9b7ec12100bf3257087f0f24f6123f3645;
    if [ "$flavor" = voice ]; then echo 'MLX voice is supported on Apple Silicon macOS only.' >&2; exit 2; fi;;
  *) echo 'Supported: Apple Silicon macOS; Linux x86_64 core preview. See README.' >&2; exit 2;;
esac
[ ! -L "$prefix" ] || { echo 'Refusing symlink installation prefix.' >&2; exit 2; }
mkdir -p "$prefix"
prefix=$(CDPATH='' cd -- "$prefix" && pwd)
mkdir "$prefix/.install-lock" || { echo 'Another install is active; inspect .install-lock.' >&2; exit 2; }
work=$(mktemp -d "$prefix/.install-XXXXXX")
trap 'rm -rf "$work"; rmdir "$prefix/.install-lock"' EXIT HUP INT TERM
release="$prefix/releases/0.10.0rc4-$flavor"
[ ! -e "$release" ] || { echo "Release already exists: $release. Existing installation preserved." >&2; exit 2; }
mkdir -p "$prefix/bin"
if [ -e "$prefix/bin/wechat-reader" ]; then
  grep -q '^# wechat-reader managed launcher$' "$prefix/bin/wechat-reader" || { echo 'Existing command is not managed by this installer.' >&2; exit 2; }
fi
echo 'Downloading pinned uv 0.13.6 and a private Python 3.12.16 runtime...'
curl --fail --location --proto '=https' --tlsv1.2 --retry 2 \
  "https://github.com/astral-sh/uv/releases/download/0.13.6/uv-$uv_target.tar.gz" -o "$work/uv.tar.gz"
if command -v shasum >/dev/null 2>&1; then actual=$(shasum -a 256 "$work/uv.tar.gz" | cut -d ' ' -f 1);
else actual=$(sha256sum "$work/uv.tar.gz" | cut -d ' ' -f 1); fi
[ "$actual" = "$uv_sha" ] || { echo 'uv checksum mismatch.' >&2; exit 2; }
tar -xzf "$work/uv.tar.gz" -C "$work"
uv="$work/uv-$uv_target/uv"
export UV_PYTHON_INSTALL_DIR="$prefix/python"
export UV_CACHE_DIR="$prefix/cache/uv"
"$uv" --no-config python install --no-bin 3.12.16
mkdir -p "$release/lib"
"$uv" --no-config venv --python 3.12.16 --managed-python "$release/runtime"
if [ "$flavor" = voice ]; then
  [ -d "$source_dir/bin/macos-arm64/wheels" ] || { echo 'Voice installation requires the macOS release archive with its prebuilt codec wheel.' >&2; exit 2; }
  "$uv" --no-config pip sync --python "$release/runtime/bin/python" --require-hashes --only-binary :all: --find-links "$source_dir/bin/macos-arm64/wheels" "$source_dir/requirements-voice.lock"
else
  "$uv" --no-config pip sync --python "$release/runtime/bin/python" --require-hashes --only-binary :all: "$source_dir/requirements-core.lock"
fi
for file in rion_wechat_reader.py reader_app.py runtime_paths.py wechat_voice.py voice_worker.py wechat_images.py media_worker.py image_native.swift; do
  cp "$source_dir/$file" "$release/lib/$file"
done
if [ "$(uname -s)" = Darwin ]; then
  if [ -f "$source_dir/bin/macos-arm64/image_native" ]; then
    cp "$source_dir/bin/macos-arm64/image_native" "$release/lib/image_native"
  else
    command -v swiftc >/dev/null 2>&1 || { echo 'Source installation needs Swift; download the macOS release archive for a prebuilt helper.' >&2; exit 2; }
    swiftc -O "$release/lib/image_native.swift" -o "$release/lib/image_native"
  fi
  chmod 700 "$release/lib/image_native"
fi
if [ "$(uname -s)" = Darwin ]; then
  "$release/runtime/bin/python" -E -s "$release/lib/reader_app.py" self-test --require-sqlcipher
  "$release/runtime/bin/python" -E -s "$release/lib/reader_app.py" runtime-status --require-images
else
  "$release/runtime/bin/python" -E -s "$release/lib/reader_app.py" self-test
fi
"$release/runtime/bin/python" -E -s "$release/lib/reader_app.py" demo
cat > "$work/launcher" <<EOF
#!/bin/sh
# wechat-reader managed launcher
set -eu
umask 077
app_root=\$(CDPATH='' cd -- "\$(dirname -- "\$0")/.." && pwd)
export WECHAT_READER_HOME="\$app_root"
exec "\$app_root/releases/0.10.0rc4-$flavor/runtime/bin/python" -E -s "\$app_root/releases/0.10.0rc4-$flavor/lib/reader_app.py" "\$@"
EOF
chmod 700 "$work/launcher"
if [ -f "$prefix/bin/wechat-reader" ]; then cp "$prefix/bin/wechat-reader" "$release/previous-launcher"; fi
mv "$work/launcher" "$prefix/bin/wechat-reader"
echo "Installed: $prefix/bin/wechat-reader"
echo "Next: \"$prefix/bin/wechat-reader\" runtime-status"
echo "Then: \"$prefix/bin/wechat-reader\" onboard"
echo 'Installation does not establish account access. Existing profiles and speech models are preserved.'
