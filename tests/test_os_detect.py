from pathlib import Path
from types import SimpleNamespace

import pytest

from hackingtool import os_detect
from hackingtool.os_detect import OSInfo


def _os(system: str, manager: str, *, root: bool) -> OSInfo:
    return OSInfo(
        system=system,
        pkg_manager=manager,
        is_root=root,
        home_dir=Path("/tmp/test-home"),
    )


def test_install_packages_uses_list_form_and_preserves_each_package(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(os_detect.subprocess, "run", fake_run)
    monkeypatch.setattr("hackingtool.constants.PRIV_CMD", "doas")

    assert os_detect.install_packages(
        ["git", "python3-pip"],
        _os("linux", "apt-get", root=False),
    )
    assert calls == [
        (["doas", "apt-get", "install", "-y", "git", "python3-pip"], {"check": False})
    ]


def test_install_packages_never_parses_shell_metacharacters(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(os_detect.subprocess, "run", fake_run)

    payload = "nmap;touch-owned"
    assert os_detect.install_packages(
        [payload],
        _os("linux", "apt-get", root=True),
    )
    assert calls[0][0][-1] == payload
    assert "shell" not in calls[0][1]


def test_brew_install_does_not_use_privilege_escalation(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(os_detect.subprocess, "run", fake_run)

    assert os_detect.install_packages(
        ["wget"],
        _os("macos", "brew", root=False),
    )
    assert calls == [(["brew", "install", "wget"], {"check": False})]


@pytest.mark.parametrize("package", ["", "  ", "--help", "git curl", "bad\x00name"])
def test_invalid_package_names_are_rejected_before_execution(monkeypatch, package):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("subprocess.run must not be called")

    monkeypatch.setattr(os_detect.subprocess, "run", fail_if_called)

    assert not os_detect.install_packages(
        [package],
        _os("linux", "apt-get", root=True),
    )


def test_unknown_package_manager_does_not_spawn(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("subprocess.run must not be called")

    monkeypatch.setattr(os_detect.subprocess, "run", fail_if_called)

    assert not os_detect.install_packages(
        ["git"],
        _os("linux", "unknown", root=True),
    )


def test_execution_error_is_reported_as_failure(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("package manager disappeared")

    monkeypatch.setattr(os_detect.subprocess, "run", fake_run)

    assert not os_detect.install_packages(
        ["git"],
        _os("linux", "apt-get", root=True),
    )


def test_empty_package_list_is_a_successful_noop(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("subprocess.run must not be called")

    monkeypatch.setattr(os_detect.subprocess, "run", fail_if_called)

    assert os_detect.install_packages(
        [],
        _os("linux", "apt-get", root=True),
    )
