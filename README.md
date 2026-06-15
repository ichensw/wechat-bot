# WeChatBot v2.0

基于 [WeChatFerry](https://github.com/lich0821/WeChatFerry) 的生产级微信监控机器人，仅支持 Windows 系统。

## ✨ 功能

| 功能 | 说明 |
|------|------|
| 🎯 **群聊黑白名单** | 支持 whitelist / blacklist / all 三种过滤模式，运行时可动态修改 |
| 👥 **群成员监控** | 人数变动检测、消息记录、活跃度统计、数据持久化到 SQLite |
| 👑 **管理员绑定** | 仅支持绑定一个管理员，通过微信私聊发送命令控制机器人 |
| 🪝 **WebHook API** | HTTP API 支持向指定群发消息、给管理员发消息、查询群聊数据 |
| 🔄 **热更新配置** | 修改 config.yaml 后自动生效，无需重启 |
| 🏗️ **可扩展架构** | Handler Pipeline + Event Bus + Command Registry，新增功能只需添加 Handler |
| 🔒 **私聊白名单** | 只有管理员和私聊白名单用户可与机器人私聊 |
| 📢 **@机器人触发** | 群内只有 @机器人 才会回复（命令免@） |
| 🔁 **并发安全** | ThreadSafeSender 保证消息发送线程安全 + 限流 |

## 📁 项目架构

```
wechat-bot/
├── main.py                    # CLI 入口
├── start.bat                  # Windows 一键启动脚本
├── config.yaml                # 配置文件
├── requirements.txt           # Python 依赖
├── pyproject.toml             # 项目元数据 & 工具配置
│
├── bot/
│   ├── __init__.py            # 版本号
│   ├── core/                  # 核心层
│   │   ├── exceptions.py      # 异常层级（15个异常类型）
│   │   ├── event_bus.py       # 事件总线（发布/订阅/前缀匹配/异步）
│   │   ├── sender.py          # ThreadSafeSender（并发安全 + 限流）
│   │   ├── app.py             # 应用上下文（DI 容器）
│   │   └── bot.py             # 机器人主类（状态机 + 生命周期）
│   │
│   ├── config/                # 配置层
│   │   ├── settings.py        # Pydantic 风格数据类（验证 + 环境变量覆盖）
│   │   └── loader.py          # 配置加载器（YAML + SHA256 热更新）
│   │
│   ├── wcf/                   # WCF 抽象层
│   │   ├── models.py          # 数据模型（WxMessage, Contact, GroupInfo）
│   │   └── client.py          # LocalWcfClient（wcferry 直连）
│   │
│   ├── handlers/              # 处理器层
│   │   ├── base.py            # BaseHandler ABC + HandlerPriority + HandlerResult
│   │   ├── registry.py        # 处理器注册表（优先级排序/启用禁用）
│   │   ├── pipeline.py        # 处理器管线（优先级执行 + 钩子 + 指标）
│   │   └── group_message.py   # 群消息/私聊消息/系统消息处理器
│   │
│   ├── group/                 # 群组模块
│   │   ├── filter.py          # 群聊黑白名单（运行时修改 + 持久化）
│   │   ├── monitor.py         # 群成员监控（人数检测/消息存储/变动告警）
│   │   └── cache.py           # 群信息缓存（TTL 过期/线程安全）
│   │
│   ├── admin/                 # 管理员模块
│   │   ├── commands.py        # 命令注册表（装饰器自注册/别名/权限）
│   │   └── manager.py         # 管理员管理（绑定/解绑/命令分发）
│   │
│   ├── db/                    # 数据层
│   │   ├── manager.py         # 数据库连接管理（WAL/线程安全/迁移）
│   │   └── repository.py      # 数据仓库（消息存储/成员快照/统计/清理）
│   │
│   ├── webhook/               # WebHook 模块
│   │   ├── server.py          # Flask HTTP 服务器
│   │   ├── routes.py          # API 路由（RESTful + 蓝图）
│   │   └── middleware.py      # 中间件（认证/限流/CORS/日志/错误处理）
│   │
│   ├── scheduler/             # 调度模块
│   │   └── manager.py         # 定时任务（APScheduler/间隔+定时/重试）
│   │
│   └── utils/                 # 工具层
│       ├── logger.py          # 日志（结构化/上下文注入/文件轮转）
│       ├── retry.py           # 重试（指数退避+抖动）
│       └── rate_limit.py      # 限流（令牌桶+滑动窗口）
│
├── tests/                     # 测试
│   ├── conftest.py            # 公共 fixtures
│   ├── test_config.py         # 配置验证测试
│   ├── test_models.py         # 数据模型测试
│   ├── test_commands.py       # 命令注册表测试
│   ├── test_event_bus.py      # 事件总线测试
│   ├── test_group_filter.py   # 群过滤测试
│   └── test_at_mention.py     # @提及 + 私聊白名单测试
│
└── docs/
    └── windows-deployment.md # Windows 完整部署教程
```

## 🚀 快速开始

### 环境要求

- **Windows 10/11**
- **Python 3.9 ~ 3.11**（3.12+ 暂不支持）
- **微信 3.9.12.51**（与 wcferry v39.5.2 配套）

### 安装

```bash
# 克隆项目
git clone https://github.com/ichensw/wechat-bot.git && cd wechat-bot

# 安装依赖（使用国内镜像加速）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 生成默认配置
python main.py --init

# 编辑配置（⚠️ 务必修改 webhook.token）
notepad config.yaml
```

### 启动

```bash
# 检查微信登录状态
python main.py --check

# 启动机器人
python main.py

# 使用自定义配置
python main.py -c C:\wechat-bot\config.yaml

# 或直接双击 start.bat 一键启动
```

## ⚙️ 配置说明

```yaml
bot:
  name: "WeChatBot"
  admin_wxid: null              # 管理员 wxid，通过 #绑定管理员 命令绑定
  command_prefix: "#"           # 命令前缀
  at_me_required: true          # 群内是否需要@才回复（命令免@）
  private_whitelist: []          # 私聊白名单 wxid 列表

group_filter:
  mode: "whitelist"             # whitelist / blacklist / all
  whitelist: []                  # 白名单群ID列表
  blacklist: []                  # 黑名单群ID列表

monitor:
  member_count: true             # 是否监控群人数
  member_count_interval: 300     # 人数检查间隔（秒）
  message: true                  # 是否记录群消息
  message_types: []              # 记录的消息类型（空=全部）
  alert_member_change: true     # 人数变动时告警
  member_change_threshold: 5    # 变动超过N人时告警
  group_cache_ttl: 600          # 群缓存 TTL（秒）

webhook:
  enabled: true                 # 是否启用 WebHook
  host: "0.0.0.0"               # 监听地址
  port: 8080                    # 监听端口
  token: "your-secure-token"    # API 认证 token（务必修改！）
  rate_limit: 60                # 每分钟请求限制
  cors_origins: []              # CORS 允许来源

database:
  path: "data/wechat_bot.db"   # SQLite 数据库路径
  wal_mode: true                # WAL 模式（推荐开启）
  busy_timeout: 5000            # 锁等待超时（毫秒）
  batch_size: 100               # 批量写入大小
  batch_flush_interval: 10      # 批量刷新间隔（秒）

logging:
  level: "INFO"                 # 日志级别
  file: null                    # 日志文件路径（null=仅控制台）
  max_size_mb: 10               # 日志文件最大大小
  backup_count: 5               # 日志备份数量
```

## 👑 管理员命令

通过微信私聊发送命令（前缀默认 `#`）：

| 命令 | 说明 | 参数 |
|------|------|------|
| `#绑定管理员` | 绑定自己为管理员 | 无 |
| `#解绑管理员` | 解绑当前管理员 | 无 |
| `#帮助` / `#help` | 显示所有命令 | 无 |
| `#状态` | 查看机器人状态 | 无 |
| `#群列表` | 查看所有群聊 | 无 |
| `#群概要` | 查看群聊详情 | `<群ID>` |
| `#监控列表` | 查看过滤状态 | 无 |
| `#刷新群` | 从微信刷新群信息 | 无 |
| `#添加白名单` | 添加群到白名单 | `<群ID>` |
| `#移除白名单` | 从白名单移除群 | `<群ID>` |
| `#添加黑名单` | 添加群到黑名单 | `<群ID>` |
| `#移除黑名单` | 从黑名单移除群 | `<群ID>` |
| `#过滤模式` | 设置过滤模式 | `whitelist/blacklist/all` |
| `#添加私聊白名单` | 添加私聊白名单 | `<wxid>` |
| `#移除私聊白名单` | 移除私聊白名单 | `<wxid>` |
| `#私聊白名单` | 查看私聊白名单 | 无 |

## 🪝 WebHook API

所有接口需要 Bearer Token 认证：

```bash
# 健康检查（无需认证）
curl http://localhost:8080/api/health

# 向群发送消息
curl -X POST http://localhost:8080/api/send_group \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"room_id": "xxx@chatroom", "content": "Hello!"}'

# 向管理员发送消息
curl -X POST http://localhost:8080/api/send_admin \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"content": "Alert!"}'

# 查询群列表
curl -H "Authorization: Bearer your-token" \
  http://localhost:8080/api/groups

# 查询群详情
curl -H "Authorization: Bearer your-token" \
  http://localhost:8080/api/groups/xxx@chatroom

# 查询消息
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8080/api/messages?room_id=xxx@chatroom&limit=50"

# 机器人状态
curl -H "Authorization: Bearer your-token" \
  http://localhost:8080/api/status
```

## 🏗️ 架构设计

### 核心模式

1. **Handler Pipeline** — 消息通过优先级排序的 Handler 链处理，新功能只需新增 Handler
2. **Event Bus** — 组件间解耦通信，支持前缀匹配和异步处理
3. **Command Registry** — 装饰器自注册命令系统，告别 if/elif 链
4. **Repository Pattern** — 数据访问层与业务逻辑分离
5. **DI Container** — ApplicationContext 统一管理组件初始化和依赖注入
6. **State Machine** — 机器人状态管理（UNINITIALIZED→INITIALIZING→RUNNING→DEGRADED→STOPPING→STOPPED）
7. **ThreadSafeSender** — 并发安全消息发送（Lock + 限流）

## 🧪 测试

```bash
# 运行所有测试
make test

# 带覆盖率
make test-cov

# 代码检查
make lint
```

## 📚 文档

| 文档 | 说明 |
|------|------|
| [QUICKSTART.md](QUICKSTART.md) | 快速启动指南 |
| [docs/windows-deployment.md](docs/windows-deployment.md) | Windows 完整部署教程 |
| [WeChatFerry 文档](https://wechatferry.readthedocs.io/) | WeChatFerry Python SDK 文档 |
| [WeChatFerry 仓库](https://github.com/lich0821/WeChatFerry) | WeChatFerry 官方仓库 |

## 📄 License

MIT
