# Aleria AI Town API Contract

Version: v3.2

Last Updated: 2026-09-17

# 1. API Design Overview

API Contract defines communication between Frontend, Backend, World
Engine and NPC Agent modules.

Design goals:

-   Frontend and backend decoupling
-   Stable data structures
-   Clear responsibilities
-   Future extensibility

# 2. Common Response Format

Success:

``` json
{
  "success": true,
  "data": {},
  "message": "ok"
}
```

Failure:

``` json
{
  "success": false,
  "data": null,
  "message": "error message"
}
```

# 3. World and Runtime APIs

## 3.1 Get World State

`GET /api/world` returns `data = {world, locations, npcs}`. The initial world object is:

```json
{"id":"aleria-town","name":"曦谷","day":1,"time":"08:00","world_version":0,"clock_tick":0,"event_sequence":0}
```

Locations and NPCs are ordered by persisted sort_order. NPC data includes id/name/role/personality, location_id, current_action and energy/mood/social status. The three counters have different meanings: authoritative mutations increment world_version, advancement increments clock_tick, and domain events increment event_sequence. There is no writable tick alias.

Missing/unavailable world state returns HTTP 503 with `message="world state is unavailable"`.

## 3.2 Advance One Hour

`POST /api/world/tick` is synchronous and returns HTTP 200 after atomic persistence. It requires the client's latest world_version:

```json
{"expected_world_version":0}
```

```text
Snapshot -> ActionProposal -> Registry validation
-> deterministic resolution -> atomic world/run/action/event/trace commit
```

Response data contains `run`, `world`, `actions`, and `events`. Here `world` is the entire `GET /api/world` data object, not a patch. For the first seed advancement its inner world is Day 1 09:00, world_version 1, clock_tick 1, event_sequence 3.

Example `run` summary:

```json
{
  "id":"00000000-0000-0000-0000-000000000001",
  "mode":"deterministic",
  "trigger_type":"world_advance",
  "status":"completed",
  "base_world_version":0,
  "resulting_world_version":1,
  "base_clock_tick":0,
  "resulting_clock_tick":1
}
```

The UUID is illustrative. Actions include id, clock_tick, actor_id, action_type, target_kind/target_id, reason (machine code), status `executed`, run_id, proposal_id, world_version and world_time. The seed produces three actions, three events and three proposals. Legal action IDs are `move/rest/work/eat/talk/wait`.

Events include id/run_id, world_version/clock_tick/event_sequence, event_type, actor_id/action_id/source_event_id, factual description/payload, world_time, visibility/secrecy, causation_id/correlation_id and created_at. Event sequence is ordered within each world. Public summaries and structured payloads are sanitized.

A stale expected_world_version returns HTTP 409; refresh world state before retry. Missing/negative version fields return HTTP 422. Unavailable state or persistence failure returns HTTP 503 without partial mutation. Async 202 submission is deferred.

## 3.3 Read a Persisted Run

`GET /api/agent-runs/{run_id}` returns HTTP 200 and:

```text
data:
  run: the same summary contract as advancement
  proposals: ordered by ordinal
  events: ordered by event_sequence
  trace: ordered by sequence
```

Proposal fields are id, ordinal, actor_id, action_type, target_kind/target_id, reason_code, source, payload, status, rejection_code and rejection_message. Trace fields are sequence, stage, actor_id, summary, data, visibility and UTC created_at.

Trace stage 取值：`run_started`、`planning`、`rule_rejection`、`proposal`、`validation`、`execution`、`event`、`run_completed`。顺序固定：`run_started` 之后是每个 NPC 的 `planning`，然后是本 tick 发生的 `rule_rejection`，再按 ordinal 排列 `proposal` 与 `validation`，被接受的提案各追加一对 `execution` / `event`，最后 `run_completed`。纯确定性推进（无规划、无拒绝）的三 NPC run 是 sequence 1–14。

两个与兜底归因有关的 stage：

- **`planning`** 的 `data` 含 `npc_id`、`source`、`goal`、`thought`、`provider`、`model`、`latency_ms`、`tokens_used`、`failure_stage`、`failure_code`。后两项在规划成功或复用既有计划时为 `null`；当 Provider 未返回可用决策时，`failure_stage` 为 `"provider"`，`failure_code` 取 `timeout` / `http_status` / `transport` / `parse_error` / `unknown` 之一。它们是**枚举出来的类别名**，不含响应正文、URL 或凭据。
- **`rule_rejection`** 记录被规则拒绝、因而**被替换成确定性兜底**的原始提案。公开 `data` 含 `npc_id`、`failure_stage`（恒为 `"rule"`）、`failure_code`（`ActionRegistry` 与冲突处理的拒绝码，如 `unknown_location`、`wrong_duty_location`）、`attempted_action` 与 `attempted_source`。**`attempted_target` 只落盘、不公开** —— 它是模型编造的自由文本（`unknown_location` 恰恰意味着它不指向任何真实地点）。落盘完整、对外收窄，与 §4.4 的 `evidence` 同一条规则。

These are concise factual records. Hidden reasoning, raw prompts, credentials and raw provider errors are not exposed. Unknown run UUID returns 404, malformed UUID returns 422, database failure returns a safe 503. This read creates no new run and changes no world state.

# 4. NPC APIs

## 4.1 Get NPC Detail

Phase 1B 权威契约：

`docs/superpowers/specs/2026-08-23-phase-1b-npc-detail-explainability-design.md`

Method:

    GET /api/npcs/{npc_id}

Purpose:

返回指定 NPC 的 Profile、权威当前状态、当前世界上下文，以及最近三条持久化 Action。`npc_id` 使用稳定小写字符串 ID；Phase 1B 不提供 `limit` 查询参数。

Response:

``` json
{
  "success": true,
  "data": {
    "profile": {
      "id": "ryan",
      "name": "Ryan",
      "role": "Knight",
      "personality": ["optimistic", "brave", "kind"]
    },
    "state": {
      "location_id": "park",
      "location_name": "中央公园",
      "current_action": "work",
      "status": {
        "energy": 70,
        "mood": 75,
        "social": 67
      }
    },
    "world_context": {
      "day": 1,
      "time": "09:00",
      "clock_tick": 1,
      "time_phase": "morning"
    },
    "recent_actions": [
      {
        "id": 1,
        "clock_tick": 1,
        "world_time": "09:00",
        "action_type": "work",
        "target_kind": null,
        "target_id": null,
        "target_name": null,
        "reason_code": "knight_duty",
        "reason_text": "当前处于骑士履行训练职责的时间。"
      }
    ]
  },
  "message": "ok"
}
```

数据规则：

-   `recent_actions` 按 `clock_tick DESC, id DESC` 返回，最多三条；Tick 0 时为空列表。
-   历史 Action 的持久化 `reason` 机器代码对外暴露为 `reason_code`，`reason_text` 是确定性规则摘要。
-   `reason_text` 不是 chain-of-thought、隐藏推理或完整 Agent Trace。
-   地点/NPC 目标名称由 Backend 解析；无法解析时保留 `target_id` 并作为 `target_name` 回退。
-   本端点不返回 `relationships` 或重复的 Event 记录。

NPC Profile 不存在时返回 HTTP 404：

``` json
{
  "success": false,
  "data": null,
  "message": "NPC not found"
}
```

标准世界、NPC State、当前 Location 或数据库不可用时返回 HTTP 503：

``` json
{
  "success": false,
  "data": null,
  "message": "NPC detail is unavailable"
}
```

## 4.2 NPC Chat

Phase 1C 已实现。Chat 是独立文本交互切片，不修改 World Tick、NPC State、Action 或 Event。

Method:

    POST /api/npcs/{npc_id}/chat

首轮 Request：

``` json
{
  "conversation_id": null,
  "message": "你好 Ryan"
}
```

续聊 Request：

``` json
{
  "conversation_id": "5e547c21-a228-4e86-940d-a1bf5d65702f",
  "message": "那我们该怎么应对？"
}
```

带当前玩家自述的 Request（首轮、续聊均可选）：

``` json
{
  "conversation_id": null,
  "message": "你认识我吗？",
  "player_profile": {
    "display_name": "洛恩",
    "adventurer_class": "ranger"
  }
}
```

约束：

-   `conversation_id` 为 UUID 或 `null`；首轮由 Backend 分配 UUID。
-   `message` 去除首尾空白后长度为 1–500。
-   续聊 UUID 必须属于相同 `world_id + npc_id`，不能跨 NPC 复用。
-   `player_profile` 整体可省略；省略时保持 Phase 1C 请求兼容。
-   `display_name` 去除首尾空白后长度为 1–16，只允许汉字、英文字母、数字、空格、`·` 和 `-`。
-   `adventurer_class` 只能是 `mage`、`ranger`、`cleric`。
-   `player_profile` 内出现额外字段、非法名称或未知职业时返回 HTTP 422，不进入 ChatService。
-   该对象只用于当次称呼和对话风格，不是玩家过去、身份、任务或世界事实的证据。
-   当前没有账号、登录或 Backend Player Profile Schema；固定 `default-player` 仍只保存语义地点和 Quest 状态。

成功响应：

``` json
{
  "success": true,
  "data": {
    "conversation_id": "5e547c21-a228-4e86-940d-a1bf5d65702f",
    "npc_id": "ryan",
    "turn": {
      "user": {
        "id": 1,
        "role": "user",
        "content": "你害怕史莱姆吗？"
      },
      "assistant": {
        "id": 2,
        "role": "assistant",
        "content": "害怕？当然不是……我只是觉得史莱姆比看起来更麻烦。",
        "emotion": "guarded"
      }
    },
    "provider": "mock",
    "fallback_used": false
  },
  "message": "ok"
}
```

`emotion` 只能是：`neutral`、`cheerful`、`reserved`、`guarded`、`thoughtful`、`concerned`。

当 Primary compatible Provider 失败并成功回退时，HTTP 仍为 200，`provider="mock"` 且 `fallback_used=true`；这两个字段同时保存到 Assistant 消息元数据。

NPC 不存在或 conversation 不属于当前 NPC 时返回 HTTP 404：

``` json
{
  "success": false,
  "data": null,
  "message": "NPC not found"
}
```

或：

``` json
{
  "success": false,
  "data": null,
  "message": "Conversation not found"
}
```

请求 UUID、消息长度/空白、玩家名称/职业或嵌套额外字段校验失败时，使用 FastAPI 标准 HTTP 422 `detail` 响应，不进入 ChatService。

上下文不可用时返回 HTTP 503：

``` json
{
  "success": false,
  "data": null,
  "message": "Chat context is unavailable"
}
```

Provider 与 Mock 均不可用或聊天持久化失败时返回：

``` json
{
  "success": false,
  "data": null,
  "message": "Chat service is unavailable"
}
```

Backend flow：

    Load NPC Profile
    ↓
    Load authoritative World/NPC/Location/recent Actions
    ↓
    Load versioned Prompt + bounded conversation history
    ↓
    Retrieve permission-filtered long-term Memory (player_dialogue scope)
    ↓
    Generate and strictly validate reply + emotion
    ↓
    Atomically save complete User + Assistant turn
    ↓
    Project the committed turn into cognition (post-commit, best-effort)

Stage 2 在此链路中新增了两步，但**请求体、响应体和状态码完全不变**。检索在 `player_dialogue` scope 下执行，排除来源 Turn 仍在活跃 history 窗口内的记忆；当前这条消息只影响**下一轮**，它自己的 Turn 在事务提交后才被投影。检索或投影失败只降级上下文，不会让 Chat 失败。

## 4.3 Get NPC Memory Explanations

Method:

    GET /api/npcs/{npc_id}/memory-explanations

只读接口。返回该 NPC **已被允许公开**的记忆的安全摘要，用于 RPG 页面的"相关记忆"区域。

Request：无请求体。**不接受任何 query 参数** —— 没有 query、owner、scope、limit 或 secrecy。查询情境由 Backend 用当前公开的 World/Quest 上下文自行构造。

Success response：

```json
{
  "success": true,
  "data": {
    "npc_id": "grey",
    "retrieval_mode": "hybrid",
    "fallback_used": false,
    "memories": [
      {
        "id": "0f5f1f4c-5a7a-4a9c-9d0e-9a1b2c3d4e5f",
        "type": "episodic",
        "summary": "Grey 记得在低语森林附近发生过一件与当前线索有关的事。",
        "occurred_clock_tick": 2,
        "source": {
          "kind": "world_event",
          "label": "亲历事件"
        },
        "reason_text": "这段记忆和你此刻关心的事情在含义上最接近。"
      }
    ]
  },
  "message": "ok"
}
```

字段约束（与 `backend/app/schemas/npc.py` 逐字段一致）：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `npc_id` | string | — |
| `retrieval_mode` | enum | `hybrid` 或 `lexical_fallback` |
| `fallback_used` | bool | `retrieval_mode == "lexical_fallback"` 时为 true |
| `memories` | array | **最多 5 条** |
| `memories[].id` | UUID | 记忆的不透明标识 |
| `memories[].type` | enum | `episodic`、`conversation`、`reflection`、`knowledge` |
| `memories[].summary` | string | 1–240 字符 |
| `memories[].occurred_clock_tick` | int | >= 0 |
| `memories[].source.kind` | enum | `world_event`、`conversation`、`authored_knowledge`、`reflection` |
| `memories[].source.label` | string | 1–40 字符，取值 `亲历事件`、`听到的说法`、`稳定知识`、`形成的看法` |
| `memories[].reason_text` | string | 1–120 字符，固定模板集 |

`reason_text` 由已选中记忆的公开评分分量确定性映射到固定模板，**不返回任何数字分数**。模板按检索模式选取：降级为 `lexical_fallback` 时语义分量结构性为 0，因此不会输出语义相关的理由。

隐私边界：

- 只返回 `secrecy=public` **且** `disclosure_scope=public` 的记忆。过滤发生在 SQL 层、在任何相似度排序之前。
- 不返回玩家聊天原文、秘密 Memory、隐藏 reflection、Belief 全文、Embedding、完整分数、Prompt 或 Provider 错误。
- 不可见内容不通过总数、占位符、ID 或不同的错误形态泄露 —— 不满足条件的记忆直接不出现。
- `conversation` 出现在两个枚举中是**面向未来的扩展位**。当前实现里，玩家对话产生的 Observation 固定为 `secrecy=private` / `disclosure_scope=player_dialogue`，因此被硬过滤排除，该分支实际不可达。若未来出现 `public/public` 的对话记忆，其 summary 固定为非原文说明「这位居民记得与你有过一次相关交谈。」，永不使用原始 `content`。
- 跨会话的真实召回通过 Chat 行为体现，不通过这个匿名 GET 暴露聊天历史。

Error responses：

| 状态码 | 场景 | 响应 |
| --- | --- | --- |
| 404 | NPC 不存在 | 沿用现有风格：`{"success": false, "data": null, "message": "NPC not found"}` |
| 503 | 认知读取不可用 | `{"success": false, "data": null, "message": "NPC memory explanations are unavailable"}` |

503 只在**记忆读取本身失败**时返回。读取前的有界 `catch_up_owner` 若失败，接口降级为读取已投影的既有记忆并记录安全日志，不返回 503 —— 投影新鲜度不是正确性前提。

本阶段不新增 Memory 写接口、Reflection 触发接口、任意向量搜索接口或调试参数。

## 4.4 Get NPC Plan

Method:

    GET /api/npcs/{npc_id}/plan

只读接口（Stage 3m 新增）。返回该 NPC 当前活跃的计划与最近若干条历史计划，用于 NPC 详情页的「思考」Tab。

Request：无请求体。**不接受任何 query 参数** —— 没有 limit、status 或 world_id。世界由 Backend 用 `CANONICAL_WORLD_ID` 自行确定，历史条数固定为 5。

Success response：

```json
{
  "success": true,
  "data": {
    "current": {
      "id": "8f1c2d3e-4a5b-4c6d-8e9f-0a1b2c3d4e5f",
      "goal": "确认孩子最后出现的位置",
      "goal_reason": "旅人刚提到低语森林的石堆，值得先去看看。",
      "thought": "先到森林边缘，再决定要不要深入。",
      "steps": [
        {
          "action_type": "move",
          "target_kind": "location",
          "target_id": "whisper_forest",
          "intent": "前往低语森林边缘查看"
        }
      ],
      "current_step_index": 0,
      "status": "active",
      "created_clock_tick": 7,
      "provider": "openai_compatible",
      "model": "hy3",
      "latency_ms": 15976,
      "tokens_used": 3688,
      "evidence": [
        {
          "id": "0f5f1f4c-5a7a-4a9c-9d0e-9a1b2c3d4e5f",
          "type": "episodic",
          "label": "亲历事件",
          "summary": "Grey 记得在低语森林附近发生过一件与当前线索有关的事。"
        }
      ]
    },
    "recent": []
  },
  "message": "ok"
}
```

字段约束（与 `backend/app/schemas/plan.py` 逐字段一致）：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `current` | object \| null | 当前活跃计划；没有活跃计划时为 `null` |
| `recent` | array | 最近计划，**最多 5 条**，含已结束的 |
| `*.id` | UUID | 计划的不透明标识 |
| `*.goal` | string | <= 200 字符 |
| `*.goal_reason` | string | <= 500 字符 |
| `*.thought` | string | <= 800 字符 |
| `*.steps` | array | 1–4 步 |
| `*.steps[].action_type` | enum | `move`、`work`、`eat`、`talk`、`rest`、`wait` |
| `*.steps[].target_kind` | string \| null | `location` 或 `npc`；无目标时为 `null` |
| `*.steps[].target_id` | string \| null | 对应地点或 NPC 的 id |
| `*.steps[].intent` | string | 1–200 字符，该步意图的自然语言说明 |
| `*.current_step_index` | int | >= 0 |
| `*.status` | enum | `active`、`completed`、`abandoned` |
| `*.created_clock_tick` | int | >= 0 |
| `*.provider` / `*.model` | string | 由 Backend 记录，**不由模型自报** |
| `*.latency_ms` / `*.tokens_used` | int \| null | 复用已有计划的 tick 不产生新值 |
| `*.evidence` | array | 本次规划检索命中、**且允许公开**的记忆 |
| `*.evidence[].type` | enum | `episodic`、`conversation`、`reflection`、`knowledge` |
| `*.evidence[].label` | string | 取值 `亲历事件`、`听到的说法`、`稳定知识`、`形成的看法` |
| `*.evidence[].summary` | string | <= 240 字符，安全摘要，非原文 |

隐私边界：

- 计划落盘的引用 id 是**完整**的（planner 用 `INTERNAL_REFLECTION` scope 检索，含 secret 与 internal_only），但本接口返回前会**重新过一遍 `PUBLIC_EXPLANATION` 硬过滤**。不可公开的记忆既不出现内容，也不以计数或占位符暴露差额 —— 与 `4.3` 同一条规则。
- `evidence` 表示**进入规划上下文的检索结果**，不表示模型在 `thought` 里逐条明确引用了它们。
- `recent[].evidence` 恒为空数组：历史计划只展示目标与状态，不为每条再查一次记忆（那是 N 次额外查询）。这是**设计决定**，不代表那些计划没有引用记忆。
- 不返回 Prompt、模型原始响应、Embedding、检索分数或 Provider 错误详情。
- `evidence_memory_ids_json` 为 `None`（`0006` 之前写入的计划）与 `[]`（确实没检索到）在存储层刻意可区分，但在本接口的响应里都表现为空数组。

Error responses：

| 状态码 | 场景 | 响应 |
| --- | --- | --- |
| 404 | NPC 不存在 | `{"success": false, "data": null, "message": "NPC not found"}` |
| 503 | NPC 详情不可用，或计划行读取失败 / 形状异常 | `{"success": false, "data": null, "message": "npc plan is unavailable"}` |

计划行由本服务自己写入，因此形状异常属于**服务端**故障，对外仍收敛成有界的 503，不泄露内部结构。

本接口不提供计划的创建、修改、取消或重规划入口 —— 计划只能由 `POST /api/world/tick` 的推进过程产生。

# 5. Player APIs

Phase 1D 使用固定玩家 `default-player`，不提供创建、登录或职业 API。

## 5.1 Get Player And Quest

Method:

    GET /api/player

Purpose:

返回玩家权威位置、任务状态、版本、当前 objective、当前位置可执行 interaction 和最近五条 Quest Event。

Response excerpt:

``` json
{
  "success": true,
  "data": {
    "player": {
      "id": "default-player",
      "location_id": "tavern",
      "location_name": "星辉酒馆"
    },
    "quest": {
      "id": "missing-child",
      "title": "失踪的孩子",
      "status": "available",
      "version": 0,
      "objective": "查看星辉酒馆告示板上的失踪委托。",
      "available_interactions": [
        {"id": "accept_quest", "label": "接受委托"}
      ],
      "recent_events": []
    }
  },
  "message": "ok"
}
```

Errors: Player/Quest 不存在为 404；数据库不可用为安全 503。

## 5.2 Travel

Method:

    POST /api/player/travel

Request:

``` json
{"target_location_id": "castle", "expected_world_version": 0}
```

旅行到当前地点是幂等成功。未知地点为 404，非法 ID 为 422，数据库失败为 503。成功实际旅行更新 Player location、world_version，并写入 player_travelled 事件，不推进 clock_tick、NPC State 或 Quest。过期 expected_world_version 返回 409；旅行到当前地点不会重复增加版本或事件。

## 5.3 Interact With Missing Child Quest

Method:

    POST /api/quests/missing-child/interact

Request:

``` json
{
  "interaction": "ask_grey",
  "expected_version": 1,
  "expected_world_version": 2
}
```

合法 interaction 为 `accept_quest/ask_grey/inspect_shoe/search_child/return_child`。Backend 校验当前状态、玩家位置、Grey 实时位置、任务 expected_version 和全局 expected_world_version；成功返回与 `GET /api/player` 相同的完整聚合，并原子写入 Quest Progress + Quest Event + quest_transitioned 领域事件，同时增加 world_version。clock_tick 保持不变；示例版本值需使用客户端最新状态。

错误契约：

-   404：Player、Quest 或目标资源不存在。
-   409：`expected_version` 或 `expected_world_version` 过期，或当前状态/地点不允许该 interaction。
-   422：字段缺失、非法 ID、未知 interaction 或负版本。
-   503：读取或事务提交失败；不得留下半次迁移。

# 6. Health, Reset and Deferred APIs

`GET /api/health` checks API/database/provider configuration and reports database unavailability as 503.

`POST /api/demo/reset` resets the target demo world and its quest/chat/runtime history in one transaction. It is an explicit demo reset, not an incremental migration.

There is no independent `GET /api/events` endpoint yet. Events are returned by advancement and persisted-run detail. The bounded `GET /api/npcs/{npc_id}/memory-explanations` and `GET /api/npcs/{npc_id}/plan` contracts are implemented as documented above; arbitrary memory search/write APIs, plan creation/cancellation APIs, async submission, SSE and Agent Lab are not implemented.

# 7. Internal Agent Contracts

`backend/app/agents/` implements immutable ActionProposal, ActionValidation, ResolvedProposal, DomainEventDraft, TraceDraft and AgentRuntimeResult contracts. The registry alone validates legal actions and effects. All proposals consume one immutable WorldSnapshot; no proposal sees another proposal's result.

Proposal `source` records how each proposal was produced: `llm` (a new plan returned by the planning provider), `existing_plan` (a step reused from an active plan, with no model call this tick), `fallback` (planning was unavailable and the deterministic policy took over) and `deterministic` (the run advanced in deterministic mode). Whatever the source, every proposal passes the same registry validation, conflict resolution and single-transaction commit.

# 8. Error Handling

400:

参数错误

422:

请求 Schema 校验错误

404:

资源不存在

500:

服务器异常

AI failure:

    LLM Error
    ↓
    Mock Provider
    ↓
    Valid Result with fallback_used=true

Provider 失败不会修改 World Engine。若 Primary 与 Mock 均失败，则返回安全 HTTP 503，且不保存半轮消息。

# 9. API Design Principles

## Backend Authority

所有世界状态修改必须经过Backend。

## AI Output Validation

模型输出不能直接执行。

## Future Compatibility

支持未来：

-   Agent Lab 与异步运行（当前 RPG 已使用 Phaser）
-   Memory增强
-   更多任务与通用 Quest 引擎
-   多玩家扩展

# End of Document
