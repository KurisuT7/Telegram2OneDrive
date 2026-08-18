# Telegram2OneDrive

[简体中文](README.zh-CN.md)

Automatically classify files sent to a Telegram bot and upload them to OneDrive. The bot accepts
private-chat files from allowlisted users by default and is designed for a long-running Linux
server.

```text
Telegram2OneDrive/
├── Images/
├── Videos/
├── Audio/
├── Documents/
├── Archives/
└── Other/
```

| Download path | Per-file limit | Best for |
| --- | ---: | --- |
| Telegram cloud Bot API | 20 MiB | Default mode with no extra Telegram credentials |
| MTProto | 2048 MiB | Large files; recommended |
| Local Bot API Server | Set by the local service | Advanced deployments already operating the official local API |

MTProto only takes over downloads above 20 MiB. Bot commands, small downloads, classification,
and OneDrive uploads keep using the normal path.

## Quick start with Docker Compose

Use a Linux server that can reach Telegram and Microsoft OneDrive and has the
[Docker Engine and Compose plugin](https://docs.docker.com/engine/install/) installed. Before
starting, prepare:

- A bot token created with [@BotFather](https://t.me/BotFather)
- For files above 20 MiB, an `api_id` and `api_hash` from `API development tools` at
  [my.telegram.org](https://my.telegram.org)

### 1. Download and configure

```bash
curl -fLO https://github.com/KurisuT7/Telegram2OneDrive/releases/latest/download/telegram2onedrive.tar.gz
curl -fLO https://github.com/KurisuT7/Telegram2OneDrive/releases/latest/download/SHA256SUMS
sha256sum --check SHA256SUMS
mkdir -p telegram2onedrive
tar -xzf telegram2onedrive.tar.gz -C telegram2onedrive --strip-components=1
cd telegram2onedrive
cp .env.example .env
chmod 600 .env
```

The checksum command must print `telegram2onedrive.tar.gz: OK`. The runtime bundle contains the
Compose file, configuration example, and documentation, and pins the container image released with
it. The server does not build the image locally.

Edit `.env`. For large-file support, set:

```dotenv
TELEGRAM_BOT_TOKEN=token-returned-by-BotFather
TELEGRAM_ALLOWED_USER_IDS=

TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=your-api-id
TELEGRAM_API_HASH=your-api-hash
```

For files up to 20 MiB, keep `TELEGRAM_MTPROTO_ENABLED=false` and leave the API ID and hash empty.
The remaining settings can keep their defaults.

### 2. Connect OneDrive

Pull the published image, then run rclone's configuration wizard inside the container:

```bash
docker compose pull
docker compose run --rm --entrypoint rclone bot config
```

Create a Microsoft OneDrive remote named `onedrive` and complete browser authorization. On a
headless server, follow rclone's [OneDrive](https://rclone.org/onedrive/) and
[Remote Setup](https://rclone.org/remote_setup/) documentation. Then verify it:

```bash
docker compose run --rm --entrypoint rclone bot lsd onedrive:
docker compose run --rm bot check
```

The first command should list the OneDrive root, and the second should print
`OneDrive check passed`. The empty-allowlist warning is expected during initial setup.

### 3. Start and set the allowlist

```bash
docker compose up -d
docker compose logs -f
```

Send `/whoami` to the bot in a private chat and place the returned `User ID` in `.env`:

```dotenv
TELEGRAM_ALLOWED_USER_IDS=123456789
```

Separate multiple IDs with commas. Recreate the container to load the new configuration:

```bash
docker compose up -d --force-recreate
```

Send a small file to the bot. The deployment is complete when the bot reports `Uploaded ...` and
the file appears under `Telegram2OneDrive` in OneDrive. With MTProto enabled, also send a file above
20 MiB to verify the large-file path.

## Routine operations

```bash
# Status and logs
docker compose ps
docker compose logs -f

# Stop and remove the container
docker compose down
```

To upgrade, download the newest runtime bundle into the deployment directory. It replaces the
Compose file and documentation but does not contain `.env`; the Docker volumes are also preserved.

```bash
curl -fLO https://github.com/KurisuT7/Telegram2OneDrive/releases/latest/download/telegram2onedrive.tar.gz
curl -fLO https://github.com/KurisuT7/Telegram2OneDrive/releases/latest/download/SHA256SUMS
sha256sum --check SHA256SUMS
tar -xzf telegram2onedrive.tar.gz --strip-components=1
docker compose pull
docker compose up -d
rm telegram2onedrive.tar.gz SHA256SUMS
```

To roll back, replace `v0.2.0` below with the required release. Each release bundle pins the exact
container-image digest built for that release.

```bash
RELEASE=v0.2.0
curl -fLO "https://github.com/KurisuT7/Telegram2OneDrive/releases/download/${RELEASE}/telegram2onedrive.tar.gz"
curl -fLO "https://github.com/KurisuT7/Telegram2OneDrive/releases/download/${RELEASE}/SHA256SUMS"
sha256sum --check SHA256SUMS
tar -xzf telegram2onedrive.tar.gz --strip-components=1
docker compose pull
docker compose up -d
rm telegram2onedrive.tar.gz SHA256SUMS
```

rclone configuration and the MTProto session live in the `rclone-config` and `telegram-state`
Docker volumes. Recreating the container preserves both. Do not run `docker compose down -v` unless
you intend to delete the OneDrive authorization and MTProto session as well.

For a non-container deployment, use the [native Linux guide](docs/native-linux.md). It is retained
for servers with an existing Python/rclone environment or deployments that need direct systemd
process management.

## Common settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | None | Required BotFather token |
| `TELEGRAM_ALLOWED_USER_IDS` | Empty | Allowed numeric user IDs, separated by commas |
| `TELEGRAM_ALLOW_GROUP_CHATS` | `false` | Allow group transfers from allowlisted users |
| `TELEGRAM_MTPROTO_ENABLED` | `false` | Use MTProto for files above 20 MiB |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | Empty | Application credentials required by MTProto |
| `MAX_FILE_MIB` | Automatic | 20 normally; 2048 with MTProto |
| `RCLONE_REMOTE` | `onedrive` | rclone remote name |
| `ONEDRIVE_BASE_PATH` | `Telegram2OneDrive` | Destination directory in OneDrive |
| `DUPLICATE_POLICY` | `rename` | `rename`, `replace`, or `fail` for duplicate names |

See [.env.example](.env.example) for every setting and its comments. After changing `.env`, recreate
the container; `docker compose restart` alone does not load changed environment variables.

## Behavior and limitations

- The bot supports `/start`, `/whoami`, and `/status`; `/status` checks OneDrive access.
- Files transfer serially, and upload status refreshes every 30 seconds.
- Temporary downloads are removed after the upload attempt; rclone authorization and MTProto
  sessions persist.
- Duplicate names get ` (n)` by default instead of overwriting an existing file.
- Private-chat files from allowlisted users are accepted by default; group transfers are disabled.
- Never commit a completed `.env`, rclone configuration, or MTProto session, and do not let multiple
  instances share one bot token or session.
- The project uses polling and does not support webhooks. OneDrive's own path and file-size limits
  still apply.

## More documentation

- [MTProto large-file mode](docs/mtproto.md)
- [Local Bot API Server](docs/local-bot-api.md)
- [Native Linux installation](docs/native-linux.md)
- [Contributing](https://github.com/KurisuT7/Telegram2OneDrive/blob/main/CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

Report security issues through [GitHub private vulnerability reporting](SECURITY.md).
Telegram2OneDrive uses the [MIT License](LICENSE) and is not affiliated with or endorsed by
Telegram, Microsoft, or rclone.
