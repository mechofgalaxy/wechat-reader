# WeChat Reader — Read-only Troubleshooting

Please continue investigating this WeChat Reader failure with a **read-only diagnostic pass**.

The connection failed, but the available evidence does **not yet establish that this Mac or WeChat build is unsupported**. No administrator dialog appearing is not sufficient to determine the cause. `new_machine_compatibility` is a general limitation notice, not an error code. In a status response, `provider_executed: false` describes that status check, not necessarily earlier attempts.

## Reference links

First-use guide:
https://github.com/mechofgalaxy/wechat-reader/blob/main/START_HERE.md

Exact rc1 diagnostic source:
https://github.com/mechofgalaxy/wechat-reader/blob/c018f5d0403d3b3daad593cc72beaf0a8f9aefcb/rion_wechat_access.py

Exact rc1 first-connection source:
https://github.com/mechofgalaxy/wechat-reader/blob/c018f5d0403d3b3daad593cc72beaf0a8f9aefcb/first_run.py

## Diagnostic steps

1. Retrieve the **original `error.code`** from the previous execution output. Do not rerun acquisition to reproduce it.
2. Run the installed launcher's read-only diagnostics:

   ```sh
   "$HOME/.local/share/wechat-reader/bin/wechat-reader" runtime-status
   "$HOME/.local/share/wechat-reader/bin/wechat-reader" connect --name PROFILE_NAME --status
   ```

   Replace `PROFILE_NAME` with the exact label used previously, not the WeChat account ID. If the launcher was installed elsewhere, use its previously verified absolute path. If the previous profile label cannot be recovered, report that gap rather than guessing or creating a new profile.
3. Report `last_attempt_state` and `last_attempt_diagnostics`, including any `phase`, `provider_started`, `exit_code`, and `signals`. If a field is absent, report it as unavailable.
4. Include the Mac architecture, macOS version, and WeChat version/build.
5. Separately confirm whether the **“Connect my account” consent dialog** appeared and whether an **administrator authorization dialog** appeared.

## Interpretation and scope

Distinguish observations from hypotheses. In particular, a recorded `worker_preflight_failed` means the worker reached its preflight stage; it does not mean the worker never launched. Check whether the saved receipt actually corresponds to the failed attempt. A missing receipt or an older receipt does not establish what happened in the latest attempt.

Keep the installation in place. During this pass, do not retry acquisition, clear recovery locks, restart or modify WeChat, or change macOS security settings. Share only the safe diagnostic fields—no account identifiers, personal paths, keys, databases, or raw acquisition logs.

Return the collected facts, the earliest failure stage supported by those facts, and any remaining evidence gaps. Identify any proposed follow-up action that would require fresh user authorization; do not perform it during this diagnostic pass.
