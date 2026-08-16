import asyncio
from pathlib import Path

import pytest

from telegram2onedrive.config import Settings
from telegram2onedrive.rclone import (
    CheckResult,
    CommandResult,
    DestinationExists,
    RcloneClient,
    RcloneError,
)


def settings(policy: str = "rename") -> Settings:
    return Settings.from_mapping(
        {
            "TELEGRAM_BOT_TOKEN": "synthetic-token",
            "TELEGRAM_ALLOWED_USER_IDS": "123",
            "RCLONE_REMOTE": "cloud",
            "DUPLICATE_POLICY": policy,
            "ONEDRIVE_BASE_PATH": "Telegram",
        }
    )


class FakeRclone(RcloneClient):
    def __init__(self, configured: Settings, results: list[CommandResult]) -> None:
        super().__init__(configured)
        self.results = results
        self.calls: list[tuple[str, ...]] = []

    async def _run(self, *arguments: str) -> CommandResult:
        self.calls.append(arguments)
        return self.results.pop(0)


def result(code: int = 0, stdout: str = "", stderr: str = "") -> CommandResult:
    return CommandResult(code, stdout, stderr)


def test_check_requires_onedrive_backend() -> None:
    client = FakeRclone(
        settings(),
        [result(stdout="rclone v1.0\n"), result(stdout="cloud: s3\n")],
    )
    with pytest.raises(RcloneError, match="not a OneDrive"):
        asyncio.run(client.check())


def test_check_returns_version_and_backend() -> None:
    client = FakeRclone(
        settings(),
        [result(stdout="rclone v1.2.3\n"), result(stdout="cloud: onedrive\n"), result()],
    )
    assert asyncio.run(client.check()) == CheckResult("rclone v1.2.3", "onedrive")


def test_replace_upload_does_not_use_immutable(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("content", encoding="utf-8")
    client = FakeRclone(settings("replace"), [result(), result()])
    upload = asyncio.run(client.upload(source, "Documents", "file.txt"))
    assert upload.destination == "cloud:Telegram/Documents/file.txt"
    copy_call = client.calls[-1]
    assert copy_call[0] == "copyto"
    assert "--immutable" not in copy_call


def test_fail_policy_rejects_case_insensitive_duplicate(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("content", encoding="utf-8")
    client = FakeRclone(settings("fail"), [result(), result(stdout="FILE.TXT\n")])
    with pytest.raises(DestinationExists):
        asyncio.run(client.upload(source, "Documents", "file.txt"))


def test_rename_policy_allocates_next_name(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("content", encoding="utf-8")
    client = FakeRclone(
        settings("rename"),
        [result(), result(stdout="file.txt\nfile (1).txt\n"), result()],
    )
    upload = asyncio.run(client.upload(source, "Documents", "file.txt"))
    assert upload.destination.endswith("file (2).txt")
    assert upload.renamed is True
    assert "--immutable" in client.calls[-1]


def test_rejects_missing_source(tmp_path: Path) -> None:
    client = FakeRclone(settings(), [])
    with pytest.raises(RcloneError, match="not a file"):
        asyncio.run(client.upload(tmp_path / "missing", "Other", "missing"))


def test_command_places_config_outside_remote_arguments(tmp_path: Path) -> None:
    config = tmp_path / "rclone.conf"
    config.write_text("[cloud]\ntype = onedrive\n", encoding="utf-8")
    configured = Settings.from_mapping(
        {
            "TELEGRAM_BOT_TOKEN": "synthetic-token",
            "RCLONE_REMOTE": "cloud",
            "RCLONE_CONFIG": str(config),
        }
    )
    command = RcloneClient(configured)._command("version")
    assert command == [
        "rclone",
        "--config",
        str(config),
        "--ask-password=false",
        "version",
    ]


def test_check_rejects_missing_remote_and_failed_access() -> None:
    missing = FakeRclone(
        settings(),
        [result(stdout="rclone v1\n"), result(stdout="other: onedrive\n")],
    )
    with pytest.raises(RcloneError, match="was not found"):
        asyncio.run(missing.check())

    failed = FakeRclone(
        settings(),
        [
            result(stdout="rclone v1\n"),
            result(stdout="cloud: onedrive\n"),
            result(1, stderr="offline"),
        ],
    )
    with pytest.raises(RcloneError, match="offline"):
        asyncio.run(failed.check())


def test_fail_policy_detects_race(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("content", encoding="utf-8")
    client = FakeRclone(
        settings("fail"),
        [result(), result(), result(1, stderr="race"), result(stdout="file.txt\n")],
    )
    with pytest.raises(DestinationExists):
        asyncio.run(client.upload(source, "Documents", "file.txt"))


def test_rename_policy_retries_race(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("content", encoding="utf-8")
    client = FakeRclone(
        settings("rename"),
        [
            result(),
            result(),
            result(1, stderr="race"),
            result(stdout="file.txt\n"),
            result(),
        ],
    )
    upload = asyncio.run(client.upload(source, "Documents", "file.txt"))
    assert upload.destination.endswith("file (1).txt")


def test_rename_policy_propagates_non_race_error(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("content", encoding="utf-8")
    client = FakeRclone(
        settings("rename"),
        [result(), result(), result(1, stderr="permission denied"), result()],
    )
    with pytest.raises(RcloneError, match="permission denied"):
        asyncio.run(client.upload(source, "Documents", "file.txt"))


def test_require_success_uses_fallback_message() -> None:
    with pytest.raises(RcloneError, match="returned an error"):
        RcloneClient._require_success(result(1), "operation")
