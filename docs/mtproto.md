# MTProto large-file mode

[简体中文](mtproto.zh-CN.md) · [Back to README](../README.md)

The Telegram cloud Bot API only lets a bot download files up to 20 MiB. With MTProto enabled:

- commands, updates, and files up to 20 MiB still use the Bot API;
- files larger than 20 MiB automatically use MTProto for the download;
- downloaded files follow the same classification and rclone upload path to OneDrive.

The program opens a bot session using the same bot token. It does not sign in to a personal
account. This project limits each file to 2048 MiB.

## 1. Get an API ID and hash

1. Make sure you are signed in to an official Telegram app on your phone or computer.
2. Open [my.telegram.org](https://my.telegram.org) in a browser.
3. Enter the phone number for your Telegram account.
4. Telegram sends the code to the Telegram app. Enter that code on the website.
5. Select `API development tools`.
6. Complete the form: use `Telegram2OneDrive` for `App title`, `telegram2onedrive` for `Short
   name`, leave `URL` empty if the form permits it (otherwise use this repository URL), choose
   `Desktop` or `Other` for `Platform`, and use `Telegram file transfer to OneDrive` for
   `Description`.
7. Submit the form and record the displayed `api_id` and `api_hash`.

If the page says that an application already exists, use the `api_id` and `api_hash` displayed
there.

## 2. Install MTProto support

Enter the Telegram2OneDrive repository directory. If no virtual environment exists yet, run the
complete sequence:

```bash
cd ~/Telegram2OneDrive
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install ".[mtproto]"
```

For an existing installation, only the final install command is required. MTProto currently
supports Python 3.11–3.13.

## 3. Edit `.env`

If `.env` does not exist yet, create it from the example:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Make sure the bot token is set, then find these three entries. Replace only the text after each
equals sign; do not add quotation marks or duplicate entries:

```dotenv
TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=paste-api-id-here
TELEGRAM_API_HASH=paste-api-hash-here
```

You do not need to set `MAX_FILE_MIB` or a session path. Enabling MTProto automatically uses these
defaults:

```dotenv
MAX_FILE_MIB=2048
TELEGRAM_MTPROTO_SESSION_DIR=~/.local/state/telegram2onedrive/mtproto
TELEGRAM_MTPROTO_SESSION_NAME=telegram2onedrive
```

These lines show the defaults; do not copy them into `.env`. In nano, press `Ctrl+O`, press Enter to
confirm, and then press `Ctrl+X` to exit.

## 4. Check and start

The program automatically loads `.env` from the repository directory:

```bash
.venv/bin/telegram2onedrive check
.venv/bin/telegram2onedrive run
```

On its first start, the program creates the session in the state directory automatically. It does
not ask for a phone number or an additional interactive sign-in.

Send a small file first to confirm the normal upload path, then send a file larger than 20 MiB.
`Uploaded ...` confirms that the MTProto download and OneDrive upload both completed.

If you use the systemd service, restart it after editing `.env`:

```bash
systemctl --user restart telegram2onedrive
journalctl --user -u telegram2onedrive -f
```

## Troubleshooting

### `MTProto support is not installed`

Pyrogram is missing from the virtual environment that runs the bot. Enter the repository directory
and run:

```bash
.venv/bin/python -m pip install ".[mtproto]"
```

### Invalid `TELEGRAM_API_ID` or `TELEGRAM_API_HASH`

`TELEGRAM_API_ID` must be a positive integer, and `TELEGRAM_API_HASH` must contain 32 hexadecimal
characters. Check for copied spaces, quotation marks, or labels.

### `session belongs to a different bot`

The existing session does not match the current bot token. Stop the service, preserve the logs and
session while you verify the configuration, and then use a new empty session directory for the
current bot.

### `could not find the Telegram message`

Confirm that the original message still exists and the bot can still access its private chat or
group.

### Repeated SQLite locking errors

Two processes are usually using the same session. Stop the manually started copy and make sure only
one systemd service instance remains.

### A large file still uses the Bot API or is rejected

Confirm `TELEGRAM_MTPROTO_ENABLED=true`, then run:

```bash
.venv/bin/telegram2onedrive check
```

If you set `MAX_FILE_MIB` manually, it must be above 20 and no greater than 2048. Leaving it empty is
the simplest option.

## Advanced settings

Only override these values when the default directory is unsuitable:

```dotenv
TELEGRAM_MTPROTO_SESSION_DIR=/absolute/path/telegram2onedrive/mtproto
TELEGRAM_MTPROTO_SESSION_NAME=telegram2onedrive
MAX_FILE_MIB=2048
```

The session directory must be absolute. The session name accepts letters, digits, underscores, and
hyphens only. Do not let two processes share one session, and do not place the session under the
source checkout or temporary download directory.

MTProto and `TELEGRAM_LOCAL_MODE` cannot be enabled together. A Local Bot API Server supplies its
own large-file path, so one bot instance must use only one of these backends.

For higher MTProto cryptographic throughput, you may try the optional TgCrypto package in the same
virtual environment:

```bash
.venv/bin/python -m pip install TgCrypto
```

TgCrypto is a native extension and is not required for correct behavior. Skip it if a compatible
wheel or compiler is unavailable.

## Sessions and temporary files

The session database contains MTProto authorization for the bot. On POSIX systems, the program
restricts the session directory to mode `0700` and session files to `0600`. Do not place a completed
`.env`, session, rclone config, or temporary download in Git, container images, or public release
artifacts.

Bot API and MTProto downloads use a per-transfer temporary directory that is removed after the
upload attempt. The session is persistent runtime data and is not removed with temporary files.
