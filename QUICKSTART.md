# 快速启动指南

## Windows

双击 `start.bat` 即可启动（自动创建虚拟环境 + 安装依赖）。

或在 PowerShell 中：
```powershell
.\start.bat           # 启动机器人
.\start.bat --check   # 检查微信登录
.\start.bat --init    # 创建默认配置
```

详细部署教程见 [docs/windows-deployment.md](docs/windows-deployment.md)

## Mac / Linux（Mock 调试模式）

```bash
pip install -r requirements.txt
BOT_WCF_MODE=mock python main.py
```

## Linux 服务器（远程模式）

```bash
# 1. 在 Windows 上启动 wcfhttp 服务
# 2. 在 Linux 上配置远程 URL
python main.py -c config.yaml
```
