# Changelog

User-visible changes are recorded here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-18

### Added

- A prebuilt Linux container image for AMD64 and ARM64, plus a checksum-protected runtime bundle
  containing only the Compose deployment, configuration example, license, and user documentation.
- A tag-triggered release workflow that validates the release version, publishes the image, pins the
  runtime bundle to its manifest digest, and prepares a draft GitHub release for review.
- A Docker Compose deployment with a non-root application image, bundled rclone and MTProto
  dependencies, persistent credential/session volumes, and container build validation in CI.
- An optional Pyrogram MTProto fallback for files above the cloud Bot API's 20 MiB boundary, up to
  the configured 2048 MiB project limit. Bot API polling, commands and small downloads remain
  unchanged.
- Persistent MTProto bot sessions outside the repository, with bot-identity verification,
  restricted POSIX permissions and explicit protection against concurrent session use.

### Changed

- Docker Compose now pulls the published image for end users. Local image builds remain available
  through a separate contributor override.
- Reworked the English and Chinese documentation around one Docker Compose quick start, with native
  Linux deployment and advanced download backends kept in focused guides.
- The command now loads `.env` from the current directory automatically. Enabling MTProto also
  defaults the file limit to 2048 MiB and the session directory to the user's state directory.

### Security

- MTProto application credentials and sessions are treated as runtime credentials and excluded
  from source, logs, and examples.

## [0.1.0] - 2026-08-16

### Added

- An allowlisted Telegram bot that classifies files and transfers them to OneDrive through rclone.
- Rename, replace, and fail policies for destination name conflicts.
- Bounded temporary downloads with cleanup after success or failure.
- Optional Local Bot API Server support for files above the cloud Bot API's 20 MiB limit.
- English and Simplified Chinese setup, security, privacy, and operations documentation.
- Synthetic tests, static analysis, package validation, dependency auditing, and GitHub Actions CI.

### Security

- OneDrive OAuth tokens remain in rclone's restricted, writable configuration instead of being
  copied into application configuration or token files.
- Telegram user IDs form an explicit allowlist; group transfers are disabled by default.
- Bot tokens, rclone configuration, sessions, downloaded files, and runtime data are excluded from
  the repository.

[Unreleased]: https://github.com/KurisuT7/Telegram2OneDrive/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/KurisuT7/Telegram2OneDrive/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/KurisuT7/Telegram2OneDrive/releases/tag/v0.1.0
