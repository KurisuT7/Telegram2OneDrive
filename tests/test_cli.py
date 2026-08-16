from pathlib import Path

import pytest

from telegram2onedrive import cli
from telegram2onedrive.config import ConfigurationError, Settings
from telegram2onedrive.rclone import CheckResult, RcloneError


def configured(allowed: str = "123") -> Settings:
    return Settings.from_mapping(
        {
            "TELEGRAM_BOT_TOKEN": "synthetic-token",
            "TELEGRAM_ALLOWED_USER_IDS": allowed,
            "RCLONE_REMOTE": "onedrive",
        }
    )


class FakeClient:
    outcome: CheckResult | Exception = CheckResult("rclone v1", "onedrive")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def check(self) -> CheckResult:
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_configuration_load_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_load(path: Path | None) -> Settings:
        raise ConfigurationError("missing")

    monkeypatch.setattr(cli.Settings, "load", fail_load)
    assert cli.main(["check"]) == 2
    assert "Configuration error" in capsys.readouterr().out


def test_validation_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.Settings, "load", lambda path: Settings.from_mapping({}))
    assert cli.main(["check"]) == 2
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().out


def test_rclone_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    FakeClient.outcome = RcloneError("synthetic failure")
    monkeypatch.setattr(cli.Settings, "load", lambda path: configured())
    monkeypatch.setattr(cli, "RcloneClient", FakeClient)
    assert cli.main(["check"]) == 1
    assert "OneDrive check failed" in capsys.readouterr().out


def test_check_success_and_bootstrap_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    FakeClient.outcome = CheckResult("rclone v1", "onedrive")
    monkeypatch.setattr(cli.Settings, "load", lambda path: configured(""))
    monkeypatch.setattr(cli, "RcloneClient", FakeClient)
    assert cli.main(["check"]) == 0
    output = capsys.readouterr().out
    assert "Warning" in output
    assert "check passed" in output


def test_run_starts_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[Settings] = []
    FakeClient.outcome = CheckResult("rclone v1", "onedrive")
    monkeypatch.setattr(cli.Settings, "load", lambda path: configured())
    monkeypatch.setattr(cli, "RcloneClient", FakeClient)
    monkeypatch.setattr(cli, "run_bot", called.append)
    assert cli.main(["run"]) == 0
    assert len(called) == 1
