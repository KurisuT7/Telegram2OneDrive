# Telegram2OneDrive

[English](README.md)

把文件发送给 Telegram Bot，程序会自动分类并上传到 OneDrive：

```text
Telegram2OneDrive/
├── Images/
├── Videos/
├── Audio/
├── Documents/
├── Archives/
└── Other/
```

默认模式支持不超过 20 MiB 的文件。启用 MTProto 后，同一个 Bot 可以处理不超过 2048 MiB 的
文件。下面是一套面向 Ubuntu 24.04 和 Debian 12 服务器的完整安装流程，从空服务器开始即可。

## 开始前准备

你需要：

- 一台能访问 Telegram、Microsoft 登录和 OneDrive 的 Linux 服务器；
- 一个可以使用 `sudo` 的 Linux 用户；
- 一台带浏览器的本地电脑，用来登录 Microsoft 和 Telegram；
- 一个 Telegram 账号和一个 OneDrive 账号。

如果只传 20 MiB 以内的文件，可以跳过第 2 步。其余步骤不变。

## 1. 创建 Telegram Bot

1. 在 Telegram 中打开 [@BotFather](https://t.me/BotFather)。
2. 发送 `/newbot`。
3. 按提示输入 Bot 的显示名称，例如 `My OneDrive Bot`。
4. 再输入一个以 `bot` 结尾的用户名，例如 `my_onedrive_upload_bot`。
5. BotFather 会返回一段 Token。先把它保存在安全的位置，稍后要填入 `.env`。

## 2. 获取 MTProto 的 API ID 和 Hash

只有需要传输大于 20 MiB 的文件时才做这一步。

1. 确认手机或电脑上已经登录 Telegram 官方客户端。
2. 在浏览器打开 [my.telegram.org](https://my.telegram.org)。
3. 输入 Telegram 账号的手机号码并继续。
4. 验证码会发到 Telegram 客户端中，把验证码填回网页。
5. 点击 `API development tools`。
6. 填写表单：`App title` 可以写 `Telegram2OneDrive`；`Short name` 可以写
   `telegram2onedrive`；`URL` 允许留空时直接留空，否则填写本仓库地址；`Platform` 选择
   `Desktop` 或 `Other`；`Description` 可以写 `Telegram file transfer to OneDrive`。
7. 提交表单后记录页面显示的 `api_id` 和 `api_hash`，稍后填入 `.env`。

## 3. 登录服务器并安装基础软件

在本地电脑打开终端。将下面的用户名和服务器地址换成实际值：

```bash
ssh -L 53682:127.0.0.1:53682 <Linux用户名>@<服务器地址>
```

这个 SSH 连接同时建立了一个临时通道，后面可以在本地浏览器完成 OneDrive 登录。保持该终端
连接，不要提前关闭。

在服务器中逐行运行：

```bash
sudo apt update
sudo apt install -y git python3 python3-venv curl nano
python3 --version
sudo -v
curl https://rclone.org/install.sh | sudo bash
rclone version
```

`python3 --version` 应显示 3.11、3.12 或 3.13。Ubuntu 24.04 和 Debian 12 的默认 Python
版本符合要求。这里使用的是 [rclone 官方 Linux 安装方法](https://rclone.org/install/)。

## 4. 连接 OneDrive

在服务器中运行：

```bash
rclone config
```

remote 是 rclone 保存的一份网盘连接配置，不是另一台服务器。这里把它命名为 `onedrive`，后续
命令就可以用 `onedrive:` 访问网盘。

按照下面的顺序回答。rclone 不同版本显示的序号可能不同，所以请看选项名称，不要只看序号。

1. 输入 `n`，新建一个 remote。
2. 名称输入 `onedrive`。
3. 存储类型选择 `Microsoft OneDrive`，也可以直接输入 `onedrive`。
4. `client_id` 直接按回车，留空。
5. `client_secret` 直接按回车，留空。
6. 如果询问 OneDrive 区域，普通国际版选择 `Microsoft Cloud Global`；其他版本按实际区域选择。
7. `Edit advanced config?` 输入 `n`。
8. `Use web browser to automatically authenticate rclone?` 输入 `y`。
9. 如果浏览器没有自动打开，把终端中以 `http://127.0.0.1:53682/` 开头的完整地址复制到本地
   浏览器。这一步能工作是因为第 3 步建立了 SSH 通道。
10. 在浏览器登录 Microsoft 账号并同意授权，然后回到服务器终端。
11. 普通个人版或企业版 OneDrive 选择 `OneDrive Personal or Business`。
12. 如果列出多个网盘，选择要保存文件的那个。
13. 看到确认信息后输入 `y`。保存 remote 时再次输入 `y`。
14. 回到主菜单后输入 `q` 退出。

这个无桌面服务器的登录方法与 [rclone 官方远程配置说明](https://rclone.org/remote_setup/)
一致。

检查 OneDrive 是否连接成功：

```bash
rclone lsd onedrive:
```

命令能正常结束并列出目录，或者网盘为空且没有报错，就表示配置成功。若失败，重新运行
`rclone config` 检查 remote 名称和 Microsoft 授权。

## 5. 下载并安装 Telegram2OneDrive

继续在服务器中逐行运行：

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

在打开的 `.env` 中找到以下项目，只替换等号右边的内容，不要添加引号，也不要重复新增同名行：

```dotenv
TELEGRAM_BOT_TOKEN=在这里填写BotFather返回的Token
TELEGRAM_ALLOWED_USER_IDS=

TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=在这里填写api_id
TELEGRAM_API_HASH=在这里填写api_hash
```

如果只传 20 MiB 以内的文件，把 `TELEGRAM_MTPROTO_ENABLED` 保持为 `false`，并让
`TELEGRAM_API_ID` 和 `TELEGRAM_API_HASH` 留空。其他配置暂时不需要修改。

在 nano 中按 `Ctrl+O` 保存，按回车确认文件名，再按 `Ctrl+X` 退出。

## 6. 第一次启动并锁定使用者

先检查配置和 OneDrive：

```bash
.venv/bin/telegram2onedrive check
```

看到 `OneDrive check passed` 表示检查通过。然后启动 Bot：

```bash
.venv/bin/telegram2onedrive run
```

接下来：

1. 在 Telegram 中打开刚创建的 Bot，点击 `START` 或发送 `/start`。
2. 发送 `/whoami`。
3. Bot 会回复 `User ID: 一串数字`。只复制这串数字。
4. 回到服务器终端，按 `Ctrl+C` 停止程序。
5. 重新编辑配置：

   ```bash
   nano .env
   ```

6. 把数字填到 `TELEGRAM_ALLOWED_USER_IDS=` 后面，例如：

   ```dotenv
   TELEGRAM_ALLOWED_USER_IDS=123456789
   ```

   允许多个账号时用英文逗号分隔，例如 `123456789,987654321`。
7. 保存并退出 nano，再检查一次：

   ```bash
   .venv/bin/telegram2onedrive check
   .venv/bin/telegram2onedrive run
   ```

现在向 Bot 发送一个小文件。看到 `Uploaded ...` 后，再到 OneDrive 的
`Telegram2OneDrive` 文件夹确认文件。如果启用了 MTProto，可以再发送一个大于 20 MiB 的文件
验证大文件路径。

## 7. 设置开机自动运行

手动测试成功后，先按 `Ctrl+C` 停止程序，再运行：

```bash
mkdir -p ~/.config/systemd/user
cp deploy/telegram2onedrive.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now telegram2onedrive
sudo loginctl enable-linger "$USER"
systemctl --user status telegram2onedrive
```

看到 `Active: active (running)` 就表示服务已经运行。按 `q` 退出状态页面。

这个服务文件默认项目位于 `~/Telegram2OneDrive`。如果克隆到了其他目录，需要同步修改服务文件
中的 `WorkingDirectory` 和 `ExecStart`。

常用管理命令：

```bash
# 查看实时日志；按 Ctrl+C 退出
journalctl --user -u telegram2onedrive -f

# 重启
systemctl --user restart telegram2onedrive

# 停止
systemctl --user stop telegram2onedrive

# 再次启动
systemctl --user start telegram2onedrive
```

## 8. 以后如何更新

```bash
cd ~/Telegram2OneDrive
git pull --ff-only
.venv/bin/python -m pip install ".[mtproto]"
systemctl --user restart telegram2onedrive
systemctl --user status telegram2onedrive
```

## 常见问题

### `python3` 版本低于 3.11

不要继续安装。建议换用 Ubuntu 24.04 或 Debian 12，或者先通过发行版的正规方式安装
Python 3.11–3.13。

### `OneDrive check failed`

先运行 `rclone lsd onedrive:`。如果这里也失败，问题在 rclone 的 remote 名称或 Microsoft
授权；重新运行 `rclone config`。如果你把 remote 命名成了别的名称，需要把 `.env` 中的
`RCLONE_REMOTE=onedrive` 改成对应名称。

### Bot 没有回复

查看 `journalctl --user -u telegram2onedrive -f`。同时确认 Token 没有填错，并且没有第二个程序
使用同一个 Bot Token。Telegram 的轮询 Bot 只能由一个实例接收更新。

### 出现 `MTProto support is not installed`

在项目目录运行：

```bash
.venv/bin/python -m pip install ".[mtproto]"
systemctl --user restart telegram2onedrive
```

### 大于 20 MiB 的文件仍然失败

确认 `.env` 中的 `TELEGRAM_MTPROTO_ENABLED=true`，并检查 `TELEGRAM_API_ID`、
`TELEGRAM_API_HASH` 是否完整。然后运行 `.venv/bin/telegram2onedrive check` 查看明确错误。

### 修改 `.env` 后没有生效

服务不会自动重载配置。修改后运行：

```bash
systemctl --user restart telegram2onedrive
```

## 工作方式和默认值

- 20 MiB 以内的文件使用 Telegram Bot API；启用 MTProto 后，更大的文件自动改走 MTProto。
- 未填写 `MAX_FILE_MIB` 时，普通模式默认为 20 MiB，MTProto 模式默认为 2048 MiB。
- MTProto Session 默认保存在 `~/.local/state/telegram2onedrive/mtproto`，不需要手工配置。
- 文件按顺序传输；上传状态每 30 秒更新一次。
- 同名文件默认在扩展名前添加 ` (n)`，不会直接覆盖原文件。
- `/status` 可以检查 Bot 当前是否能访问 OneDrive remote。
- 默认只接受私聊和 `TELEGRAM_ALLOWED_USER_IDS` 中的用户。

完整配置项可以查看 [.env.example](.env.example)。Local Bot API Server 是另一种高级大文件方案，
见 [docs/local-bot-api.zh-CN.md](docs/local-bot-api.zh-CN.md)。MTProto 的工作原理和进阶设置见
[docs/mtproto.zh-CN.md](docs/mtproto.zh-CN.md)。两种大文件方案不能同时启用。

## 隐私、安全与限制

Telegram 会接收原始消息和文件；服务器会临时下载文件；rclone 会把文件和目标名称发送到
Microsoft OneDrive。项目不包含遥测。

不要提交填好的 `.env`、rclone 配置或 MTProto Session。默认关闭群组转存，因为群成员可能看到
文件名和状态消息。不要让多个进程共用同一个 Bot Token 或 MTProto Session。

Bot API 使用轮询，不支持 Webhook。OneDrive 的路径和文件大小限制仍然适用。Local Bot API 和
MTProto 的真实外部服务不会在 GitHub Actions 中连接测试，但关键路由、生命周期、清理和失败行为
有自动化测试覆盖。

安全问题请通过 [GitHub 私密漏洞报告](SECURITY.md)提交。

## 开发与许可证

开发检查见 [CONTRIBUTING.md](CONTRIBUTING.md)，更新记录见 [CHANGELOG.md](CHANGELOG.md)。
Telegram2OneDrive 使用 [MIT License](LICENSE)。
