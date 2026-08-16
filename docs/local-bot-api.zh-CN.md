# Local Bot API Server

Telegram 官方云端 Bot API 的 `getFile` 下载上限是 20 MiB。官方 Local Bot API Server 使用
`--local` 模式时可不受此下载上限限制。Telegram2OneDrive 会直接读取返回的本地文件路径，
不再复制一份文件。

这是可选集成。默认云端路径更简单，运行部件也更少。

## 前置条件

- 官方 [`tdlib/telegram-bot-api`](https://github.com/tdlib/telegram-bot-api) 服务以 `--local`
  模式运行
- 从 [my.telegram.org](https://my.telegram.org/apps) 获取 Telegram `api_id` 和 `api_hash`
- 程序与 API Server 位于同一主机，或通过共享卷暴露服务返回的相同绝对路径
- API 监听地址只在受信网络中使用；不要把没有额外认证的本地 HTTP 端点暴露到互联网

请按 Telegram 官方构建和迁移说明操作。从云端 API 迁移前，必须按文档调用 `logOut`，否则
更新投递没有保证。切回云端 API 时还有十分钟的重新登录等待时间。

## 程序配置

先完成普通配置，再设置：

```dotenv
TELEGRAM_LOCAL_MODE=true
TELEGRAM_BASE_URL=http://127.0.0.1:8081/bot
TELEGRAM_BASE_FILE_URL=http://127.0.0.1:8081/file/bot
MAX_FILE_MIB=2000
```

先在项目目录运行 `.venv/bin/telegram2onedrive check`，再运行
`.venv/bin/telegram2onedrive run` 启动 Bot。使用小型测试文件完成一次转存后，再测试更大的
文件。

本地模式下，Telegram2OneDrive 会解析并读取 API Server 返回的绝对路径。该文件属于 Local
Bot API Server，程序不会删除；请独立监控该服务的存储和保留策略。

单元测试覆盖适配器配置和本地路径行为。GitHub Actions 不会启动真实 Local Bot API Server，
因此本项目不对特定服务版本或容器镜像作端到端兼容性声明。
