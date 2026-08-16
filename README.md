# Telegram2OneDrive

[简体中文](README.zh-CN.md)

Telegram2OneDrive accepts files from explicitly allowed Telegram users, classifies them by media
type, and transfers them to a OneDrive remote managed by rclone.

The default Telegram cloud Bot API path supports files up to 20 MiB. An optional Local Bot API
Server or a Pyrogram MTProto large-file fallback can handle larger downloads without changing the
Bot API update and OneDrive upload paths.

## Requirements

- Python 3.11 or newer
- A Telegram bot created with [@BotFather](https://t.me/BotFather)
- [rclone](https://rclone.org/downloads/) with a OneDrive remote
- A host that can reach Telegram, Microsoft login, Microsoft Graph, and OneDrive

The MTProto fallback additionally requires your own Telegram application from
[my.telegram.org/apps](https://my.telegram.org/apps). It uses the BotFather bot identity only and
does not require a personal-account session.

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

## Optional large-file paths

The default cloud Bot API needs no additional Telegram configuration. For larger files, choose one
documented alternative:

- [Local Bot API Server](docs/local-bot-api.md): retains the HTTP Bot API and requires a shared
  filesystem with the local server.
- [MTProto large-file fallback](docs/mtproto.md): keeps Bot API polling and small downloads, but
  uses Pyrogram for files above 20 MiB. It requires your own `api_id` and `api_hash` and stores a
  restricted bot session outside the repository.

Local Bot API mode and MTProto fallback are mutually exclusive. Never let multiple processes share
the same Bot token or MTProto session database.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | none | BotFather token; required |
| `TELEGRAM_ALLOWED_USER_IDS` | empty | Comma-separated positive user IDs |
| `TELEGRAM_ALLOW_GROUP_CHATS` | `false` | Permit allowed users to transfer from groups |
| `MAX_FILE_MIB` | `20` | Reject larger files before download |
| `TELEGRAM_LOCAL_MODE` | `false` | Use a Local Bot API Server |
| `TELEGRAM_BASE_URL` | empty | Local Bot API method URL ending in `/bot` |
| `TELEGRAM_BASE_FILE_URL` | empty | Local Bot API file URL ending in `/file/bot` |
| `TELEGRAM_MTPROTO_ENABLED` | `false` | Use MTProto only for files above 20 MiB |
| `TELEGRAM_API_ID` | empty | Own numeric Telegram application ID for MTProto |
| `TELEGRAM_API_HASH` | empty | Own 32-character application hash for MTProto |
| `TELEGRAM_MTPROTO_SESSION_DIR` | empty | Required absolute MTProto session directory outside the repository |
| `TELEGRAM_MTPROTO_SESSION_NAME` | `telegram2onedrive` | Safe Pyrogram session basename |
| `RCLONE_REMOTE` | `onedrive` | Name of the configured OneDrive remote |
| `RCLONE_CONFIG` | rclone discovery | Optional absolute config path |
| `ONEDRIVE_BASE_PATH` | `Telegram2OneDrive` | Destination below the OneDrive root |
| `DUPLICATE_POLICY` | `rename` | `rename`, `replace`, or `fail` |
| `RCLONE_TIMEOUT_SECONDS` | `3600` | Per-command timeout, 60–86400 seconds |
| `TRANSFER_TMP_DIR` | system temp | Optional cloud Bot API and MTProto download directory |

Transport-specific setup is documented in [docs/local-bot-api.md](docs/local-bot-api.md) and
[docs/mtproto.md](docs/mtproto.md).

## Operation and failure behavior

- Transfers are serialized so two updates cannot choose the same renamed destination concurrently.
- Cloud Bot API and MTProto downloads use a per-transfer temporary directory that is removed after
  success or failure. The MTProto session database remains in its separately configured directory.
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

Keep the bot token, MTProto application credentials and session, rclone config, downloaded files,
logs, and process environment private. Prefer a dedicated service account, a private bot chat, and
an explicit user allowlist. Group transfers are off by default because other group members can see
file names and status messages. Never configure MTProto with an API ID/hash copied from a public
channel or another application.

Report vulnerabilities through [GitHub private vulnerability reporting](SECURITY.md).

## Limitations

- The cloud Bot API cannot download files above 20 MiB.
- The Local Bot API adapter requires a shared filesystem and has not been exercised end to end in
  GitHub Actions; its URL, local-path, and size behavior are covered by configuration and unit tests.
- The MTProto fallback is limited to 2048 MiB by this project and is not exercised against Telegram
  in GitHub Actions; bot-identity verification, lifecycle, routing, cleanup and failures have unit
  tests. A production-derived Pyrogram design informed this implementation, but that is not a
  compatibility guarantee for every Telegram environment.
- The Bot API uses polling. Webhooks and multiple instances sharing a bot or session are unsupported.
- Destination conflict checks cannot make external OneDrive writers transactional. `--immutable`
  prevents the application from silently overwriting a race for `rename` and `fail` policies.
- OneDrive path and file-size limits still apply. rclone maps characters unsupported by OneDrive.

Telegram, OneDrive, Microsoft, and rclone are trademarks of their respective owners. This project is
independent and is not endorsed by Telegram, Microsoft, or the rclone project.

## Development and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for local checks and fixture rules. Changes are recorded in
[CHANGELOG.md](CHANGELOG.md). Telegram2OneDrive is licensed under the [MIT License](LICENSE).
