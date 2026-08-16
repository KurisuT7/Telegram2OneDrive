# 原生 Linux 安装

[English](native-linux.md) · [返回中文 README](../README.zh-CN.md)

Docker Compose 是推荐部署方式。本页适用于已经在 Linux 服务器上维护 Python、rclone 和
systemd 环境的用户。

## 前置条件

- Python 3.11 或更高版本；启用 MTProto 时使用 Python 3.11–3.13；
- 已安装 rclone，并已按[官方 OneDrive 文档](https://rclone.org/onedrive/)创建 remote；
- BotFather Token；启用 MTProto 时还需要 `api_id` 和 `api_hash`。

以下命令以 Ubuntu/Debian、remote 名称 `onedrive`、项目目录 `~/Telegram2OneDrive` 为例。

## 安装与配置

```bash
sudo apt update
sudo apt install -y git python3 python3-venv

git clone https://github.com/KurisuT7/Telegram2OneDrive.git ~/Telegram2OneDrive
cd ~/Telegram2OneDrive
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install ".[mtproto]"
cp .env.example .env
chmod 600 .env
```

编辑 `.env`，至少填写 Bot Token。要传输大于 20 MiB 的文件，再启用 MTProto 并填写 API ID
和 Hash。配置项与主 README 相同。

确认 rclone 和程序均可访问 OneDrive：

```bash
rclone lsd onedrive:
.venv/bin/telegram2onedrive check
```

看到 `OneDrive check passed` 后前台启动：

```bash
.venv/bin/telegram2onedrive run
```

私聊 Bot 发送 `/whoami`，把返回的 User ID 写入 `TELEGRAM_ALLOWED_USER_IDS`。重启程序后发送
一个文件，确认 Bot 返回 `Uploaded ...` 且 OneDrive 中出现对应文件。

## 使用 systemd 运行

手动验证完成后安装仓库内的用户服务：

```bash
mkdir -p ~/.config/systemd/user
cp deploy/telegram2onedrive.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now telegram2onedrive
sudo loginctl enable-linger "$USER"
systemctl --user status telegram2onedrive
```

服务文件默认使用 `~/Telegram2OneDrive`。项目位于其他目录时，修改服务文件中的
`WorkingDirectory` 和 `ExecStart`。

```bash
# 查看日志
journalctl --user -u telegram2onedrive -f

# 修改 .env 后重启
systemctl --user restart telegram2onedrive
```

## 更新

```bash
cd ~/Telegram2OneDrive
git pull --ff-only
.venv/bin/python -m pip install ".[mtproto]"
systemctl --user restart telegram2onedrive
systemctl --user status telegram2onedrive
```

rclone 配置必须保持可写，因为 OAuth Token 会刷新。MTProto Session 默认保存在
`~/.local/state/telegram2onedrive/mtproto`；这两类凭据都不应进入仓库或与其他实例共用。
