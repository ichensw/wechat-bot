# 快速启动指南

## Windows（本地模式）

### 最快方式：双击启动

1. 安装 Python 3.11 + 微信 3.9.12.51
2. 双击 `start.bat` → 自动安装依赖 + 启动

### PowerShell 手动启动

```powershell
# 1. 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 检查微信连接
python main.py --check

# 4. 启动
python main.py
```

> 📖 详细部署教程见 [docs/windows-deployment.md](docs/windows-deployment.md)

## Mac / Linux（Mock 调试模式）

Mac/Linux 无法直接连接微信，使用 Mock 模式模拟调试：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 环境变量设置 Mock 模式
BOT_WCF_MODE=mock python main.py
```

Mock 模式会自动生成模拟群聊消息，支持终端交互输入测试消息。

## Linux 服务器（远程模式）

微信运行在 Windows 上，通过 HTTP API 转发到 Linux 服务器：

```bash
# 1. Windows 上启动 wcfhttp 服务
#    方式 A: wcfrust (Rust) - https://github.com/lich0821/wcf-client-rust
#    方式 B: go_wcf_http (Go) - 见 WeChatFerry 仓库

# 2. Linux 上编辑 config.yaml
#    bot.wcf_mode: "remote"
#    bot.wcf_remote_url: "http://Windows_IP:8080"

# 3. 启动
python main.py -c config.yaml
```

> 📖 远程模式详解见 [docs/windows-deployment.md](docs/windows-deployment.md) 中的远程部署章节

## 三种模式对比

| 模式 | 适用场景 | 微信位置 | Bot 位置 |
|------|---------|---------|---------|
| **local** | Windows 部署 | 本机 | 本机 |
| **remote** | Linux 服务器 | Windows | Linux |
| **mock** | 开发调试 | 不需要 | Mac/Linux |

## 管理员命令速查

启动后，用微信私聊机器人发送：

```
#绑定管理员          绑定自己为管理员（首次必须）
#帮助               查看所有命令
#状态               查看运行状态
#群列表              查看所有群
#过滤模式 all        监控所有群
#添加白名单 xxx@chatroom  添加群到白名单
#过滤模式 whitelist   切换到白名单模式
```
