# Aleria AI Town API Contract

Version: v1.1

Last Updated: 2026-08-22

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

Method:

    POST /api/world/tick

Purpose:

推进一个世界回合。

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
    "world_time": "11:00",
    "actions": [
      {
        "actor": "ryan",
        "action": "move",
        "target": "tavern",
        "reason": "want to socialize"
      }
    ]
  }
}
```

# 4. NPC APIs

## 4.1 Get NPC Detail

Method:

    GET /api/npcs/{npc_id}

Returns:

-   profile
-   current state
-   recent actions
-   relationships

Example:

``` json
{
  "profile": {
    "name": "Ryan",
    "role": "Knight",
    "personality": [
      "brave",
      "kind"
    ]
  },
  "state": {
    "location_id": "tavern",
    "current_action": "social",
    "energy": 70,
    "mood": 75,
    "social": 60
  }
}
```

## 4.2 NPC Chat

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
