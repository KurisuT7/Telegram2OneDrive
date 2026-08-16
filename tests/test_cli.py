from pathlib import Path

import pytest

from telegram2onedrive import cli
from telegram2onedrive.config import ConfigurationError, Settings
from telegram2onedrive.rclone import CheckResult, RcloneError


def configured(allowed: str = "123") -> Settings:
    return Settings.from_mapping(
        {
            "TELEGRAM_BOT_TOKEN": "1:test",
            "TELEGRAM_ALLOWED_USER_IDS": allowed,
            "RCLONE_REMOTE": "onedrive",
        }
    )


def configured_mtproto(tmp_path: Path) -> Settings:
    return Settings.from_mapping(
        {
            "TELEGRAM_BOT_TOKEN": "1:test",
            "TELEGRAM_ALLOWED_USER_IDS": "123",
            "TELEGRAM_MTPROTO_ENABLED": "true",
            "TELEGRAM_API_ID": "12345",
            "TELEGRAM_API_HASH": "a" * 32,
            "TELEGRAM_MTPROTO_SESSION_DIR": str(tmp_path / "session"),
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


def test_resolve_env_file_uses_dotenv_in_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli._resolve_env_file(None) is None
    (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=1:test\n", encoding="utf-8")
    assert cli._resolve_env_file(None) == Path(".env")


def test_resolve_env_file_prefers_explicit_path(tmp_path: Path) -> None:
    explicit = tmp_path / "production.env"
    assert cli._resolve_env_file(explicit) == explicit


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


def test_mtproto_extra_is_required(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli.Settings, "load", lambda path: configured_mtproto(tmp_path))
    monkeypatch.setattr(cli, "find_spec", lambda name: None)
    assert cli.main(["check"]) == 2
    assert "telegram2onedrive[mtproto]" in capsys.readouterr().out


def test_run_starts_bot_with_mtproto_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[Settings] = []
    FakeClient.outcome = CheckResult("rclone v1", "onedrive")
    monkeypatch.setattr(cli.Settings, "load", lambda path: configured_mtproto(tmp_path))
    monkeypatch.setattr(cli, "RcloneClient", FakeClient)
    monkeypatch.setattr(cli, "find_spec", lambda name: object())
    monkeypatch.setattr(cli, "run_bot", called.append)
    assert cli.main(["run"]) == 0
    assert len(called) == 1


def test_mtproto_startup_failure_is_reported_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from telegram2onedrive.mtproto import MTProtoError

    FakeClient.outcome = CheckResult("rclone v1", "onedrive")
    monkeypatch.setattr(cli.Settings, "load", lambda path: configured_mtproto(tmp_path))
    monkeypatch.setattr(cli, "RcloneClient", FakeClient)
    monkeypatch.setattr(cli, "find_spec", lambda name: object())

    def fail(settings: Settings) -> None:
        raise MTProtoError("synthetic safe failure")

    monkeypatch.setattr(cli, "run_bot", fail)
    assert cli.main(["run"]) == 1
    assert "synthetic safe failure" in capsys.readouterr().out
