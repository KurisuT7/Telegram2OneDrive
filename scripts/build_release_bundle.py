#!/usr/bin/env python3
"""Build the minimal runtime bundle attached to GitHub releases."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import re
import tarfile
import tomllib
from pathlib import Path

ARCHIVE_NAME = "telegram2onedrive.tar.gz"
ARCHIVE_ROOT = "telegram2onedrive"
DEFAULT_IMAGE = "ghcr.io/kurisut7/telegram2onedrive:latest"
RUNTIME_FILES = (
    ".env.example",
    "compose.yaml",
    "README.md",
    "README.zh-CN.md",
    "CHANGELOG.md",
    "LICENSE",
    "SECURITY.md",
    "docs/local-bot-api.md",
    "docs/local-bot-api.zh-CN.md",
    "docs/mtproto.md",
    "docs/mtproto.zh-CN.md",
    "docs/native-linux.md",
    "docs/native-linux.zh-CN.md",
)
TAG_PATTERN = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
IMAGE_TAG_PATTERN = re.compile(r"ghcr\.io/kurisut7/telegram2onedrive:v\d+\.\d+\.\d+\Z")
IMAGE_DIGEST_PATTERN = re.compile(r"ghcr\.io/kurisut7/telegram2onedrive@sha256:[0-9a-f]{64}\Z")


def project_version(repo_root: Path) -> str:
    with (repo_root / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _validate_release(repo_root: Path, tag: str) -> str:
    match = TAG_PATTERN.fullmatch(tag)
    if match is None:
        raise ValueError(f"release tag must be vMAJOR.MINOR.PATCH, got {tag!r}")

    version = tag.removeprefix("v")
    expected = project_version(repo_root)
    if version != expected:
        raise ValueError(f"tag {tag} does not match project version {expected}")

    package_version = repo_root / "src" / "telegram2onedrive" / "__init__.py"
    if f'__version__ = "{version}"' not in package_version.read_text(encoding="utf-8"):
        raise ValueError("runtime version does not match project metadata")

    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    release_heading = rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$"
    if re.search(release_heading, changelog, re.M) is None:
        raise ValueError(f"CHANGELOG.md has no dated {version} release section")

    missing = [relative for relative in RUNTIME_FILES if not (repo_root / relative).is_file()]
    if missing:
        raise ValueError(f"runtime bundle inputs are missing: {', '.join(missing)}")
    return version


def _directory_info(name: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    info.mtime = 0
    return info


def _file_info(name: str, data: bytes) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    return info


def build_bundle(
    repo_root: Path,
    output_dir: Path,
    tag: str,
    image_ref: str | None = None,
) -> tuple[Path, Path]:
    """Create a reproducible runtime archive and its checksum file."""
    _validate_release(repo_root, tag)
    selected_image = image_ref or f"ghcr.io/kurisut7/telegram2onedrive:{tag}"
    if (
        IMAGE_TAG_PATTERN.fullmatch(selected_image) is None
        and IMAGE_DIGEST_PATTERN.fullmatch(selected_image) is None
    ):
        raise ValueError("image reference must use the Telegram2OneDrive GHCR package")

    compose_path = repo_root / "compose.yaml"
    compose = compose_path.read_text(encoding="utf-8")
    if compose.count(DEFAULT_IMAGE) != 1:
        raise ValueError("compose.yaml must contain exactly one default release image")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / ARCHIVE_NAME
    archive_path.unlink(missing_ok=True)

    directories = {ARCHIVE_ROOT}
    for relative in RUNTIME_FILES:
        parent = Path(relative).parent
        while parent != Path("."):
            directories.add(f"{ARCHIVE_ROOT}/{parent.as_posix()}")
            parent = parent.parent

    with (
        archive_path.open("wb") as raw_handle,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as gzip_handle,
        tarfile.open(fileobj=gzip_handle, mode="w", format=tarfile.PAX_FORMAT) as archive,
    ):
        for directory in sorted(directories):
            archive.addfile(_directory_info(directory))
        for relative in RUNTIME_FILES:
            data = (repo_root / relative).read_bytes()
            if relative == "compose.yaml":
                text = data.decode("utf-8").replace(DEFAULT_IMAGE, selected_image)
                data = text.encode("utf-8")
            archive.addfile(
                _file_info(f"{ARCHIVE_ROOT}/{relative}", data),
                fileobj=io.BytesIO(data),
            )

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = output_dir / "SHA256SUMS"
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8", newline="\n")
    return archive_path, checksum_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="annotated release tag, for example v1.2.3")
    parser.add_argument("--image-ref", help="published image tag or manifest digest")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    archive_path, checksum_path = build_bundle(
        repo_root,
        args.output_dir.resolve(),
        args.tag,
        args.image_ref,
    )
    print(archive_path)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
