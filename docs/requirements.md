# WeChatBot 需求文档

> 版本: v2.0 | 更新日期: 2026-06-16 | 项目仓库: https://github.com/ichensw/wechat-bot

---

## 一、项目概述

### 1.1 项目定位

基于 [WeChatFerry](https://github.com/lich0821/WeChatFerry) 的生产级微信监控机器人，运行于 **Windows 系统**，通过 hook 微信 PC 客户端实现消息收发和群聊管理。

### 1.2 技术栈

| 层面 | 技术选型 |
|------|---------|
| 微信 SDK | WeChatFerry (wcferry) v39.5.2 |
| 微信版本 | 3.9.12.51（强制绑定，不支持其他版本） |
| 运行环境 | Windows 10/11（仅支持 Windows） |
| 语言 | Python 3.9 ~ 3.11 |
| HTTP 框架 | Flask |
| 数据库 | SQLite (WAL 模式) |
| 定时任务 | APScheduler |
| 配置格式 | YAML + 环境变量覆盖 |

### 1.3 核心约束

- **仅支持 Windows**：WeChatFerry 通过 hook 微信 PC 客户端工作，必须在 Windows 上运行
- **微信版本锁定**：必须使用微信 3.9.12.51，与 wcferry v39.5.2 配套
- **单管理员**：机器人仅支持绑定一个管理员
- **并发安全**：所有消息发送操作必须通过 ThreadSafeSender 串行化

---

## 二、功能需求

### FR-1 群聊黑白名单

**优先级**: P0 | **状态**: ✅ 已实现

#### FR-1.1 三种过滤模式

| 模式 | 行为 |
|------|------|
| `whitelist` | 仅监控白名单中的群（默认模式） |
| `blacklist` | 监控所有群，但排除黑名单中的群 |
| `all` | 监控所有群（不过滤） |

#### FR-1.2 运行时动态修改

- 管理员可通过微信命令实时增删白名单/黑名单
- 修改即时生效，无需重启
- 修改后自动持久化到 `config.yaml`

#### FR-1.3 群 ID 格式校验

- 群 ID 必须以 `@chatroom` 结尾
- 非法格式的群 ID 会被拒绝并提示

---

### FR-2 群成员监控

**优先级**: P0 | **状态**: ✅ 已实现

#### FR-2.1 消息记录

- 记录允许群中的所有消息到 SQLite 数据库
- 支持按消息类型过滤（`message_types` 配置项，空=全部记录）
- 存储字段：msg_id, room_id, sender_wxid, sender_name, msg_type, content, xml_content, created_at
- 消息入库不依赖 @mention，只要群通过过滤，所有消息都会被记录

#### FR-2.2 人数变动检测

- 定时检查所有监控群的成员人数（默认 300 秒一次）
- 记录成员快照（人数 + MD5 哈希）到 `group_member_snapshots` 表
- 人数变化超过阈值（默认 5 人）时告警管理员

#### FR-2.3 告警通知

- 群成员变动超过阈值时，私聊通知管理员
- 告警内容：群名、群 ID、变动方向、变动人数

#### FR-2.4 群信息缓存

- 缓存群名、成员数等信息，设置 TTL（默认 600 秒）
- 缓存过期自动从微信刷新
- 管理员可手动执行 `#刷新群` 立即刷新

#### FR-2.5 群聊统计

- 近 24h 消息数量
- 近 24h 活跃发言人数
- 发言排行榜 Top 5
- 消息类型分布

---

### FR-3 管理员绑定

**优先级**: P0 | **状态**: ✅ 已实现

#### FR-3.1 单管理员约束

- 机器人仅支持绑定 **一个** 管理员
- 已绑定管理员时，其他人尝试绑定会提示"管理员已绑定"
- 管理员 wxid 持久化到 `config.yaml` 的 `bot.admin_wxid`

#### FR-3.2 绑定流程

1. 用户私聊发送 `#绑定管理员`
2. 系统检查是否已有管理员
3. 若无：绑定发送者为管理员，返回成功
4. 若有：返回当前管理员 wxid，拒绝绑定

#### FR-3.3 解绑流程

1. 当前管理员私聊发送 `#解绑管理员`
2. 系统验证发送者是当前管理员
3. 清除 `admin_wxid`，返回成功

#### FR-3.4 管理员权限

- 执行所有管理员命令（`admin_only=True` 的命令）
- 接收群成员变动告警
- 接收 WebHook `send_admin` 推送的消息
- 自动拥有私聊权限（无需加入私聊白名单）

---

### FR-4 WebHook API

**优先级**: P0 | **状态**: ✅ 已实现

#### FR-4.1 认证机制

- Bearer Token 认证（`Authorization: Bearer <token>`）
- 健康检查接口 `/api/health` 免认证
- Token 不足 16 位时启动告警日志

#### FR-4.2 API 端点

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/health` | 健康检查 | 否 |
| POST | `/api/send_group` | 向群发送消息 | 是 |
| POST | `/api/send_admin` | 向管理员发送消息 | 是 |
| GET | `/api/groups` | 查询群列表 | 是 |
| GET | `/api/groups/<room_id>` | 查询群详情+统计 | 是 |
| GET | `/api/messages` | 查询消息（分页+过滤） | 是 |
| GET | `/api/status` | 机器人状态 | 是 |

#### FR-4.3 限流

- 基于 IP 的滑动窗口限流（默认 60 次/分钟）
- 超限返回 429 + `Retry-After` 头
- 响应头包含 `X-RateLimit-Limit` / `X-RateLimit-Remaining`

#### FR-4.4 CORS

- 可配置允许的跨域来源
- 支持 OPTIONS 预检请求

#### FR-4.5 全局错误处理

- 400/404/405/500 统一 JSON 错误格式
- 错误体包含 `error`、`message`、`code` 字段

---

### FR-5 @机器人触发机制

**优先级**: P1 | **状态**: ✅ 已实现

#### FR-5.1 群内 @触发规则

- `at_me_required: true`（默认）：群内只有 @机器人 才会回复
- `at_me_required: false`：群内所有消息都会触发回复
- **命令免@**：以命令前缀（默认 `#`）开头的消息，无论是否 @机器人，都会被处理

#### FR-5.2 @mention 检测

- 从消息 XML 中的 `<atuserlist>` 标签解析 @的 wxid
- 格式：`<atuserlist>wxid1|wxid2</atuserlist>`
- `WxMessage.is_at(bot_wxid)` 判断是否 @了机器人

#### FR-5.3 消息处理顺序

```
群消息进入
  │
  ├─ Step 1: 群过滤（GroupFilter）→ 不允许则 REJECTED
  │
  ├─ Step 2: 消息入库（无论是否 @，监控群消息都存储）
  │
  ├─ Step 3: 命令检测（#开头 → 执行命令，返回 HANDLED）
  │
  ├─ Step 4: @检测（at_me_required=true 且未@机器人 → CONTINUE）
  │
  └─ Step 5: 被@或 at_me_required=false → CONTINUE（交由后续 Handler）
```

---

### FR-6 私聊白名单

**优先级**: P1 | **状态**: ✅ 已实现

#### FR-6.1 私聊访问控制

- **管理员**：自动拥有私聊权限，无需额外配置
- **白名单用户**：`private_whitelist` 列表中的 wxid 允许私聊
- **其他人**：私聊消息被 REJECTED（机器人不回复）

#### FR-6.2 私聊白名单管理命令

| 命令 | 说明 |
|------|------|
| `#添加私聊白名单 <wxid>` | 添加 wxid 到私聊白名单 |
| `#移除私聊白名单 <wxid>` | 从私聊白名单移除 wxid |
| `#私聊白名单` | 查看当前私聊白名单 |

#### FR-6.3 私聊消息处理顺序

```
私聊消息进入
  │
  ├─ Step 1: 访问控制（管理员或白名单 → 允许；否则 REJECTED）
  │
  ├─ Step 2: 尝试作为命令执行（#开头 → 执行并回复）
  │
  └─ Step 3: 非命令但授权用户 → CONTINUE（交由后续 Handler）
```

---

### FR-7 并发安全

**优先级**: P1 | **状态**: ✅ 已实现

#### FR-7.1 ThreadSafeSender

- 所有消息发送（Handler Pipeline、WebHook、定时任务、管理员命令）共用同一个 `ThreadSafeSender` 实例
- 使用 `threading.Lock` 串行化发送操作
- 内置 0.3 秒最小发送间隔限流
- 发送失败记录错误日志，返回非零结果码

#### FR-7.2 并发发送来源

| 来源 | 线程 | 说明 |
|------|------|------|
| 消息处理循环 | MessageLoopThread | Handler 处理后回复 |
| WebHook API | Flask 线程 | 外部 HTTP 触发发送 |
| 定时任务 | APScheduler 线程 | 定时检查/告警通知 |
| 管理员命令 | MessageLoopThread | 命令执行后回复 |

---

### FR-8 配置管理

**优先级**: P1 | **状态**: ✅ 已实现

#### FR-8.1 配置项

```yaml
bot:
  name: "WeChatBot"              # 机器人名称
  admin_wxid: null                # 管理员 wxid（通过 #绑定管理员 命令设置）
  command_prefix: "#"             # 命令前缀（最长 3 字符）
  at_me_required: true            # 群内是否需要@才回复
  private_whitelist: []           # 私聊白名单 wxid 列表

group_filter:
  mode: "whitelist"               # 过滤模式: whitelist / blacklist / all
  whitelist: []                    # 白名单群 ID 列表
  blacklist: []                    # 黑名单群 ID 列表

monitor:
  member_count: true              # 是否监控群人数
  member_count_interval: 300      # 人数检查间隔（秒，最小 30）
  message: true                    # 是否记录群消息
  message_types: []                # 记录的消息类型（空=全部）
  alert_member_change: true       # 人数变动时告警
  member_change_threshold: 5     # 变动超过 N 人时告警（最小 1）
  group_cache_ttl: 600            # 群缓存 TTL（秒，最小 60）

webhook:
  enabled: true                    # 是否启用 WebHook
  host: "0.0.0.0"                 # 监听地址
  port: 8080                      # 监听端口（1-65535）
  token: "change-me"              # API 认证 token（务必修改！）
  rate_limit: 60                  # 每分钟请求限制（最小 1）
  cors_origins: []                # CORS 允许来源

database:
  path: "data/wechat_bot.db"     # SQLite 数据库路径
  wal_mode: true                  # WAL 模式
  busy_timeout: 5000              # 锁等待超时（毫秒）
  batch_size: 100                  # 批量写入大小
  batch_flush_interval: 10        # 批量刷新间隔（秒）

logging:
  level: "INFO"                   # 日志级别
  file: "data/wechat_bot.log"    # 日志文件路径
  max_size_mb: 10                 # 日志文件最大大小
  backup_count: 5                 # 日志备份数量
```

#### FR-8.2 环境变量覆盖

所有配置项均可通过环境变量覆盖，规则：
- 环境变量名 = `BOT_` / `GROUP_FILTER_` / `MONITOR_` / `WEBHOOK_` / `DATABASE_` / `LOG_` + 字段名大写
- 布尔值: `1`/`true`/`yes`/`on` → True
- 列表值: 逗号分隔，如 `BOT_PRIVATE_WHITELIST=wxid_a,wxid_b`
- 环境变量优先级高于 YAML 配置

#### FR-8.3 热更新

- `config.yaml` 修改后自动检测并生效（基于 SHA256 哈希比对）
- 群过滤白名单/黑名单修改即时生效并持久化
- 无需重启机器人

#### FR-8.4 配置校验

- 所有配置值在加载时进行类型和范围校验
- 校验失败抛出 `ConfigValidationError`，机器人无法启动
- 默认 token 启动时打印警告日志

---

### FR-9 管理员命令系统

**优先级**: P0 | **状态**: ✅ 已实现

#### FR-9.1 命令注册机制

- 装饰器自注册：使用 `@registry.command(name, ...)` 装饰器注册命令
- 命令别名：支持 `aliases` 参数（如 `#帮助` 别名 `#help`）
- 权限控制：`admin_only=True` 的命令仅管理员可执行
- 新增命令只需定义函数 + 装饰器，无需修改 if/elif 链

#### FR-9.2 内置命令清单

| 命令 | 别名 | 权限 | 说明 | 参数 |
|------|------|------|------|------|
| `#绑定管理员` | — | 公开 | 绑定自己为管理员 | 无 |
| `#解绑管理员` | — | 管理员 | 解绑当前管理员 | 无 |
| `#帮助` | `#help` | 公开 | 显示命令帮助 | 无 |
| `#状态` | `#status` | 管理员 | 查看机器人状态 | 无 |
| `#群列表` | — | 管理员 | 查看所有群聊 | 无 |
| `#群概要` | — | 管理员 | 查看群聊详情 | `<群ID>` |
| `#监控列表` | — | 管理员 | 查看过滤状态 | 无 |
| `#刷新群` | — | 管理员 | 从微信刷新群信息 | 无 |
| `#添加白名单` | — | 管理员 | 添加群到白名单 | `<群ID>` |
| `#移除白名单` | — | 管理员 | 从白名单移除群 | `<群ID>` |
| `#添加黑名单` | — | 管理员 | 添加群到黑名单 | `<群ID>` |
| `#移除黑名单` | — | 管理员 | 从黑名单移除群 | `<群ID>` |
| `#过滤模式` | — | 管理员 | 设置过滤模式 | `whitelist/blacklist/all` |
| `#添加私聊白名单` | — | 管理员 | 添加私聊白名单 | `<wxid>` |
| `#移除私聊白名单` | — | 管理员 | 移除私聊白名单 | `<wxid>` |
| `#私聊白名单` | — | 管理员 | 查看私聊白名单 | 无 |

#### FR-9.3 命令执行上下文

每个命令处理器接收 `CommandContext` 对象：
- `sender_wxid`: 发送者 wxid
- `sender_name`: 发送者昵称
- `raw_content`: 原始消息内容
- `command_name`: 解析出的命令名
- `args`: 命令参数（命令名之后的部分）
- `is_admin`: 是否为管理员
- `services`: DI 容器（提供 admin_manager、group_filter、db、wcf 等服务）

#### FR-9.4 群内命令响应规则

- **管理员**在群内执行命令：直接发送回复到群
- **非管理员**在群内执行命令：回复带 @发送者 的消息

---

### FR-10 定时任务

**优先级**: P2 | **状态**: ✅ 已实现

| 任务 | 类型 | 间隔/时间 | 说明 |
|------|------|----------|------|
| 成员人数检查 | 间隔 | 300s（可配置） | 检查各监控群人数变动 |
| 群缓存刷新 | 间隔 | 600s（可配置） | 从微信刷新群信息到缓存和数据库 |
| 数据库清理 | 定时 | 每日 03:00 | 清理 90 天前的消息 |
| 数据库 VACUUM | 定时 | 每日 04:00 | 回收 SQLite 磁盘空间 |

---

### FR-11 机器人生命周期管理

**优先级**: P1 | **状态**: ✅ 已实现

#### FR-11.1 状态机

```
UNINITIALIZED → INITIALIZING → RUNNING ⇄ DEGRADED → STOPPING → STOPPED
```

| 状态 | 说明 |
|------|------|
| UNINITIALIZED | 初始状态 |
| INITIALIZING | 正在初始化所有组件 |
| RUNNING | 正常运行，可处理消息 |
| DEGRADED | WCF 连接异常，尝试恢复 |
| STOPPING | 正在优雅关闭 |
| STOPPED | 已停止 |

#### FR-11.2 启动流程

1. 加载配置文件
2. 初始化所有组件（DI 容器）
3. 连接 WCF 并验证登录
4. 扫描群列表
5. 启动定时任务
6. 启动 WebHook 服务器
7. 启动消息处理线程
8. 主线程阻塞 + 健康检查循环

#### FR-11.3 关闭流程

1. 捕获 SIGINT/SIGTERM 信号
2. 设置 `_running = False`
3. 发布 BOT_STOPPING 事件
4. 调用 `ApplicationContext.shutdown()` 释放资源

#### FR-11.4 健康检查

- 主线程每秒检查 WCF 连接状态
- 连接丢失 → 转入 DEGRADED 状态
- 连接恢复 → 回到 RUNNING 状态

---

## 三、非功能需求

### NFR-1 架构设计

| 模式 | 说明 |
|------|------|
| Handler Pipeline | 消息通过优先级排序的 Handler 链处理，新功能只需新增 Handler |
| Event Bus | 组件间解耦通信，支持前缀匹配和异步处理 |
| Command Registry | 装饰器自注册命令系统，告别 if/elif 链 |
| Repository Pattern | 数据访问层与业务逻辑分离 |
| DI Container | ApplicationContext 统一管理组件初始化和依赖注入 |
| State Machine | 机器人生命周期状态管理 |

### NFR-2 数据库

- SQLite WAL 模式，支持并发读写
- 批量写入优化（`batch_size` + `batch_flush_interval`）
- 自动建表 + 迁移
- 定时清理 + VACUUM

### NFR-3 日志

- 结构化日志格式：`%(asctime)s [%(name)s] %(levelname)s: %(message)s`
- 日志文件轮转（按大小 + 备份数量）
- 关键操作（管理员绑定、过滤变更、发送失败）均有日志

### NFR-4 错误处理

- 15 个自定义异常类型，形成层级结构
- 配置校验异常：`ConfigValidationError`
- 管理员异常：`AdminAlreadyBoundError` / `AdminNotBoundError` / `AdminPermissionDeniedError`
- WebHook 异常：`WebHookAuthError` / `WebHookRateLimitError`
- 所有异常有明确的错误码和消息

### NFR-5 重试与限流

- 指数退避 + 抖动重试（`retry.py`）
- 令牌桶 + 滑动窗口限流（`rate_limit.py`）
- 发送限流 0.3 秒间隔（ThreadSafeSender）

---

## 四、数据模型

### 4.1 WxMessage

| 字段 | 类型 | 说明 |
|------|------|------|
| msg_id | str | 消息唯一 ID |
| type | int | 消息类型（见 MessageType 枚举） |
| content | str | 消息内容 |
| sender | str | 发送者 wxid |
| room_id | str | 群 ID（私聊为空） |
| sender_name | str | 发送者昵称 |
| xml | str | 消息 XML |
| at_wxids | List[str] | 被 @的 wxid 列表 |
| timestamp | float | 时间戳 |

**关键方法**：
- `is_group` / `is_private` / `is_text` / `is_system`：消息类型判断
- `is_at(wxid)`：是否 @了指定用户
- `parse_at_wxids(content, xml)`：从 XML 解析 @列表

### 4.2 Contact

| 字段 | 类型 | 说明 |
|------|------|------|
| wxid | str | 微信 ID |
| name | str | 昵称 |
| alias | str | 微信号 |
| type | int | 类型（0=好友, 1=群, 2=订阅号, 3=服务号） |
| remark | str | 备注名 |

### 4.3 数据库表

**group_messages**：消息存储

| 列 | 类型 | 说明 |
|----|------|------|
| msg_id | TEXT PK | 消息 ID |
| room_id | TEXT | 群 ID |
| sender_wxid | TEXT | 发送者 wxid |
| sender_name | TEXT | 发送者昵称 |
| msg_type | INTEGER | 消息类型 |
| content | TEXT | 消息内容 |
| xml_content | TEXT | XML 内容 |
| created_at | REAL | Unix 时间戳 |

**group_member_snapshots**：成员快照

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 自增 ID |
| room_id | TEXT | 群 ID |
| member_count | INTEGER | 成员数 |
| members_hash | TEXT | 成员列表 MD5 |
| created_at | REAL | Unix 时间戳 |

**group_info**：群信息

| 列 | 类型 | 说明 |
|----|------|------|
| room_id | TEXT PK | 群 ID |
| room_name | TEXT | 群名 |
| member_count | INTEGER | 成员数 |
| owner_wxid | TEXT | 群主 wxid |
| updated_at | REAL | 更新时间 |

---

## 五、接口设计

### 5.1 命令接口（微信私聊/群聊）

**输入格式**：`#命令名 [参数]`

```
示例:
  #绑定管理员
  #添加白名单 12345678@chatroom
  #过滤模式 all
  #私聊白名单
```

**输出格式**：纯文本回复，包含 emoji 状态指示

```
示例:
  ✅ 已将 12345678@chatroom 添加到白名单
  ⚠️ 12345678 已在白名单中
  ❌ 用法: #添加白名单 <群ID>
```

### 5.2 WebHook API 接口

**基础 URL**: `http://<host>:<port>/api/`

**认证方式**: `Authorization: Bearer <token>`

**请求/响应示例**：

```bash
# 发送群消息
POST /api/send_group
{
  "room_id": "12345678@chatroom",
  "content": "Hello!",
  "at_list": ["wxid_user1"]  // 可选
}
→ { "success": true, "result": 0, "room_id": "..." }

# 查询消息
GET /api/messages?room_id=xxx@chatroom&limit=50&offset=0
→ {
  "messages": [...],
  "total": 1234,
  "limit": 50,
  "offset": 0
}
```

---

## 六、部署要求

### 6.1 系统要求

- Windows 10/11
- Python 3.9 ~ 3.11
- 微信 3.9.12.51（从 WeChatFerry Releases 下载安装包）
- 关闭微信自动更新

### 6.2 一键启动

- 双击 `start.bat` 自动检查 Python、创建虚拟环境、安装依赖、启动
- 支持命令行参数：`--check`（检查登录）、`--init`（生成配置）、`-c`（自定义配置路径）

### 6.3 微信版本过低问题

微信 3.9.12.51 可能被服务器强制要求升级，解决方案：
1. 使用注册表修复工具绕过版本检测
2. 使用 Cheat Engine 修改内存版本号
3. 使用 Python `pymem` 库自动化修改

---

## 七、项目结构

```
wechat-bot/
├── main.py                 # CLI 入口
├── start.bat               # Windows 一键启动脚本
├── config.yaml             # 配置文件
├── requirements.txt        # Python 依赖
├── bot/
│   ├── core/               # 核心层
│   │   ├── app.py          # DI 容器（ApplicationContext）
│   │   ├── bot.py          # 机器人主类（状态机 + 消息循环）
│   │   ├── sender.py       # ThreadSafeSender（并发安全 + 限流）
│   │   ├── event_bus.py    # 事件总线
│   │   └── exceptions.py   # 异常层级
│   ├── config/             # 配置层
│   │   ├── settings.py     # 数据类配置（验证 + 环境变量覆盖）
│   │   └── loader.py       # 配置加载器（YAML + SHA256 热更新）
│   ├── wcf/                # WCF 层
│   │   ├── client.py       # LocalWcfClient（wcferry 直连）
│   │   └── models.py       # 数据模型（WxMessage, Contact, GroupInfo）
│   ├── handlers/           # 处理器层
│   │   ├── base.py         # BaseHandler ABC + HandlerPriority + HandlerResult
│   │   ├── registry.py     # 处理器注册表
│   │   ├── pipeline.py     # 处理器管线
│   │   └── group_message.py # 群/私聊/系统消息处理器
│   ├── group/              # 群组模块
│   │   ├── filter.py       # 黑白名单过滤
│   │   ├── monitor.py      # 群成员监控
│   │   └── cache.py         # 群信息缓存
│   ├── admin/              # 管理员模块
│   │   ├── commands.py     # 命令注册表
│   │   └── manager.py      # 管理员管理
│   ├── db/                 # 数据层
│   │   ├── manager.py      # 数据库连接管理
│   │   └── repository.py   # 数据仓库
│   ├── webhook/            # WebHook 模块
│   │   ├── server.py       # Flask 服务器
│   │   ├── routes.py       # API 路由
│   │   └── middleware.py   # 中间件（认证/限流/CORS/日志/错误处理）
│   ├── scheduler/          # 调度模块
│   │   └── manager.py      # APScheduler 定时任务
│   └── utils/              # 工具层
│       ├── logger.py       # 日志
│       ├── retry.py        # 重试
│       └── rate_limit.py   # 限流
├── tests/                   # 测试（100 个测试用例）
└── docs/
    └── windows-deployment.md
```

---

## 八、测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|---------|--------|---------|
| test_at_mention.py | 42 | @mention 解析、群过滤、命令免@、私聊白名单 |
| test_commands.py | 11 | 命令注册、别名、权限、解析 |
| test_config.py | 18 | 配置校验、环境变量覆盖、默认值 |
| test_event_bus.py | 8 | 事件发布/订阅/前缀匹配 |
| test_group_filter.py | 10 | 三种过滤模式、增删白名单/黑名单 |
| test_models.py | 13 | WxMessage 属性、序列化、@检测 |
| **合计** | **102** | — |

---

## 九、已知限制

1. **仅 Windows**：WeChatFerry 依赖 Windows 微信客户端，无法在 Mac/Linux 运行
2. **微信版本锁定**：必须使用 3.9.12.51，微信可能强制升级导致无法登录
3. **单管理员**：不支持多管理员
4. **无 AI 回复**：当前版本被 @后仅继续 Pipeline，未接入大模型（预留扩展点）
5. **WebHook 发送未经过 ThreadSafeSender**：WebHook 路由直接调用 wcf_client.send_text，存在并发风险
6. **群内非管理员命令响应**：非管理员在群内发命令，机器人会 @发送者回复（此行为未与用户最终确认）
