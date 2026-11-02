# Connect your own WeChat with a local AI agent

Give this page to any agent that can run commands **on your own Mac** (for example,
a local Claude Code, Codex, or another terminal agent). Ask it to install this tool
and connect your own account. The same commands and JSON states work across agents.
An agent running only in a remote VM cannot reach your Mac's WeChat or authorization
dialogs. A browser chat needs a separately authorized local execution connection.

**Preview: Apple Silicon, macOS 14+, WeChat 4.x.** First-time acquisition remains
experimental: synthetic tests and a built helper do not prove compatibility with
every WeChat/macOS version. Installation can complete while connection is blocked.
The helper currently expects the official `/Applications/WeChat.app` installation.
Other installations, multiple running copies, and renamed clients stop for review.
Intel Mac, Windows, and Linux first acquisition are not supported in this release.

## If anything fails: read-only diagnostics first

For a failed installation, connection or query, follow
[the troubleshooting guide](docs/TROUBLESHOOTING.md) before changing anything.
Canonical link (also usable when an older installed archive lacks this file):
https://github.com/mechofgalaxy/wechat-reader/blob/main/docs/TROUBLESHOOTING.md

Proceed with the guide's read-only checks within existing access; do not wait for
the user to ask again. Preserve the original error, use the installed absolute
launcher when available, and reuse the exact profile label from the earlier
attempt. If the launcher or label is unavailable, report that gap instead of
inventing a profile, repeating installation or rerunning acquisition. This pass
collects safe diagnostic fields, not chat bodies or raw acquisition logs.

Report the evidence and the earliest supported failure stage before proposing a
repair. A missing administrator dialog or a compatibility disclaimer alone does
not establish the cause. For a proposed action that requires authorization—such
as installing a dependency, changing permissions, restarting WeChat, process
access, signing a separate copy or saving account configuration—explain the exact
action and effects, then obtain any required user authorization before proceeding.
The human handles native consent and administrator dialogs. Do not automatically
retry acquisition, manually clear a recovery lock or bypass system protections.
Follow the post-run recovery confirmation in step 7 when applicable.

## Instructions for the agent

1. Read this page, [account access](docs/ACCOUNT-ACCESS.md), and [security](SECURITY.md).
   Confirm you are executing on the user's own Mac. Check `uname -s`, `uname -m`,
   and `sw_vers -productVersion`. Do not infer local access from a GitHub connector.
2. Download `wechat-reader-0.11.0rc1-macos-arm64.tar.gz` and `SHA256SUMS` from the
   [fixed release](https://github.com/mechofgalaxy/wechat-reader/releases/tag/v0.11.0rc1).
   Check the archive's SHA256 before extracting into a new directory. Do not run
   a moving remote shell script or a helper from an unrelated directory.
3. Run `./install.sh` from the extracted directory as the ordinary user. It installs
   a private runtime; Homebrew, system Python changes, sudo, and API keys are not
   needed for installation. Network is used for pinned runtime/dependency downloads.
   If installed already, inspect its version and reuse it; do not delete profiles
   to bypass a reinstall error. Optional voice dependencies/models need a separate
   discussion of their download size.
4. Use the absolute installed launcher, normally
   `~/.local/share/wechat-reader/bin/wechat-reader`. Run `runtime-status`, `demo`,
   then `connect --discover`. Discovery only lists candidate account directories.
   Ask the person to select their own account, even if only one candidate appears.
   Do not use an account name from an unrelated tool, scan the whole home directory,
   or automatically import another app's credentials.
5. Choose a new local profile label such as `personal`. Run:

   ```sh
   ~/.local/share/wechat-reader/bin/wechat-reader connect --name personal --database-root '/selected/account/db_storage'
   ```

   Use the actual path the user selected. Do not execute the placeholder literally.
   Read `data.state`, not just the top-level `ok` or process exit code.

| State | Next action |
| --- | --- |
| `ready` and `live_database_read_ok=true` | Reuse this profile; do not reacquire. Review recovery and identity flags. |
| `account_selection_required` / `needs_database_location` | Ask for the user's account selection, login, or correct local location. |
| `ready_to_configure` | Explain that a private profile will be saved; repeat with `--apply`. |
| `existing_provider_material_available` | Ask permission to reuse that local file for this account; use `--access-file PATH --apply`. Never print its contents. |
| `authorization_required` | Explain the one-time experimental effects below, then request human authorization. |
| `filesystem_access_required` / `dependency_required` | Follow [read-only troubleshooting](docs/TROUBLESHOOTING.md), identify the named permission/dependency, then explain the fix and obtain any required user authorization before making changes. Do not reacquire keys. |
| `partial` / `scan_incomplete` / `verification_failed` | Follow [read-only troubleshooting](docs/TROUBLESHOOTING.md) and report the gap. Preserve the profile/materials; do not claim full access or retry acquisition automatically. |
| `existing_configuration_requires_review` | Follow [read-only troubleshooting](docs/TROUBLESHOOTING.md) for the existing profile; never overwrite it or silently select another account. |
| Any unknown/error state | Stop dependent operations, follow [read-only troubleshooting](docs/TROUBLESHOOTING.md), and report the exact safe code. Do not improvise security changes. |

6. If access materials are missing, this package supplies a fixed, modified helper.
   Explain to the user that it may quit/reopen WeChat, sign a **separate local copy**,
   and inspect that copy's process to obtain local database access. Login may be
   needed again. Ask them to save their work and authorize this one attempt. Then:

   ```sh
   ~/.local/share/wechat-reader/bin/wechat-reader connect --name personal --database-root '/selected/account/db_storage' --request-access
   ```

   If `debugger_unavailable` is reported, explain that Apple Command Line Tools are
   required for the optional acquisition step. Follow the read-only troubleshooting
   guide first. Explain the dependency installation and obtain user authorization
   before starting the official `xcode-select --install` flow. The person completes
   its dialogs; then recheck. Do not fetch a debugger from a mirror.

   The person must handle the native consent and macOS administrator dialogs.
   **Never click through these for the user, collect their password, paste a password
   into the agent, store it, or substitute a confirmation flag for their consent.**
   The helper does not re-sign the original app or disable SIP. A platform refusal
   is a stop condition, not permission to bypass macOS protections.
7. After an attempt, run `connect --name personal --status`. A recovery lock prevents
   automatic repeats. The person must check that the official WeChat is usable,
   with the same intended account, and that the authorization/acquisition activity
   has ended. Only after that **post-run confirmation**, execute:

   ```sh
   ~/.local/share/wechat-reader/bin/wechat-reader connect --finish-recovery --confirm-wechat-ready --confirm-no-acquisition
   ```

   This checks observed processes before clearing only the recovery lock. It does
   not prove login by itself. Never clear the lock manually to force another attempt.
8. Verify the named profile using `--profile personal doctor --pretty` and
   `--profile personal freshness --inventory-only --pretty`. These return diagnostics;
   setup does not return chat bodies. Explain that any selected messages returned
   to a cloud agent enter that provider's context. Ask the user for an allowed chat,
   time range or known test phrase before the first content query. Use a small limit.
   For example, after that scope is authorized:

   ```sh
   ~/.local/share/wechat-reader/bin/wechat-reader --profile personal search 'user-chosen phrase' --limit 3 --pretty
   ```

   If the account identity was inferred, have the person confirm it before relying
   on sender direction, images or voice. Reading local files does not establish
   that unsynced phone history or every attachment is available.

## Completion message

State separately: software installed, selected account verified readable, local
coverage, WeChat recovery confirmed, and one user-scoped query verified. Report any
missing stage honestly. A successful Demo is never proof of real account access.
Do not send WeChat messages, enable background jobs, or add agent permissions.

For problems, follow [read-only troubleshooting](docs/TROUBLESHOOTING.md).
`connect --name ACTUAL_PROFILE --status` produces a limited support summary; replace
`ACTUAL_PROFILE` with the previously selected label. Do not upload keys, database
files, raw acquisition logs, or private message samples.

For a first trial, report the release version, macOS/WeChat versions, the stage
reached (installed / selected account / authorized / readable / recovery confirmed),
and the exact safe error code or support summary. Say whether official WeChat is
usable afterwards. The agent should help collect this summary without including
account names, local paths, chat content, or screenshots of private conversations.
