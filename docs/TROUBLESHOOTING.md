# WeChat Reader — Read-only Troubleshooting

Please continue investigating this WeChat Reader failure with a **read-only diagnostic pass**.

The connection failed, but the available evidence does **not yet establish that this Mac or WeChat build is unsupported**. No administrator dialog appearing is not sufficient to determine the cause. `new_machine_compatibility` is a general limitation notice, not an error code. In a status response, `provider_executed: false` describes that status check, not necessarily earlier attempts.

## Reference links

First-use guide:
https://github.com/mechofgalaxy/wechat-reader/blob/main/START_HERE.md

Exact rc1 diagnostic source:
https://github.com/mechofgalaxy/wechat-reader/blob/c018f5d0403d3b3daad593cc72beaf0a8f9aefcb/rion_wechat_access.py

Exact rc1 first-connection source:
https://github.com/mechofgalaxy/wechat-reader/blob/c018f5d0403d3b3daad593cc72beaf0a8f9aefcb/first_run.py

## Diagnostic steps

1. Retrieve the **original `error.code`** from the previous execution output. Do not rerun acquisition to reproduce it.
2. Run the installed launcher's read-only diagnostics:

   ```sh
   "$HOME/.local/share/wechat-reader/bin/wechat-reader" runtime-status
   "$HOME/.local/share/wechat-reader/bin/wechat-reader" connect --name PROFILE_NAME --status
   ```

   Replace `PROFILE_NAME` with the exact label used previously, not the WeChat account ID. If the launcher was installed elsewhere, use its previously verified absolute path. If the previous profile label cannot be recovered, skip this named status command and report `profile_label_unknown`. Do not invent a label or create a profile. The filesystem probe below does not need a profile label; see the missing-selection recovery steps.
3. Report `last_attempt_state` and `last_attempt_diagnostics`, including any `phase`, `provider_started`, `exit_code`, and `signals`. If a field is absent, report it as unavailable.
4. Include the Mac architecture, macOS version, and WeChat version/build.
5. Separately confirm whether the **“Connect my account” consent dialog** appeared and whether an **administrator authorization dialog** appeared.


## Next pass for `database_read_permission_denied`

Use this section when the first pass reports `database_read_permission_denied`
with `database_preflight` or when no consent/administrator dialog appeared.
These are **read-only diagnostics, not another acquisition attempt**. Do not add
`--request-access`, `--apply`, `--finish-recovery`, `sudo`, `--verbose` or `--trace`;
rc1's `connect` has no verbose/trace flags. Do not reinstall or change permissions
to make these checks pass. If a native permission dialog appears during a read,
leave it to the person and report that the check is blocked pending their decision.

### 1. Identify the exact local execution context

Prefer the same local agent/terminal context as the failed command. If the user
has switched to another agent, such as Codex, **continue with the existing local
installation**; do not reinstall or retry acquisition just to recreate history.
Record the current host app and the original app if known. Access previously
granted to one app does not establish another app's access. Treat the probe as a
check of the current context and leave any required permission decision to the user.
Recover the installed launcher and selected `db_storage` directory from this
task's supplied diagnostic report, conversation or execution history where available. Do not search unrelated agent
sessions, shell history, the entire home directory, credentials or configuration
contents. If selections are missing, use the bounded recovery steps below.

A profile label is needed only for the named `connect --status` command. The
filesystem probe in step 2 needs the installed release and a confirmed database
directory, **not a profile label**. A failed first connection may never have saved
a profile or its label. Keep an unrecoverable label as `profile_label_unknown`;
do not create a new label, try example names or copy someone else's selections.

Read the managed launcher locally to identify its release directory and Python:

```sh
# Adjust only if the previous installation used a different prefix.
WR_PREFIX="$HOME/.local/share/wechat-reader"
sed -n '1,12p' "$WR_PREFIX/bin/wechat-reader"
```

Resolve the launcher's literal `$app_root` to `WR_PREFIX`. Read the exact release
name (for example `0.11.0rc1-core` or `0.11.0rc1-voice`); do not guess or switch
interpreters. Do not source/eval the launcher text. Keep actual paths on this Mac.
Record the host app's name and whether it was relaunched after any prior Full Disk
Access change, without changing its settings. A normal-user read does not verify
the access of an administrator worker launched through a different context.

#### If the previous database folder is unavailable

Within the user's existing local-read authorization, use rc1's built-in directory
discovery. Set `WR_RELEASE` from the managed launcher as above, using the same
installed release whose source hashes were verified. This invokes the same
`--discover` branch used by `wechat-reader connect --discover`; `-B` prevents
bytecode writes. It does not require a profile or run the image-helper self-test.

```sh
WR_RELEASE='/absolute/release/directory/from/the/managed/launcher'
"$WR_RELEASE/runtime/bin/python" -B -E -s "$WR_RELEASE/lib/first_run.py" --discover
```

Discovery checks only rc1's three fixed WeChat locations under the current user's
home, with bounded depth and at most 200 visited directories per location. It
lists candidate `db_storage` directories; it does not read database contents,
read keys, create a profile, restart WeChat or start acquisition. Candidate paths
and account folder names are **local selection information**: do not include them
in a forwarded report. Do not automatically approve a native access dialog.

- An `ok: true` response with `data.state: account_selection_required` is a
  successful candidate listing. rc1 still exits with code **1** in this state;
  inspect the JSON instead of treating that exit code as an acquisition failure.
- Have the user confirm which candidate belongs to their own intended account
  before running the database probe, even if there is only one candidate. Do not
  silently select the first directory or scan every candidate's databases.
- Use that confirmed path as `WR_DB_ROOT` in step 2. If the original selection
  cannot be established, describe the result as a **new current-context check**
  of the newly confirmed selection, not a reproduction of the failed attempt.
- If there are no candidates, warnings, or a denied read, report the exact safe
  state/warning. Ask the user to identify their own data directory locally, or
  explain the specific permission needed and wait for their decision. Do not
  broaden the search, open/log into WeChat, change permissions or retry acquisition
  merely because discovery's generic `next_action` suggests a setup action.

A path in a report such as `/Users/.../redacted-diagnostics.json` is a local file
on the reporting machine, not a shareable download link. The local Agent can read
that exact report within its existing authorization. To share it with the
maintainer, provide only the redacted JSON text or attach the redacted file; never
substitute raw receipts, configurations, account paths or keys.

### 2. Run only the installed rc1 filesystem preflight

Replace the two placeholders below using the recovered or user-confirmed local
values. No profile label is needed for this probe. Do not execute the placeholders
literally. This command uses the installed Python,
checks the exact rc1 source hashes, then loads **only** the error class, path check
and database-preflight function. It does not import the application or load its
worker, debugger, acquisition, consent or recovery functions. `-B` prevents Python
bytecode writes. No package or dependency installation is required.

It reads only 16-byte database headers, never prints them, and reports fixed
operation names and OS error numbers without filenames or account identifiers.
It stops after 30 seconds, 500 visited directories, 5000 entries in one directory,
or the rc1 limit of 500 databases (rc1 detects that limit after its 501st read).
A source-hash mismatch is a stop condition; do not remove the check.

```sh
WR_RELEASE='/absolute/release/directory/from/the/managed/launcher'
WR_DB_ROOT='/exact/previously-selected/account/db_storage'
"$WR_RELEASE/runtime/bin/python" -B -E -s - "$WR_RELEASE" "$WR_DB_ROOT" <<'PY'
import ast
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import stat
import sys
from types import SimpleNamespace

EXPECTED = {
    'rion_wechat_access.py': '5614425b99e591055c7575585c6d5efdd46d2c6b58113db7dd31dcd24d9ba41d',
    'first_run.py': '810fb95228f6245dcb18883b21e812664ffaf93f0794ae2c7e8de04696c3df4a',
}
report = {'probe': 'rc1_database_preflight_only', 'provider_started': False,
          'authorization_requested': False, 'configuration_changed': False,
          'chat_content_read': False, 'network_called': False,
          'historical_failure_reproduced': 'not_established',
          'execution_context': 'current_normal_user_only',
          'python_version': platform.python_version(),
          'directories_visited': 0, 'database_headers_read': 0}
failure = {}
operation = 'validate_inputs'


def error_fields(exc):
    number = exc.errno if type(exc.errno) is int else None
    return {'errno': number, 'errno_name': errno.errorcode.get(number, 'UNKNOWN')}


def observed(name, fn, *args):
    global operation
    operation = name
    try:
        return fn(*args)
    except OSError as exc:
        if not failure:
            failure.update(operation=name, **error_fields(exc))
        raise


def walk(root, onerror, followlinks=False):
    def failed(exc):
        failure.update(operation='list_directory', **error_fields(exc))
        onerror(exc)
    for row in os.walk(root, onerror=failed, followlinks=False):
        report['directories_visited'] += 1
        if report['directories_visited'] > 500 or len(row[1]) + len(row[2]) > 5000:
            raise RuntimeError('diagnostic_scan_limit_reached')
        global operation
        operation = 'check_path_metadata'
        yield row


def read(fd, size):
    result = observed('read_database_header', os.read, fd, size)
    if len(result) == 16:
        report['database_headers_read'] += 1
    return result


def timed_out(*args):
    raise RuntimeError('diagnostic_timeout')


try:
    if len(sys.argv) != 3 or os.geteuid() == 0:
        raise RuntimeError('normal_user_and_two_explicit_paths_required')
    release, root = (Path(x).expanduser().absolute() for x in sys.argv[1:])
    if Path(sys.prefix).resolve() != (release / 'runtime').resolve():
        raise RuntimeError('use_the_installed_launcher_python')
    if root.name != 'db_storage':
        raise RuntimeError('exact_selected_db_storage_required')
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise RuntimeError('symlink_database_path_rejected')
    if not root.is_dir():
        raise RuntimeError('selected_database_directory_unavailable')
    signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(30)
    sources = {}
    for name, digest in EXPECTED.items():
        source = release / 'lib' / name
        if any(p.is_symlink() for p in (source, *source.parents)):
            raise RuntimeError('symlink_source_path_rejected')
        if not source.is_file() or source.stat().st_size > 1000000:
            raise RuntimeError('source_file_unavailable')
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError('installed_source_differs_from_reviewed_rc1')
        sources[name] = data.decode('utf-8')
    report['installed_rc1_sources_match'] = True
    # Execute only these three hash-verified definitions. No application imports,
    # main(), worker(), provider, debugger, subprocess or consent code is loaded.
    names = {'AccessError', 'private_path', 'preflight_database_access'}
    nodes = [n for n in ast.parse(sources['rion_wechat_access.py']).body
             if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    if len(nodes) != 3:
        raise RuntimeError('expected_definitions_missing')
    traced_os = SimpleNamespace(
        walk=walk, O_RDONLY=os.O_RDONLY, O_NOFOLLOW=os.O_NOFOLLOW,
        O_NONBLOCK=os.O_NONBLOCK,
        open=lambda *a: observed('open_database', os.open, *a),
        fstat=lambda *a: observed('stat_database', os.fstat, *a),
        read=read, close=os.close)
    namespace = {'os': traced_os, 'stat': stat, 'Path': Path}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<verified-rc1-preflight>', 'exec'), namespace)
    operation = 'check_path_metadata'
    count = namespace['preflight_database_access'](root, max_files=500)
    report.update(state='current_user_preflight_passed', database_count=count)
except Exception as exc:
    known = {'normal_user_and_two_explicit_paths_required', 'use_the_installed_launcher_python',
             'exact_selected_db_storage_required', 'symlink_database_path_rejected',
             'selected_database_directory_unavailable', 'diagnostic_scan_limit_reached',
             'diagnostic_timeout', 'symlink_source_path_rejected', 'source_file_unavailable',
             'installed_source_differs_from_reviewed_rc1', 'expected_definitions_missing',
             'database_read_permission_denied', 'database_preflight_failed',
             'database_files_not_found', 'database_header_unreadable',
             'database_not_regular_file', 'database_preflight_limit_exceeded', 'symlink_path_rejected'}
    code = str(exc) if str(exc) in known else 'diagnostic_check_failed'
    report.update(state='stopped', error_code=code)
    if not failure:
        failure['operation'] = operation
        if isinstance(exc, OSError):
            failure.update(error_fields(exc))
    report['failure'] = failure
finally:
    signal.alarm(0)
print(json.dumps(report, indent=2))
PY
```

This reports the **current normal-user check**, not proof of the historical cause
or privileged-worker access. The directory limit and deadline are diagnostic
bounds. If either is reached, report incomplete coverage rather than widening the
scope or retrying acquisition. A pass does not decrypt anything or establish that
the account is readable.

### 3. Compare receipt times without reading raw logs

Keep the same `WR_RELEASE` value. The next command reads only file metadata in
Reader's fixed per-user receipt directory. It does not read receipt contents,
keys, database contents or logs, and does not create/delete a lock.

```sh
"$WR_RELEASE/runtime/bin/python" -B -E -s - <<'PY'
import json
import os
from pathlib import Path
import stat
from datetime import datetime, timezone

report = {'probe': 'receipt_metadata_only', 'configuration_changed': False,
          'provider_started': False, 'receipt_account_binding': 'not_available_in_rc1'}
try:
    if os.geteuid() == 0:
        raise RuntimeError('normal_user_required')
    parent = Path.home() / '.local/share/wechat-reader-access/access-runs'
    if any(p.is_symlink() for p in (parent, *parent.parents)):
        raise RuntimeError('symlink_path_rejected')
    rows = []
    if parent.is_dir():
        for number, item in enumerate(parent.iterdir(), 1):
            if number > 500:
                raise RuntimeError('receipt_scan_limit_reached')
            if not item.name.startswith('run-') or item.is_symlink() or not item.is_dir():
                continue
            result = item / 'worker-result.json'
            if not os.path.lexists(result):
                rows.append((item.stat().st_mtime_ns, 'no_worker_result', None))
                continue
            metadata = result.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise RuntimeError('non_regular_receipt_rejected')
            rows.append((metadata.st_mtime_ns, 'worker_result_present', metadata.st_size))
    report['recent_entries'] = [
        {'label': 'receipt_' + str(i), 'status': status,
         'mtime_utc': datetime.fromtimestamp(stamp / 1e9, timezone.utc).isoformat(),
         'bytes': size}
        for i, (stamp, status, size) in enumerate(sorted(rows, reverse=True)[:5], 1)]
    report['state'] = 'metadata_checked'
except (OSError, RuntimeError):
    report['state'] = 'metadata_unavailable_or_limit_reached'
print(json.dumps(report, indent=2))
PY
```

Compare these UTC times with the failed command's timestamp in the agent's existing
execution history. If that timestamp was not recorded, say `correlation_unknown`.
File modification time is supporting evidence, not an invocation ID. `receipt_1`
is only a local output label; it does not identify an account. rc1's status selects
the newest existing worker result for this OS user, regardless of profile, and a
new failure before consent can leave an older worker result displayed. Missing or
older receipts must not be described as records of the latest attempt.

### 4. Interpret and return only the safe evidence

| Observation | Supported conclusion / next step |
| --- | --- |
| `open_database` / `read_database_header` with `EACCES` or `EPERM` | This process was denied a file operation. One other readable file does not exclude it. Explain the specific permission investigation before proposing a grant. The code alone does not distinguish filesystem ACLs, macOS privacy controls or an agent sandbox. |
| `list_directory` with `ENOENT`, `ENOTDIR` or another non-permission error | rc1 maps every directory-traversal error to `database_read_permission_denied`. Report the underlying error; do not request broader access based on the misleading label. |
| `database_header_unreadable` | A header was shorter than 16 bytes. This is not a key/decryption result. |
| `current_user_preflight_passed` | All checked headers were readable in this context now. The earlier failure and any privileged-worker access remain unverified. Do not proceed to acquisition automatically. |
| Source mismatch, timeout, scan limit or missing input | Stop this check and report the specific gap; do not patch the installed tool or widen scope to continue. |
| No corresponding worker receipt, or uncertain timing | Keep `last_attempt` historical/unconfirmed. The normal-user database and debugger checks occur before the consent dialog in rc1. |

Return the probe JSON, receipt metadata, host-app name, prior relaunch status,
original error code and whether the receipt timing matches. If a selection was
newly confirmed, state that; if the profile label is unknown, preserve that gap.
An image-helper failure is a separate runtime finding, not evidence of the cause
of a database-preflight failure. Its repair is not a prerequisite for this
filesystem probe; record the safe helper status and avoid reinstalling or
changing security settings to investigate it during this pass.
Do not return personal
paths, account IDs, header bytes, keys, raw logs or full process command lines.
The `chat_content_read: false` field means no message bodies were queried; 16-byte
file headers were read locally. Empty `signals` and a missing `exit_code` are
expected if the provider never started; do not run it just to obtain those fields.

Finish this diagnostic pass with the supported stage, remaining uncertainty and
one proposed next action. Explain and obtain any required human authorization
before installing software, changing permissions, accessing processes, restarting
WeChat or starting another acquisition attempt. These instructions grant none of
those permissions. Do not switch WeChat clients or weaken system protections.

## Interpretation and scope

Distinguish observations from hypotheses. In particular, a recorded `worker_preflight_failed` means the worker reached its preflight stage; it does not mean the worker never launched. Check whether the saved receipt actually corresponds to the failed attempt. A missing receipt or an older receipt does not establish what happened in the latest attempt.

Keep the installation in place. During this pass, do not retry acquisition, clear recovery locks, restart or modify WeChat, or change macOS security settings. Share only the safe diagnostic fields—no account identifiers, personal paths, keys, databases, or raw acquisition logs.

Return the collected facts, the earliest failure stage supported by those facts, and any remaining evidence gaps. Identify any proposed follow-up action that would require fresh user authorization; do not perform it during this diagnostic pass.
