#!/usr/bin/env python3
"""Public tree check. A bounded aid, not a substitute for reviewing the diff."""
import re
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ALLOWED_BINARY={'tests/fixtures/ocr.png','tests/fixtures/ocr.jpg','tests/fixtures/voice.silk','tests/fixtures/synthetic.hevc','vendor/pilk-0.2.4.tar.gz'}
FORBIDDEN=[rb'/Users/[^/\s]+/',rb'/home/[^/\s]+/',rb'/opt/homebrew/',rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'github_pat_[A-Za-z0-9_]{30,}',rb'sk-[A-Za-z0-9]{32,}']

def files():
    values=(ROOT/'release-files.txt').read_text().splitlines()
    if len(values)!=len(set(values)):raise ValueError('duplicate release path')
    for name in values:
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or not name or (ROOT/p).is_symlink():raise ValueError('unsafe release path')
        if not (ROOT/p).is_file():raise ValueError(f'missing {name}')
    return values

def main():
    errors=[]
    for name in files():
        p=ROOT/name;data=p.read_bytes()
        if name in ALLOWED_BINARY:continue
        try:data.decode('utf-8')
        except UnicodeDecodeError:errors.append(f'unexpected binary: {name}');continue
        if name=='scripts/check_public.py':continue
        if name=='providers/wxkey/lifecycle.patch':
            # Exact public upstream patch: these two test-home literals are fictional.
            if hashlib.sha256(data).hexdigest()!='b7052b04c0703a80099ec0ce77f9f042fbf1bcf04f779c07dde147a888387eb3':
                errors.append('unreviewed upstream patch: '+name)
            data=data.replace(b'/home/user',b'/example-home/user')
        if any(re.search(pattern,data) for pattern in FORBIDDEN):errors.append(f'private path or token pattern: {name}')
        if name.endswith(('.db','.log','.pyc')):errors.append(f'runtime file: {name}')
    if errors:raise SystemExit('\n'.join(errors))
    print(f'Public allowlist check passed: {len(files())} files; synthetic media only.')

if __name__=='__main__':main()
