# Provenance and third-party components

The core reader and original contract tests derive from Rion-Wu-tech/wechat-intelligence-hub,
base revision `3afe33e0742ef4e92b4babe399bf471fdcd86a7b`, under AGPL-3.0-only.
Original attribution and LICENSE are retained. This maintained derivative is published by mechofgalaxy.
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
The `httpx2` / `httpcore2` names are intentional: the pinned
[Hugging Face Hub 2.4.0 dependency declaration](https://github.com/huggingface/huggingface_hub/blob/v2.4.0/setup.py)
requires HTTPX2, whose [upstream project is maintained by Pydantic](https://github.com/pydantic/httpx2).
Speech model repositories are identified with immutable revisions in runtime_paths.py.

No third-party proprietary WeChat binary or original historical WeChat CLI binary is included.

## First-connection additions (0.11.0rc1)

The access coordinator and its contract tests derive from Rion WeChat Intelligence
Hub revision `fb6a42c34160d2ffa66ed5f114f8d8cdabe7f5f9` (AGPL-3.0-only), adapted to
portable profiles. Account discovery, native consent and the agent-neutral guide
are maintained here.

The optional helper derives from r266-tech/wxkey revision
`01e96fa58ce3ff061dce83e4c36f62104ebc6b16` (MIT), plus the Rion lifecycle patch and
this project's restrictions. Full modified source is in `providers/wxkey/source`;
the original MIT license and patch are retained. Credential-storage/elevation and
original-app resign operations are disabled. Process stop handling is scoped to
verified owners/executables. The bundled helper remains experimental and has no
fresh-account compatibility claim. `access-provider.json` binds binary/source
hashes; `scripts/build_provider.sh` reproduces the ordinary-user build.

The helper statically includes Go standard-library code (BSD-style license) and purego v0.10.0 (Apache-2.0); their original license texts are retained under providers/wxkey/licenses. See source/go.mod and source/go.sum for the exact module dependency.
