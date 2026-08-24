# Aleria AI Town API Contract

Version: v1.5

Last Updated: 2026-08-24

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

# 3. World APIs

## 3.1 Get World State

Phase 0权威契约：

`docs/superpowers/specs/2026-08-22-phase-0-engineering-initialization-design.md`

Method:

    GET /api/world

Purpose:

获取当前世界状态：

-   世界时间
-   地点
-   NPC状态

玩家状态和最近事件将在对应功能进入实施阶段后扩展，不属于Phase 0响应。

Response example:

``` json
{
  "success": true,
  "data": {
    "world": {
      "id": "aleria-town",
      "name": "曦谷",
      "day": 1,
      "time": "08:00",
      "tick": 0
    },
    "locations": [
      {
        "id": "tavern",
        "name": "星辉酒馆",
        "description": "旅行者交换消息、接受委托和休息的温暖酒馆"
      },
      {
        "id": "park",
        "name": "中央公园",
        "description": "居民散步、放松和进行日常训练的开阔绿地"
      },
      {
        "id": "castle",
        "name": "晨曦城堡",
        "description": "守卫曦谷、眺望山谷边境的古老城堡"
      },
      {
        "id": "forest",
        "name": "低语森林",
        "description": "林间低语与旧日传闻交织的幽深森林"
      }
    ],
    "npcs": [
      {
        "id": "ryan",
        "name": "Ryan",
        "role": "Knight",
        "personality": ["optimistic", "brave", "kind"],
        "location_id": "castle",
        "current_action": "rest",
        "status": {
          "energy": 80,
          "mood": 78,
          "social": 70
        }
      },
      {
        "id": "shir",
        "name": "Shir",
        "role": "Assassin",
        "personality": ["quiet", "introverted", "observant"],
        "location_id": "tavern",
        "current_action": "eat",
        "status": {
          "energy": 72,
          "mood": 65,
          "social": 35
        }
      },
      {
        "id": "grey",
        "name": "Grey",
        "role": "Guardian",
        "personality": ["reliable", "calm", "protective"],
        "location_id": "park",
        "current_action": "work",
        "status": {
          "energy": 88,
          "mood": 74,
          "social": 55
        }
      }
    ]
  },
  "message": "ok"
}
```

排序规则：

-   `locations`按照持久化的 `sort_order` 升序返回。
-   `npcs`按照 `npc_profiles.sort_order` 升序返回。

SQLite未初始化或世界状态不可用时：

HTTP Status:

    503

``` json
{
  "success": false,
  "data": null,
  "message": "world state is unavailable"
}
```

## 3.2 Advance World Tick

Phase 1A权威契约：

`docs/superpowers/specs/2026-08-23-phase-1a-deterministic-world-tick-design.md`

Method:

    POST /api/world/tick

Purpose:

使用乐观锁推进一个一小时世界回合。请求必须携带Frontend当前看到的Tick：

``` json
{
  "expected_tick": 0
}
```

Flow:

    Update Clock
    ↓
    NPC Decision
    ↓
    Action Validation
    ↓
    Execute Action
    ↓
    Update State
    ↓
    Save Event

Response:

``` json
{
  "success": true,
  "data": {
    "world": {
      "world": {
        "id": "aleria-town",
        "name": "曦谷",
        "day": 1,
        "time": "09:00",
        "tick": 1
      },
      "locations": [
        {"id": "tavern", "name": "星辉酒馆", "description": "旅行者交换消息、接受委托和休息的温暖酒馆"},
        {"id": "park", "name": "中央公园", "description": "居民散步、放松和进行日常训练的开阔绿地"},
        {"id": "castle", "name": "晨曦城堡", "description": "守卫曦谷、眺望山谷边境的古老城堡"},
        {"id": "forest", "name": "低语森林", "description": "林间低语与旧日传闻交织的幽深森林"}
      ],
      "npcs": [
        {
          "id": "ryan", "name": "Ryan", "role": "Knight",
          "personality": ["optimistic", "brave", "kind"],
          "location_id": "castle", "current_action": "work",
          "status": {"energy": 70, "mood": 75, "social": 67}
        },
        {
          "id": "shir", "name": "Shir", "role": "Assassin",
          "personality": ["quiet", "introverted", "observant"],
          "location_id": "park", "current_action": "move",
          "status": {"energy": 65, "mood": 64, "social": 32}
        },
        {
          "id": "grey", "name": "Grey", "role": "Guardian",
          "personality": ["reliable", "calm", "protective"],
          "location_id": "park", "current_action": "work",
          "status": {"energy": 78, "mood": 71, "social": 52}
        }
      ]
    },
    "actions": [
      {
        "id": 1,
        "tick": 1,
        "actor_id": "ryan",
        "action_type": "work",
        "target_kind": null,
        "target_id": null,
        "reason": "knight_training",
        "status": "recorded",
        "world_time": "09:00"
      }
    ],
    "events": [
      {
        "id": 1,
        "tick": 1,
        "event_type": "npc_action",
        "actor_id": "ryan",
        "action_id": 1,
        "description": "Ryan 工作",
        "world_time": "09:00"
      }
    ]
  },
  "message": "ok"
}
```

`world`是完整的 `GET /api/world` Data对象，不是局部补丁。

当 `expected_tick` 已过期时返回HTTP 409：

``` json
{
  "success": false,
  "data": null,
  "message": "world tick conflict; refresh and retry"
}
```

世界未初始化或事务持久化失败时返回HTTP 503。`expected_tick < 0` 返回HTTP 422。

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
      "tick": 1,
      "time_phase": "morning"
    },
    "recent_actions": [
      {
        "id": 1,
        "tick": 1,
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

-   `recent_actions` 按 `tick DESC, id DESC` 返回，最多三条；Tick 0 时为空列表。
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

约束：

-   `conversation_id` 为 UUID 或 `null`；首轮由 Backend 分配 UUID。
-   `message` 去除首尾空白后长度为 1–500。
-   续聊 UUID 必须属于相同 `world_id + npc_id`，不能跨 NPC 复用。
-   当前没有 `player_id`、登录或 Player 表。

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

请求 UUID/长度/空白校验失败使用 FastAPI 标准 HTTP 422 `detail` 响应，不进入 ChatService。

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
      "objective": "查看星辉酒馆的委托板。",
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
{"target_location_id": "castle"}
```

旅行到当前地点是幂等成功。未知地点为 404，非法 ID 为 422，数据库失败为 503。成功旅行只更新 Player location，不推进 World Tick、NPC State 或 Quest。

## 5.3 Interact With Missing Child Quest

Method:

    POST /api/quests/missing-child/interact

Request:

``` json
{
  "interaction": "ask_grey",
  "expected_version": 1
}
```

合法 interaction 为 `accept_quest/ask_grey/inspect_shoe/search_child/return_child`。Backend 校验当前状态、玩家位置、Grey 实时位置和版本；成功返回与 `GET /api/player` 相同的完整聚合，并原子写入 Quest Progress + Quest Event。

错误契约：

-   404：Player、Quest 或目标资源不存在。
-   409：`expected_version` 过期，或当前状态/地点不允许该 interaction。
-   422：字段缺失、非法 ID、未知 interaction 或负版本。
-   503：读取或事务提交失败；不得留下半次迁移。

# 6. Event APIs

独立 Event 查询 API 尚未实现。当前 Event 只在成功的 `POST /api/world/tick` 响应中返回。

## Get Timeline

Method:

    GET /api/events

Purpose:

获取世界事件历史。

Example:

``` json
{
  "time": "10:00",
  "actor": "Ryan",
  "event": "started training"
}
```

# 7. Internal Agent Interfaces

以下是后续 Hybrid Agent 的概念接口，尚未作为可调用模块实现。Phase 1A/1B 当前使用 `backend/app/world/` 中经过测试的确定性 Decision Policy 和 Action Validation。

## Decide Action

    agent.decide_action()

Input:

``` json
{
  "npc_id": "ryan",
  "world_state": {},
  "memory": []
}
```

Output:

``` json
{
  "action": "social",
  "target": "grey",
  "reason": "want to talk"
}
```

## Validate Action

    agent.validate_action()

Checks:

-   action validity
-   target existence
-   world rule constraints

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

-   Canvas/Pixi地图
-   Memory增强
-   更多任务与通用 Quest 引擎
-   多玩家扩展

# End of Document
