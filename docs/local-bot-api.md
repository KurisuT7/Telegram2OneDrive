# Local Bot API Server

The official cloud Bot API limits `getFile` downloads to 20 MiB. Telegram's official Local Bot API
Server can download without a size limit in `--local` mode. Telegram2OneDrive can consume the local
file path instead of creating another copy.

This integration is optional. The default cloud path is smaller and has fewer operational parts.

## Requirements

- The official [`tdlib/telegram-bot-api`](https://github.com/tdlib/telegram-bot-api) server running
  with `--local`
- Your own Telegram `api_id` and `api_hash` from
  [my.telegram.org](https://my.telegram.org/apps)
- The application and API server on the same host, or a shared volume exposing the exact absolute
  file paths returned by the server
- A private API listener; do not expose the unauthenticated local HTTP endpoint to the internet

Follow Telegram's official build and migration instructions. Before moving a bot from the cloud API,
call `logOut` as documented by Telegram; otherwise update delivery is not guaranteed. Returning to
the cloud API also has a ten-minute login delay.

## Application configuration

Start from the normal configuration, then set:

```dotenv
TELEGRAM_LOCAL_MODE=true
TELEGRAM_BASE_URL=http://127.0.0.1:8081/bot
TELEGRAM_BASE_FILE_URL=http://127.0.0.1:8081/file/bot
MAX_FILE_MIB=2000
```

Run `telegram2onedrive --env-file .env check`, then start the bot and transfer a small synthetic file
before relying on larger transfers.

In local mode, Telegram2OneDrive resolves and reads the absolute path returned by the API server. It
does not delete that file because the Local Bot API Server owns its retention. Monitor that server's
storage and retention independently.

The adapter's configuration and local-path behavior are covered by unit tests. A real Local Bot API
Server is not started in GitHub Actions, so no end-to-end compatibility claim is made for a specific
server release or container image.
