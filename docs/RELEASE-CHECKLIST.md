# Release acceptance

1. Review exact tracked tree and archive allowlist. No private profiles, keys, accounts, logs or real media.
2. Preserve LICENSE/NOTICE, upstream revision and dependency lock hashes.
3. Run synthetic tests, public-content checks and source/installer syntax checks.
4. Build helper from included source; inspect linked libraries; generate deterministic archives and checksums.
5. Install archive bytes in a new prefix (including a path with spaces), run runtime-status/demo/self-test.
6. Exercise supported media paths with generated fixtures. Report optional/unsupported skips explicitly.
7. Publish exact tested commit/tag, read back public metadata, download assets and compare hashes.
8. Perform the requested independent model review of that published commit, then a separate VM trial.

Do not claim an independent physical Mac, live user onboarding, Apple features on Linux, or a
completed external review without the corresponding execution evidence.
