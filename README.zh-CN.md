# Telegram2OneDrive

[English](README.md)

把发给 Telegram Bot 的文件自动分类并上传到 OneDrive。Bot 默认只接受白名单用户的私聊文件，
适合部署在长期运行的 Linux 服务器上。

```text
Telegram2OneDrive/
├── Images/
├── Videos/
├── Audio/
├── Documents/
├── Archives/
└── Other/
```

| 下载方式 | 单文件上限 | 适用场景 |
| --- | ---: | --- |
| Telegram 云端 Bot API | 20 MiB | 默认模式，无额外 Telegram 凭据 |
| MTProto | 2048 MiB | 需要传大文件，推荐方案 |
| Local Bot API Server | 由本地服务决定 | 已经维护官方本地 API 服务的高级部署 |

MTProto 只接管大于 20 MiB 的文件下载；Bot 命令、小文件下载、分类和 OneDrive 上传仍使用原来的
流程。

## 快速开始（Docker Compose）

需要一台能访问 Telegram 和 Microsoft OneDrive 的 Linux 服务器，并已安装
[Docker Engine 和 Compose 插件](https://docs.docker.com/engine/install/)。开始前准备好：

- 在 [@BotFather](https://t.me/BotFather) 创建 Bot 后得到的 Token；
- 如果要传输大于 20 MiB 的文件，从 [my.telegram.org](https://my.telegram.org) 的
  `API development tools` 获取 `api_id` 和 `api_hash`。

### 1. 下载并填写配置

```bash
git clone https://github.com/KurisuT7/Telegram2OneDrive.git
cd Telegram2OneDrive
cp .env.example .env
chmod 600 .env
```

编辑 `.env`。需要大文件支持时填写：

```dotenv
TELEGRAM_BOT_TOKEN=BotFather返回的Token
TELEGRAM_ALLOWED_USER_IDS=

TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=你的api_id
TELEGRAM_API_HASH=你的api_hash
```

只传 20 MiB 以内的文件时，保持 `TELEGRAM_MTPROTO_ENABLED=false`，API ID 和 Hash 留空即可。
其余配置先保留默认值。

### 2. 连接 OneDrive

先构建镜像，再在容器中运行 rclone 的配置向导：

```bash
docker compose build
docker compose run --rm --entrypoint rclone bot config
```

在向导中创建一个名为 `onedrive` 的 Microsoft OneDrive remote，并完成浏览器授权。无桌面服务器
可参考 rclone 的 [OneDrive 配置](https://rclone.org/onedrive/)和
[Remote Setup](https://rclone.org/remote_setup/)文档。完成后验证：

```bash
docker compose run --rm --entrypoint rclone bot lsd onedrive:
docker compose run --rm bot check
```

第一条命令应能列出 OneDrive 根目录，第二条应显示 `OneDrive check passed`。首次配置时出现白名单
为空的 Warning 属于正常情况。

### 3. 启动并设置白名单

```bash
docker compose up -d
docker compose logs -f
```

私聊 Bot 并发送 `/whoami`，把返回的 `User ID` 写入 `.env`：

```dotenv
TELEGRAM_ALLOWED_USER_IDS=123456789
```

多个 ID 用英文逗号分隔。重新创建容器使配置生效：

```bash
docker compose up -d --force-recreate
```

向 Bot 发送一个小文件。Bot 显示 `Uploaded ...`，并且文件出现在 OneDrive 的
`Telegram2OneDrive` 目录中，即表示部署完成。启用了 MTProto 时，再发送一个大于 20 MiB 的文件
验证大文件路径。

## 日常操作

```bash
# 查看状态和日志
docker compose ps
docker compose logs -f

# 更新代码并重建
git pull --ff-only
docker compose up -d --build

# 停止并移除容器
docker compose down
```

rclone 配置和 MTProto Session 分别保存在 Docker 的 `rclone-config` 与 `telegram-state` 持久卷
中，重建容器不会丢失。不要运行 `docker compose down -v`，除非确定要同时删除 OneDrive 授权和
MTProto Session。

不使用 Docker 时，参照[原生 Linux 安装](docs/native-linux.zh-CN.md)。项目保留该方式用于已有
Python/rclone 环境或需要 systemd 直接管理进程的部署。

## 常用配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | 无 | BotFather Token，必填 |
| `TELEGRAM_ALLOWED_USER_IDS` | 空 | 允许使用 Bot 的数字 User ID，多个 ID 用逗号分隔 |
| `TELEGRAM_ALLOW_GROUP_CHATS` | `false` | 是否允许白名单用户从群组上传 |
| `TELEGRAM_MTPROTO_ENABLED` | `false` | 为大于 20 MiB 的文件启用 MTProto |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | 空 | MTProto 所需的应用凭据 |
| `MAX_FILE_MIB` | 自动 | 普通模式为 20，MTProto 模式为 2048 |
| `RCLONE_REMOTE` | `onedrive` | rclone remote 名称 |
| `ONEDRIVE_BASE_PATH` | `Telegram2OneDrive` | OneDrive 中的目标目录 |
| `DUPLICATE_POLICY` | `rename` | 同名文件使用 `rename`、`replace` 或 `fail` |

全部配置和注释见 [.env.example](.env.example)。修改 `.env` 后需要重新创建容器，单纯执行
`docker compose restart` 不会加载新的环境变量。

## 使用说明与限制

- Bot 支持 `/start`、`/whoami` 和 `/status`；`/status` 用于检查 OneDrive 连接。
- 文件按顺序传输，上传状态每 30 秒更新一次。
- 临时下载会在上传结束后清理；rclone 授权和 MTProto Session 会保留。
- 同名文件默认添加 ` (n)`，不会覆盖已有文件。
- 默认只接受白名单用户的私聊文件，群组上传默认关闭。
- 不要提交填好的 `.env`、rclone 配置或 MTProto Session，也不要让多个实例共用同一个 Bot
  Token 或 Session。
- 项目使用轮询，不支持 Webhook；OneDrive 自身的路径和文件大小限制仍然适用。

## 更多文档

- [MTProto 大文件模式](docs/mtproto.zh-CN.md)
- [Local Bot API Server](docs/local-bot-api.zh-CN.md)
- [原生 Linux 安装](docs/native-linux.zh-CN.md)
- [参与开发](CONTRIBUTING.md)
- [更新记录](CHANGELOG.md)

安全问题请通过 [GitHub 私密漏洞报告](SECURITY.md)提交。项目使用 [MIT License](LICENSE)，与
Telegram、Microsoft 和 rclone 项目无隶属或背书关系。
