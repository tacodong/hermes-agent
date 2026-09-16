"""Real approval gate -> session event -> response, without process GUI flags."""
import contextvars
import queue
import threading
from types import SimpleNamespace

import pytest


@pytest.fixture
def surface(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    (home / "config.yaml").write_text("approvals:\n  mode: manual\n  timeout: 1\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    for key in ("HERMES_GATEWAY_SESSION", "HERMES_EXEC_ASK", "HERMES_INTERACTIVE"):
        monkeypatch.delenv(key, raising=False)
    from tui_gateway import server
    from tools import approval
    from tools.approval_context import set_current_session_key, reset_current_session_key

    class Peer:
        def __init__(self):
            self.frames = queue.Queue()

        def write(self, frame):
            self.frames.put(frame)
            return True

        def close(self):
            pass

    owner, foreign = Peer(), Peer()
    server._sessions["approval-owner"] = {
        "session_key": "approval-durable", "source": "desktop", "transport": owner,
        "agent": SimpleNamespace(session_id="approval-durable"), "history": [],
    }
    server._sessions["approval-other"] = {
        "session_key": "other-durable", "source": "desktop", "transport": foreign,
        "agent": SimpleNamespace(session_id="other-durable"), "history": [],
    }
    approval.register_gateway_notify("approval-durable", lambda data: server._emit_approval_request("approval-owner", data))
    token = set_current_session_key("approval-durable")
    tokens = server._set_session_context("approval-durable", ui_session_id="approval-owner")
    yield server, approval, owner, foreign
    server._clear_session_context(tokens)
    reset_current_session_key(token)
    approval.unregister_gateway_notify("approval-durable")
    approval.clear_session("approval-durable")
    server._sessions.pop("approval-owner", None)
    server._sessions.pop("approval-other", None)


def start_gate(approval, command):
    results = queue.Queue()
    ctx = contextvars.copy_context()
    thread = threading.Thread(target=lambda: results.put(ctx.run(approval.check_dangerous_command, command, "ssh")))
    thread.start()
    return thread, results


def reply(server, peer, session_id, request_id, choice):
    from tui_gateway.transport import bind_transport, reset_transport
    token = bind_transport(peer)
    try:
        return server.handle_request({"id": "answer", "method": "approval.respond", "params": {
            "session_id": session_id, "request_id": request_id, "choice": choice,
        }})
    finally:
        reset_transport(token)


@pytest.mark.parametrize("choice,allowed", [("deny", False), ("once", True)])
def test_remote_source_delivers_exact_command_and_single_use(surface, choice, allowed):
    server, approval, owner, foreign = surface
    command = "chmod -R 777 /tmp/synthetic-approval-only"
    thread, results = start_gate(approval, command)
    event = owner.frames.get(timeout=2)["params"]
    assert event["type"] == "approval.request"
    assert event["session_id"] == "approval-owner"
    assert event["payload"]["command"] == command
    request_id = event["payload"]["request_id"]
    assert reply(server, foreign, "approval-owner", request_id, "once")["error"]["code"] == 4001
    assert reply(server, foreign, "retired-other", request_id, "once")["error"]["code"] == 4001
    assert reply(server, foreign, "approval-other", request_id, "once")["result"]["resolved"] == 0
    assert thread.is_alive()
    assert reply(server, owner, "approval-owner", request_id, choice)["result"]["resolved"] == 1
    thread.join(2)
    assert results.get(timeout=1)["approved"] is allowed
    assert reply(server, owner, "approval-owner", request_id, "once")["result"]["resolved"] == 0
    # Once never caches the pattern: a different command needs a new decision.
    second, results = start_gate(approval, command + "-second")
    next_event = owner.frames.get(timeout=2)["params"]
    assert next_event["payload"]["request_id"] != request_id
    second.join(3)
    assert results.get(timeout=1)["approved"] is False


def test_unattended_platform_still_denied(surface):
    from gateway.session_context import set_session_vars, clear_session_vars
    from tools.approval_context import _is_gateway_approval_context, _is_unattended_platform_approval_context
    tokens = set_session_vars(platform="api_server", source="desktop", session_key="api")
    try:
        assert not _is_gateway_approval_context()
        assert _is_unattended_platform_approval_context()
    finally:
        clear_session_vars(tokens)
