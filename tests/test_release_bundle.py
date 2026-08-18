from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

from scripts.build_release_bundle import ARCHIVE_ROOT, build_bundle, project_version

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_release_bundle_is_minimal_pinned_and_reproducible(tmp_path: Path) -> None:
    tag = f"v{project_version(REPO_ROOT)}"
    image_ref = "ghcr.io/kurisut7/telegram2onedrive@sha256:" + "a" * 64
    first_archive, first_checksums = build_bundle(REPO_ROOT, tmp_path / "first", tag, image_ref)
    second_archive, _ = build_bundle(REPO_ROOT, tmp_path / "second", tag, image_ref)

    assert first_archive.read_bytes() == second_archive.read_bytes()
    digest = hashlib.sha256(first_archive.read_bytes()).hexdigest()
    assert first_checksums.read_text(encoding="utf-8") == (f"{digest}  telegram2onedrive.tar.gz\n")

    with tarfile.open(first_archive, "r:gz") as archive:
        names = set(archive.getnames())
        compose = archive.extractfile(f"{ARCHIVE_ROOT}/compose.yaml")
        assert compose is not None
        compose_text = compose.read().decode("utf-8")

    assert image_ref in compose_text
    assert f"{ARCHIVE_ROOT}/.env.example" in names
    assert f"{ARCHIVE_ROOT}/README.zh-CN.md" in names
    assert not any(name.startswith(f"{ARCHIVE_ROOT}/src/") for name in names)
    assert not any(name.startswith(f"{ARCHIVE_ROOT}/tests/") for name in names)
    assert f"{ARCHIVE_ROOT}/Dockerfile" not in names
    assert f"{ARCHIVE_ROOT}/compose.build.yaml" not in names
