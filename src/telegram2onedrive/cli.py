"""Command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Sequence
from importlib.util import find_spec
from pathlib import Path

from telegram2onedrive import __version__
from telegram2onedrive.bot import run_bot
from telegram2onedrive.config import ConfigurationError, Settings
from telegram2onedrive.rclone import RcloneClient, RcloneError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="telegram2onedrive")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--env-file", type=Path, help="load configuration from this dotenv file")
    parser.add_argument("command", choices=("check", "run"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = Settings.load(args.env_file)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return 2

    errors = settings.validation_errors()
    if errors:
        for error in errors:
            print(f"Configuration error: {error}")
        return 2
    for warning in settings.warnings():
        print(f"Warning: {warning}")

    if settings.telegram_mtproto_enabled and find_spec("pyrogram") is None:
        print(
            "Configuration error: MTProto support is not installed; "
            'install "telegram2onedrive[mtproto]"'
        )
        return 2

    try:
        result = asyncio.run(RcloneClient(settings).check())
    except (OSError, RcloneError) as exc:
        print(f"OneDrive check failed: {exc}")
        return 1

    print(f"OneDrive check passed: {result.backend} via {result.version}")
    if args.command == "check":
        return 0

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    if settings.telegram_mtproto_enabled:
        from telegram2onedrive.mtproto import MTProtoError

        try:
            run_bot(settings)
        except MTProtoError as exc:
            print(f"Telegram MTProto startup failed: {exc}")
            return 1
    else:
        run_bot(settings)
    return 0
