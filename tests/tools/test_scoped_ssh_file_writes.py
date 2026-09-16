"""Real filesystem checks behind a synthetic SSH transport; no remote credentials."""
import json
from contextlib import contextmanager
import subprocess

import pytest

from tools.environments.ssh import SSHEnvironment
from tools.file_operations import ShellFileOperations
from tools.terminal_scope import set_terminal_scope, reset_terminal_scope


@contextmanager
def scoped_terminal(mapping):
    token = set_terminal_scope(mapping)
    try:
        yield
    finally:
        reset_terminal_scope(token)


class SyntheticSSH(SSHEnvironment):
    def __init__(self, cwd):
        self.cwd = str(cwd)

    def execute(self, command, cwd=None, **kwargs):
        result = subprocess.run(['bash', '-c', command], cwd=cwd or self.cwd,
                                input=kwargs.get('stdin_data'), text=True,
                                capture_output=True, timeout=10)
        return {'output': result.stdout + result.stderr, 'returncode': result.returncode}


def test_profile_roots_write_patch_and_symlink_isolation(tmp_path, monkeypatch):
    root = tmp_path.resolve() / 'managed worktree'
    root.mkdir()
    elsewhere = tmp_path.resolve() / 'other-profile'
    elsewhere.mkdir()
    (root / 'escape').symlink_to(elsewhere, target_is_directory=True)
    monkeypatch.setenv('HERMES_WRITE_SAFE_ROOT', str(elsewhere))
    ops = ShellFileOperations(SyntheticSSH(root))
    target = root / 'fixture.txt'
    with scoped_terminal({'TERMINAL_FILE_WRITE_ROOTS': json.dumps([str(root)])}):
        assert ops.write_file(str(target), 'ONE\n').error is None
        assert ops.patch_replace(str(target), 'ONE', 'TWO').error is None
        assert target.read_text() == 'TWO\n'
        assert ops.write_file(str(root / 'escape' / 'not-written.txt'), 'NO').error
        assert ops.move_file(str(target), str(elsewhere / 'moved.txt')).error
        assert target.exists()
    with scoped_terminal({}):
        assert ops.write_file(str(target), 'CROSS-PROFILE').error
    assert target.read_text() == 'TWO\n'
    assert not (elsewhere / 'not-written.txt').exists()


@pytest.mark.parametrize('policy', ['[]', 'null', '"/tmp"', '["/"]', 'invalid'])
def test_invalid_roots_fail_closed(tmp_path, policy):
    ops = ShellFileOperations(SyntheticSSH(tmp_path))
    with scoped_terminal({'TERMINAL_FILE_WRITE_ROOTS': policy}):
        assert ops.write_file(str(tmp_path / 'not-created'), 'NO').error
    assert not (tmp_path / 'not-created').exists()


def test_gateway_cwd_uses_profile_scope_not_ambient(monkeypatch):
    from tui_gateway import server
    monkeypatch.setenv('TERMINAL_ENV', 'local')
    monkeypatch.setenv('TERMINAL_CWD', '/opt/data')
    with scoped_terminal({'TERMINAL_ENV': 'ssh', 'TERMINAL_CWD': '/remote/profile/workspace'}):
        assert server._effective_terminal_backend() == 'ssh'
        assert server._terminal_task_cwd({'source': 'desktop', 'cwd': '/opt/data'}) == '/remote/profile/workspace'
        assert server._terminal_task_cwd({'explicit_cwd': True, 'cwd': '/remote/chosen'}) == '/remote/chosen'
