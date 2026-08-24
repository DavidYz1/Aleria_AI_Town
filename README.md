# Aleria AI Town

> 腾讯游戏 AI 小镇工程作业 · Phase 1D 可运行版本

## 提交信息

| 项目 | 内容 |
| --- | --- |
| 候选人姓名 | `[提交前由候选人填写]` |
| 仓库地址 | `[提交前由候选人填写]` |
| 在线体验地址 | `[提交前由候选人填写；未部署时写 N/A]` |
| 实际开发用时 | `[提交前由候选人填写]` |
| 技术栈 | Vue 3 + TypeScript + Pinia / FastAPI + SQLAlchemy / SQLite |
| 当前完成范围 | World Tick、NPC Detail、Mock/真实模型 Chat、Player、确定性 Quest、响应式 DOM UI |
| 已知问题 | 暂无线上部署；地图渲染、复杂 Memory/Relationship、多人系统尚未实现 |

## 项目概览

Aleria AI Town 是一个“世界状态优先”的 AI 小镇原型。玩家进入战后重建中的**曦谷**，观察 Ryan、Shir、Grey 按状态、职业和时间阶段行动，与他们对话，并完成“失踪的孩子”任务。

系统刻意拆分两类能力：

- World Engine 使用确定性规则推进时间和 NPC 状态，结果可测试、可回放。
- NPC Chat 使用可切换的 Mock 或 OpenAI-compatible 模型增强表达，但不能修改 Tick、NPC State、Action、Event 或 Quest。

运行时权威数据保存在 SQLite；`data/*.json` 仅用于初始化。即使没有 API Key，默认 Mock 模式也能完整验收 World、NPC、Chat、Player 和 Quest 闭环。

### 一分钟体验路径

1. 打开页面，确认世界为“曦谷”，看到星辉酒馆、中央公园、晨曦城堡、低语森林和三名 NPC。
2. 在星辉酒馆接受“失踪的孩子”。
3. 前往 Grey 当前所在地点（初始为晨曦城堡）询问线索。
4. 前往低语森林，发现鞋子并找到孩子。
5. 返回星辉酒馆完成任务，查看五条持久化进展。
6. 与 NPC 对话；在 Mock 与真实模型故障回退时，任务和世界状态都不会被对话改写。
7. 推进一次 World Tick，观察 NPC 行动和事件；玩家位置与任务进度保持不变。

## 玩法与 NPC 设定

### 四个地点

| 地点 | 稳定 ID | 体验职责 |
| --- | --- | --- |
| 星辉酒馆 | `tavern` | 玩家初始地点、接受和交付任务、Shir 日常活动 |
| 中央公园 | `park` | Ryan 的骑士训练地点 |
| 晨曦城堡 | `castle` | Grey 的守护与巡逻地点 |
| 低语森林 | `forest` | Shir 的侦察地点、任务调查区域 |

显示名称可以演进，技术 ID 保持稳定，以免破坏数据库、API 和前端状态。

### 三名 NPC

- **Ryan / Knight**：热情、正直、渴望证明自己；表面勇敢，面对史莱姆时会暴露不愿承认的谨慎。白天倾向在中央公园训练。
- **Shir / Assassin**：寡言、敏锐、重事实；与人保持距离，却对甜食有不愿承认的偏好。傍晚倾向前往低语森林侦察。
- **Grey / Guardian**：沉稳、负责、保护欲强；掌握更多灰烬战争线索，但对未经确认的历史保持克制。日间倾向在晨曦城堡巡逻。

NPC 决策优先处理低能量、低心情、低社交等状态需求，再执行角色例程；夜间优先休息。决定基于同一份不可变世界快照，Action 通过规则校验后才在单个事务中落库。

### “失踪的孩子”任务

任务是一个有界、确定性的状态机：

```text
available
  → accepted
  → briefed_by_grey
  → shoe_found
  → child_found
  → completed
```

每次成功迁移写入一条 Quest Event，并令 `version + 1`。跳步、错误地点或过期版本会被 Backend 拒绝。询问 Grey 还要求玩家与 Grey 处于同一地点；若 World Tick 使 Grey 移动，任务目标会跟随他的权威当前位置。

## 快速启动（默认 Mock，无需 API Key）

前置环境：Python 3.11+、Node.js 20+、npm。

### 1. Backend

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
python scripts\seed_world.py
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

macOS/Linux 使用 `source .venv/bin/activate`，并将路径分隔符改为 `/`。

默认配置是 `CHAT_PROVIDER=mock`。Backend 地址为 `http://127.0.0.1:8000`，Swagger UI 为 `http://127.0.0.1:8000/docs`。

已有数据库需要保留状态时，运行非破坏性的增量建表命令：

```powershell
python scripts\upgrade_schema.py
```

`seed_world.py` 用于可重复演示，会重置当前世界、Player/Quest、Chat 和 Action/Event 数据；不要把它当作生产迁移工具。

### 2. Frontend

新开终端：

```powershell
Set-Location frontend
npm install
npm run dev -- --host 127.0.0.1
```

访问 `http://127.0.0.1:5173`。Backend 地址不同可通过 `VITE_API_BASE_URL` 指定。

## 真实 AI 与 Mock 模式

所有非 Mock 标签都复用同一个 `OpenAICompatibleChatProvider`。`ChatService` 不知道腾讯混元、Gemini、DeepSeek 或本地模型的差异；供应商通过 `.env` 配置切换。

### 腾讯混元 / TokenHub：hy3

```env
CHAT_PROVIDER=hy3
CHAT_LLM_BASE_URL=<TokenHub 控制台给出的 OpenAI-compatible Base URL>
CHAT_LLM_API_KEY=<仅保存在本地 Backend 的 Key>
CHAT_LLM_MODEL=<TokenHub 控制台给出的 hy3 模型 ID>
CHAT_LLM_AUTH_MODE=bearer
CHAT_LLM_OUTPUT_MODE=structured_json
CHAT_LLM_TIMEOUT_SECONDS=30
CHAT_PROMPT_VERSION=v2
```

### 腾讯混元 / TokenHub：hy-role

`hy-role` 更倾向返回自然文本，不应强制按 `reply + emotion` JSON 解析：

```env
CHAT_PROVIDER=hunyuan
CHAT_LLM_BASE_URL=<TokenHub 控制台给出的 OpenAI-compatible Base URL>
CHAT_LLM_API_KEY=<仅保存在本地 Backend 的 Key>
CHAT_LLM_MODEL=hy-role
CHAT_LLM_AUTH_MODE=bearer
CHAT_LLM_OUTPUT_MODE=text
CHAT_LLM_TIMEOUT_SECONDS=30
CHAT_PROMPT_VERSION=v2
```

Text 模式仍由 Adapter 生成确定性的安全 emotion，公共 Chat API 不变。

### Gemini OpenAI compatibility

```env
CHAT_PROVIDER=gemini
CHAT_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
CHAT_LLM_API_KEY=<仅保存在本地 Backend 的 Key>
CHAT_LLM_MODEL=gemini-2.5-flash
CHAT_LLM_AUTH_MODE=bearer
CHAT_LLM_OUTPUT_MODE=structured_json
CHAT_LLM_TIMEOUT_SECONDS=30
CHAT_PROMPT_VERSION=v2
```

修改 `.env` 后必须完整重启 Backend。部分本地网络访问 Gemini 需要系统代理，这是网络可达性问题，不应通过业务代码绕过。

Primary Provider 的 HTTP、超时、传输、响应结构或校验故障会安全回退到 Mock。前端显示“AI 暂不可用，已使用 Mock 回复”，响应同时返回实际 `provider` 与 `fallback_used`；日志只记录安全错误分类，不输出 Key、Authorization、完整 Prompt 或响应正文。

## 架构、数据流与决策流程

```text
Vue View / Components
  ├─ World Store  ── World API ── WorldTickService ── deterministic engine
  ├─ NPC Store    ── NPC Detail API ──────────────── read-only query
  ├─ Chat Store   ── Chat API ── ChatService ── ChatProvider ── Mock/LLM
  └─ PlayerQuest Store ── Player/Quest API ── PlayerQuestService
                                                    │
data/*.json ── seed_world.py ── SQLite repositories ┘
```

关键边界：

- Backend 是 World、NPC、Player 和 Quest 的唯一事实来源。
- World Tick 一次推进一小时，使用 `expected_tick` 乐观锁；全部 NPC 从同一快照决策并在单事务中更新。
- Chat 只读 World/NPC/最近 Action 与 Player/Quest 摘要，只写完整的 User/Assistant 会话轮次。
- Quest 只由明确的 Interaction 推进；旅行只改玩家地点，不推进时间。
- Frontend 不复制任务迁移规则，只展示 Backend 返回的 objective 和 available interactions。

## API 与 Quest 契约

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/world` | 世界时间、四地点、NPC 基础状态 |
| `POST` | `/api/world/tick` | 以 `expected_tick` 推进一小时 |
| `GET` | `/api/npcs/{npc_id}` | NPC 档案、状态和最近行动 |
| `POST` | `/api/npcs/{npc_id}/chat` | 首轮/续聊，返回完整持久化轮次 |
| `GET` | `/api/player` | 玩家位置、任务目标、版本和最近事件 |
| `POST` | `/api/player/travel` | 移动到稳定地点 ID，不推进 Tick |
| `POST` | `/api/quests/missing-child/interact` | 按 interaction + expected_version 推进任务 |

示例：

```json
{"interaction": "ask_grey", "expected_version": 1}
```

成功统一返回 `{"success": true, "data": ..., "message": "ok"}`。常见错误包括 404（资源不存在）、409（Tick/Quest 冲突或交互条件不满足）、422（请求结构非法）、503（数据库、上下文或 Provider 不可用）。

详细契约见 [`docs/06_API_Contract.md`](docs/06_API_Contract.md)，数据库结构见 [`docs/07_Database_Schema.md`](docs/07_Database_Schema.md)。

## 测试与验收

Backend：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider
```

Phase 1D 跨模块验收：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_phase1d_acceptance.py -q -p no:cacheprovider
```

Frontend：

```powershell
Set-Location frontend
npm test
npm run type-check
npm run build
```

自动测试全部使用 disposable SQLite 和 Mock/假 Provider，不发起真实模型网络请求，也不需要 API Key。

## AI 工具使用与人工修正案例

本项目使用 AI Coding 辅助拆分 Spec/Plan、生成测试骨架、实现模块和同步文档；每个模块坚持 TDD，并由开发者人工 review diff 后提交。AI 不被允许自动 commit，也不能把模型输出直接作为 World Action 执行。

一个真实人工修正案例发生在腾讯混元接入：最初 compatible Adapter 强制校验 `reply + emotion` JSON。`hy-role` 已在 TokenHub 消耗 Token，但返回自然文本，Backend 将其分类为 `response_validation` 并触发 Mock fallback。人工结合安全日志和真实响应行为确认问题后，没有复制一个 Hunyuan 专用 Provider，也没有修改 ChatService/Fallback；只在统一 Adapter 增加 `structured_json | text` 输出模式，Text 模式对回复做同样长度校验并确定性派生 emotion。这样既跑通 `hy-role`，也保持了公共契约和未来供应商扩展能力。

## 已知限制与路线图

当前已完成并通过自动测试的是 Phase 1D：四地点世界、角色化例程、Prompt/Mock v2、compatible Adapter 双输出模式、Player/Quest Backend、Frontend DOM 任务闭环与持久化验收。

尚未实现：

- 线上体验地址、Docker 和 CI/CD；计划在 Phase 1E 完成部署与交付工程化。
- PixiJS/Canvas/Cocos 地图、角色精灵、碰撞、动画；计划在 Phase 2 迁移展示层，复用现有 API/Store。
- 任务奖励、背包、账号、多人和通用 Quest DSL。
- 长期 Memory、Relationship、Reflection、Planning、RAG 和 LLM 驱动 World Tick。

这些能力不会为了“看起来复杂”而提前进入当前确定性核心。完整设计与路线见 [`docs/`](docs/)。
