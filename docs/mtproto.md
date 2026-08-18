# MTProto large-file mode

[简体中文](mtproto.zh-CN.md) · [Back to README](../README.md)

The Telegram cloud Bot API limits file downloads to 20 MiB. With MTProto enabled, Pyrogram
downloads files above that boundary and passes them to the existing classification and rclone
upload path. The project limit is 2048 MiB.

MTProto creates a bot session from the bot token; it does not sign in to a personal Telegram
account.

## Enable it

Get an `api_id` and `api_hash` from `API development tools` at
[my.telegram.org](https://my.telegram.org), then set:

```dotenv
TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=your-api-id
TELEGRAM_API_HASH=your-api-hash
```

The published Docker image already includes the MTProto dependency. Recreate the container after
changing `.env`:

```bash
docker compose up -d --force-recreate
docker compose logs -f
```

For a native install, add the optional dependency first:

```bash
.venv/bin/python -m pip install ".[mtproto]"
systemctl --user restart telegram2onedrive
```

The first start creates the bot session automatically and does not ask for a phone number or login
code. Send a small file, followed by one above 20 MiB. Both paths are working when both transfers
finish with `Uploaded ...`.

## Defaults and persistence

| Setting | Default |
| --- | --- |
| `MAX_FILE_MIB` | `2048` |
| `TELEGRAM_MTPROTO_SESSION_DIR` | `~/.local/state/telegram2onedrive/mtproto` |
| `TELEGRAM_MTPROTO_SESSION_NAME` | `telegram2onedrive` |

Docker stores the session in the `telegram-state` volume; native installations use the directory
above. The session contains the bot's MTProto authorization. Do not commit or share it, and do not
let multiple instances use it concurrently.

## Troubleshooting

| Error or symptom | Resolution |
| --- | --- |
| `MTProto support is not installed` | Reinstall `.[mtproto]` natively, or pull the published Docker image |
| Invalid API ID or hash | The ID must be positive and the hash must contain 32 hexadecimal characters |
| `session belongs to a different bot` | Restore the original token or start with a new session |
| `could not find the Telegram message` | Confirm that the message still exists and the bot can access its chat |
| SQLite lock error | Stop any other instance using the same session |
| Large file is still rejected | Check the three MTProto settings; an explicit `MAX_FILE_MIB` must be above 20 |

MTProto and `TELEGRAM_LOCAL_MODE` are mutually exclusive. TgCrypto only improves encryption
throughput; it is not required for correct operation and is not installed in the default image.
