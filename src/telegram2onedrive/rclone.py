"""Restricted rclone adapter for OneDrive uploads."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from telegram2onedrive.config import Settings
from telegram2onedrive.files import renamed_candidate


class RcloneError(RuntimeError):
    """Raised when rclone cannot complete an operation."""


class DestinationExists(RcloneError):
    """Raised when the configured duplicate policy rejects a destination."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class CheckResult:
    version: str
    backend: str


@dataclass(frozen=True, slots=True)
class UploadResult:
    destination: str
    renamed: bool


class RcloneClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _command(self, *arguments: str) -> list[str]:
        command = ["rclone"]
        if self.settings.rclone_config is not None:
            command.extend(("--config", str(self.settings.rclone_config)))
        command.append("--ask-password=false")
        command.extend(arguments)
        return command

    async def _run(self, *arguments: str) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            *self._command(*arguments),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.settings.rclone_timeout_seconds
            )
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise RcloneError("rclone timed out") from exc
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
            with suppress(ProcessLookupError):
                await process.wait()
            raise
        return CommandResult(
            process.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    @staticmethod
    def _require_success(result: CommandResult, operation: str) -> None:
        if result.returncode != 0:
            detail = result.stderr.strip().replace("\r", " ").replace("\n", " ")[:800]
            raise RcloneError(f"{operation} failed: {detail or 'rclone returned an error'}")

    def _remote_path(self, *parts: str) -> str:
        path = "/".join(
            part.strip("/")
            for part in (self.settings.onedrive_base_path, *parts)
            if part.strip("/")
        )
        return f"{self.settings.rclone_remote}:{path}"

    async def check(self) -> CheckResult:
        version_result = await self._run("version")
        self._require_success(version_result, "rclone version check")
        version = (
            version_result.stdout.splitlines()[0].strip() if version_result.stdout else "rclone"
        )

        remotes_result = await self._run("listremotes", "--long")
        self._require_success(remotes_result, "rclone remote listing")
        expected = f"{self.settings.rclone_remote}:"
        backend = ""
        for line in remotes_result.stdout.splitlines():
            fields = line.split()
            if fields and fields[0] == expected:
                backend = fields[1] if len(fields) > 1 else ""
                break
        if not backend:
            raise RcloneError(f"rclone remote {expected} was not found")
        if backend.lower() != "onedrive":
            raise RcloneError(f"rclone remote {expected} is not a OneDrive backend")

        access_result = await self._run(
            "lsd", f"{self.settings.rclone_remote}:", "--max-depth", "1"
        )
        self._require_success(access_result, "OneDrive access check")
        return CheckResult(version=version, backend=backend)

    async def _list_names(self, directory: str) -> set[str]:
        result = await self._run("lsf", directory, "--files-only", "--max-depth", "1")
        self._require_success(result, "destination listing")
        return {line.rstrip("\r") for line in result.stdout.splitlines() if line.rstrip("\r")}

    async def _copy(self, source: Path, destination: str, *, immutable: bool) -> CommandResult:
        arguments = [
            "copyto",
            str(source),
            destination,
            "--log-level",
            "ERROR",
            "--retries",
            "3",
            "--low-level-retries",
            "10",
        ]
        if immutable:
            arguments.append("--immutable")
        return await self._run(*arguments)

    async def upload(self, source: Path, category: str, filename: str) -> UploadResult:
        if not source.is_file():
            raise RcloneError("upload source is not a file")

        directory = self._remote_path(category)
        mkdir_result = await self._run("mkdir", directory)
        self._require_success(mkdir_result, "destination directory creation")

        if self.settings.duplicate_policy == "replace":
            destination = self._remote_path(category, filename)
            result = await self._copy(source, destination, immutable=False)
            self._require_success(result, "file upload")
            return UploadResult(destination=destination, renamed=False)

        names = await self._list_names(directory)
        folded_names = {name.casefold() for name in names}

        if self.settings.duplicate_policy == "fail":
            if filename.casefold() in folded_names:
                raise DestinationExists("a file with the same name already exists")
            destination = self._remote_path(category, filename)
            result = await self._copy(source, destination, immutable=True)
            if result.returncode != 0:
                current = {name.casefold() for name in await self._list_names(directory)}
                if filename.casefold() in current:
                    raise DestinationExists("a file with the same name already exists")
                self._require_success(result, "file upload")
            return UploadResult(destination=destination, renamed=False)

        for index in range(10000):
            candidate = renamed_candidate(filename, index)
            if candidate.casefold() in folded_names:
                continue
            destination = self._remote_path(category, candidate)
            result = await self._copy(source, destination, immutable=True)
            if result.returncode == 0:
                return UploadResult(destination=destination, renamed=index > 0)
            current_names = await self._list_names(directory)
            folded_names = {name.casefold() for name in current_names}
            if candidate.casefold() not in folded_names:
                self._require_success(result, "file upload")
        raise RcloneError("could not allocate a destination filename")
