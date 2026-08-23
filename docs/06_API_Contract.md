# Aleria AI Town API Contract

Version: v1.3

Last Updated: 2026-08-23

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
      "name": "晨曦镇",
      "day": 1,
      "time": "08:00",
      "tick": 0
    },
    "locations": [
      {
        "id": "tavern",
        "name": "星辰酒馆",
        "description": "冒险者交流和休息的地方"
      },
      {
        "id": "park",
        "name": "中央公园",
        "description": "居民散步和放松的地方"
      }
    ],
    "npcs": [
      {
        "id": "ryan",
        "name": "Ryan",
        "role": "Knight",
        "personality": ["optimistic", "brave", "kind"],
        "location_id": "park",
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
        "name": "晨曦镇",
        "day": 1,
        "time": "09:00",
        "tick": 1
      },
      "locations": [
        {"id": "tavern", "name": "星辰酒馆", "description": "冒险者交流和休息的地方"},
        {"id": "park", "name": "中央公园", "description": "居民散步和放松的地方"}
      ],
      "npcs": [
        {
          "id": "ryan", "name": "Ryan", "role": "Knight",
          "personality": ["optimistic", "brave", "kind"],
          "location_id": "park", "current_action": "work",
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
        "reason": "knight_duty",
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

规划中，尚未实现。以下仅为后续方向，不属于当前公共 API。

Method:

    POST /api/npcs/{npc_id}/chat

Request:

``` json
{
  "player_id": "player001",
  "message": "你好Ryan"
}
```

Backend flow:

    Load NPC Profile
    ↓
    Load Relationship
    ↓
    Retrieve Memory
    ↓
    Generate Reply
    ↓
    Save Memory

# 5. Player APIs

规划中，尚未实现。本节不属于当前公共 API。

## 5.1 Create Player

Method:

    POST /api/player

Purpose:

创建轻量玩家档案。

不包含：

-   登录
-   密码
-   权限系统

Request:

``` json
{
  "name": "Aria",
  "class": "Mage"
}
```

## 5.2 Get Player

Method:

    GET /api/player/{player_id}

## 5.3 Player Action

Method:

    POST /api/player/{player_id}/action

Example:

``` json
{
  "action": "move",
  "target": "park"
}
```

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

404:

资源不存在

500:

服务器异常

AI failure:

下列为未来 LLM Provider 接入后的计划降级路径；当前未实现 LLM/Mock Provider。

    LLM Error
    ↓
    Mock Provider
    ↓
    Valid Result

# 9. API Design Principles

## Backend Authority

所有世界状态修改必须经过Backend。

## AI Output Validation

模型输出不能直接执行。

## Future Compatibility

支持未来：

-   Canvas/Pixi地图
-   Memory增强
-   Quest系统
-   多玩家扩展

# End of Document
