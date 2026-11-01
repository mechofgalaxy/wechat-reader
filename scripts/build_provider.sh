#!/bin/sh
# Normal-user reproducible build; this never runs the acquisition helper.
set -eu
umask 077
[ "$(id -u)" -ne 0 ] || { echo 'Build as the ordinary user.' >&2; exit 2; }
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
go_bin=${1:-go}
case "$("$go_bin" version)" in *'go1.26.5 '*) ;; *) echo 'Use audited Go 1.26.5.' >&2; exit 2;; esac
[ "$(uname -s)-$(uname -m)" = Darwin-arm64 ] || { echo 'Provider build target: Apple Silicon macOS.' >&2; exit 2; }
cd "$root/providers/wxkey/source"
GOTOOLCHAIN=local "$go_bin" test ./cmd/wxkey ./internal/dbfiles ./internal/scan ./internal/verify
GOTOOLCHAIN=local "$go_bin" build -trimpath -o "$root/wxkey" ./cmd/wxkey
python3 - "$root" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);source=root/'providers/wxkey/source'
files={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in sorted(source.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
record={'upstream':'https://github.com/r266-tech/wxkey',
        'upstream_commit':'01e96fa58ce3ff061dce83e4c36f62104ebc6b16',
        'go_version':'1.26.5','target':'darwin-arm64',
        'binary_sha256':hashlib.sha256((root/'wxkey').read_bytes()).hexdigest(),
        'source_hashes':files,'status':'experimental_opt_in',
        'fresh_wechat_acquisition_verified':False,'native_gui_recovery_verified':False}
(root/'access-provider.json').write_text(json.dumps(record,indent=2)+'\n')
print('Built and hashed experimental helper; no acquisition executed.')
PY
