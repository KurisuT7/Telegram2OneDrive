# Telegram2OneDrive

[简体中文](README.zh-CN.md)

Send a file to a Telegram bot and Telegram2OneDrive will classify and upload it to OneDrive:

```text
Telegram2OneDrive/
├── Images/
├── Videos/
├── Audio/
├── Documents/
├── Archives/
└── Other/
```

The default mode handles files up to 20 MiB. With MTProto enabled, the same bot can handle files up
to 2048 MiB. The guide below starts from a fresh Ubuntu 24.04 or Debian 12 server.

## Before you begin

You need:

- a Linux server that can reach Telegram, Microsoft sign-in, and OneDrive;
- a Linux user with `sudo` access;
- a local computer with a browser for Microsoft and Telegram sign-in;
- a Telegram account and a OneDrive account.

If you only transfer files up to 20 MiB, skip step 2. All other steps remain the same.

## 1. Create a Telegram bot

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot`.
3. Enter a display name, such as `My OneDrive Bot`.
4. Enter a username ending in `bot`, such as `my_onedrive_upload_bot`.
5. Save the token returned by BotFather. You will place it in `.env` later.

## 2. Get an MTProto API ID and hash

Only complete this step if you need to transfer files larger than 20 MiB.

1. Make sure you are signed in to an official Telegram app on your phone or computer.
2. Open [my.telegram.org](https://my.telegram.org) in a browser.
3. Enter the phone number for your Telegram account and continue.
4. Telegram sends the sign-in code to the Telegram app. Enter it on the website.
5. Select `API development tools`.
6. Complete the form: use `Telegram2OneDrive` for `App title`, `telegram2onedrive` for `Short
   name`, leave `URL` empty if the form permits it (otherwise use this repository URL), choose
   `Desktop` or `Other` for `Platform`, and use `Telegram file transfer to OneDrive` for
   `Description`.
7. Submit the form and record the displayed `api_id` and `api_hash` for `.env`.

## 3. Connect to the server and install prerequisites

Open a terminal on your local computer. Replace the placeholders with your Linux username and
server address:

```bash
ssh -L 53682:127.0.0.1:53682 <linux-user>@<server-address>
```

This SSH connection also creates a temporary tunnel for OneDrive sign-in from your local browser.
Keep the terminal connected.

Run these commands on the server, one line at a time:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv curl nano
python3 --version
sudo -v
curl https://rclone.org/install.sh | sudo bash
rclone version
```

`python3 --version` should report 3.11, 3.12, or 3.13. The default Python versions in Ubuntu 24.04
and Debian 12 are supported. The rclone command follows the
[official Linux installation method](https://rclone.org/install/).

## 4. Connect OneDrive

Run this command on the server:

```bash
rclone config
```

A remote is a saved cloud connection in rclone, not another server. Naming it `onedrive` lets later
commands access the drive as `onedrive:`.

Answer the prompts as follows. Numbers may differ between rclone versions, so follow the option
names rather than copying a number blindly.

1. Enter `n` to create a new remote.
2. Name it `onedrive`.
3. Choose `Microsoft OneDrive` as the storage type, or enter `onedrive`.
4. Press Enter to leave `client_id` empty.
5. Press Enter to leave `client_secret` empty.
6. If rclone asks for a OneDrive region, choose `Microsoft Cloud Global` for an ordinary global
   account; choose the matching region for another cloud.
7. Answer `n` to `Edit advanced config?`.
8. Answer `y` to `Use web browser to automatically authenticate rclone?`.
9. If a browser does not open, copy the complete URL beginning with `http://127.0.0.1:53682/`
   from the terminal into your local browser. The SSH tunnel from step 3 makes it reachable.
10. Sign in to Microsoft and approve access, then return to the server terminal.
11. For an ordinary personal or business drive, choose `OneDrive Personal or Business`.
12. If rclone lists multiple drives, choose the one that should store the files.
13. Answer `y` when rclone asks you to confirm the drive, then `y` again to keep the remote.
14. Enter `q` at the main menu to exit.

This headless-server sign-in flow follows rclone's
[official remote setup guide](https://rclone.org/remote_setup/).

Test the connection:

```bash
rclone lsd onedrive:
```

The setup is working if the command lists directories, or finishes without an error when the drive
is empty. If it fails, run `rclone config` again and check the remote name and Microsoft approval.

## 5. Download and install Telegram2OneDrive

Continue on the server:

```bash
cd ~
git clone https://github.com/KurisuT7/Telegram2OneDrive.git
cd Telegram2OneDrive
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install ".[mtproto]"
cp .env.example .env
chmod 600 .env
nano .env
```

Find these entries in `.env` and replace only the text after each equals sign. Do not add quotation
marks or duplicate entries:

```dotenv
TELEGRAM_BOT_TOKEN=paste-the-token-from-BotFather-here
TELEGRAM_ALLOWED_USER_IDS=

TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=paste-api-id-here
TELEGRAM_API_HASH=paste-api-hash-here
```

If you only transfer files up to 20 MiB, keep `TELEGRAM_MTPROTO_ENABLED=false` and leave
`TELEGRAM_API_ID` and `TELEGRAM_API_HASH` empty. The other settings can keep their defaults.

In nano, press `Ctrl+O`, press Enter to confirm the filename, and then press `Ctrl+X` to exit.

## 6. First start and user allowlist

Check the configuration and OneDrive connection:

```bash
.venv/bin/telegram2onedrive check
```

`OneDrive check passed` means the check succeeded. Start the bot:

```bash
.venv/bin/telegram2onedrive run
```

Then:

1. Open the new bot in Telegram and select `START`, or send `/start`.
2. Send `/whoami`.
3. The bot replies with `User ID:` followed by a number. Copy only that number.
4. Return to the server and press `Ctrl+C` to stop the program.
5. Edit the configuration again:

   ```bash
   nano .env
   ```

6. Add the number after `TELEGRAM_ALLOWED_USER_IDS=`, for example:

   ```dotenv
   TELEGRAM_ALLOWED_USER_IDS=123456789
   ```

   Separate multiple IDs with commas, such as `123456789,987654321`.
7. Save and exit nano, then check and run the bot again:

   ```bash
   .venv/bin/telegram2onedrive check
   .venv/bin/telegram2onedrive run
   ```

Send a small file to the bot. After it reports `Uploaded ...`, check the `Telegram2OneDrive` folder
in OneDrive. If MTProto is enabled, also test with a file larger than 20 MiB.

## 7. Start automatically at boot

After the manual test succeeds, press `Ctrl+C` to stop it and run:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/telegram2onedrive.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now telegram2onedrive
sudo loginctl enable-linger "$USER"
systemctl --user status telegram2onedrive
```

`Active: active (running)` means the service is running. Press `q` to leave the status screen.

The included service expects the repository at `~/Telegram2OneDrive`. If you cloned it elsewhere,
update `WorkingDirectory` and `ExecStart` in the service file.

Useful service commands:

```bash
# Follow logs; press Ctrl+C to exit
journalctl --user -u telegram2onedrive -f

# Restart
systemctl --user restart telegram2onedrive

# Stop
systemctl --user stop telegram2onedrive

# Start again
systemctl --user start telegram2onedrive
```

## 8. Update later

```bash
cd ~/Telegram2OneDrive
git pull --ff-only
.venv/bin/python -m pip install ".[mtproto]"
systemctl --user restart telegram2onedrive
systemctl --user status telegram2onedrive
```

## Troubleshooting

### `python3` is older than 3.11

Do not continue the installation. Use Ubuntu 24.04 or Debian 12, or install Python 3.11–3.13 using
the supported method for your distribution.

### `OneDrive check failed`

Run `rclone lsd onedrive:` first. If it also fails, the problem is the rclone remote name or
Microsoft approval; run `rclone config` again. If you used a different remote name, set that name in
`RCLONE_REMOTE` in `.env`.

### The bot does not reply

Read `journalctl --user -u telegram2onedrive -f`. Also check the bot token and make sure no second
program is using it. Only one polling instance can receive updates for a bot.

### `MTProto support is not installed`

Run this in the repository directory:

```bash
.venv/bin/python -m pip install ".[mtproto]"
systemctl --user restart telegram2onedrive
```

### Files larger than 20 MiB still fail

Confirm that `.env` contains `TELEGRAM_MTPROTO_ENABLED=true` and complete values for
`TELEGRAM_API_ID` and `TELEGRAM_API_HASH`. Then run `.venv/bin/telegram2onedrive check` to get the
specific configuration error.

### Changes to `.env` have no effect

The service does not reload configuration automatically. Restart it after a change:

```bash
systemctl --user restart telegram2onedrive
```

## Behavior and defaults

- Files up to 20 MiB use the Telegram Bot API. With MTProto enabled, larger files automatically use
  MTProto.
- When `MAX_FILE_MIB` is empty, the limit is 20 MiB normally and 2048 MiB with MTProto.
- The MTProto session defaults to `~/.local/state/telegram2onedrive/mtproto`; no path is required.
- Files transfer serially, and upload status is refreshed every 30 seconds.
- Duplicate names get ` (n)` before the extension by default instead of overwriting an existing file.
- `/status` checks whether the bot can currently access the OneDrive remote.
- Private chats and users in `TELEGRAM_ALLOWED_USER_IDS` are allowed by default.

See [.env.example](.env.example) for every setting. A Local Bot API Server is an alternative
advanced large-file backend; see [docs/local-bot-api.md](docs/local-bot-api.md). See
[docs/mtproto.md](docs/mtproto.md) for MTProto internals and advanced settings. The two large-file
backends cannot be enabled together.

## Privacy, security, and limitations

Telegram receives the original message and file. The server temporarily downloads the file, and
rclone sends the file and destination name to Microsoft OneDrive. The project has no telemetry.

Do not commit a completed `.env`, the rclone config, or the MTProto session. Group transfers are off
by default because group members may see filenames and status messages. Do not let multiple
processes share the same bot token or MTProto session.

The Bot API uses polling and does not support webhooks. OneDrive path and file-size limits still
apply. GitHub Actions does not connect to real Local Bot API or MTProto services, but automated tests
cover the important routing, lifecycle, cleanup, and failure behavior.

Report security issues through [GitHub private vulnerability reporting](SECURITY.md).

## Development and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for development checks and [CHANGELOG.md](CHANGELOG.md) for
user-visible changes. Telegram2OneDrive uses the [MIT License](LICENSE).
