# Windows 部署教程

> WeChatBot v2.0 在 Windows 上的完整部署指南（本地模式 local）

---

## 📋 前置条件

| 要求 | 说明 |
|------|------|
| 操作系统 | Windows 10 / Windows 11（64位） |
| 微信版本 | **3.9.12.51**（与 wcferry v39.5.2 配套） |
| Python | 3.9 ~ 3.11（**3.12+ 暂不支持**） |
| 网络 | 能访问 PyPI（或使用国内镜像） |

> ⚠️ **免责声明**：WeChatFerry 通过注入微信进程实现功能，存在账号风险。请使用小号测试，不要用于重要账号。详见 [WeChatFerry 免责声明](https://github.com/lich0821/WeChatFerry/blob/master/WeChatFerry/DISCLAIMER.md)

---

## 第一步：安装 Python

### 1.1 下载安装

前往 https://www.python.org/downloads/ 下载 Python 3.11.x

> ⚠️ **注意**：wcferry 目前对 Python 3.12+ 支持不完整，**建议使用 Python 3.11**

安装时**务必勾选**：
```
☑ Add Python 3.11 to PATH
☑ Install pip
```

### 1.2 验证安装

打开 **PowerShell** 或 **CMD**：

```powershell
python --version
# 期望输出: Python 3.11.x

pip --version
# 期望输出: pip 2x.x from ... (python 3.11)
```

如果 `python` 命令不可用，手动添加 PATH 环境变量：

1. 右键"此电脑" → 属性 → 高级系统设置 → 环境变量
2. 在"系统变量"的 `Path` 中添加：
   ```
   C:\Users\<你的用户名>\AppData\Local\Programs\Python\Python311\
   C:\Users\<你的用户名>\AppData\Local\Programs\Python\Python311\Scripts\
   ```
3. 重新打开 PowerShell 验证

---

## 第二步：安装指定版本微信

WeChatFerry 对微信版本有**严格要求**，版本不匹配会导致注入失败。当前 wcferry v39.5.2 配套微信版本为 **3.9.12.51**。

### 2.1 下载指定版本微信

WeChatFerry 官方在 GitHub Releases 提供了配套的微信安装包：

👉 https://github.com/lich0821/WeChatFerry/releases

在 Assets 中找到并下载 `WeChatSetup-3.9.12.51.exe`

> 💡 如果 GitHub 访问慢，可以使用镜像站或搜索 "微信 3.9.12.51 安装包" 下载

### 2.2 卸载当前微信（如果已安装）

1. **完全退出微信**（右键托盘图标 → 退出）
2. 打开"设置" → "应用" → 找到微信 → 点击"卸载"
3. 确认卸载完成

### 2.3 安装指定版本微信

1. 双击运行下载的 `WeChatSetup-3.9.12.51.exe`
2. 按照向导完成安装
3. **启动微信并登录**

### 2.4 关闭微信自动更新（关键！）

微信自动更新会导致版本不匹配，必须关闭：

**方法 1：微信内设置**
1. 打开微信 → 左下角三条横线 → 设置
2. 通用设置 → 取消勾选"自动更新微信"

**方法 2：修改配置文件（推荐，更可靠）**

微信更新配置文件路径：
```
C:\Users\<用户名>\AppData\Roaming\Tencent\WeChat\config\update.cfg
```

如果没有此文件，创建一个 `update.cfg` 文件，内容为：
```ini
[update]
auto_update=0
```

**方法 3：防火墙拦截（最保险）**

1. 打开"Windows Defender 防火墙" → "高级设置"
2. 出站规则 → 新建规则
3. 程序 → 浏览找到 `C:\Program Files (x86)\Tencent\WeChat\WeChatUpdater.exe`
4. 选择"阻止连接"
5. 完成

### 2.5 确认微信版本

打开微信 → 左下角三条横线 → 设置 → 关于微信，确认版本号为 **3.9.12.51**

> 💡 如果版本号不是 3.9.12.51，说明微信已自动更新，需要重新执行步骤 2.2 ~ 2.4

---

## 第三步：获取项目代码

### 方式 A：Git 克隆（推荐）

```powershell
# 安装 Git（如果没有）
# 前往 https://git-scm.com/download/win 下载安装

# 克隆项目到 D 盘
git clone https://github.com/ichensw/wechat-bot.git D:\wechat-bot
cd D:\wechat-bot
```

### 方式 B：直接下载

1. 打开 https://github.com/ichensw/wechat-bot
2. 点击绿色 "Code" 按钮 → "Download ZIP"
3. 解压到 `D:\wechat-bot\`

### 验证目录结构

```powershell
cd D:\wechat-bot
dir
# 应看到: main.py, config.yaml, requirements.txt, bot\, start.bat 等
```

---

## 第四步：安装 Python 依赖

### 4.1 创建虚拟环境

```powershell
cd D:\wechat-bot

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境（PowerShell）
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 报错 `无法加载文件...因为在此系统上禁止运行脚本`：

```powershell
# 临时允许（仅当前会话）
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 或永久允许（推荐，只需执行一次）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

激活成功后，命令行前面会显示 `(.venv)` 前缀：
```
(.venv) PS D:\wechat-bot>
```

### 4.2 安装依赖包

```powershell
# 使用国内镜像加速（推荐）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 如果清华镜像不可用，尝试阿里云镜像
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

依赖列表：
```
wcferry>=39.5.2      # WeChatFerry SDK（核心依赖）
pyyaml>=6.0          # YAML 配置解析
flask>=3.0           # WebHook HTTP 服务
apscheduler>=3.10    # 定时任务调度
requests>=2.28       # HTTP 客户端（远程模式）
cryptography>=41.0   # 加密库
```

### 4.3 验证 wcferry 安装

```powershell
python -c "from wcferry import Wcf; print('✅ wcferry 安装成功')"
```

如果报错 `ModuleNotFoundError`：
```powershell
# 确认在虚拟环境中
pip list | findstr wcferry

# 重新安装
pip install wcferry==39.5.2.0 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 第五步：配置机器人

### 5.1 编辑配置文件

```powershell
# 使用记事本
notepad config.yaml

# 或使用 VS Code
code config.yaml
```

### 5.2 关键配置项说明

```yaml
bot:
  name: "WeChatBot"
  admin_wxid: null              # 先留空，启动后通过 #绑定管理员 命令绑定
  command_prefix: "#"           # 管理员命令前缀，可自定义（如 "!" "/"）
  wcf_mode: "local"             # ★ Windows 本地模式，必须为 local
  wcf_remote_url: ""            # 本地模式留空

group_filter:
  mode: "all"                   # ★ 初始建议设为 all，监控所有群
  whitelist: []                  # 白名单群 ID 列表（mode=whitelist 时生效）
  blacklist: []                  # 黑名单群 ID 列表（mode=blacklist 时生效）
  # 群 ID 格式: xxxxx@chatroom，启动后可通过 #群列表 查看

monitor:
  member_count: true             # 监控群人数变化
  member_count_interval: 300     # 检查间隔（秒），建议 300~600
  message: true                  # 记录群消息到数据库
  message_types: []              # 空=记录所有类型；也可指定：[1, 3] 只记录文本和图片
  alert_member_change: true      # 人数变动超过阈值时通知管理员
  member_change_threshold: 5    # 变动超过 N 人时告警
  group_cache_ttl: 600          # 群信息缓存刷新间隔（秒）

webhook:
  enabled: true                  # 开启 WebHook HTTP API
  host: "127.0.0.1"             # 仅本机访问（安全）
  port: 8080                     # API 端口
  token: "你的安全密钥"           # ★★ 必须修改！否则不安全
  rate_limit: 60                 # 每分钟每 IP 最大请求数
  cors_origins: []               # CORS 允许来源（一般留空）

database:
  path: "data/wechat_bot.db"    # SQLite 数据库路径
  wal_mode: true                 # WAL 模式（提升并发性能）
  busy_timeout: 5000             # 数据库锁等待超时（毫秒）

logging:
  level: "INFO"                  # 日志级别：DEBUG / INFO / WARNING / ERROR
  file: "data/wechat_bot.log"   # 日志文件（null=仅控制台）
  max_size_mb: 10                # 单个日志文件最大 MB
  backup_count: 5                # 保留的日志备份数
```

### 5.3 生成 WebHook Token

**务必修改默认 token**，否则任何人都能调用你的 WebHook API：

```powershell
# PowerShell 生成 32 位随机 token
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | % {[char]$_})

# 示例输出: aB3kX9mN2pQ7rS4tU1vW8yZ5
```

将生成的字符串填入 `webhook.token`。

---

## 第六步：启动机器人

### 6.1 使用启动脚本（最简单）

双击 `start.bat` 即可自动创建虚拟环境、安装依赖、启动机器人。

### 6.2 手动启动

```powershell
# 1. 以管理员身份打开 PowerShell
#    右键开始菜单 → "终端(管理员)" 或 "Windows PowerShell(管理员)"

# 2. 进入项目目录
cd D:\wechat-bot

# 3. 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 4. 确认微信已打开并登录

# 5. 检查微信连接
python main.py --check
```

期望输出：
```
✅ WeChat is logged in!
   wxid:  wxid_xxxxxxxx
   name:  你的微信名
   mode:  local (direct wcferry)
```

如果提示 `❌ WeChat is NOT logged in`：
- ✅ 确认微信已打开并登录
- ✅ 确认微信版本为 3.9.12.51
- ✅ 确认以**管理员权限**运行 PowerShell
- ✅ 尝试重启微信后重新检查

### 6.3 正式启动

```powershell
python main.py
```

启动成功输出：
```
============================================================
  WeChatBot v2.0.0 starting...
============================================================
LocalWcfClient: Connected to WeChat via wcferry
Logged in as: 你的微信名 (wxid_xxxxxxxx)
Initial group scan: 15 groups found
Group filter: 模式: 全部群聊 (不过滤)
WebHook: http://127.0.0.1:8080/api/
Task scheduler started with 4 tasks
============================================================
  WeChatBot is running! Press Ctrl+C to stop.
============================================================
```

### 6.4 验证 Bot 工作

启动后，用另一个微信号给你的机器人微信号（登录的那个）发送私聊消息：

```
#绑定管理员
```

成功回复：
```
✅ 管理员绑定成功: 你的微信名 (wxid_xxxxxxxx)
```

然后发送：
```
#帮助
```

可以看到所有可用命令。

### 6.5 停止机器人

按 `Ctrl+C` 停止。Bot 会自动执行清理（停止消息接收、关闭数据库、断开 WCF）。

---

## 第七步：管理员命令使用

绑定管理员后，通过微信私聊发送命令（前缀默认 `#`）：

### 基础命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `#绑定管理员` | 绑定自己为管理员（仅一个） | `#绑定管理员` |
| `#解绑管理员` | 解绑当前管理员 | `#解绑管理员` |
| `#帮助` | 显示所有命令 | `#帮助` |
| `#帮助` / `#help` | 帮助（别名） | `#help` |

### 状态查询

| 命令 | 说明 | 示例 |
|------|------|------|
| `#状态` | 查看机器人状态 | `#状态` |
| `#群列表` | 查看所有群聊 | `#群列表` |
| `#群概要` | 查看群聊详情 | `#群概要 123456@chatroom` |
| `#监控列表` | 查看过滤状态 | `#监控列表` |
| `#刷新群` | 从微信刷新群信息 | `#刷新群` |

### 群过滤管理

| 命令 | 说明 | 示例 |
|------|------|------|
| `#过滤模式` | 设置过滤模式 | `#过滤模式 all` |
| `#添加白名单` | 添加群到白名单 | `#添加白名单 123456@chatroom` |
| `#移除白名单` | 从白名单移除 | `#移除白名单 123456@chatroom` |
| `#添加黑名单` | 添加群到黑名单 | `#添加黑名单 123456@chatroom` |
| `#移除黑名单` | 从黑名单移除 | `#移除黑名单 123456@chatroom` |

> 💡 群 ID 格式为 `数字@chatroom`，可通过 `#群列表` 查看所有群的 ID

### 典型使用流程

```
1. #绑定管理员          ← 绑定自己
2. #群列表              ← 查看所有群
3. #过滤模式 all        ← 先监控所有群
4. #群概要 xxx@chatroom ← 查看某个群的详情
5. #添加白名单 xxx@chatroom ← 把关注的群加入白名单
6. #过滤模式 whitelist   ← 切换到白名单模式，只监控关注的群
```

---

## 第八步：验证 WebHook API

机器人启动后，WebHook API 在 `http://127.0.0.1:8080` 可用。

### 8.1 健康检查（无需认证）

```powershell
# PowerShell
Invoke-RestMethod http://127.0.0.1:8080/api/health

# 期望返回：
# status  timestamp          version
# ------  ---------          -------
# ok      1718456789.123     2.0.0
```

### 8.2 向指定群发消息

```powershell
$token = "你的webhook-token"
$headers = @{ "Authorization" = "Bearer $token" }

$body = @{
    room_id = "xxxxx@chatroom"
    content = "Hello from WebHook API!"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8080/api/send_group" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

### 8.3 给管理员发消息

```powershell
$body = @{ content = "⚠️ 这是一条告警通知" } | ConvertTo-Json

Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8080/api/send_admin" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

### 8.4 查询消息记录

```powershell
# 查询最近 10 条消息
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/messages?limit=10" -Headers $headers

# 查询指定群的消息
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/messages?room_id=xxx@chatroom&limit=20" -Headers $headers
```

### 8.5 查看机器人状态

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/status" -Headers $headers
```

### 8.6 使用 curl 测试（如果已安装）

```bash
# 健康检查
curl http://127.0.0.1:8080/api/health

# 发送消息
curl -X POST http://127.0.0.1:8080/api/send_group \
  -H "Authorization: Bearer 你的token" \
  -H "Content-Type: application/json" \
  -d '{"room_id":"xxx@chatroom","content":"Hello!"}'

# 查询消息
curl -H "Authorization: Bearer 你的token" \
  "http://127.0.0.1:8080/api/messages?limit=10"
```

---

## 第九步：设置开机自启（可选）

### 方式 A：Windows 任务计划程序

1. 按 `Win+R`，输入 `taskschd.msc`，回车
2. 右侧点击"创建基本任务"
3. 名称填：`WeChatBot`
4. 触发器选：**计算机启动时**
5. 操作选：**启动程序**
   - 程序或脚本：`D:\wechat-bot\.venv\Scripts\pythonw.exe`
   - 添加参数：`main.py`
   - 起始于：`D:\wechat-bot`
6. 勾选 **"使用最高权限运行"**
7. 完成

> 💡 使用 `pythonw.exe`（无窗口）而非 `python.exe`，避免弹出黑色控制台窗口

### 方式 B：启动文件夹（简单）

按 `Win+R`，输入 `shell:startup`，回车打开启动文件夹。

创建 `wechat-bot.bat`：

```batch
@echo off
chcp 65001 >nul
cd /d D:\wechat-bot
call .venv\Scripts\activate.bat
python main.py
```

### 方式 C：NSSM 注册为 Windows 服务（推荐，最稳定）

```powershell
# 1. 下载 NSSM: https://nssm.cc/download
# 2. 将 nssm.exe 放到 PATH 目录或当前目录

# 3. 安装服务
nssm install WeChatBot

# 会弹出 GUI 配置窗口，填写：
#   Application → Path:     D:\wechat-bot\.venv\Scripts\python.exe
#   Application → Arguments: main.py
#   Application → Startup directory: D:\wechat-bot
#   I/O → Output:   D:\wechat-bot\data\service_stdout.log
#   I/O → Error:    D:\wechat-bot\data\service_stderr.log

# 4. 启动服务
nssm start WeChatBot

# 5. 常用命令
nssm status WeChatBot    # 查看状态
nssm stop WeChatBot      # 停止
nssm restart WeChatBot   # 重启
nssm remove WeChatBot    # 卸载（需先停止）
```

### 方式 D：使用 start.bat 后台运行

```powershell
# 使用 pythonw 无窗口运行
D:\wechat-bot\.venv\Scripts\pythonw.exe D:\wechat-bot\main.py
```

---

## 🔧 常见问题排查

### Q1: 启动报错 `wcferry package not installed`

```powershell
# 确认在虚拟环境中（命令行前有 (.venv)）
.\.venv\Scripts\Activate.ps1

# 重新安装
pip install wcferry==39.5.2.0 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q2: 启动报错 `WeChat is not logged in`

排查顺序：
1. ✅ 微信是否已打开并登录？（必须保持窗口打开）
2. ✅ 微信版本是否为 3.9.12.51？（设置 → 关于微信 查看）
3. ✅ 是否以管理员权限运行？（wcferry 需要注入进程）
4. ✅ 微信是否已自动更新？（如果版本变了，重新安装 3.9.12.51）
5. ✅ 尝试重启微信 → 重新运行 `python main.py --check`

### Q3: 微信版本不匹配（已自动更新）

```powershell
# 检查当前 wcferry 版本
pip show wcferry

# 最新 wcferry 版本和配套微信
# wcferry v39.5.2 → 微信 3.9.12.51
# wcferry v39.4.0 → 微信 3.9.12.17
# wcferry v39.3.0 → 微信 3.9.11.25
```

**解决方法**：
1. 卸载当前微信
2. 重新安装配套版本的微信（见第二步）
3. 关闭自动更新（见 2.4）

### Q4: Bot 启动后收不到消息

1. 检查 `group_filter.mode`，默认 `whitelist` 模式下如果白名单为空，则**没有任何群被监控**
2. 用微信发送 `#过滤模式 all` 切换到监控所有群
3. 发送 `#状态` 查看当前过滤模式和消息数
4. 确认 `monitor.message` 设为 `true`

### Q5: WebHook 返回 401/403

1. 请求头必须包含 `Authorization: Bearer <token>`
2. Token 必须与 `config.yaml` 中 `webhook.token` 完全一致
3. `/api/health` 端点**不需要**认证，可用来测试服务是否启动

### Q6: PowerShell 执行策略报错

```powershell
# 报错内容：无法加载文件...因为在此系统上禁止运行脚本

# 临时允许（仅当前会话有效）
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 永久允许（推荐，只需执行一次）
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

或者直接用 CMD 代替 PowerShell：
```cmd
cd D:\wechat-bot
.venv\Scripts\activate.bat
python main.py
```

### Q7: 终端中文乱码

```powershell
# CMD 中设置 UTF-8 编码
chcp 65001

# PowerShell 中设置
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

### Q8: `pip install` 下载慢或超时

```powershell
# 使用国内镜像（清华源）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 阿里云源
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 豆瓣源
pip install -r requirements.txt -i https://pypi.doubanio.com/simple/
```

### Q9: Bot 运行一段时间后断连

wcferry 依赖微信进程，微信如果崩溃或更新会导致断连：

1. 确认微信自动更新已关闭（见 2.4）
2. 查看日志：`type data\wechat_bot.log` 或用记事本打开
3. Bot 会自动进入 DEGRADED 状态并尝试恢复
4. 如果微信崩溃，重启微信后再重启 Bot

### Q10: 管理员命令无响应

1. 确认已绑定管理员（`#状态` 查看是否有管理员）
2. 命令必须通过**私聊**发送（不是群聊）
3. 命令前缀必须与 `config.yaml` 中 `command_prefix` 一致（默认 `#`）
4. 确认发送者的 wxid 与绑定的 admin_wxid 一致

---

## 📂 数据文件位置

| 文件 | 路径 | 说明 |
|------|------|------|
| 数据库 | `D:\wechat-bot\data\wechat_bot.db` | SQLite 消息和群数据 |
| 日志 | `D:\wechat-bot\data\wechat_bot.log` | 运行日志（自动轮转） |
| 配置 | `D:\wechat-bot\config.yaml` | 运行时热更新配置 |
| 服务日志 | `D:\wechat-bot\data\service_*.log` | NSSM 服务的输出日志 |

💡 用 [DB Browser for SQLite](https://sqlitebrowser.org/) 可以可视化查看数据库内容。

---

## 📊 wcferry 版本与微信版本对照表

| wcferry 版本 | 配套微信版本 | 发布日期 |
|-------------|------------|---------|
| **v39.5.2** (最新) | **3.9.12.51** | 2026-03-28 |
| v39.5.0 | 3.9.12.51 | - |
| v39.4.0 | 3.9.12.17 | - |
| v39.3.0 | 3.9.11.25 | - |
| v39.2.0 | 3.9.10.27 | - |

> 版本号规则：`w.x.y.z`，其中 `w` = 微信大版本(39=3.9.x)，`x` = 微信小版本序号，`y` = wcferry 版本，`z` = 客户端版本

---

## 🛡️ 安全提醒

1. **WebHook Token** 必须修改为强随机字符串，**不要使用默认值**
2. 如果不需要外部访问 WebHook，`host` 设为 `127.0.0.1`（仅本机）
3. 如果需要外部访问，配合 Windows 防火墙规则限制来源 IP
4. 数据库包含群聊消息内容，注意数据隐私
5. **不要在公网直接暴露 WebHook 端口**，如需外网访问请配置反向代理
6. 建议使用**小号**运行 Bot，避免主号被风控
7. 微信有风控机制，不要短时间内大量发送消息

---

## 📝 完整启动流程速查

```powershell
# ═══ 前提 ═══
# 微信已安装 3.9.12.51 版本，已登录，已关闭自动更新

# 1. 管理员打开 PowerShell
# 2. 进入项目
cd D:\wechat-bot

# 3. 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 4. 检查连接
python main.py --check

# 5. 启动
python main.py

# 6. 用微信私聊: #绑定管理员
# 7. 用微信私聊: #帮助
# 8. Ctrl+C 停止
```

---

## 🔗 相关链接

| 资源 | 链接 |
|------|------|
| 本项目仓库 | https://github.com/ichensw/wechat-bot |
| WeChatFerry 官方 | https://github.com/lich0821/WeChatFerry |
| wcferry Python 文档 | https://wechatferry.readthedocs.io/ |
| WeChatRobot 示例 | https://github.com/lich0821/WeChatRobot |
| wcferry Releases | https://github.com/lich0821/WeChatFerry/releases |
| 微信安装包下载 | 见 Releases 页面 Assets |
| wcfrust (HTTP服务) | https://github.com/lich0821/wcf-client-rust |
| go_wcf_http (HTTP服务) | https://github.com/lich0821/WeChatFerry/tree/master/clients/go_wcf_http |
