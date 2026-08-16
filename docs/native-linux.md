# Native Linux installation

[简体中文](native-linux.zh-CN.md) · [Back to README](../README.md)

Docker Compose is the recommended deployment. Use this guide when you already maintain Python,
rclone, and systemd directly on a Linux server.

## Prerequisites

- Python 3.11 or newer; use Python 3.11–3.13 with MTProto
- rclone installed with a remote created using the official
  [OneDrive guide](https://rclone.org/onedrive/)
- A BotFather token; MTProto also requires an `api_id` and `api_hash`

The commands below target Ubuntu/Debian, an rclone remote named `onedrive`, and a project directory
at `~/Telegram2OneDrive`.

## Install and configure

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

Edit `.env` and set at least the bot token. For files above 20 MiB, enable MTProto and add the API
ID and hash. The settings are the same as in the main README.

Verify both rclone and the application can reach OneDrive:

```bash
rclone lsd onedrive:
.venv/bin/telegram2onedrive check
```

After `OneDrive check passed`, start the bot in the foreground:

```bash
.venv/bin/telegram2onedrive run
```

Send `/whoami` to the bot in a private chat and place the returned User ID in
`TELEGRAM_ALLOWED_USER_IDS`. Restart the process, send a file, and confirm both the `Uploaded ...`
reply and the resulting OneDrive file.

## Run with systemd

After the manual verification succeeds, install the included user service:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/telegram2onedrive.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now telegram2onedrive
sudo loginctl enable-linger "$USER"
systemctl --user status telegram2onedrive
```

The service expects `~/Telegram2OneDrive`. If the project is elsewhere, update `WorkingDirectory`
and `ExecStart` in the service file.

```bash
# Follow logs
journalctl --user -u telegram2onedrive -f

# Restart after changing .env
systemctl --user restart telegram2onedrive
```

## Update

```bash
cd ~/Telegram2OneDrive
git pull --ff-only
.venv/bin/python -m pip install ".[mtproto]"
systemctl --user restart telegram2onedrive
systemctl --user status telegram2onedrive
```

Keep the rclone configuration writable because its OAuth token refreshes. The MTProto session
defaults to `~/.local/state/telegram2onedrive/mtproto`. Neither credential should enter the
repository or be shared by multiple instances.
