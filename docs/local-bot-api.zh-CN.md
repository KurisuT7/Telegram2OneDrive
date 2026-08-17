# Local Bot API Server

[English](local-bot-api.md) · [返回中文 README](../README.zh-CN.md)

这是大文件下载的高级备选方案。只有已经运行 Telegram 官方
[`tdlib/telegram-bot-api`](https://github.com/tdlib/telegram-bot-api) 并需要复用它时才建议启用；
新部署优先使用 [MTProto](mtproto.zh-CN.md)。

## 前置条件

- API Server 以 `--local` 模式运行；
- 从 [my.telegram.org](https://my.telegram.org/apps) 获取 `api_id` 和 `api_hash`；
- Telegram2OneDrive 能访问 API 地址和它返回的绝对文件路径；
- API 监听地址只位于受信网络，不直接暴露到互联网。

从 Telegram 云端 Bot API 迁移前，按官方文档调用 `logOut`。切回云端 API 时还需要等待重新登录
窗口，具体行为以 Telegram 官方说明为准。

## 配置

```dotenv
TELEGRAM_LOCAL_MODE=true
TELEGRAM_BASE_URL=http://127.0.0.1:8081/bot
TELEGRAM_BASE_FILE_URL=http://127.0.0.1:8081/file/bot
MAX_FILE_MIB=2000
```

`TELEGRAM_LOCAL_MODE` 与 MTProto 不能同时启用。先运行 `telegram2onedrive check`，再启动 Bot，
依次用小文件和大文件验证。

仓库自带的 `compose.yaml` 没有部署或连接 Local Bot API Server。容器化使用此模式时，需要自行
提供 Compose 覆盖文件，让两个服务使用相同 Docker 网络，并把 API Server 返回的文件目录以相同
绝对路径挂载到 Telegram2OneDrive。无法满足这两个条件时，请使用原生安装。

本地模式会直接读取 API Server 返回的文件，不会删除它。存储清理和保留策略由 API Server
部署独立负责。
