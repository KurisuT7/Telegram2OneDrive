# Telegram2OneDrive

[English](README.md)

Telegram2OneDrive 只接收明确授权的 Telegram 用户发送的文件，按媒体类型分类后，通过 rclone
转存到 OneDrive。

默认使用 Telegram 云端 Bot API，单文件下载上限为 20 MiB。若 Bot 与 Local Bot API Server
共享文件系统，可启用可选适配器处理更大的文件。

## 前置条件

- Python 3.11 或更高版本
- 通过 [@BotFather](https://t.me/BotFather) 创建的 Telegram Bot
- 已配置 OneDrive remote 的 [rclone](https://rclone.org/downloads/)
- 能访问 Telegram、Microsoft 登录、Microsoft Graph 和 OneDrive 的主机

程序不直接接收 OneDrive Token。OAuth 授权、Token 刷新、大文件上传及可写凭据文件均由
rclone 管理。

## 完成第一次转存

### 1. 创建 Telegram Bot

打开 [@BotFather](https://t.me/BotFather)，发送 `/newbot`，设置显示名称和用户名，并把返回的
Token 保存在仓库之外。任何获得 Token 的人都可以控制这个 Bot。

### 2. 在 rclone 中配置 OneDrive

安装 rclone 后运行：

```bash
rclone config
```

新建名为 `onedrive` 的 remote，选择 Microsoft OneDrive，并在浏览器中完成授权。除非使用自己
管理的 Microsoft 应用，否则 Client ID 和 Client Secret 留空。不要打印配置内容，使用以下命令
验证连接：

```bash
rclone lsd onedrive:
```

rclone 配置包含刷新凭据。只允许服务账号读取，同时保持文件可写，以便 rclone 轮换 Token。

### 3. 安装程序

在本仓库的克隆目录中运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
cp .env.example .env
```

Windows PowerShell 使用 `.venv\Scripts\Activate.ps1` 激活，使用
`Copy-Item .env.example .env` 复制配置。

在 `.env` 中填写 `TELEGRAM_BOT_TOKEN`。如果 rclone 没有使用默认配置位置，把
`RCLONE_CONFIG` 设置为绝对路径。首次启动时先让 `TELEGRAM_ALLOWED_USER_IDS` 保持为空。

### 4. 获取 Telegram User ID

先验证配置和 OneDrive，再启动 Bot：

```bash
telegram2onedrive --env-file .env check
telegram2onedrive --env-file .env run
```

在 Telegram 中私聊 Bot，发送 `/whoami`。停止程序，把返回的数字 User ID 写入
`TELEGRAM_ALLOWED_USER_IDS` 后重新启动。多个 ID 以逗号分隔。

### 5. 发送文件

在私聊中向 Bot 发送文件。出现 `Uploaded ...` 表示转存完成，文件会进入：

```text
Telegram2OneDrive/
├── Images/
├── Videos/
├── Audio/
├── Documents/
├── Archives/
└── Other/
```

发送 `/status` 可从 Telegram 侧检查当前 OneDrive remote 是否可访问。

## 配置项

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | 无 | BotFather Token，必填 |
| `TELEGRAM_ALLOWED_USER_IDS` | 空 | 逗号分隔的正整数 User ID |
| `TELEGRAM_ALLOW_GROUP_CHATS` | `false` | 允许已授权用户从群组转存 |
| `MAX_FILE_MIB` | `20` | 下载前拒绝更大的文件 |
| `RCLONE_REMOTE` | `onedrive` | 已配置的 OneDrive remote 名称 |
| `RCLONE_CONFIG` | rclone 自动查找 | 可选的配置文件绝对路径 |
| `ONEDRIVE_BASE_PATH` | `Telegram2OneDrive` | OneDrive 根目录下的目标路径 |
| `DUPLICATE_POLICY` | `rename` | `rename`、`replace` 或 `fail` |
| `RCLONE_TIMEOUT_SECONDS` | `3600` | 单次命令超时，范围 60–86400 秒 |
| `TRANSFER_TMP_DIR` | 系统临时目录 | 可选的云端 Bot API 下载目录 |

Local Bot API 配置见 [docs/local-bot-api.zh-CN.md](docs/local-bot-api.zh-CN.md)。

## 运行与失败行为

- 文件转存按顺序执行，避免两个更新同时选择同一个重命名目标。
- 云端 Bot API 下载使用独立临时目录，无论成功或失败都会删除。
- Local Bot API 文件属于该服务，Telegram2OneDrive 不会删除。
- 上传状态每 30 秒刷新一次；rclone 可能在传输前等待 Microsoft 授权刷新。
- `rename` 在扩展名前添加 ` (n)`，`replace` 允许覆盖，`fail` 遇到 OneDrive
  大小写不敏感的同名文件时拒绝上传。
- rclone 从自身配置文件读取凭据。程序不会运行 `rclone config dump`，也不会把 OAuth Token
  复制到日志或程序状态中。

## 安全与隐私

Telegram 会接收原始消息和文件；运行主机会临时接收云端 Bot API 文件；rclone 会把文件和目标
名称发送给 Microsoft OneDrive。程序不包含遥测。

请保护 Bot Token、rclone 配置、下载文件、日志和进程环境。建议使用独立服务账号、私聊 Bot
以及明确的用户白名单。默认关闭群组转存，因为其他群成员可能看到文件名和状态消息。

安全问题请通过 [GitHub 私密漏洞报告](SECURITY.md)提交。

## 限制

- 云端 Bot API 无法下载超过 20 MiB 的文件。
- Local Bot API 适配器要求共享文件系统；GitHub Actions 未做端到端服务器测试，但配置、URL、
  本地路径和大小行为有单元测试覆盖。
- 仅支持轮询，不支持 Webhook 和多个 Bot 实例。
- 外部 OneDrive 写入无法纳入同一个事务；`rename` 和 `fail` 使用 `--immutable`，避免竞争时静默覆盖。
- 仍受 OneDrive 路径和文件大小限制；不受 OneDrive 支持的字符由 rclone 映射。

Telegram、OneDrive、Microsoft 和 rclone 是各自所有者的商标。本项目为独立项目，未获得
Telegram、Microsoft 或 rclone 项目的认可或背书。

## 开发与许可证

本地检查和测试数据规则见 [CONTRIBUTING.md](CONTRIBUTING.md)，更新记录见
[CHANGELOG.md](CHANGELOG.md)。Telegram2OneDrive 使用 [MIT License](LICENSE)。
