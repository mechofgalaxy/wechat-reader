# Changelog

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
