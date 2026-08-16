# MTProto large-file fallback

[简体中文](mtproto.zh-CN.md)

Telegram2OneDrive normally receives updates and downloads files through the HTTP Bot API. When the
optional MTProto fallback is enabled, the same bot also opens a Pyrogram session:

- updates, commands, authorization and files up to 20 MiB remain on the Bot API;
- files above 20 MiB are fetched by chat ID and message ID through MTProto;
- both paths use the same validation, temporary storage, classification and rclone upload code.

This is a large-file download fallback, not a personal-account client and not a second update
consumer. The cloud Bot API's 20 MiB download boundary is documented in Telegram's
[Local Bot API Server guide](https://core.telegram.org/bots/features#local-bot-api).

## Requirements

- Python 3.11–3.13 for the MTProto fallback (the core Bot API path also supports Python 3.14)
- the `mtproto` package extra
- a BotFather bot token
- an application ID and hash created by the operator at
  [my.telegram.org/apps](https://my.telegram.org/apps)
- an absolute session directory outside the source checkout

Do not use application credentials copied from a public channel, sample file or another operator.
Telegram documents application IDs as belonging to the application that obtained them and can
reject published credentials.

Install the normal implementation:

```bash
python -m pip install -e ".[mtproto]"
```

The production design this adapter follows also uses TgCrypto for faster cryptography. TgCrypto is
a native extension and is therefore not forced by the portable package extra. On a compatible
Linux host, install and verify it separately in the same environment:

```bash
python -m pip install TgCrypto
```

TgCrypto improves cryptographic throughput but is not required for correctness. If no compatible
wheel or compiler is available, leave it uninstalled rather than weakening the host toolchain.

## Configuration

Start from `.env.example` and set:

```dotenv
TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
TELEGRAM_MTPROTO_SESSION_DIR=/var/lib/telegram2onedrive/mtproto
TELEGRAM_MTPROTO_SESSION_NAME=telegram2onedrive
MAX_FILE_MIB=2048
```

The examples are placeholders. Do not reuse them. `TELEGRAM_MTPROTO_SESSION_NAME` accepts letters,
digits, underscores and hyphens only.

MTProto fallback and `TELEGRAM_LOCAL_MODE` are mutually exclusive. A local Bot API Server already
provides its own larger-file path; choose one approach per bot instance.

## First start

Validate local configuration and OneDrive access first:

```bash
telegram2onedrive --env-file /etc/telegram2onedrive.env check
```

Then start the bot normally:

```bash
telegram2onedrive --env-file /etc/telegram2onedrive.env run
```

The Bot API polling application starts Pyrogram in its startup callback and closes it during
shutdown. Pyrogram creates `<session-name>.session` in the configured directory. On POSIX systems,
Telegram2OneDrive restricts the directory to mode `0700` and matching session files to `0600`.

Do not start two processes with the same session. Do not run an interactive smoke test against the
live service's session database. Stop the service first or use a separate disposable bot and session.

## Security and operations

The session database contains an MTProto authorization key. Anyone who obtains it may act as the
bot. Keep the directory out of Git, backups intended for publication, container images, logs and
support bundles. On Windows, apply an ACL granting access only to the service account because POSIX
mode bits are not enforced there.

The client verifies that an existing session belongs to the bot ID encoded in
`TELEGRAM_BOT_TOKEN`. A mismatched or user-account session is rejected. Preserve an unexpected
session as evidence, configure a new empty session directory and investigate before deleting it.

Files are still bounded by `MAX_FILE_MIB`, currently limited by this project to 2048 MiB. Every
cloud Bot API or MTProto download uses a per-transfer temporary directory that is removed after the
upload attempt. The Pyrogram session directory is persistent and must not be placed under the
temporary download directory.

## Troubleshooting

- `MTProto support is not installed`: install `.[mtproto]` in the same environment that runs the bot.
- `session belongs to a different bot`: do not reuse that session; verify the token and session path.
- `could not find the Telegram message`: confirm the original message still exists and the bot can
  access its chat.
- repeated SQLite locking errors: verify that only one process uses the configured session name.
- Bot API errors on files above 20 MiB: confirm MTProto is enabled, `MAX_FILE_MIB` is above 20 and
  startup completed without an MTProto error.
