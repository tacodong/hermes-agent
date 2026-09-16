# Remote Desktop approval and terminal repair

This maintenance change is based on deployed revision
8af5c55b79aeef1e5d16b114c926ac64ddf7d791, not the newer Desktop client checkout.

A lazily resumed session is minted without `_enable_gateway_prompts()`. Its
session-local source is `desktop`, but its platform can be empty. Classifying
only by platform and process-global flags can send its approval to CLI stdin.
A new session initializes those flags and masks the failure for later sessions.
Use the session-local Desktop/TUI source after unattended-platform exclusions.
The registered session callback then emits `approval.request` over its existing
transport; Desktop's input-request handler renders the inline approval card and
sends the response through `requestForOwnedSession`.

The approval RPCs additionally require the current transport to own the named
session. A request ID is correlation data, never authority to search another
session. Durable session IDs remain supported for reconnects. Once is consumed
only by that pending command; denial and timeout remain closed. No approval
policy, provider, credential or allowlist changes are included.

Non-local background execution previously recorded `cwd` but launched a login
shell without entering it. The launch now enters the quoted requested directory
and fails if it does not exist, before executing the command.

Focused regression command:

```
scripts/run_tests.sh tests/tui_gateway/test_remote_desktop_approval.py tests/tui_gateway/test_protocol.py tests/tools/test_background_remote_cwd.py tests/tools/test_process_registry.py -q
```

The new approval and cwd tests fail on the unpatched deployed revision. Eight
existing systemd tests require Linux and fail when run on macOS; Linux validation
must be recorded separately. Desktop acceptance and deployment receipts belong
to the homelab owner; Python tests do not prove visible UI acceptance.

`docker/maintenance/Desktop.Dockerfile` overlays only the three changed runtime
files onto the immutable deployed image. Build with the source revision label,
then deploy by digest through the existing fleet controller.
