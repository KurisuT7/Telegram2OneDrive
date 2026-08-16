"""Configuration loading and validation."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

_REMOTE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_BOT_TOKEN_RE = re.compile(r"[1-9][0-9]*:[A-Za-z0-9_-]+")
_API_HASH_RE = re.compile(r"[0-9A-Fa-f]{32}")
_SESSION_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


class ConfigurationError(ValueError):
    """Raised when configuration cannot be loaded."""


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ConfigurationError(f"{name} must be true or false")


def _parse_int(name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _parse_optional_int(name: str, value: str) -> int | None:
    if not value:
        return None
    return _parse_int(name, value)


def _parse_user_ids(value: str) -> frozenset[int]:
    if not value.strip():
        return frozenset()
    result: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item or not item.isdecimal() or int(item) <= 0:
            raise ConfigurationError("TELEGRAM_ALLOWED_USER_IDS must contain positive integers")
        result.add(int(item))
    return frozenset(result)


def _normalize_base_path(value: str) -> str:
    parts = [part.strip() for part in value.strip(" /").split("/") if part.strip()]
    if any(part in {".", ".."} for part in parts):
        raise ConfigurationError("ONEDRIVE_BASE_PATH cannot contain . or .. segments")
    if any("\\" in part or ":" in part or any(ord(char) < 32 for char in part) for part in parts):
        raise ConfigurationError("ONEDRIVE_BASE_PATH contains unsupported characters")
    return "/".join(parts)


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    allowed_user_ids: frozenset[int]
    allow_group_chats: bool
    max_file_mib: int
    telegram_local_mode: bool
    telegram_base_url: str
    telegram_base_file_url: str
    telegram_mtproto_enabled: bool
    telegram_api_id: int | None
    telegram_api_hash: str
    telegram_mtproto_session_dir: Path | None
    telegram_mtproto_session_name: str
    rclone_remote: str
    rclone_config: Path | None
    onedrive_base_path: str
    duplicate_policy: str
    rclone_timeout_seconds: int
    transfer_tmp_dir: Path | None

    @classmethod
    def load(cls, env_file: Path | None = None) -> Settings:
        values: dict[str, str] = {}
        if env_file is not None:
            if not env_file.is_file():
                raise ConfigurationError(f"Environment file does not exist: {env_file}")
            values.update(
                {str(key): str(value) for key, value in dotenv_values(env_file).items() if value}
            )
        values.update(os.environ)
        return cls.from_mapping(values)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Settings:
        def get(name: str, default: str = "") -> str:
            return str(values.get(name, default)).strip()

        config_value = get("RCLONE_CONFIG")
        temp_value = get("TRANSFER_TMP_DIR")
        session_dir_value = get("TELEGRAM_MTPROTO_SESSION_DIR")
        return cls(
            telegram_bot_token=get("TELEGRAM_BOT_TOKEN"),
            allowed_user_ids=_parse_user_ids(get("TELEGRAM_ALLOWED_USER_IDS")),
            allow_group_chats=_parse_bool(
                "TELEGRAM_ALLOW_GROUP_CHATS", get("TELEGRAM_ALLOW_GROUP_CHATS", "false")
            ),
            max_file_mib=_parse_int("MAX_FILE_MIB", get("MAX_FILE_MIB", "20")),
            telegram_local_mode=_parse_bool(
                "TELEGRAM_LOCAL_MODE", get("TELEGRAM_LOCAL_MODE", "false")
            ),
            telegram_base_url=get("TELEGRAM_BASE_URL"),
            telegram_base_file_url=get("TELEGRAM_BASE_FILE_URL"),
            telegram_mtproto_enabled=_parse_bool(
                "TELEGRAM_MTPROTO_ENABLED", get("TELEGRAM_MTPROTO_ENABLED", "false")
            ),
            telegram_api_id=_parse_optional_int("TELEGRAM_API_ID", get("TELEGRAM_API_ID")),
            telegram_api_hash=get("TELEGRAM_API_HASH"),
            telegram_mtproto_session_dir=(
                Path(session_dir_value).expanduser() if session_dir_value else None
            ),
            telegram_mtproto_session_name=get("TELEGRAM_MTPROTO_SESSION_NAME", "telegram2onedrive"),
            rclone_remote=get("RCLONE_REMOTE", "onedrive"),
            rclone_config=Path(config_value).expanduser() if config_value else None,
            onedrive_base_path=_normalize_base_path(get("ONEDRIVE_BASE_PATH", "Telegram2OneDrive")),
            duplicate_policy=get("DUPLICATE_POLICY", "rename").lower(),
            rclone_timeout_seconds=_parse_int(
                "RCLONE_TIMEOUT_SECONDS", get("RCLONE_TIMEOUT_SECONDS", "3600")
            ),
            transfer_tmp_dir=Path(temp_value).expanduser() if temp_value else None,
        )

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        elif not _BOT_TOKEN_RE.fullmatch(self.telegram_bot_token):
            errors.append("TELEGRAM_BOT_TOKEN has an invalid format")
        if not _REMOTE_RE.fullmatch(self.rclone_remote):
            errors.append("RCLONE_REMOTE must use only letters, digits, underscores, or hyphens")
        if self.rclone_config is not None:
            if not self.rclone_config.is_absolute():
                errors.append("RCLONE_CONFIG must be an absolute path")
            elif not self.rclone_config.is_file():
                errors.append("RCLONE_CONFIG does not point to a readable file")
        if self.transfer_tmp_dir is not None and not self.transfer_tmp_dir.is_absolute():
            errors.append("TRANSFER_TMP_DIR must be an absolute path")
        if self.duplicate_policy not in {"rename", "replace", "fail"}:
            errors.append("DUPLICATE_POLICY must be rename, replace, or fail")
        if not 1 <= self.max_file_mib <= 2048:
            errors.append("MAX_FILE_MIB must be between 1 and 2048")
        if (
            not self.telegram_local_mode
            and not self.telegram_mtproto_enabled
            and self.max_file_mib > 20
        ):
            errors.append("MAX_FILE_MIB cannot exceed 20 without a large-file download backend")
        if self.telegram_local_mode:
            if self.telegram_mtproto_enabled:
                errors.append(
                    "TELEGRAM_LOCAL_MODE and TELEGRAM_MTPROTO_ENABLED are mutually exclusive"
                )
            if not self.telegram_base_url.startswith(("http://", "https://")):
                errors.append("TELEGRAM_BASE_URL is required in local mode")
            elif not self.telegram_base_url.rstrip("/").endswith("/bot"):
                errors.append("TELEGRAM_BASE_URL must end with /bot")
            if not self.telegram_base_file_url.startswith(("http://", "https://")):
                errors.append("TELEGRAM_BASE_FILE_URL is required in local mode")
            elif not self.telegram_base_file_url.rstrip("/").endswith("/file/bot"):
                errors.append("TELEGRAM_BASE_FILE_URL must end with /file/bot")
            if self.telegram_bot_token and (
                self.telegram_bot_token in self.telegram_base_url
                or self.telegram_bot_token in self.telegram_base_file_url
            ):
                errors.append("Telegram base URLs must not contain the bot token")
        if self.telegram_mtproto_enabled:
            if self.telegram_api_id is None or self.telegram_api_id <= 0:
                errors.append("TELEGRAM_API_ID must be a positive integer when MTProto is enabled")
            if not _API_HASH_RE.fullmatch(self.telegram_api_hash):
                errors.append(
                    "TELEGRAM_API_HASH must be 32 hexadecimal characters when MTProto is enabled"
                )
            if self.telegram_mtproto_session_dir is None:
                errors.append("TELEGRAM_MTPROTO_SESSION_DIR is required when MTProto is enabled")
            elif not self.telegram_mtproto_session_dir.is_absolute():
                errors.append("TELEGRAM_MTPROTO_SESSION_DIR must be an absolute path")
            elif self.telegram_mtproto_session_dir.is_symlink():
                errors.append("TELEGRAM_MTPROTO_SESSION_DIR must not be a symbolic link")
            elif (
                self.telegram_mtproto_session_dir.exists()
                and not self.telegram_mtproto_session_dir.is_dir()
            ):
                errors.append("TELEGRAM_MTPROTO_SESSION_DIR must point to a directory")
            if not _SESSION_NAME_RE.fullmatch(self.telegram_mtproto_session_name):
                errors.append(
                    "TELEGRAM_MTPROTO_SESSION_NAME must use only letters, digits, "
                    "underscores, or hyphens"
                )
        elif (
            self.telegram_api_id is not None
            or self.telegram_api_hash
            or self.telegram_mtproto_session_dir
        ):
            errors.append("MTProto credentials require TELEGRAM_MTPROTO_ENABLED=true")
        if not 60 <= self.rclone_timeout_seconds <= 86400:
            errors.append("RCLONE_TIMEOUT_SECONDS must be between 60 and 86400")
        return errors

    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.allowed_user_ids:
            warnings.append(
                "No allowed user IDs are configured; only /start and /whoami will be available"
            )
        if self.telegram_mtproto_enabled and self.max_file_mib <= 20:
            warnings.append(
                "MTProto is enabled, but MAX_FILE_MIB does not allow files above the Bot API limit"
            )
        return warnings

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mib * 1024 * 1024
