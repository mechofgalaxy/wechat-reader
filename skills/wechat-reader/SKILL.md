---
name: wechat-reader
description: Read the user's authorized local WeChat with an explicit account profile; guide first connection with human authorization.
---

Use the [agent-neutral first-use guide](../../START_HERE.md) and
[agent contract](../../AGENTS.md). This skill needs execution on the user's Mac;
a remote sandbox cannot access local WeChat. A skill file is not a grant of access.

The default executable is `~/.local/share/wechat-reader/bin/wechat-reader`.
Use the user's chosen prefix if different. Run `runtime-status` and `connect
--discover` before connecting; subsequent queries always name `--profile NAME`.
Never use a binary discovered in the current working directory.

First connection: inspect with `connect --name NAME --database-root PATH`; existing
authorized access files can be supplied by path with `--access-file PATH --apply`.
When the returned state requires authorization, explain the effects and invoke
`--request-access` only after the person agrees; leave native dialogs to them.
Do not infer completion from a command's exit status. Follow recovery, privacy and
real-read checks in START_HERE. This preview does not guarantee first acquisition
on every macOS/WeChat version.
