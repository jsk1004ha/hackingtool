import json
import os

import pytest

import hackingtool.engagement as engagement


def _root(tmp_path, monkeypatch):
    monkeypatch.setattr(engagement, "ENGAGEMENTS_ROOT", tmp_path)


def test_create_and_load_roundtrip(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme", targets=["example.com"], scope_in=["*.example.com"])
    e.save()
    assert (tmp_path / "acme" / "engagement.json").exists()
    loaded = engagement.load("acme")
    assert loaded.name == "acme"
    assert loaded.targets == ["example.com"]
    assert loaded.scope_in == ["*.example.com"]


def test_scope_matching(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create(
        "acme",
        scope_in=["*.example.com"],
        scope_out=["admin.example.com"],
    )
    assert e.in_scope("dev.example.com") is True
    assert e.in_scope("admin.example.com") is False
    assert e.in_scope("evil.test") is False


def test_scope_defaults_to_targets(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme", targets=["example.com"])
    assert e.in_scope("example.com") is True


def test_get_or_create_is_idempotent(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    engagement.get_or_create("acme", targets=["example.com"])
    existing = engagement.get_or_create("acme")
    assert existing.targets == ["example.com"]


def test_log_appends(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    e = engagement.create("acme")
    e.log("hello")
    assert "hello" in e.log_file.read_text()


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        ".",
        "..",
        "../outside",
        "nested/name",
        r"nested\name",
        "/tmp/outside",
        "C:outside",
    ],
)
def test_rejects_names_that_are_not_single_path_components(
    tmp_path,
    monkeypatch,
    name,
):
    _root(tmp_path / "root", monkeypatch)
    with pytest.raises((TypeError, ValueError)):
        engagement.create(name)
    assert not (tmp_path / "engagement.json").exists()


def test_allows_human_readable_single_component_names(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    created = engagement.create("Acme assessment 2026")
    assert created.workspace == (tmp_path / "Acme assessment 2026").resolve()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_rejects_existing_symlink_that_escapes_root(tmp_path, monkeypatch):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    _root(root, monkeypatch)

    with pytest.raises(ValueError, match="escapes"):
        engagement.create("escape")
    assert not (outside / "engagement.json").exists()


def test_load_rejects_mismatched_stored_name(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    stored = tmp_path / "safe" / "engagement.json"
    stored.parent.mkdir()
    stored.write_text(
        json.dumps(
            {
                "name": "../outside",
                "created": "2026-08-18T00:00:00+00:00",
                "scope_in": [],
                "scope_out": [],
                "targets": [],
                "runs": [],
            }
        )
    )

    with pytest.raises(ValueError, match="does not match"):
        engagement.load("safe")
