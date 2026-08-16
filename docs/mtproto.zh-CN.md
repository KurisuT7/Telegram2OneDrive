# MTProto 大文件回退

[English](mtproto.md)

Telegram2OneDrive 默认通过 HTTP Bot API 接收更新并下载文件。启用可选 MTProto 回退后，同一个
Bot 还会建立一个 Pyrogram Session：

- 更新、命令、权限校验及不超过 20 MiB 的文件仍走 Bot API；
- 超过 20 MiB 的文件按 Chat ID 和 Message ID 改由 MTProto 下载；
- 两条下载路径共用文件校验、临时目录、分类和 rclone 上传逻辑。

它只是大文件下载回退，不会登录个人账号，也不会再启动一套 MTProto 更新消费。Telegram 在
[Local Bot API Server 文档](https://core.telegram.org/bots/features#local-bot-api)中说明了云端
Bot API 的 20 MiB 下载边界。

## 要求

- MTProto 回退使用 Python 3.11–3.13（核心 Bot API 路径同时支持 Python 3.14）
- `mtproto` 可选依赖
- BotFather 创建的 Bot Token
- 由部署者本人在 [my.telegram.org/apps](https://my.telegram.org/apps) 创建的 Application ID
  和 Hash
- 位于源码检出目录之外的 Session 绝对目录

不要使用公开频道、示例文件或其他部署者分享的 Application 凭据。Telegram 将 API ID 视为申请
它的应用所有，并可能拒绝已公开的凭据。

安装普通实现：

```bash
python -m pip install -e ".[mtproto]"
```

该适配器参考的生产方案还使用 TgCrypto 加速加密。TgCrypto 是原生扩展，因此不强制放进可移植
Extra。在有兼容 Wheel 或编译环境的 Linux 主机上，可在同一个环境中单独安装并验证：

```bash
python -m pip install TgCrypto
```

TgCrypto 只改善加密吞吐量，不影响功能正确性。没有兼容 Wheel 或编译器时应保持不安装，不要为了
它降低主机工具链安全性。

## 配置

从 `.env.example` 复制配置并填写：

```dotenv
TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
TELEGRAM_MTPROTO_SESSION_DIR=/var/lib/telegram2onedrive/mtproto
TELEGRAM_MTPROTO_SESSION_NAME=telegram2onedrive
MAX_FILE_MIB=2048
```

以上值只是占位符，不得照抄。`TELEGRAM_MTPROTO_SESSION_NAME` 只能包含字母、数字、下划线和
连字符。

MTProto 回退与 `TELEGRAM_LOCAL_MODE` 互斥。本地 Bot API Server 已提供自己的大文件路径；同一
Bot 实例只能选择其中一种方案。

## 首次启动

先检查本地配置和 OneDrive 访问：

```bash
telegram2onedrive --env-file /etc/telegram2onedrive.env check
```

再按普通方式启动 Bot：

```bash
telegram2onedrive --env-file /etc/telegram2onedrive.env run
```

Bot API 轮询程序会在启动回调中连接 Pyrogram，并在退出回调中关闭它。Pyrogram 会在配置目录中
创建 `<session-name>.session`。在 POSIX 系统中，Telegram2OneDrive 会把目录权限限制为 `0700`，
并把对应 Session 文件限制为 `0600`。

不得让两个进程共用同一个 Session，也不得使用正在运行的服务 Session 做交互式冒烟测试。应先
停止服务，或改用独立的临时 Bot 与 Session。

## 安全与运维

Session 数据库包含 MTProto 授权密钥，取得它的人可能以该 Bot 身份操作。不得把它放进 Git、
公开备份、容器镜像、日志或支持包。Windows 不执行 POSIX 权限位，需要通过 ACL 只允许服务账号
访问该目录。

客户端会核对现有 Session 是否属于 `TELEGRAM_BOT_TOKEN` 中的 Bot ID；个人账号 Session 或
其他 Bot 的 Session 会被拒绝。遇到异常 Session 时，先将其保留为证据，改用新的空 Session
目录并完成调查，再决定是否删除。

文件仍受 `MAX_FILE_MIB` 限制，本项目当前上限为 2048 MiB。云端 Bot API 与 MTProto 下载都使用
一次一目录的临时空间，并在上传尝试结束后删除。Pyrogram Session 目录是持久数据，不能放在临时
下载目录中。

## 故障排查

- `MTProto support is not installed`：在运行 Bot 的同一 Python 环境安装 `.[mtproto]`。
- `session belongs to a different bot`：不要复用该 Session，核对 Token 与 Session 路径。
- `could not find the Telegram message`：确认原消息仍存在，而且 Bot 能访问所在聊天。
- 反复出现 SQLite 锁错误：确认只有一个进程使用配置的 Session Name。
- 大于 20 MiB 的文件仍报 Bot API 错误：确认 MTProto 已启用、`MAX_FILE_MIB` 大于 20，且启动时
  没有 MTProto 错误。
