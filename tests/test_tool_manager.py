from pathlib import Path
from types import SimpleNamespace

from hackingtool.os_detect import OSInfo
from hackingtool.tools import tool_manager


def _os(system: str, manager: str, *, root: bool) -> OSInfo:
    return OSInfo(
        system=system,
        pkg_manager=manager,
        is_root=root,
        home_dir=Path("/tmp/test-home"),
    )


def test_system_update_runs_each_step_as_argv_with_configured_privilege(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(tool_manager.subprocess, "run", fake_run)
    monkeypatch.setattr(tool_manager, "PRIV_CMD", "doas")

    assert tool_manager._run_system_update(
        "apt-get update -qq && apt-get upgrade -y",
        _os("linux", "apt-get", root=False),
    )
    assert calls == [
        (["doas", "apt-get", "update", "-qq"], {"check": False}),
        (["doas", "apt-get", "upgrade", "-y"], {"check": False}),
    ]


def test_system_update_does_not_escalate_brew_on_macos(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(tool_manager.subprocess, "run", fake_run)

    assert tool_manager._run_system_update(
        "brew update && brew upgrade",
        _os("macos", "brew", root=False),
    )
    assert calls == [
        (["brew", "update"], {"check": False}),
        (["brew", "upgrade"], {"check": False}),
    ]


def test_system_update_stops_after_first_failed_step(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(tool_manager.subprocess, "run", fake_run)

    assert not tool_manager._run_system_update(
        "apt-get update && apt-get upgrade -y",
        _os("linux", "apt-get", root=True),
    )
    assert calls == [(["apt-get", "update"], {"check": False})]


def test_system_update_reports_spawn_failure(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("manager disappeared")

    monkeypatch.setattr(tool_manager.subprocess, "run", fake_run)

    assert not tool_manager._run_system_update(
        "apt-get update",
        _os("linux", "apt-get", root=True),
    )


def test_empty_system_update_is_rejected(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("subprocess.run must not be called")

    monkeypatch.setattr(tool_manager.subprocess, "run", fail_if_called)
    assert not tool_manager._run_system_update(
        "   ",
        _os("linux", "apt-get", root=True),
    )
