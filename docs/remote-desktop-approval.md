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

`docker/maintenance/Desktop.Dockerfile` overlays only the changed runtime
files onto the immutable deployed image. Build with the source revision label,
then deploy by digest through the existing fleet controller.

Native Bot Chat local/peer messaging also used bare `hermes`, unlike the relay
path. Both now use the existing venv-sibling executable resolver. The focused
Bot Mode suite passes 43 tests, including a real child launch with an empty PATH
and a runtime path containing spaces. No roster or recipient authorization changes.

The follow-up file baseline uses the routed profile's terminal scope for Desktop
backend/cwd resolution instead of ambient process values. SSH file writes can
opt into `terminal.file_write_roots`, a nonempty list of canonical existing
executor directories. The override applies only with a bound profile scope and
an SSH environment. Remote canonicalization rejects escaping symlinks, broad
roots, malformed policy, and failed probes; other profiles/backends retain the
existing process root. Credential/system guards remain. This is a file-tool
boundary, not an OS sandbox or protection against concurrent filesystem races.
Tests use a synthetic SSH transport over real files for write/readback, patch,
move refusal, symlink escape, malformed roots and cross-profile fallback.

### Scheduled results under a named multiplex owner

Bot Chat cron delivery retains the custom installation root for explicit profile
selection and the context-local home for own-profile delivery. Child processes
reload recipient credentials rather than inheriting gateway-owner credentials.
Scheduler liveness also consults live named-owner topology, so a satellite served
by a named multiplexer does not receive a false inactive warning. Regression
coverage exercises custom roots, context-local homes, secret removal, and served
versus unrelated or unknown scheduler owners.
