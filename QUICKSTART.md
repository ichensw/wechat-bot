# 快速启动指南

## 前提条件

- **Windows 10/11**
- **Python 3.9 ~ 3.11**（3.12+ 暂不支持）
- **微信 3.9.12.51**（[下载地址](https://github.com/lich0821/WeChatFerry/releases)）
- 关闭微信自动更新（设置 → 通用设置 → 自动下载更新包 → 关闭）

## 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/ichensw/wechat-bot.git
cd wechat-bot

# 2. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 生成默认配置
python main.py --init
```

## 启动机器人

```bash
# 检查微信是否已登录
python main.py --check

# 启动机器人
python main.py

# 或直接双击 start.bat
```

## 首次使用

1. **绑定管理员**：用你的微信给机器人私聊发送 `#绑定管理员`
2. **添加白名单群**：发送 `#添加白名单 <群ID>`
3. **测试命令**：发送 `#帮助` 查看所有命令

## 常用命令速查

| 命令 | 说明 |
|------|------|
| `#帮助` | 查看所有命令 |
| `#状态` | 机器人运行状态 |
| `#群列表` | 查看所有群聊 |
| `#添加白名单 <群ID>` | 添加监控群 |
| `#私聊白名单` | 查看私聊白名单 |
| `#添加私聊白名单 <wxid>` | 添加私聊白名单 |

## 注意事项

- 本项目**仅支持 Windows 系统**，需在本地运行微信客户端
- `at_me_required: true` 表示群内只有 @机器人 才会回复（命令 `#` 开头的免@）
- 私聊只回复管理员和 `private_whitelist` 中的用户
- 修改 `config.yaml` 后会自动热更新，无需重启
