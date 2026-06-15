# Windows 部署教程

> WeChatBot v2.0 在 Windows 上的完整部署指南（本地模式 local）

---

## 📋 前置条件

| 要求 | 说明 |
|------|------|
| 操作系统 | Windows 10 / Windows 11（64位） |
| 微信版本 | 需要特定版本，与 wcferry 匹配（见下方） |
| Python | 3.9 ~ 3.11（**3.12+ 暂不支持**） |
| 网络 | 能访问 PyPI（或使用国内镜像） |

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

如果 `python` 命令不可用，检查 PATH 环境变量是否包含：
```
C:\Users\<你的用户名>\AppData\Local\Programs\Python\Python311\
C:\Users\<你的用户名>\AppData\Local\Programs\Python\Python311\Scripts\
```

---

## 第二步：安装微信（指定版本）

WeChatFerry 对微信版本有严格要求，版本不匹配会注入失败。

### 2.1 查看当前 wcferry 支持的微信版本

```powershell
pip install wcferry
python -c "import wcferry; print(wcferry.__version__)"
```

前往 WeChatFerry 官方仓库查看适配的微信版本：
- https://github.com/nicepkg/WeChatFerry

> 📌 **重要**：每次 wcferry 更新可能适配不同的微信版本，务必查看官方说明。

### 2.2 安装/降级微信

如果当前微信版本不匹配：

1. **完全卸载**当前微信（控制面板 → 卸载程序）
2. 删除微信数据目录（可选，建议备份）：
   ```
   C:\Users\<用户名>\Documents\WeChat Files\
   ```
3. 下载对应版本的微信安装包
4. 安装后**关闭自动更新**：
   - 微信设置 → 通用设置 → 取消勾选"自动更新"

### 2.3 登录微信

启动微信并登录，**保持微信窗口打开**（不要最小化到托盘）。

---

## 第三步：获取项目代码

### 方式 A：Git 克隆

```powershell
# 安装 Git（如果没有）
# 前往 https://git-scm.com/download/win 下载

# 克隆项目
git clone <你的仓库地址> D:\wechat-bot
cd D:\wechat-bot
```

### 方式 B：直接下载

将项目文件复制到 `D:\wechat-bot\` 目录。

### 项目目录结构验证

```powershell
dir D:\wechat-bot
# 应看到: main.py, config.yaml, requirements.txt, bot\ 目录等
```

---

## 第四步：安装 Python 依赖

### 4.1 创建虚拟环境（推荐）

```powershell
cd D:\wechat-bot

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 如果 PowerShell 报错"执行策略"，先运行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# 然后重新激活
.\.venv\Scripts\Activate.ps1
```

激活后，命令行前面会显示 `(.venv)` 前缀。

### 4.2 安装依赖包

```powershell
# 使用国内镜像加速（推荐）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或使用默认源
pip install -r requirements.txt
```

依赖列表：
```
wcferry>=39.2.4     # WeChatFerry SDK
pyyaml>=6.0         # YAML 配置解析
flask>=3.0          # WebHook HTTP 服务
apscheduler>=3.10   # 定时任务调度
requests>=2.28      # HTTP 客户端
cryptography>=41.0  # 加密库
```

### 4.3 验证 wcferry 安装

```powershell
python -c "from wcferry import Wcf; print('wcferry 安装成功')"
```

如果报错，尝试指定版本：
```powershell
pip install wcferry==39.2.4 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 第五步：配置机器人

### 5.1 编辑配置文件

```powershell
# 使用记事本打开
notepad config.yaml

# 或使用 VS Code
code config.yaml
```

### 5.2 关键配置项

```yaml
bot:
  name: "WeChatBot"
  admin_wxid: null              # 先留空，启动后通过命令绑定
  command_prefix: "#"           # 命令前缀
  wcf_mode: "local"             # ★ Windows 本地模式，不要改
  wcf_remote_url: ""            # 本地模式留空

group_filter:
  mode: "all"                   # ★ 初始设为 all 监控所有群，后续可改
  whitelist: []
  blacklist: []

monitor:
  member_count: true
  member_count_interval: 300     # 5 分钟检查一次成员数
  message: true                  # ★ 开启消息记录
  message_types: []              # 空=记录所有类型
  alert_member_change: true
  member_change_threshold: 5
  group_cache_ttl: 600

webhook:
  enabled: true                  # ★ 开启 WebHook API
  host: "127.0.0.1"             # 仅本机访问（安全）
  port: 8080
  token: "你的安全密钥"           # ★★ 必须修改！自定义一个随机字符串
  rate_limit: 60
  cors_origins: []

database:
  path: "data/wechat_bot.db"    # 数据库文件路径
  wal_mode: true
  busy_timeout: 5000

logging:
  level: "INFO"
  file: "data/wechat_bot.log"   # 日志文件
  max_size_mb: 10
  backup_count: 5
```

### 5.3 WebHook Token 生成

建议使用随机字符串作为 token：

```powershell
# PowerShell 生成随机 token
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | % {[char]$_})
```

将生成的字符串填入 `webhook.token`。

---

## 第六步：启动机器人

### 6.1 确认微信已登录

```powershell
# 确保虚拟环境已激活
.\.venv\Scripts\Activate.ps1

# 检查微信登录状态
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
- 确认微信已打开并登录
- 确认微信版本与 wcferry 匹配
- 尝试以**管理员权限**运行 PowerShell

### 6.2 正式启动

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

### 6.3 管理员权限问题

如果启动时报错 `wcferry` 相关错误：

1. **以管理员身份运行 PowerShell**
2. 右键 PowerShell → "以管理员身份运行"
3. 重新执行启动命令

---

## 第七步：绑定管理员

机器人启动后，用你的微信**私聊机器人微信号**发送：

```
#绑定管理员
```

成功后回复：
```
✅ 管理员绑定成功: 你的微信名 (wxid_xxxxxxxx)
```

之后可以发送 `#帮助` 查看所有命令：

```
#帮助                显示所有命令
#状态                查看机器人状态
#群列表              查看所有群聊
#监控列表            查看过滤状态
#群概要 <群ID>       查看群聊详情
#添加白名单 <群ID>   添加群到白名单
#过滤模式 whitelist  设置过滤模式
...
```

---

## 第八步：验证 WebHook API

机器人启动后，WebHook API 在 `http://127.0.0.1:8080` 可用。

### 8.1 健康检查

```powershell
# 无需认证
curl http://127.0.0.1:8080/api/health

# 如果没有 curl，用 PowerShell
Invoke-RestMethod http://127.0.0.1:8080/api/health
```

### 8.2 向群发消息

```powershell
$headers = @{ "Authorization" = "Bearer 你的token" }
$body = @{
    room_id = "xxxxx@chatroom"
    content = "Hello from WebHook!"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/send_group" -Headers $headers -ContentType "application/json" -Body $body
```

### 8.3 给管理员发消息

```powershell
$body = @{ content = "⚠️ 告警通知" } | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/send_admin" -Headers $headers -ContentType "application/json" -Body $body
```

### 8.4 查询消息

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/messages?limit=10" -Headers $headers
```

---

## 第九步：设置开机自启（可选）

### 方式 A：Windows 任务计划程序

1. 打开"任务计划程序"（Win+R → `taskschd.msc`）
2. 点击"创建基本任务"
3. 名称：`WeChatBot`
4. 触发器：计算机启动时
5. 操作：启动程序
   - 程序：`D:\wechat-bot\.venv\Scripts\python.exe`
   - 参数：`main.py`
   - 起始于：`D:\wechat-bot`
6. 勾选"使用最高权限运行"
7. 完成

### 方式 B：启动文件夹

创建 `C:\Users\<用户名>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\wechat-bot.bat`：

```batch
@echo off
cd /d D:\wechat-bot
call .venv\Scripts\activate.bat
python main.py
pause
```

### 方式 C：NSSM 服务（推荐，最稳定）

```powershell
# 下载 NSSM: https://nssm.cc/download
# 安装为 Windows 服务
nssm install WeChatBot D:\wechat-bot\.venv\Scripts\python.exe "main.py"
nssm set WeChatBot AppDirectory D:\wechat-bot
nssm set WeChatBot DisplayName "WeChat Bot Service"
nssm set WeChatBot Start SERVICE_AUTO_START
nssm set WeChatBot AppStdout D:\wechat-bot\data\service_stdout.log
nssm set WeChatBot AppStderr D:\wechat-bot\data\service_stderr.log

# 启动服务
nssm start WeChatBot

# 查看状态
nssm status WeChatBot

# 停止服务
nssm stop WeChatBot

# 卸载服务
nssm remove WeChatBot confirm
```

---

## 🔧 常见问题排查

### Q1: 启动报错 `wcferry package not installed`

```powershell
# 确认在虚拟环境中
.\.venv\Scripts\Activate.ps1

# 重新安装
pip install wcferry -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q2: 启动报错 `WeChat is not logged in`

1. 确认微信已打开并登录
2. 确认微信版本匹配（查看 wcferry 文档）
3. 以管理员权限运行
4. 尝试重启微信后重新启动 Bot

### Q3: 微信版本不匹配

```powershell
# 查看当前 wcferry 版本
pip show wcferry

# 升级到最新
pip install --upgrade wcferry

# 如果新版适配的微信版本不同，需要降级/升级微信
```

### Q4: Bot 启动后收不到消息

1. 检查 `group_filter.mode` 是否设为 `all`（默认 whitelist 模式下无群被监控）
2. 发送 `#过滤模式 all` 切换到监控所有群
3. 发送 `#状态` 查看当前状态

### Q5: WebHook 访问 401/403

1. 确认请求头包含 `Authorization: Bearer <token>`
2. Token 必须与 `config.yaml` 中的 `webhook.token` 一致
3. `/api/health` 端点不需要认证

### Q6: 微信自动更新导致 Bot 失效

1. 关闭微信自动更新：设置 → 通用 → 取消自动更新
2. 如果已更新，需要降级微信版本
3. 或等待 wcferry 更新适配新版

### Q7: PowerShell 执行策略报错

```powershell
# 临时允许脚本执行
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 或永久允许（需管理员）
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Q8: 编码问题（中文乱码）

```powershell
# 设置终端编码为 UTF-8
chcp 65001

# PowerShell 中设置
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

---

## 📂 数据文件位置

| 文件 | 路径 | 说明 |
|------|------|------|
| 数据库 | `D:\wechat-bot\data\wechat_bot.db` | SQLite 消息和群数据 |
| 日志 | `D:\wechat-bot\data\wechat_bot.log` | 运行日志 |
| 配置 | `D:\wechat-bot\config.yaml` | 运行时热更新配置 |

可以用 [DB Browser for SQLite](https://sqlitebrowser.org/) 查看数据库内容。

---

## 🛡️ 安全提醒

1. **WebHook Token** 必须修改为强随机字符串，不要使用默认值
2. 如果不需要外部访问 WebHook，`host` 设为 `127.0.0.1`
3. 如果需要外部访问，配合防火墙规则限制来源 IP
4. 数据库包含群聊消息，注意数据隐私
5. 不要在公网直接暴露 WebHook 端口

---

## 📝 完整启动流程速查

```powershell
# 1. 打开 PowerShell（管理员）
# 2. 进入项目目录
cd D:\wechat-bot

# 3. 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 4. 确认微信已登录

# 5. 检查连接
python main.py --check

# 6. 启动
python main.py

# 7. 用微信私聊发: #绑定管理员
# 8. 用微信私聊发: #帮助
# 9. Ctrl+C 停止
```
