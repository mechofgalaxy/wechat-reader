# Changelog

## 0.10.0rc4 — 2026-11-01

- Check protected paths by device/inode identity as well as normalized spelling,
  preventing case-alias bypasses on case-insensitive filesystems. Apply this to
  text export, image output, voice output and selected configuration/access files.
- Protect recognized db_storage roots above individual shards. Extend regression
  tests to existing symlink targets and actual filesystem case behavior.

## 0.10.0rc3 — 2026-11-01

- Reject export destinations that are symbolic links, including dangling links and
  `--force`. Check the actual destination parent so an outward-pointing link cannot
  cause a write inside a protected WeChat resource directory.

## 0.10.0rc2 — 2026-11-01

- Keep Python command shortcuts inside the application boundary: the installer now
  passes `--no-bin` to uv, preventing creation of a versioned Python shortcut in
  the user's general executable directory. rc1 could create that shortcut even
  when a custom application prefix was selected.
- Isolate demo/profile keys from legacy environment settings; keep unspecified keys beside
  the selected configuration instead of reading a global legacy account.
- Enforce strict read-only exports/setup and protect database/resource/configuration paths
  from export writes; correct export tool metadata.
- Add explicit onboarding account identity and mark inference as requiring confirmation.
- Probe native OCR and SQLCipher during macOS installation, report quarantine without
  changing security controls, disable model-download telemetry, and correct portable CLI/docs links.

## 0.10.0rc1 — 2026-11-01

First portable preview of this maintained Reader derivative.

- User-owned isolated installer; pinned uv/Python and hashed dependency locks.
- Explicit account profiles and guided import of existing authorized access materials.
- Fictional-data demo and runtime capability reporting independent of account access.
- Account-bound freshness, image/OCR and voice support carried forward from the reviewed local extensions.
- Removed maintainer-specific Python/model paths and Homebrew FFmpeg/FFprobe paths.
- Static HEVC and audio conversion use PyAV; speech models install by pinned revision.
- Source and macOS ARM64 release archives, synthetic tests, checksums and provenance.

Preview limits: no included database-key acquisition; Apple Silicon macOS is the full-feature
target; Linux is a core-only preview. Physical second-Mac/live account compatibility is not
implied by clean-prefix tests or cloud-VM execution. Package and review evidence is reported separately.
