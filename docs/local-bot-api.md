# Local Bot API Server

[简体中文](local-bot-api.zh-CN.md) · [Back to README](../README.md)

This is an advanced large-file alternative. Enable it only when you already operate Telegram's
official [`tdlib/telegram-bot-api`](https://github.com/tdlib/telegram-bot-api) and need to reuse it.
For a new deployment, prefer [MTProto](mtproto.md).

## Prerequisites

- The API server runs in `--local` mode
- An `api_id` and `api_hash` from [my.telegram.org](https://my.telegram.org/apps)
- Telegram2OneDrive can reach both the API endpoint and the absolute file paths it returns
- The API listener stays on a trusted network and is not exposed directly to the internet

Before migrating a bot from the Telegram cloud Bot API, call `logOut` as described by the official
server documentation. Returning to the cloud API also has a login wait period; follow Telegram's
current instructions.

## Configuration

```dotenv
TELEGRAM_LOCAL_MODE=true
TELEGRAM_BASE_URL=http://127.0.0.1:8081/bot
TELEGRAM_BASE_FILE_URL=http://127.0.0.1:8081/file/bot
MAX_FILE_MIB=2000
```

`TELEGRAM_LOCAL_MODE` and MTProto are mutually exclusive. Run `telegram2onedrive check` before
starting the bot, then verify both a small and a large file.

The included `compose.yaml` does not deploy or connect a Local Bot API Server. A containerized local
mode needs a custom Compose override: both services must share a Docker network, and the API
server's file directory must be mounted into Telegram2OneDrive at the same absolute path. Use the
native installation if those conditions cannot be met.

Local mode reads the file returned by the API server directly and does not delete it. Storage
cleanup and retention remain the responsibility of the API server deployment.
