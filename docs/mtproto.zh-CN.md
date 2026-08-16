# MTProto 大文件模式

[English](mtproto.md) · [返回中文 README](../README.zh-CN.md)

Telegram 云端 Bot API 只能让 Bot 下载不超过 20 MiB 的文件。开启 MTProto 后：

- 命令、消息更新和 20 MiB 以内的文件仍由 Bot API 处理；
- 大于 20 MiB 的文件自动改用 MTProto 下载；
- 下载完成后仍按相同规则分类，并通过 rclone 上传到 OneDrive。

程序使用同一个 Bot Token 建立 Bot Session，不会登录个人账号。项目设置的单文件上限是
2048 MiB。

## 1. 获取 API ID 和 Hash

1. 确认手机或电脑上已经登录 Telegram 官方客户端。
2. 在浏览器打开 [my.telegram.org](https://my.telegram.org)。
3. 输入 Telegram 账号的手机号码。
4. Telegram 会把验证码发到 Telegram 客户端，把验证码填回网页。
5. 点击 `API development tools`。
6. 填写表单：`App title` 可以写 `Telegram2OneDrive`；`Short name` 可以写
   `telegram2onedrive`；`URL` 允许留空时直接留空，否则填写本仓库地址；`Platform` 选择
   `Desktop` 或 `Other`；`Description` 可以写 `Telegram file transfer to OneDrive`。
7. 提交表单后记录 `api_id` 和 `api_hash`。

如果页面提示已经创建过应用，直接使用页面显示的 `api_id` 和 `api_hash` 即可。

## 2. 安装 MTProto 支持

进入 Telegram2OneDrive 的项目目录。如果还没有创建虚拟环境，先完整运行：

```bash
cd ~/Telegram2OneDrive
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install ".[mtproto]"
```

如果程序已经安装，只需要重新运行最后一条安装命令。MTProto 当前支持 Python 3.11–3.13。

## 3. 修改 `.env`

如果还没有 `.env`，先复制示例：

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

确认 Bot Token 已填写，再找到下面三项。只替换等号右边的内容，不要添加引号，也不要重复新增
同名行：

```dotenv
TELEGRAM_MTPROTO_ENABLED=true
TELEGRAM_API_ID=在这里填写api_id
TELEGRAM_API_HASH=在这里填写api_hash
```

不需要填写 `MAX_FILE_MIB` 或 Session 路径。启用 MTProto 后，程序会自动使用以下默认值：

```dotenv
MAX_FILE_MIB=2048
TELEGRAM_MTPROTO_SESSION_DIR=~/.local/state/telegram2onedrive/mtproto
TELEGRAM_MTPROTO_SESSION_NAME=telegram2onedrive
```

这里展示的是默认行为，不需要把这三行复制回 `.env`。在 nano 中按 `Ctrl+O` 保存，按回车确认，
再按 `Ctrl+X` 退出。

## 4. 检查并启动

程序会自动读取项目目录中的 `.env`：

```bash
.venv/bin/telegram2onedrive check
.venv/bin/telegram2onedrive run
```

第一次启动时，程序会自动在状态目录创建 Session。无需输入手机号，也无需进行额外的交互式登录。

先向 Bot 发送一个小文件，确认基础上传正常；再发送一个大于 20 MiB 的文件。看到
`Uploaded ...` 表示 MTProto 下载和 OneDrive 上传都已完成。

如果使用 systemd 服务，修改 `.env` 后需要重启：

```bash
systemctl --user restart telegram2onedrive
journalctl --user -u telegram2onedrive -f
```

## 常见问题

### `MTProto support is not installed`

运行 Bot 的虚拟环境中没有安装 Pyrogram。进入项目目录并运行：

```bash
.venv/bin/python -m pip install ".[mtproto]"
```

### `TELEGRAM_API_ID` 或 `TELEGRAM_API_HASH` 报错

`TELEGRAM_API_ID` 应为正整数，`TELEGRAM_API_HASH` 应为 32 位十六进制字符。检查复制时是否带入
空格、引号或其他文字。

### `session belongs to a different bot`

现有 Session 与当前 Bot Token 不匹配。先停止服务，把日志和 Session 文件保留下来进行核对，
然后为当前 Bot 配置一个新的空 Session 目录。

### `could not find the Telegram message`

确认原消息没有被删除，并且 Bot 仍能访问消息所在的私聊或群组。

### 反复出现 SQLite 锁错误

通常是有两个进程同时使用同一个 Session。停止手动运行的程序，并确认只保留一个 systemd 服务
实例。

### 大文件仍然走 Bot API 或被拒绝

确认 `TELEGRAM_MTPROTO_ENABLED=true`，然后运行：

```bash
.venv/bin/telegram2onedrive check
```

如果手工设置过 `MAX_FILE_MIB`，它必须大于 20 且不超过 2048。一般直接留空最简单。

## 进阶设置

只有在默认目录不合适时才需要修改：

```dotenv
TELEGRAM_MTPROTO_SESSION_DIR=/绝对路径/telegram2onedrive/mtproto
TELEGRAM_MTPROTO_SESSION_NAME=telegram2onedrive
MAX_FILE_MIB=2048
```

Session 目录必须是绝对路径，Session Name 只能包含字母、数字、下划线和连字符。不要让两个进程
共用同一个 Session，也不要把 Session 目录放进源码目录或临时下载目录。

MTProto 与 `TELEGRAM_LOCAL_MODE` 不能同时启用。Local Bot API Server 已经提供自己的大文件下载
路径，同一个 Bot 实例只能选择一种方案。

如需提高 MTProto 加密吞吐量，可以在相同虚拟环境中尝试安装可选的 TgCrypto：

```bash
.venv/bin/python -m pip install TgCrypto
```

TgCrypto 是原生扩展，安装失败不会影响功能。遇到不兼容的 Wheel 或编译错误时可以不安装。

## Session 和临时文件

Session 数据库包含 Bot 的 MTProto 授权信息。程序在 POSIX 系统上把 Session 目录权限限制为
`0700`，Session 文件限制为 `0600`。不要把 `.env`、Session、rclone 配置或临时下载文件提交到
Git、容器镜像或公开发布包。

Bot API 和 MTProto 下载都会使用单次传输的临时目录，并在上传尝试结束后清理。Session 是需要
保留的运行数据，不会随临时文件删除。
