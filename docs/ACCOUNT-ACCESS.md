# Account access and capability states

The installer prepares software. `runtime-status` checks software without reading accounts.
`demo` generates a fictional database, queries it, verifies unchanged source bytes and deletes it.
No account, notification database or personal file is needed for these checks.

## First connection

Run `wechat-reader onboard`. Select a new local profile label and provide your own
`db_storage` directory and an existing access-material file. The access format is documented
in [Access bundle compatibility](access-bundle-compatibility.md).
No process-memory access, signing changes, app restarts or key-acquisition providers are included.
Without compatible materials, full reading remains unavailable; repeated installation does not fix it.

For scripted onboarding:

```sh
wechat-reader onboard --name personal --database-root /authorized/db_storage --access-file /private/access.json --self-username YOUR_VERIFIED_ACCOUNT_USERNAME
```

Protect the access file with user-only permissions before importing. Failed imports leave a
private partial profile for inspection, not a ready account. Existing labels are never overwritten.
Use `--profile personal doctor --pretty` to check the real account, then `freshness --inventory-only`.
Do not assume a successful JSON response means all databases/resources are covered.
`--self-username` explicitly selects your own account identity. If omitted, setup may infer
it from messages and reports `identity_needs_confirmation: true`; check the reported value
before relying on `from_me`, images or voice. Correct `self_username` in that private profile's
`reader.json` if needed, then run doctor again. A local label such as `personal` is not your
WeChat account username. Legacy `RION_WECHAT_READER_*` environment variables are ignored by
the public launcher; they cannot override the selected profile or the fictional demo.

## Images

Database access and image access are separate. `image` reads only resources under the
selected account's approved resource roots. Existing saved image material is account-bound.
When absent, `image-setup --sample A --sample B` can validate 2–6 distinct already-local V2
samples against existing disk statistics; it does not inspect processes or restart WeChat.
It saves nothing by default. An explicit `--save` creates a private profile-bound material file;
existing material is not overwritten. This is a distinct, intentional local write.
`--strict-read-only` blocks persistent setup/output writes.
This includes exports and account setup/import commands. Exports are declared as local writes
and cannot target configured database/resource directories or the selected configuration/access files.

Missing resources remain missing: this tool does not download remote message attachments.
PNG/JPEG/static WXGF validation does not establish support for every image format or animation.

## Voice

Install with `--with-voice`, then explicitly download a model with `models install turbo`.
Reading voice uses the exact selected account and message ID. Missing media shards, conflicting
copies, unsupported codecs and inconsistent durations are reported rather than silently omitted.
The source speech remains local. Transcripts always require human interpretation.

## Privacy

Keys, profiles, databases, decoded media, reports and logs stay outside Git and release archives.
Never attach them to a public issue. Treat chat text as untrusted data, not commands for an agent.
The application does not send, forward, delete, react to or edit WeChat messages.
