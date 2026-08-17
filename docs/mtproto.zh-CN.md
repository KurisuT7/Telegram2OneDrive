# MTProto 大文件模式

[English](mtproto.md) · [返回中文 README](../README.zh-CN.md)

Telegram 云端 Bot API 的文件下载上限为 20 MiB。启用 MTProto 后，大于 20 MiB 的文件由
Pyrogram 下载，再交给原有的分类和 rclone 上传流程，项目上限为 2048 MiB。

MTProto 使用 Bot Token 建立 Bot Session，不需要登录个人 Telegram 账号。

## 启用

从 [my.telegram.org](https://my.telegram.org) 的 `API development tools` 获取 `api_id` 和
`api_hash`，然后在 `.env` 中填写：

```dotenv
TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=你的api_id
TELEGRAM_API_HASH=你的api_hash
```

Docker 镜像已经包含 MTProto 依赖，重新创建容器即可：

```bash
docker compose up -d --build
docker compose logs -f
```

原生安装需要先安装可选依赖：

```bash
.venv/bin/python -m pip install ".[mtproto]"
systemctl --user restart telegram2onedrive
```

首次启动会自动创建 Bot Session，不会询问手机号或验证码。先发送一个小文件，再发送一个大于
20 MiB 的文件；两次都出现 `Uploaded ...` 即表示两条下载路径正常。

## 默认值与持久化

| 配置 | 默认值 |
| --- | --- |
| `MAX_FILE_MIB` | `2048` |
| `TELEGRAM_MTPROTO_SESSION_DIR` | `~/.local/state/telegram2onedrive/mtproto` |
| `TELEGRAM_MTPROTO_SESSION_NAME` | `telegram2onedrive` |

Docker 部署会把 Session 保存在 `telegram-state` 持久卷；原生部署使用上表目录。Session 包含
Bot 的 MTProto 授权信息，不要提交、分享或让多个实例同时使用。

## 排障

| 错误或现象 | 处理方式 |
| --- | --- |
| `MTProto support is not installed` | 原生环境重新安装 `.[mtproto]`；Docker 重新构建镜像 |
| API ID 或 Hash 格式错误 | API ID 应为正整数，Hash 应为 32 位十六进制字符 |
| `session belongs to a different bot` | 当前 Session 属于另一个 Bot；换回原 Token 或使用新的 Session |
| `could not find the Telegram message` | 确认消息仍存在，并且 Bot 能访问所在聊天 |
| SQLite 锁错误 | 停止共用该 Session 的其他实例 |
| 大文件仍被拒绝 | 检查 MTProto 三项配置；手工设置的 `MAX_FILE_MIB` 应大于 20 |

MTProto 与 `TELEGRAM_LOCAL_MODE` 不能同时启用。TgCrypto 仅用于提高加密吞吐量，不是功能依赖，
默认镜像不安装它。
