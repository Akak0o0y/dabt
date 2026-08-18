"""Manifests supplied from outside the package.

A manifest is a claim about someone else's software, so an organisation gating
its own MCP server has to be able to supply one without forking this package.
Without this, the HTTP evaluation path could only ever gate the servers shipped
in `dabt_core/data/manifests`.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

import dabt_api.main as main


@pytest.fixture
def service_with_extra_manifests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reload the service with an extra manifest directory, then restore it."""
    manifest = tmp_path / "acme.yaml"
    manifest.write_text(
        """
version: "0.1.0-acme"
server:
  id: acme
  description: "Acme MCP server"
tools:
  ping:
    operation: read
    resource_type: status
    persists_data: false
    confidence_level: needs_verification
    requires_legal_review: true
    returns:
      status:
        role: resource_metadata
        inspect_content: true
        maskable: false
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("DABT_MANIFEST_DIRS", str(tmp_path))
    reloaded = importlib.reload(main)
    yield reloaded
    monkeypatch.delenv("DABT_MANIFEST_DIRS", raising=False)
    importlib.reload(main)


def test_an_external_manifest_directory_is_loaded(service_with_extra_manifests) -> None:
    assert "acme" in service_with_extra_manifests.MANIFESTS


def test_packaged_manifests_are_still_loaded(service_with_extra_manifests) -> None:
    assert "cranl" in service_with_extra_manifests.MANIFESTS


def test_only_packaged_manifests_load_without_the_variable() -> None:
    os.environ.pop("DABT_MANIFEST_DIRS", None)
    reloaded = importlib.reload(main)

    assert "acme" not in reloaded.MANIFESTS
    assert "cranl" in reloaded.MANIFESTS


def test_a_missing_directory_is_ignored_rather_than_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale path in configuration must not stop the service from starting."""
    monkeypatch.setenv("DABT_MANIFEST_DIRS", str(Path("does") / "not" / "exist"))
    try:
        reloaded = importlib.reload(main)
        assert "cranl" in reloaded.MANIFESTS
    finally:
        monkeypatch.delenv("DABT_MANIFEST_DIRS", raising=False)
        importlib.reload(main)


def test_a_later_directory_overrides_a_packaged_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transcribed manifest must be able to supersede a reconstructed one."""
    override = tmp_path / "cranl.yaml"
    override.write_text(
        """
version: "9.9.9-transcribed"
server:
  id: cranl
  description: "Transcribed CranL manifest"
tools:
  get_logs:
    operation: read
    resource_type: log
    persists_data: false
    confidence_level: verified
    requires_legal_review: true
    returns:
      entries:
        role: opaque_payload
        inspect_content: true
        collection: true
        maskable: true
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("DABT_MANIFEST_DIRS", str(tmp_path))
    try:
        reloaded = importlib.reload(main)
        assert reloaded.MANIFESTS["cranl"].version == "9.9.9-transcribed"
    finally:
        monkeypatch.delenv("DABT_MANIFEST_DIRS", raising=False)
        importlib.reload(main)
