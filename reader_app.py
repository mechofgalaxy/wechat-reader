"""Public application entry point and explicit per-account onboarding."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import struct
import sys
import tempfile
import zlib

from runtime_paths import MODELS, model_path, state_root
import rion_wechat_reader as reader

def output(data):
    print(json.dumps(data,ensure_ascii=False,indent=2))

def run_core(args):
    previous=sys.argv
    try:
        sys.argv=[previous[0],*args]
        return reader.main()
    finally:sys.argv=previous

def image_runtime_status(helper=None):
    helper=Path(helper) if helper is not None else Path(__file__).with_name('image_native')
    result={'present':helper.is_file(),'execution_tested':False,'ready':False}
    if platform.system()!='Darwin':return {**result,'status':'unsupported_platform'}
    if not result['present']:return {**result,'status':'helper_missing'}
    try:
        attributes=subprocess.run(['/usr/bin/xattr',str(helper)],capture_output=True,timeout=5)
        if attributes.returncode:return {**result,'status':'helper_metadata_unreadable'}
        if b'com.apple.quarantine' in attributes.stdout.splitlines():
            return {**result,'status':'macos_security_review_required'}
    except (OSError,subprocess.TimeoutExpired):return {**result,'status':'helper_metadata_unreadable'}
    # Generated blank pixels exercise ImageIO and Vision without reading user files.
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff'*192)*64))+chunk(b'IEND',b'')
    result['execution_tested']=True
    try:
        probe=subprocess.run([str(helper),'ocr','-'],input=png,capture_output=True,timeout=15)
        data=json.loads(probe.stdout)
        result['ready']=probe.returncode==0 and data.get('ok') is True and data.get('ocr',{}).get('status')=='ok'
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
    return {**result,'status':'ready' if result['ready'] else 'helper_execution_failed'}

def runtime_status():
    from importlib.util import find_spec
    image_status=image_runtime_status()
    return {'version':reader.VERSION,'platform':platform.system(),'architecture':platform.machine(),
            'python':platform.python_version(),'database_driver':find_spec('sqlcipher3') is not None,
            'zstandard':find_spec('zstandard') is not None,'media_codec':find_spec('av') is not None,
            'image_ocr':image_status['ready'],'image_helper':image_status,
            'voice_codec':find_spec('pilk') is not None,'voice_asr':find_spec('mlx_whisper') is not None,
            'models':{name:(model_path(name)/'config.json').is_file() for name in MODELS},
            'account_access':'not_checked','network_used':False}

def demo():
    """Use only generated fictional data; no account or notification access."""
    import sqlite3
    with tempfile.TemporaryDirectory(prefix='wechat-reader-demo-') as tmp:
        root=Path(tmp);session=root/'session.db';contact=root/'contact.db';message=root/'message.db'
        with sqlite3.connect(session) as c:
            c.execute('CREATE TABLE SessionTable(username TEXT, unread_count INTEGER, summary TEXT, last_timestamp INTEGER, last_msg_local_id INTEGER)')
            c.execute('INSERT INTO SessionTable VALUES(?,?,?,?,?)',('demo_friend',0,'Fictional release demo',1700000000,1))
        with sqlite3.connect(contact) as c:
            c.execute('CREATE TABLE contact(username TEXT,nick_name TEXT,remark TEXT,local_type INTEGER)')
            c.execute('INSERT INTO contact VALUES(?,?,?,?)',('demo_friend','Demo Friend','',1))
        table='Msg_'+hashlib.md5(b'demo_friend').hexdigest()
        with sqlite3.connect(message) as c:
            c.execute('CREATE TABLE Name2Id(user_name TEXT)');c.execute('INSERT INTO Name2Id VALUES(?)',('demo_friend',))
            c.execute(f'CREATE TABLE "{table}"(local_id INTEGER,server_id INTEGER,local_type INTEGER,real_sender_id INTEGER,create_time INTEGER,message_content TEXT,WCDB_CT_message_content INTEGER)')
            c.execute(f'INSERT INTO "{table}" VALUES(1,1001,1,1,1700000000,?,0)',('This is a fictional demo message.',))
        keys=root/'keys.json';keys.write_text('{"keys":{}}');keys.chmod(0o600)
        config=root/'config.json';config.write_text(json.dumps({'session_db':str(session),'contact_db':str(contact),'message_dbs':[str(message)],'self_username':'demo_me','keys_file':str(keys)}));config.chmod(0o600)
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (session,contact,message)}
        rc=run_core(['--config',str(config),'search','fictional','--pretty'])
        if before!={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before}:raise RuntimeError('demo source changed')
        return rc

def onboard(args):
    p=argparse.ArgumentParser(description='Connect an explicitly selected, authorized account. No key acquisition.')
    p.add_argument('--name');p.add_argument('--database-root');p.add_argument('--access-file')
    p.add_argument('--self-username',default='',help='Your verified account username; otherwise inference is explicitly unverified.')
    ns=p.parse_args(args)
    if not sys.stdin.isatty() and not all((ns.name,ns.database_root,ns.access_file)):
        p.error('Supply --name, --database-root and --access-file in noninteractive mode.')
    name=ns.name or input('Local account label (letters/numbers/hyphen): ').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}',name):p.error('Invalid account label.')
    dbroot=Path(ns.database_root or input('Path to your authorized db_storage directory: ').strip()).expanduser().resolve()
    source=Path(ns.access_file or input('Path to your existing authorized access-material JSON: ').strip()).expanduser().resolve()
    if not dbroot.is_dir() or not source.is_file():p.error('Database directory or access-material file is missing.')
    folder=state_root()/'profiles'/name
    if folder.exists():p.error('Account label already exists; existing profiles are never overwritten.')
    folder.mkdir(parents=True,mode=0o700)
    keys=folder/'keys.json';config=folder/'reader.json'
    rc=run_core(['--config',str(config),'import-access','--source',str(source),'--keys-file',str(keys),'--database-root',str(dbroot)])
    if rc:return rc
    return run_core(['--config',str(config),'setup','--database-root',str(dbroot),'--keys-file',str(keys),'--self-username',ns.self_username,'--pretty'])

def install_model(args):
    p=argparse.ArgumentParser(description='Explicit network download of a pinned public speech model; no chat upload.')
    p.add_argument('name',choices=MODELS);ns=p.parse_args(args)
    if platform.system()!='Darwin' or platform.machine()!='arm64':p.error('This release supports MLX speech models on Apple Silicon macOS only.')
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    try:from huggingface_hub import snapshot_download
    except ImportError:p.error('Install with --with-voice first.')
    target=model_path(ns.name)
    if (target/'verified-files.json').exists():
        output({'status':'already_installed','model':ns.name});return 0
    repo,revision=MODELS[ns.name]
    print(f'Downloading {repo} at {revision}; several GB may be required.',file=sys.stderr)
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
    snapshot_download(repo_id=repo,revision=revision,token=False,local_dir=str(target),allow_patterns=['*.json','*.safetensors','*.npz','*.tiktoken','*.txt'])
    if not (target/'config.json').is_file() or not any((target/x).is_file() for x in ('weights.safetensors','weights.npz')):
        raise RuntimeError('Incomplete model download')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir() if p.is_file()}
    record=target/'verified-files.json';record.write_text(json.dumps({'repo':repo,'revision':revision,'files':files},indent=2));record.chmod(0o600)
    output({'status':'installed','model':ns.name,'revision':revision,'chat_data_transmitted':False});return 0

def main():
    os.umask(0o077)
    # Legacy global settings cannot silently override a selected public-app profile.
    for name in list(os.environ):
        if name.startswith('RION_WECHAT_READER_'):os.environ.pop(name)
    args=sys.argv[1:]
    if not args or args==['--help']:
        print('WeChat Reader Preview\n\n  runtime-status       Check installed capabilities (no account read)\n  demo                 Read a fictional temporary database\n  connect              Guided first connection for any local agent\n  onboard              Import an explicit existing access file\n  models install NAME  Download a pinned speech model (turbo / large-v3)\n  --profile NAME ...   Run a reader command with that account\n  --config PATH ...    Use an explicit existing account configuration\n  self-test / version / tools / tool-schema / --reader-help\n\nSee README.md for platform and access limitations.');return 0
    if args in (['runtime-status'],['runtime-status','--require-images']):
        data=runtime_status();output(data)
        return 1 if '--require-images' in args and not data['image_ocr'] else 0
    if args==['demo']:return demo()
    if args[0]=='connect':
        import first_run
        return first_run.main(args[1:])
    if args[0]=='onboard':return onboard(args[1:])
    if args[:2]==['models','install']:return install_model(args[2:])
    if args==['--reader-help']:return run_core(['--help'])
    if args[0]=='--profile':
        if len(args)<3 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}',args[1]):raise ValueError('Specify a valid profile name and command')
        config=state_root()/'profiles'/args[1]/'reader.json'
        if not config.is_file():raise ValueError('Profile is not ready. Complete onboard first.')
        args=['--config',str(config),*args[2:]]
    if args[0] not in ('--config','self-test','version','tools','tool-schema'):
        raise ValueError('Select an account explicitly with --profile NAME or --config PATH.')
    return run_core(args)

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,RuntimeError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(2)
