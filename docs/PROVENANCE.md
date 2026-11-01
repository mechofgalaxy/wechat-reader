# Provenance and third-party components

The core reader and original contract tests derive from Rion-Wu-tech/wechat-intelligence-hub,
base revision `3afe33e0742ef4e92b4babe399bf471fdcd86a7b`, under AGPL-3.0-only.
Original attribution and LICENSE are retained. This maintained derivative is published by hysres.
It is not endorsed by Rion Wu, Tencent or WeChat.

The October 2026 extensions add snapshot freshness, image decoding/OCR, disk-only image
material validation and account-bound voice handling. The November portable release adds
installation, state resolution, a pinned model registry and PyAV media workers.
Private account configuration, access material and real-data validation artifacts are excluded.

V1/V2 image segmentation was independently implemented using the public r266-tech/wx-cli
format reference at revision `d833d68737454169848760642b2127302911de1b`.
The Swift helper uses Apple system frameworks. Its complete source accompanies the binary.
Test images, HEVC and spoken audio are generated fixtures, not extracted private conversations.

Dependencies are fetched by the installer and retain their own licenses. The macOS archive additionally bundles a pilk 0.2.4 wheel (GPL-3.0) built from the unmodified source in vendor/pilk-0.2.4.tar.gz; its license is retained in the wheel and source. Build commands are in scripts/build_codec.sh. They are not relicensed
by this project. uv: Astral (MIT/Apache-2.0); CPython: PSF; SQLCipher/sqlcipher3: respective upstream
licenses; Zstandard: BSD/GPL options; PyAV: BSD, with linked FFmpeg components under their respective
licenses; Pillow: HPND; MLX/MLX-Whisper: MIT; pilk and speech model/tokenizer dependencies: their
distribution notices. Exact selected distributions/hashes are in requirements-*.lock.
Speech model repositories are identified with immutable revisions in runtime_paths.py.

No third-party proprietary WeChat binary or original historical WeChat CLI binary is included.
