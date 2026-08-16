from pathlib import Path

import pytest

from telegram2onedrive.config import ConfigurationError, Settings


def valid_values() -> dict[str, str]:
    return {
        "TELEGRAM_BOT_TOKEN": "synthetic-token",
        "TELEGRAM_ALLOWED_USER_IDS": "123, 456",
        "RCLONE_REMOTE": "onedrive",
    }


def test_parses_allowlist_and_defaults() -> None:
    settings = Settings.from_mapping(valid_values())
    assert settings.allowed_user_ids == frozenset({123, 456})
    assert settings.max_file_mib == 20
    assert settings.duplicate_policy == "rename"
    assert settings.validation_errors() == []


@pytest.mark.parametrize("value", ["x", "-1", "12,", "1.2"])
def test_rejects_invalid_user_ids(value: str) -> None:
    values = valid_values() | {"TELEGRAM_ALLOWED_USER_IDS": value}
    with pytest.raises(ConfigurationError):
        Settings.from_mapping(values)


def test_empty_allowlist_is_bootstrap_warning() -> None:
    settings = Settings.from_mapping(valid_values() | {"TELEGRAM_ALLOWED_USER_IDS": ""})
    assert settings.validation_errors() == []
    assert settings.warnings()


def test_cloud_api_enforces_twenty_mib_limit() -> None:
    settings = Settings.from_mapping(valid_values() | {"MAX_FILE_MIB": "21"})
    assert any("cannot exceed 20" in error for error in settings.validation_errors())


def test_local_mode_requires_urls() -> None:
    settings = Settings.from_mapping(
        valid_values() | {"TELEGRAM_LOCAL_MODE": "true", "MAX_FILE_MIB": "2000"}
    )
    assert len(settings.validation_errors()) == 2


def test_local_mode_accepts_explicit_urls() -> None:
    settings = Settings.from_mapping(
        valid_values()
        | {
            "TELEGRAM_LOCAL_MODE": "true",
            "TELEGRAM_BASE_URL": "http://127.0.0.1:8081/bot",
            "TELEGRAM_BASE_FILE_URL": "http://127.0.0.1:8081/file/bot",
            "MAX_FILE_MIB": "2000",
        }
    )
    assert settings.validation_errors() == []


def test_local_mode_rejects_token_and_wrong_url_shape() -> None:
    settings = Settings.from_mapping(
        valid_values()
        | {
            "TELEGRAM_LOCAL_MODE": "true",
            "TELEGRAM_BASE_URL": "http://127.0.0.1:8081/synthetic-token",
            "TELEGRAM_BASE_FILE_URL": "http://127.0.0.1:8081/file/synthetic-token",
        }
    )
    errors = settings.validation_errors()
    assert "TELEGRAM_BASE_URL must end with /bot" in errors
    assert "TELEGRAM_BASE_FILE_URL must end with /file/bot" in errors
    assert "Telegram base URLs must not contain the bot token" in errors


@pytest.mark.parametrize("value", ["../private", "a/../b", "a:b", "a\\b"])
def test_rejects_unsafe_onedrive_base_path(value: str) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_mapping(valid_values() | {"ONEDRIVE_BASE_PATH": value})


def test_reports_missing_rclone_config(tmp_path: Path) -> None:
    settings = Settings.from_mapping(
        valid_values() | {"RCLONE_CONFIG": str(tmp_path / "missing.conf")}
    )
    assert "RCLONE_CONFIG does not point to a readable file" in settings.validation_errors()


def test_rejects_relative_runtime_paths() -> None:
    settings = Settings.from_mapping(
        valid_values() | {"RCLONE_CONFIG": "rclone.conf", "TRANSFER_TMP_DIR": "tmp"}
    )
    assert "RCLONE_CONFIG must be an absolute path" in settings.validation_errors()
    assert "TRANSFER_TMP_DIR must be an absolute path" in settings.validation_errors()


def test_rejects_invalid_boolean() -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_mapping(valid_values() | {"TELEGRAM_LOCAL_MODE": "perhaps"})


def test_load_env_file_and_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_BOT_TOKEN=from-file\nRCLONE_REMOTE=file-remote\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "from-environment")
    settings = Settings.load(env_file)
    assert settings.telegram_bot_token == "from-environment"
    assert settings.rclone_remote == "file-remote"


def test_load_rejects_missing_env_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="does not exist"):
        Settings.load(tmp_path / "missing.env")


@pytest.mark.parametrize(
    ("key", "value", "fragment"),
    [
        ("RCLONE_REMOTE", "bad remote", "RCLONE_REMOTE"),
        ("DUPLICATE_POLICY", "skip", "DUPLICATE_POLICY"),
        ("MAX_FILE_MIB", "0", "between 1 and 2048"),
        ("RCLONE_TIMEOUT_SECONDS", "30", "between 60 and 86400"),
    ],
)
def test_validation_boundaries(key: str, value: str, fragment: str) -> None:
    settings = Settings.from_mapping(valid_values() | {key: value})
    assert any(fragment in error for error in settings.validation_errors())


def test_rejects_invalid_integer() -> None:
    with pytest.raises(ConfigurationError, match="must be an integer"):
        Settings.from_mapping(valid_values() | {"MAX_FILE_MIB": "large"})
