# Aleria AI Town

> 腾讯游戏 AI Town 工程作业 · Phase 1C NPC Chat & Provider Abstraction

## 提交信息

| 项目 | 内容 |
| --- | --- |
| 候选人姓名 | `[待填写]` |
| 仓库地址 | `[待填写]` |
| 在线体验地址 | `[待填写；如未部署可写 N/A]` |
| 实际开发用时 | `[待填写]` |

## 项目简介

Aleria AI Town 是一个以持续世界状态和 NPC Agent 为核心的 AI 小镇原型。本仓库当前完成 Phase 1C：在确定性 World Tick 与 NPC Detail 基础上，增加 NPC Chat、Mock/LLM Provider 抽象、完整聊天轮次持久化和可重试的前端会话体验。

当前页面展示晨曦镇的 Day/时间、两个地点，以及 Ryan、Shir、Grey 三名 NPC 的基础状态。点击“查看详情”可同时打开居民档案和聊天面板；三名 NPC 的会话彼此隔离，成功推进 Tick 后详情会刷新，但 Chat 不会修改或清空确定性世界状态。

## 当前技术栈

- Frontend：Vue 3、TypeScript、Vite、Pinia、Axios
- Backend：Python 3.11+、FastAPI、Pydantic v2、SQLAlchemy 2
- Data：SQLite（运行时）与 JSON（初始化种子）
- Test：pytest、Vitest、Vue Test Utils

## 本地启动

前置要求：Python 3.11+、Node.js 20+、npm。

### 1. 初始化 Backend

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
python scripts\seed_world.py
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

macOS/Linux 对应的环境激活命令是 `source .venv/bin/activate`，路径分隔符可改为 `/`。

Backend 启动后：

- World API：`http://127.0.0.1:8000/api/world`
- NPC Detail API：`http://127.0.0.1:8000/api/npcs/ryan`
- NPC Chat API：`POST http://127.0.0.1:8000/api/npcs/ryan/chat`
- Swagger UI：`http://127.0.0.1:8000/docs`

从已有数据库升级时，不要用重播种代替迁移；先运行以下非破坏性命令，它只创建当前模型缺失的表，不重置世界状态：

```powershell
python scripts\upgrade_schema.py
```

- `GET /api/world` 返回当前世界、地点列表和 NPC 基础状态。
- `POST /api/world/tick` 接收 `{"expected_tick": 0}`，推进一小时并返回完整世界、Action 与 Event。
- `GET /api/npcs/{npc_id}` 返回 NPC Profile、当前状态、世界阶段和最近三条行动解释。
- `POST /api/npcs/{npc_id}/chat` 接收首轮或续聊消息，返回持久化后的 User/Assistant 完整轮次和 Provider 元数据。

默认 `CHAT_PROVIDER=mock`，无需配置模型地址、模型名或 API Key。真实模型与本地模型共用一个 OpenAI-compatible Adapter：

```env
CHAT_PROVIDER=deepseek
CHAT_LLM_BASE_URL=<provider-compatible-base-url>
CHAT_LLM_API_KEY=<backend-only-secret>
CHAT_LLM_MODEL=<compatible-model-name>
CHAT_LLM_AUTH_MODE=bearer
```

腾讯混元、DeepSeek 或本地 Qwen 服务只需替换 `CHAT_PROVIDER` 标签、`CHAT_LLM_BASE_URL` 和 `CHAT_LLM_MODEL`，不需要新增供应商专用 ChatService。无鉴权的本地服务使用 `CHAT_LLM_AUTH_MODE=none` 并保持 `CHAT_LLM_API_KEY=` 为空。

首轮请求：

```json
{"conversation_id": null, "message": "你害怕史莱姆吗？"}
```

续聊请求复用上次响应的 `conversation_id`。Primary Provider 出现可预期故障时自动回退到 Mock；响应会如实返回 `provider: "mock"` 和 `fallback_used: true`。

### 2. 初始化 Frontend

新开一个终端：

```powershell
Set-Location frontend
npm install
npm run dev -- --host 127.0.0.1
```

访问 Vite 输出的本地地址，默认是 `http://127.0.0.1:5173`。

如 Backend 地址不是 `http://127.0.0.1:8000`，可在 Frontend 启动前设置 `VITE_API_BASE_URL`。

## 数据流与边界

```text
data/*.json（只作为种子）
        ↓ seed_world.py
backend/data/aleria.db（SQLite 运行时事实来源）
        ↓ Repository → Service → FastAPI
GET /api/world
        ↕ POST /api/world/tick（expected_tick 乐观锁）
Pure World Engine → Transactional Repository → actions/events
        ↓
GET /api/npcs/{npc_id}（独立只读查询切片）
        ↓ API Adapter → 独立 Pinia Store → Vue UI
POST /api/npcs/{npc_id}/chat
        ↓ ChatService → ChatProvider → ChatRepository
        ↓ conversations + conversation_messages
晨曦镇页面
```

根目录 `data/*.json` 不参与每次 API 请求，也不是运行时状态存储。`upgrade_schema.py` 用于保留状态的增量建表；修改种子后才运行 `seed_world.py` 幂等重置 SQLite 当前世界。为保持Tick 0一致性，重播种会清除该世界已有的Action/Event历史。

Frontend 将网络访问限制在 API Adapter 中，Store 管理加载/错误/空数据/成功状态，展示组件只消费类型化数据。后续迁移开源前端、引入 PixiJS 或替换页面结构时，可以保留 API 契约和状态层。

## 验证

Backend（仓库根目录）：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -v
.\.venv\Scripts\python.exe scripts\seed_world.py
```

Frontend（`frontend/`）：

```powershell
npm run test
npm run type-check
npm run build
```

## Phase 0、Phase 1A、Phase 1B 与 Phase 1C 已完成

- 初始化 Monorepo 目录与开发环境配置
- 建立 SQLite 世界、地点、NPC Profile/State 模型
- 提供经过 Pydantic 校验且可重复执行的 JSON 种子流程
- 实现 `GET /api/world`、CORS 和安全的数据库失败响应
- 实现 Vue 四态页面：加载、错误重试、空数据、成功
- 展示 2 个地点和 Ryan/Shir/Grey 的基础状态
- 覆盖 Backend API/种子和 Frontend Store/View 自动化测试
- 每次用户操作确定性推进 1 小时，并划分 morning/day/evening/night
- NPC 决策考虑状态阈值、职业特点、时间阶段和同地点居民
- 三名 NPC 从同一不可变快照决策，Action 经过验证后执行
- 单事务更新 `world_state`/`npc_states` 并写入 `actions`/`events`
- `expected_tick` 冲突返回 409；Frontend 自动刷新权威状态
- 展示推进中的状态、NPC Actions 和 World Events
- 提供 `GET /api/npcs/{npc_id}` 独立只读查询切片
- 展示 Profile、权威当前状态和 morning/day/evening/night 世界阶段
- 按 `tick DESC, id DESC` 展示最近三条持久化 Action
- 将历史 `reason` 机器代码映射为 `reason_code + reason_text`，未暴露 chain-of-thought
- 支持详情 loading、错误重试、空历史、关闭、快速切换竞态保护与 Tick 后刷新
- 提供 `POST /api/npcs/{npc_id}/chat` 首轮与续聊契约
- 使用统一 `ChatProvider` 接口、Mock Provider 和 OpenAI-compatible Adapter
- 支持云端 compatible API 与本地无鉴权模型服务，并在 Primary 故障时自动降级 Mock
- 从权威世界/NPC/最近行动、版本化 Prompt 和有界聊天历史构造 Chat Context
- 在一个事务中保存完整 User/Assistant 轮次，失败不留下半轮数据
- 前端按 NPC 隔离会话，支持 sending、错误重试、fallback 提示、切换和关闭后恢复
- Chat 只读取世界上下文，不推进 Tick，不修改 NPC State、Action 或 Event

## 当前限制与延期范围

Phase 1C 完成腾讯作业所需的确定性世界、NPC 查询与对话闭环，但仍不是完整游戏：

- 世界仅由用户点击推进，不运行后台自动时钟
- World Tick 是唯一修改世界状态的 API；Chat 只写入独立会话表，Player、登录和部署配置尚未实现
- 已实现 Chat 的 Mock/compatible Provider；尚未实现 Memory、Relationship、Background、Goal 或完整 Agent Trace
- 默认 Mock 不访问网络；真实 compatible Provider 仅在 Backend 显式配置后调用
- 前端会话仅在当前页面生命周期内保存，刷新页面后暂不主动读取历史会话
- PixiJS、Quest、RAG、复杂 Memory、多人系统和 WebSocket 均明确延期
- 当前 UI 是便于验证数据流的响应式 DOM/CSS 页面，后续可按独立阶段迁移开源界面或渲染层

更完整的产品、世界、Agent、API、数据库和后续路线设计见 [`docs/`](docs/)。
