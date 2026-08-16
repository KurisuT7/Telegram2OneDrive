# Changelog

User-visible changes are recorded here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- An optional Pyrogram MTProto fallback for files above the cloud Bot API's 20 MiB boundary, up to
  the configured 2048 MiB project limit. Bot API polling, commands and small downloads remain
  unchanged.
- Persistent MTProto bot sessions outside the repository, with bot-identity verification,
  restricted POSIX permissions and explicit protection against concurrent session use.

### Security

- Shared or publicly posted Telegram application credentials are explicitly unsupported; MTProto
  sessions are treated as bot credentials and excluded from source, logs, and examples.

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

[Unreleased]: https://github.com/KurisuT7/Telegram2OneDrive/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/KurisuT7/Telegram2OneDrive/releases/tag/v0.1.0
