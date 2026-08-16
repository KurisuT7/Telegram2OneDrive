# Telegram2OneDrive

[简体中文](README.zh-CN.md)

Telegram2OneDrive accepts files from explicitly allowed Telegram users, classifies them by media
type, and transfers them to a OneDrive remote managed by rclone.

The default Telegram cloud Bot API path supports files up to 20 MiB. An optional Local Bot API
Server adapter supports larger downloads when the bot and API server share the same filesystem.

## Requirements

- Python 3.11 or newer
- A Telegram bot created with [@BotFather](https://t.me/BotFather)
- [rclone](https://rclone.org/downloads/) with a OneDrive remote
- A host that can reach Telegram, Microsoft login, Microsoft Graph, and OneDrive

The application does not accept OneDrive tokens directly. rclone owns the OAuth flow, token refresh,
large-file upload behavior, and its writable credential file.

## First transfer

### 1. Create the Telegram bot

Open [@BotFather](https://t.me/BotFather), run `/newbot`, choose a display name and username, and
store the returned token outside the repository. Anyone with this token can control the bot.

### 2. Configure OneDrive in rclone

Install rclone, then run:

```bash
rclone config
```

Create a remote named `onedrive`, choose the Microsoft OneDrive backend, and complete browser
authorization. Leave the client ID and client secret empty unless you operate your own Microsoft
application. Verify the remote without printing its configuration:

```bash
rclone lsd onedrive:
```

The rclone config contains refresh credentials. Restrict it to the service account and keep it
writable so rclone can rotate tokens.

### 3. Install the application

Run these commands from a clone of this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
cp .env.example .env
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` and copy with
`Copy-Item .env.example .env`.

Set `TELEGRAM_BOT_TOKEN` in `.env`. If rclone does not use its default config location, set
`RCLONE_CONFIG` to its absolute path. Leave `TELEGRAM_ALLOWED_USER_IDS` empty for this first start.

### 4. Obtain your Telegram user ID

Validate the configuration and OneDrive access, then start the bot:

```bash
telegram2onedrive --env-file .env check
telegram2onedrive --env-file .env run
```

Open a private chat with the bot and send `/whoami`. Stop the process, place the returned numeric
user ID in `TELEGRAM_ALLOWED_USER_IDS`, and start it again. Multiple IDs use commas.

### 5. Send a file

Send a file in the bot's private chat. A successful transfer ends with `Uploaded ...` and places the
file under:

```text
Telegram2OneDrive/
├── Images/
├── Videos/
├── Audio/
├── Documents/
├── Archives/
└── Other/
```

Use `/status` to verify Telegram-side access to the configured OneDrive remote.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | none | BotFather token; required |
| `TELEGRAM_ALLOWED_USER_IDS` | empty | Comma-separated positive user IDs |
| `TELEGRAM_ALLOW_GROUP_CHATS` | `false` | Permit allowed users to transfer from groups |
| `MAX_FILE_MIB` | `20` | Reject larger files before download |
| `RCLONE_REMOTE` | `onedrive` | Name of the configured OneDrive remote |
| `RCLONE_CONFIG` | rclone discovery | Optional absolute config path |
| `ONEDRIVE_BASE_PATH` | `Telegram2OneDrive` | Destination below the OneDrive root |
| `DUPLICATE_POLICY` | `rename` | `rename`, `replace`, or `fail` |
| `RCLONE_TIMEOUT_SECONDS` | `3600` | Per-command timeout, 60–86400 seconds |
| `TRANSFER_TMP_DIR` | system temp | Optional cloud API download directory |

Local Bot API variables are documented in [docs/local-bot-api.md](docs/local-bot-api.md).

## Operation and failure behavior

- Transfers are serialized so two updates cannot choose the same renamed destination concurrently.
- Cloud Bot API downloads use a per-transfer temporary directory that is removed after success or
  failure.
- Local Bot API files belong to that server and are not deleted by Telegram2OneDrive.
- The upload status is refreshed every 30 seconds. rclone may pause before a transfer while it
  refreshes Microsoft authorization.
- `rename` adds ` (n)` before the extension, `replace` permits overwrite, and `fail` rejects an
  existing case-insensitive OneDrive name.
- rclone receives credentials through its config file. The application never runs `rclone config
  dump` and does not copy OAuth tokens to logs or application state.

## Security and privacy

Telegram receives the original message and file. The host temporarily receives cloud Bot API files,
and rclone sends the file and destination name to Microsoft OneDrive. The application includes no
telemetry.

Keep the bot token, rclone config, downloaded files, logs, and process environment private. Prefer a
dedicated service account, a private bot chat, and an explicit user allowlist. Group transfers are
off by default because other group members can see file names and status messages.

Report vulnerabilities through [GitHub private vulnerability reporting](SECURITY.md).

## Limitations

- The cloud Bot API cannot download files above 20 MiB.
- The Local Bot API adapter requires a shared filesystem and has not been exercised end to end in
  GitHub Actions; its URL, local-path, and size behavior are covered by configuration and unit tests.
- Only polling is implemented. Webhooks and multiple bot instances are not supported.
- Destination conflict checks cannot make external OneDrive writers transactional. `--immutable`
  prevents the application from silently overwriting a race for `rename` and `fail` policies.
- OneDrive path and file-size limits still apply. rclone maps characters unsupported by OneDrive.

Telegram, OneDrive, Microsoft, and rclone are trademarks of their respective owners. This project is
independent and is not endorsed by Telegram, Microsoft, or the rclone project.

## Development and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for local checks and fixture rules. Changes are recorded in
[CHANGELOG.md](CHANGELOG.md). Telegram2OneDrive is licensed under the [MIT License](LICENSE).
