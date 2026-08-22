# Aleria AI Town Database Schema Design

Version: v1.1

Last Updated: 2026-08-22

# 1. Database Design Overview

## 1.1 Purpose

数据库负责保存 Aleria AI Town 的长期世界状态。

设计目标：

-   支持 World Simulation
-   支持 NPC Agent
-   支持玩家交互
-   支持事件追踪
-   支持未来扩展

初始数据库：

SQLite

## 1.2 Implementation Authority And Phases

数据库概念模型保留完整演进方向，但物理建表按阶段实施。

Phase 0只创建：

-   `world_state`
-   `locations`
-   `npc_profiles`
-   `npc_states`

Phase 1在实现World Tick时增加：

-   `actions`
-   `events`

Phase 2及以后按实际用例增加：

-   `entities`
-   `player_profiles`
-   `relationships`
-   `memories`
-   `world_snapshots`

根目录 `data/*.json` 只作为可读种子输入。运行时状态只保存在SQLite中。

所有World、Location和NPC主键使用稳定的小写字符串ID。API DTO不直接等同数据库表结构。

Phase 0字段约束：

``` text
world_state(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  day INTEGER NOT NULL CHECK(day >= 1),
  time TEXT NOT NULL,
  tick INTEGER NOT NULL CHECK(tick >= 0)
)

locations(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  sort_order INTEGER NOT NULL UNIQUE
)

npc_profiles(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  personality_json TEXT NOT NULL,
  sort_order INTEGER NOT NULL UNIQUE
)

npc_states(
  npc_id TEXT PRIMARY KEY REFERENCES npc_profiles(id),
  location_id TEXT NOT NULL REFERENCES locations(id),
  current_action TEXT NOT NULL,
  energy INTEGER NOT NULL CHECK(energy BETWEEN 0 AND 100),
  mood INTEGER NOT NULL CHECK(mood BETWEEN 0 AND 100),
  social INTEGER NOT NULL CHECK(social BETWEEN 0 AND 100)
)
```

NPC当前位置只保存在 `npc_states.location_id`，不在Profile或Entity表中重复保存。

访问方式：

Application Layer

↓

Repository Layer

↓

SQLite

------------------------------------------------------------------------

# 2. Design Principles

## 2.1 Entity First

世界中的行动主体统一抽象为 Entity。

包括：

-   NPC
-   Player

结构：

    Entity

    |

    ----------------

    NPC

    Player

    ----------------

这样：

-   NPC-NPC关系
-   NPC-Player关系
-   Player-Player关系

都可以统一处理。

------------------------------------------------------------------------

## 2.2 Relational Core + JSON Extension

核心业务数据：

采用关系型设计。

例如：

-   Entity
-   Location
-   Relationship

复杂变化数据：

允许 JSON。

例如：

-   Personality
-   Traits
-   Metadata

------------------------------------------------------------------------

## 2.3 State And History Separation

当前状态：

表示现在。

历史记录：

表示过去。

分离：

    Current State

    +

    Action History

    +

    Event History

------------------------------------------------------------------------

# 3. Entity Tables

本节描述Phase 2及以后的统一Entity演进模型；Phase 0不创建 `entities` 表。

# 3.1 entities

所有世界实体。

Schema:

  Field         Type       Description
  ------------- ---------- ------------------
  id            string     Stable Entity ID
  type          string     npc/player
  name          string     Name
  created_at    datetime   Creation time

Example:

``` json
{
"id":"ryan",
"type":"npc",
"name":"Ryan"
}
```

------------------------------------------------------------------------

# 4. NPC Tables

# 4.1 npc_profiles

保存NPC静态信息。

Fields:

  Field         Description
  ------------- ------------------
  id            Stable NPC ID
  role          职业
  personality   JSON personality
  background    Background story
  sort_order    Display order

Example:

``` json
{
"personality":[
"brave",
"kind"
],
"background":"Afraid of slime"
}
```

------------------------------------------------------------------------

# 5. Player Tables

# 5.1 player_profiles

保存玩家档案。

不包含：

-   password
-   login
-   authentication

Fields:

  Field       Description
  ----------- --------------
  entity_id   Entity ID
  class       Player class

Example:

``` json
{
"class":"Mage"
}
```

------------------------------------------------------------------------

# 6. Entity State

## entity_states

保存实时状态。

Phase 0实现使用名称更明确的 `npc_states`；引入Player统一实体后再迁移为 `entity_states`。

Fields:

  Field            Description
  ---------------- ----------------
  entity_id        Entity
  location_id      Current location
  energy           Energy
  mood             Mood
  social           Social need
  current_action   Current action
  goal             Current goal

Example:

``` json
{
"location_id":"park",
"energy":70,
"mood":75,
"social":60,
"current_action":"rest"
}
```

------------------------------------------------------------------------

# 7. Location

## locations

保存世界地点。

Fields:

  Field               Description
  ------------------- --------------
  id                  Location ID
  name                Name
  description         Description
  available_actions   JSON actions
  sort_order          Display order

Example:

``` json
{
"id":"tavern",
"name":"Star Tavern"
}
```

------------------------------------------------------------------------

# 8. Relationship

## relationships

保存实体之间关系。

Fields:

  Field            Description
  ---------------- --------------------
  from_entity_id   Source
  to_entity_id     Target
  type             Relationship type
  score            Relationship score

Example:

    Ryan

    respect 80

    Grey

支持：

-   NPC-NPC
-   NPC-Player
-   Player-Player

------------------------------------------------------------------------

# 9. Action Log

## actions

记录实体行为。

Fields:

  Field         Description
  ------------- ------------------
  actor_id      Entity
  action_type   Action
  target_id     Target
  reason        Explanation
  status        Lifecycle status
  timestamp     Time

Action lifecycle:

    Proposed

    ↓

    Validated

    ↓

    Executed

    ↓

    Recorded

------------------------------------------------------------------------

# 10. Event Log

## events

记录世界事件。

Action 和 Event 区别：

Action:

某个实体做了什么。

Event:

世界发生了什么。

Example:

Action:

    Ryan move to Tavern

Event:

    Ryan met Player in Tavern

Fields:

  Field         Description
  ------------- -------------
  type          Event type
  actor_id      Actor
  description   Description
  timestamp     Time

------------------------------------------------------------------------

# 11. Memory

## memories

保存Agent记忆。

Fields:

  Field        Description
  ------------ ------------------
  entity_id    Owner
  content      Memory
  importance   Importance score
  created_at   Time

Example:

    Ryan remembers:

    Player helped him yesterday.

    importance=8

未来扩展：

增加：

    embedding

支持：

Vector Retrieval。

------------------------------------------------------------------------

# 12. World State

## world_state

保存当前世界状态。

Fields:

  Field     Description
  --------- --------------
  id        Stable World ID
  name      World display name
  day       Day
  time      Current time
  tick      Tick number
  weather   Weather

Example:

``` json
{
"id":"aleria-town",
"name":"晨曦镇",
"day":1,
"time":"10:00",
"tick":10
}
```

------------------------------------------------------------------------

# 13. World Snapshot

## world_snapshots

保存历史世界快照。

Purpose:

-   Debug
-   Rollback
-   Replay

Fields:

  Field        Description
  ------------ -------------
  id           Snapshot ID
  tick         Tick number
  state_json   World state
  created_at   Time

Example:

    Day 2 12:00 Snapshot

------------------------------------------------------------------------

# 14. Tick Version Control

## Purpose

防止多个请求同时推进世界。

World Tick采用版本控制。

Example:

Current:

    tick = 10

Request A:

    expect tick=10

Request B:

    expect tick=10

只有一个成功。

更新：

    tick 10

    ↓

    tick 11

另一个请求失败。

类似：

Optimistic Lock。

------------------------------------------------------------------------

# 15. Future Tables

预留：

## quests

任务系统。

## inventory

物品系统。

## conversations

完整聊天历史。

当前MVP不实现。

------------------------------------------------------------------------

# 16. Final Schema Overview

    Database


    world_state

    world_snapshots


    locations


    entities

        |

        |---- npc_profiles

        |

        |---- player_profiles


    entity_states


    relationships


    actions


    events


    memories


    quests(optional)

------------------------------------------------------------------------

# End of Document
