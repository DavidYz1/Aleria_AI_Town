# Aleria AI Town API Contract

Version: v2.0

Last Updated: 2026-09-07

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

Proposal fields are id, ordinal, actor_id, action_type, target_kind/target_id, reason_code, source, payload, status, rejection_code and rejection_message. Trace fields are sequence, stage, actor_id, summary, data, visibility and UTC created_at. The first three-NPC run has trace sequences 1–14 spanning run_started, proposal, validation, execution, event and run_completed.

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
    Generate and strictly validate reply + emotion
    ↓
    Atomically save complete User + Assistant turn

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

There is no independent `GET /api/events` endpoint yet. Events are returned by advancement and persisted-run detail. Async submission, SSE, Agent Lab, memory and LLM action-cognition APIs are not implemented.

# 7. Internal Agent Contracts

`backend/app/agents/` implements immutable ActionProposal, ActionValidation, ResolvedProposal, DomainEventDraft, TraceDraft and AgentRuntimeResult contracts. The registry alone validates legal actions and effects. All proposals consume one immutable WorldSnapshot; no proposal sees another proposal's result.

Proposal source enum values reserved for future modes do not mean that LLM planning or memory is implemented.

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
