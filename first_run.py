"""Agent-neutral first connection. Discovery is read-only; acquisition is opt-in."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
from types import SimpleNamespace

import rion_wechat_access as access
import rion_wechat_reader as reader
from runtime_paths import state_root, path_within


def discover(home=None):
    home = Path(home or Path.home())
    bases = [home/'Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files',
             home/'Documents/xwechat_files',
             home/'Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat']
    found = []; errors = []
    # Fixed WeChat locations and bounded depth only. No whole-home or key search.
    for base in bases:
        if not base.exists():
            continue
        try:
            access.private_path(base)
            queue = [(base, 0)]; visited = 0
            while queue:
                parent, depth = queue.pop(0)
                visited += 1
                if visited > 200:
                    errors.append('discovery_limit_reached'); break
                for child in sorted(parent.iterdir()):
                    if child.is_symlink() or not child.is_dir():
                        continue
                    if child.name == 'db_storage':
                        found.append(str(child))
                    elif depth < 2 and child.name not in {'msg', 'cache', 'temp', 'logs', 'resource'}:
                        queue.append((child, depth+1))
        except (OSError, access.AccessError):
            errors.append('filesystem_access_required')
    return {'state': 'account_selection_required' if found else 'needs_database_location',
            'candidates': [{'number': i+1, 'database_root': path} for i, path in enumerate(sorted(set(found)))],
            'warnings': sorted(set(errors)), 'chat_content_read': False, 'provider_executed': False,
            'next_action': 'Ask the user to select their own account and authorize local read access. If missing, open and log into WeChat, or supply its data directory.'}


def profile_path(name):
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}', name or ''):
        raise access.AccessError('valid_profile_name_required')
    # Check the un-resolved prefix before runtime_paths resolves it.
    access.private_path(Path(os.environ.get('WECHAT_READER_HOME', str(Path.home()/'.local/share/wechat-reader'))))
    return access.private_path(state_root()/'profiles'/name/'reader.json')


def bundled_provider():
    base = Path(__file__).resolve().parent
    manifest_path = base/'access-provider.json'
    if not manifest_path.is_file():
        raise access.AccessError('macos_release_provider_required')
    manifest = json.loads(manifest_path.read_text())
    helper = base/'wxkey'
    if manifest.get('upstream_commit') != '01e96fa58ce3ff061dce83e4c36f62104ebc6b16':
        raise access.AccessError('provider_manifest_invalid')
    digest = access.provider_digest(helper)
    if digest != manifest.get('binary_sha256'):
        raise access.AccessError('provider_digest_mismatch')
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise access.AccessError('acquisition_platform_not_supported')
    attrs = subprocess.run(['/usr/bin/xattr', str(helper)], capture_output=True, timeout=5)
    if attrs.returncode or b'com.apple.quarantine' in attrs.stdout.splitlines():
        raise access.AccessError('macos_security_review_required')
    return helper, digest


def request_user_consent(root):
    # This is a product UI: the using agent must leave both dialogs to the human.
    # A native Cancel-default prompt also works for agents without interactive stdin.
    message = ('Connect your own WeChat account?\n\nSelected data folder:\n'+str(root)+
               '\n\nThis experimental step may quit and reopen WeChat, create and locally sign a separate copy, '
               'and debug that copy to obtain database access material. You may need to log in again. '
               'The original app is not re-signed; SIP is not disabled. Your password is entered only in '
               'the following macOS authorization dialog and is never stored by this tool. '
               'Keys remain on this Mac. No chats are returned by setup. Fresh-machine compatibility is not yet verified. '
               'Proceed only after saving ongoing work. Cancel leaves WeChat untouched.')
    script = 'display dialog '+json.dumps(message)+' with title "WeChat Reader — first connection" buttons {"Cancel", "Connect my account"} default button "Cancel" cancel button "Cancel"'
    result = subprocess.run(['/usr/bin/osascript', '-e', script], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
                            env={'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'})
    if result.returncode:
        raise access.AccessError('user_cancelled_no_acquisition')


def connect(args):
    config = profile_path(args.name)
    root = access.private_path(Path(args.database_root)) if args.database_root else None
    source = access.private_path(Path(args.access_file)) if args.access_file else None
    if root and (path_within(root, config) or path_within(config.parent, root)):
        raise access.AccessError('profile_and_database_must_be_separate')
    if not config.exists() and root is None:
        return discover()
    if config.exists() and root:
        current = reader.DatabaseSet(config)
        paths = [current.session_db, current.contact_db, *current.message_dbs]
        if not paths or any(p and not path_within(root, p) for p in paths):
            raise access.AccessError('existing_profile_belongs_to_different_database')
        root = None  # Verify the actual saved configuration, then reuse it.
    ns = SimpleNamespace(config=config, database_root=root, source=source,
                         max_files=500, apply=args.apply, provider=None, sha256='',
                         confirm_reviewed_provider=False, confirm_side_effects=False, timeout=600)
    outcome = access.onboard(ns)
    if outcome['state'] != 'provider_required':
        return outcome
    helper, digest = bundled_provider()
    ns.provider, ns.sha256 = helper, digest
    outcome = access.onboard(ns)
    if not args.request_access or outcome['state'] != 'authorization_required':
        outcome['next_action'] = 'Explain the exact selected account and listed effects; with user agreement run the same connect command with --request-access. The user must handle both native dialogs.'
        return outcome
    # Check dependencies before interrupting the user or any WeChat process.
    access.preflight_database_access(root)
    access.preflight_debugger()
    request_user_consent(root)
    ns.apply = ns.confirm_reviewed_provider = ns.confirm_side_effects = True
    return access.onboard(ns)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name', help='Explicit new or existing local profile label')
    p.add_argument('--database-root', help='The selected account db_storage directory')
    p.add_argument('--access-file', help='Explicit existing private access file; never its contents')
    p.add_argument('--apply', action='store_true', help='Publish verified existing materials as a new profile')
    p.add_argument('--request-access', action='store_true', help='Ask the human through native dialogs before optional acquisition')
    p.add_argument('--discover', action='store_true')
    p.add_argument('--status', action='store_true', help='Safe support summary for the named profile')
    p.add_argument('--finish-recovery', action='store_true')
    p.add_argument('--confirm-wechat-ready', action='store_true')
    p.add_argument('--confirm-no-acquisition', action='store_true')
    args = p.parse_args(argv)
    try:
        if args.finish_recovery:
            data = access.finish_recovery(args.confirm_wechat_ready, args.confirm_no_acquisition)
        elif args.discover or not args.name:
            data = discover()
        elif args.status:
            config = profile_path(args.name)
            if config.is_file():
                data = access.support_summary(access.access_status(config, None, 500))
            else:
                data = access.support_summary({'state': 'profile_not_configured',
                                               'live_database_read_ok': False,
                                               **access.recovery_status()})
        else:
            data = connect(args)
        print(json.dumps({'ok': True, 'data': data}, ensure_ascii=False, indent=2))
        return 0 if data.get('state') in {'ready', 'recovery_review_completed', 'no_recovery_lock'} else 1
    except (access.AccessError, reader.ReaderError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        code = str(exc) if isinstance(exc, access.AccessError) else 'connection_check_failed'
        print(json.dumps({'ok': False, 'error': {'code': code, 'message': 'No success claimed. Keep existing profiles; inspect the documented state before any retry.'}}))
        return 2


if __name__ == '__main__':
    os.umask(0o077)
    raise SystemExit(main())
