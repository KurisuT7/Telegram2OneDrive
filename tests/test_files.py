import pytest

from telegram2onedrive.files import classify_file, renamed_candidate, sanitize_filename


@pytest.mark.parametrize(
    ("mime", "name", "expected"),
    [
        ("image/jpeg", "unknown", "Images"),
        (None, "clip.MP4", "Videos"),
        ("audio/ogg", "voice", "Audio"),
        ("text/plain", "notes", "Documents"),
        (None, "backup.tar.gz", "Archives"),
        (None, "no-extension", "Other"),
    ],
)
def test_classification(mime: str | None, name: str, expected: str) -> None:
    assert classify_file(mime, name) == expected


def test_sanitizes_path_and_onedrive_characters() -> None:
    assert sanitize_filename("../../bad:name?.zip") == "bad_name_.zip"
    assert sanitize_filename(" . ") == "telegram-file"


def test_bounds_long_name_and_keeps_compound_extension() -> None:
    result = sanitize_filename("a" * 300 + ".tar.gz")
    assert len(result) <= 180
    assert result.endswith(".tar.gz")


def test_renamed_candidate_keeps_compound_extension() -> None:
    assert renamed_candidate("archive.tar.gz", 2) == "archive (2).tar.gz"
    assert renamed_candidate("README", 1) == "README (1)"
    assert renamed_candidate("file.txt", 0) == "file.txt"
