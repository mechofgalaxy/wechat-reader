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


## 0.11 first-connection preview status

- Agent-neutral flow, encrypted fictional account import, profile reuse, cancellation
  gates, recovery checks and code tests are exercised locally.
- A clean macOS archive install is tested without maintainer account files.
- Requested Claude 5.1 max review was blocked by that service's cyber safeguards;
  no review verdict was produced. Do not describe this release as independently approved.
- Fresh-account acquisition, actual human authorization/cancellation, subsequent
  official WeChat login recovery, and a second physical Mac remain unverified.
- A Linux VM cannot validate these macOS-specific stages; the earlier rc4 VM
  report is not evidence that the new acquisition flow works.

These open items prevent a stable release and any claim that every user can
connect just by confirming prompts. Keep this an experimental prerelease until
actual supported-device evidence and an independent review close the gaps.
