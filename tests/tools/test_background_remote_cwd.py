"""Exercise the non-local launch wrapper with real shell execution."""
import subprocess
import time

import pytest

from tools.process_registry import ProcessRegistry


@pytest.mark.parametrize("exists", [True, False])
def test_background_env_honors_requested_cwd_and_fails_closed(tmp_path, exists):
    default = tmp_path / "default"
    default.mkdir()
    requested = tmp_path / "requested path"
    if exists:
        requested.mkdir()

    class ShellBackend:
        def execute(self, command, **kwargs):
            result = subprocess.run(["bash", "-c", command], cwd=default,
                                    capture_output=True, text=True, timeout=10)
            return {"output": result.stdout + result.stderr, "returncode": result.returncode}

    registry = ProcessRegistry()
    session = registry.spawn_via_env(ShellBackend(), "pwd", cwd=str(requested))
    deadline = time.monotonic() + 10
    while not session.exited and time.monotonic() < deadline:
        time.sleep(0.05)
    assert session.exited
    if exists:
        assert str(requested) in session.output_buffer
        assert str(default) not in session.output_buffer
        assert session.exit_code == 0
    else:
        assert session.exit_code != 0
        assert str(default) not in session.output_buffer
