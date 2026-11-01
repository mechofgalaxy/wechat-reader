#!/usr/bin/env python3
"""Build deterministic allowlisted source and macOS archives; never archive the working directory."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
from check_public import ROOT,files,main as check_public

VERSION='0.10.0rc2'
PREFIX=f'wechat-reader-{VERSION}'
EPOCH=1793491200

def archive(path,entries):
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=EPOCH) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as tar:
                for name,source in sorted(entries):
                    data=source.read_bytes();info=tarfile.TarInfo(f'{PREFIX}/{name}')
                    info.size=len(data);info.mtime=EPOCH;info.mode=0o755 if name in ('install.sh','wechat-reader','bin/macos-arm64/image_native') else 0o644
                    tar.addfile(info,io.BytesIO(data))

def main():
    check_public();out=ROOT/'dist';out.mkdir(exist_ok=True)
    entries=[(name,ROOT/name) for name in files()]
    helper=ROOT/'image_native'
    if not helper.is_file():raise SystemExit('Compile image_native from the included Swift source first.')
    info={'version':VERSION,'source_files':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in entries},
          'native_helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'native_target':'arm64-apple-macosx14.0'}
    manifest=out/'build-manifest.json';manifest.write_text(json.dumps(info,indent=2)+'\n')
    entries.append(('build-manifest.json',manifest))
    source=out/f'{PREFIX}-source.tar.gz';mac=out/f'{PREFIX}-macos-arm64.tar.gz'
    wheel=next((ROOT/'bin/macos-arm64/wheels').glob('pilk-*.whl'))
    archive(source,entries);archive(mac,entries+[('bin/macos-arm64/image_native',helper),(str(wheel.relative_to(ROOT)),wheel)])
    (out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in (source,mac,manifest)))
    print((out/'SHA256SUMS').read_text(),end='')

if __name__=='__main__':main()
