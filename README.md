# WeChat Reader — portable preview

Local, read-only access to **your own authorized** WeChat data, with text search,
account-bound images/OCR, voice decoding and optional local speech transcription.
This is a maintained derivative of [Rion WeChat Reader](https://github.com/Rion-Wu-tech/wechat-intelligence-hub),
not an official Tencent product. **Version: 0.11.0rc1. License: AGPL-3.0-only.**

**安装成功不等于已接入微信。** 日常读取只读。首次接入可以复用已有材料；缺少材料时，由使用者明确授权实验性本机获取。该过程可能退出/重开微信并签名独立副本，不改签原应用、不保存管理员密码、不关闭 SIP、不自动发消息。先运行虚构数据 Demo；真实读取需要单独验证。

## One link for any local agent / 给 Agent 的统一入口

Give [START_HERE.md](START_HERE.md) to a local Claude Code, Codex, or another agent
with command execution on your Mac. It covers installation, account selection,
permission prompts, verification and recovery. Structured JSON states are shared
across agents; no particular model subscription is required by this tool.

The new `connect` flow discovers local account locations and reuses existing
materials. When materials are absent, the macOS archive includes an **experimental,
explicitly authorized** helper. Native human confirmation comes before any process
access or restart. Its complete modified source is included. Fresh-machine
acquisition and cancelled-run GUI recovery are still unverified; do not promise
one-click compatibility or confuse mocked acquisition with a real WeChat test.

## Download and install / 安装

Download an archive and `SHA256SUMS` from [Releases](https://github.com/mechatlarge/wechat-reader/releases).
Apple Silicon Mac users should choose `wechat-reader-0.11.0rc1-macos-arm64.tar.gz`;
it includes the precompiled Apple OCR helper. The source archive contains the helper's full source.
These are command-line archives, not notarized `.app` installers.
Use the documented terminal extraction. The installer checks native image/OCR execution;
if macOS quarantine is present, it reports `macos_security_review_required` and stops before
switching launchers. It never removes quarantine or changes security controls. Review the
software using macOS's normal security process, or build the helper from the included source.
`runtime-status` distinguishes helper presence from a successful generated-image OCR probe.

```sh
# Compare the archive checksum with SHA256SUMS before extracting.
shasum -a 256 wechat-reader-0.11.0rc1-macos-arm64.tar.gz
tar -xzf wechat-reader-0.11.0rc1-macos-arm64.tar.gz
cd wechat-reader-0.11.0rc1
./install.sh
# To include local voice decoding / transcription dependencies instead:
# ./install.sh --with-voice
```

The installer downloads checksum-pinned uv, a private Python 3.12.16 runtime and
hash-locked packages. It does not need Homebrew, Codex, system-Python changes or sudo.
Network access to GitHub, Python distribution hosts and PyPI is required during setup.
Speech models are downloaded separately only when requested. Downloads may be large.
The default installation/state directory is `~/.local/share/wechat-reader`.
Use `--prefix /absolute/custom/directory` to choose another directory.

```sh
~/.local/share/wechat-reader/bin/wechat-reader runtime-status
~/.local/share/wechat-reader/bin/wechat-reader demo
~/.local/share/wechat-reader/bin/wechat-reader connect --discover
```

`onboard` asks for an account label, **that account's** `db_storage` directory and
an existing authorized access-material JSON file. It validates before importing,
keeps files private and refuses existing labels. It never obtains new database keys.
The original database/access-material files are not changed. Multiple accounts use
separate profiles; each query names its profile explicitly.

```sh
~/.local/share/wechat-reader/bin/wechat-reader --profile personal doctor --pretty
~/.local/share/wechat-reader/bin/wechat-reader --profile personal freshness --inventory-only --pretty
~/.local/share/wechat-reader/bin/wechat-reader --profile personal search 'example' --pretty
~/.local/share/wechat-reader/bin/wechat-reader --profile personal timeline 'chat name' --limit 20 --pretty
```

Advanced users may supply `--config /absolute/private/reader.json` instead of `--profile`.
See [account access](docs/ACCOUNT-ACCESS.md) and [upstream bundle format](docs/access-bundle-compatibility.md).

## Images and voice / 图片和语音

On macOS, image handling uses Apple CommonCrypto / ImageIO / Vision.
Static WXGF conversion and audio resampling use isolated PyAV workers rather than
machine-specific FFmpeg paths. Animated WXGF/general container support is not promised.

```sh
# Only existing downloaded resources belonging to the selected profile are allowed.
~/.local/share/wechat-reader/bin/wechat-reader --profile personal image /authorized/resource.dat --ocr
# When image access is absent: separately review the disk-only setup in ACCOUNT-ACCESS.md.

# Optional model download; use after installing with --with-voice:
~/.local/share/wechat-reader/bin/wechat-reader models install turbo
~/.local/share/wechat-reader/bin/wechat-reader --profile personal voice 'chat name' --server-id 123 --transcribe
```

Model downloads are pinned to public repository revisions. Transcription runs locally
and explicitly offline after download. OCR and transcripts can be wrong; quality flags
and comparisons are evidence for review, not proof of spoken content.
If you pass results to a cloud AI assistant, those selected results enter that provider's context.

## Support matrix

| Platform | Core / fictional demo | Encrypted account data | Images / Apple OCR | Local MLX voice |
|---|---|---|---|---|
| Apple Silicon macOS 14+ | Release target | Needs compatible authorized materials | Supported code path | Optional dependencies + model |
| Linux x86_64 glibc | Portable core preview | SQLCipher not bundled; unverified | Unsupported | Unsupported |
| Intel Mac / Windows | Not supported by installer | Unverified | Unverified | Unsupported |

An isolated installation on the maintainer's Mac is not a second physical Mac test.
Linux VM success cannot validate Apple frameworks, live WeChat synchronization or macOS account onboarding.
Only locally available shards/resources are readable; missing shards/downloads and stale snapshots are reported.

## Upgrade, rollback and uninstall

Version/flavor installations live in `releases/`; account profiles/models live separately.
Installing voice after core creates a separate environment and switches only this app's
managed launcher. Existing profiles, unrelated tools and installations are preserved.
Reinstalling the same version/flavor is refused rather than overwritten.
The preceding launcher is saved as `previous-launcher` inside the new release directory.
Invoke the installed launcher directly; moving or symlinking it to another directory is unsupported.
To roll back, inspect and restore that saved launcher to `bin/wechat-reader`.
If an install fails, the previous launcher remains active; the new incomplete directory is
left for inspection. Remove only that failed release directory before a deliberate retry.
Uninstall by removing the selected installation directory **only after deciding whether to retain
your profiles, access materials and models**. The installer never performs that deletion.

## Development and verification

Source checkout: Python 3.12; install `requirements-core.lock` (or voice lock) with hash checking.
The source `./wechat-reader` launcher uses your selected `python3`; the installed launcher uses its private runtime.
On macOS source checkouts, compile the OCR helper with:

```sh
xcrun swiftc -O -target arm64-apple-macosx14.0 image_native.swift -o image_native
python3 -m unittest discover -s tests -v
python3 scripts/check_public.py
./wechat-reader demo
```

Tests use fictional databases and generated media only. Before running tests from a macOS
release archive, copy `bin/macos-arm64/image_native` to the extracted source root.
Source checkouts compile that helper using the command above. Apple integration tests are
skipped on Linux; full ASR requires an installed model and `WECHAT_READER_TEST_ASR=1`.
CI has no account credentials and cannot certify live WeChat access.
See [CHANGELOG](CHANGELOG.md), [provenance](docs/PROVENANCE.md), [security](SECURITY.md),
[notices](NOTICE.md) and [release verification](docs/RELEASE-CHECKLIST.md).
