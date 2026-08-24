# Aleria AI Town Database Schema Design

Version: v1.4

Last Updated: 2026-08-24

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

Phase 1A已实现上述两表。物理约束为：

``` text
actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_id TEXT NOT NULL REFERENCES world_state(id),
  tick INTEGER NOT NULL CHECK(tick >= 1),
  actor_id TEXT NOT NULL REFERENCES npc_profiles(id),
  action_type TEXT NOT NULL CHECK(action_type IN ('move','rest','work','eat','social')),
  target_kind TEXT NULL CHECK(target_kind IS NULL OR target_kind IN ('location','npc')),
  target_id TEXT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status = 'recorded'),
  world_time TEXT NOT NULL,
  UNIQUE(world_id, tick, actor_id)
)

events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_id TEXT NOT NULL REFERENCES world_state(id),
  tick INTEGER NOT NULL CHECK(tick >= 1),
  event_type TEXT NOT NULL CHECK(event_type = 'npc_action'),
  actor_id TEXT NOT NULL REFERENCES npc_profiles(id),
  action_id INTEGER NOT NULL UNIQUE REFERENCES actions(id),
  description TEXT NOT NULL,
  world_time TEXT NOT NULL
)
```

`target_id`是由应用层严格校验的多态目标：`target_kind=location`时引用地点ID，`target_kind=npc`时引用NPC ID。Phase 1A不为了这一字段提前引入统一Entity表。

一次Tick对 `world_state`、全部 `npc_states`、`actions` 和 `events` 的写入只提交一次；任一校验或数据库错误会整体回滚。`world_state.tick = expected_tick` 的条件更新提供乐观并发控制。

Phase 1C 在不修改 World Engine 表的前提下增加：

-   `conversations`
-   `conversation_messages`

物理约束为：

``` text
conversations(
  id TEXT PRIMARY KEY,
  world_id TEXT NOT NULL REFERENCES world_state(id),
  npc_id TEXT NOT NULL REFERENCES npc_profiles(id),
  created_tick INTEGER NOT NULL CHECK(created_tick >= 0),
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX ix_conversations_npc_updated(npc_id, updated_at)
)

conversation_messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  role TEXT NOT NULL CHECK(role IN ('user','assistant')),
  content TEXT NOT NULL,
  emotion TEXT NULL,
  provider TEXT NULL,
  fallback_used INTEGER NOT NULL CHECK(fallback_used IN (0,1)),
  prompt_version TEXT NULL,
  world_tick INTEGER NOT NULL CHECK(world_tick >= 0),
  created_at DATETIME NOT NULL,
  INDEX ix_conversation_messages_conversation_id_id(conversation_id, id)
)
```

User 与 Assistant 在同一个事务中成对写入。User 行的 `emotion/provider/prompt_version` 为 `NULL`；Assistant 行记录经过校验的情绪、实际 Provider、fallback 标记和 Prompt 版本。Provider 失败时不创建 Conversation，也不留下半轮消息。

Phase 1D 增加：

-   `player_states`
-   `quest_progress`
-   `quest_events`

```text
player_states(
  id TEXT PRIMARY KEY,
  world_id TEXT NOT NULL REFERENCES world_state(id),
  location_id TEXT NOT NULL REFERENCES locations(id),
  updated_at DATETIME NOT NULL
)

quest_progress(
  player_id TEXT REFERENCES player_states(id),
  quest_id TEXT,
  status TEXT NOT NULL,
  version INTEGER NOT NULL CHECK(version >= 0),
  updated_tick INTEGER NOT NULL CHECK(updated_tick >= 0),
  updated_at DATETIME NOT NULL,
  PRIMARY KEY(player_id, quest_id)
)

quest_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id TEXT NOT NULL REFERENCES player_states(id),
  quest_id TEXT NOT NULL,
  from_status TEXT NOT NULL,
  to_status TEXT NOT NULL,
  interaction TEXT NOT NULL,
  location_id TEXT NOT NULL REFERENCES locations(id),
  world_tick INTEGER NOT NULL CHECK(world_tick >= 0),
  created_at DATETIME NOT NULL,
  INDEX ix_quest_events_player_quest_id(player_id, quest_id, id)
)
```

Quest 更新使用 `player_id + quest_id + expected version` 条件写入；命中行数为 0 表示并发冲突。一次成功 interaction 的 Progress 更新与 Quest Event 插入只提交一次，失败整体回滚。

Phase 2及以后按实际用例增加：

-   `entities`
-   `player_profiles`
-   `relationships`
-   `memories`
-   `world_snapshots`

根目录 `data/*.json` 只作为可读种子输入。运行时状态只保存在SQLite中。

重播种表示把目标世界恢复到种子 Tick，因此会在同一事务中按 `quest_events → quest_progress → player_states → conversation_messages → conversations → events → actions` 的依赖顺序清理，再插入固定 Player/Quest 初始记录并重置 World/NPC；其他 `world_id` 数据不受影响。

已有Phase 0数据库使用 `python scripts/upgrade_schema.py` 增量创建缺失表。该命令只执行SQLAlchemy `create_all` 的加表操作，不重置当前状态或历史；未来出现改列、数据迁移等需求时再引入版本化迁移工具。

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
"name":"曦谷",
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

# 15. Current And Future Tables

## player_states / quest_progress / quest_events

Phase 1D 已实现固定 Player 和一个专用任务。它们不是通用 Quest Definition、奖励或背包系统。

## inventory

物品系统。

## conversations / conversation_messages

Phase 1C 已实现聊天会话与消息历史。Conversation 绑定稳定的 World/NPC 边界；消息按自增 `id` 保持顺序，Repository 只向 Chat Context 返回配置上限内的最新消息，并恢复为时间正序。

当前实现不把 Chat 自动写入 `memories`，也不创建 Relationship 外键。上述能力仍由后续阶段按实际用例增加。

------------------------------------------------------------------------

# 16. Final Schema Overview

    Database


    world_state

    locations


    npc_profiles ── npc_states


    player_states ── quest_progress ── quest_events


    actions


    events


    conversations

        |

        └---- conversation_messages


    Future: world_snapshots / relationships / memories / inventory

------------------------------------------------------------------------

# End of Document
