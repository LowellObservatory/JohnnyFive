"""Unit tests for configuration and service utility helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from johnnyfive import utils


def test_val_checks_converts_scalars_and_lists() -> None:
    """Convert configuration literals and comma-separated values."""
    assert utils.valChecks(" true ") is True
    assert utils.valChecks("None") is None
    assert utils.valChecks("first, false, second") == ["first", False, "second"]


def test_read_config_section_and_legacy_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parse a section into J5's target object through both public names."""
    (tmp_path / "johnnyfive.conf").write_text(
        "[service]\nhost = example.test\nenabled = true\ncustom = one, two\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(utils.Paths, "config", tmp_path)

    target = utils.read_config_section("service")
    legacy_target = utils.read_ligmos_conffiles("service")

    assert target.host == "example.test"
    assert target.enabled is True
    assert target.custom == ["one", "two"]
    assert legacy_target.host == target.host


def test_read_config_section_reports_missing_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise J5Error instead of leaking a missing-section KeyError."""
    (tmp_path / "johnnyfive.conf").write_text("[other]\nvalue = 1\n", encoding="utf-8")
    monkeypatch.setattr(utils.Paths, "config", tmp_path)

    with pytest.raises(utils.J5Error, match="Configuration key missing"):
        utils.read_config_section("missing")


def test_install_conffiles_copies_requested_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Copy configuration files to the configured package directory."""
    source = tmp_path / "source.conf"
    destination = tmp_path / "destination"
    destination.mkdir()
    source.write_text("[service]\nkey = value\n", encoding="utf-8")
    monkeypatch.setattr(utils.Paths, "config", destination)

    utils.install_conffiles([str(source)])

    assert (destination / source.name).read_text(encoding="utf-8") == source.read_text(
        encoding="utf-8"
    )


def test_safe_service_connect_retries_network_failure(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retry transient connection failures and return the eventual result."""
    attempts = 0

    def flaky_service() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("temporary outage")
        return "connected"

    monkeypatch.setattr(utils.time, "sleep", lambda _: None)

    with pytest.warns(UserWarning, match="network error"):
        assert utils.safe_service_connect(flaky_service, pause=0, nretries=2) == "connected"
    assert attempts == 2
