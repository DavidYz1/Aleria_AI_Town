# Aleria AI Town World Model Design

Version: v1.1

Last Updated: 2026-08-22

# 1. Overview

## 1.1 Purpose

World Model 是 Aleria AI Town 的核心领域模型。

它负责描述：

-   世界状态
-   地点结构
-   NPC状态
-   玩家状态
-   NPC关系
-   记忆
-   事件
-   行动记录

核心思想：

> 世界不是被用户请求驱动，而是由时间推进和 Agent 行动持续演化。

## 1.2 Phase 0 Canonical Contract

Phase 0 实现以 `docs/superpowers/specs/2026-08-22-phase-0-engineering-initialization-design.md` 为权威规格。

统一约定：

-   世界回合字段使用 `tick`，不使用 `round`。
-   NPC职业字段使用 `role`。
-   NPC当前位置字段使用 `location_id`。
-   `energy`、`mood`、`social` 均为 0-100 整数。
-   World、Location、NPC均使用稳定的小写字符串ID。
-   Phase 0以SQLite为运行时唯一状态源；根目录JSON只用于种子配置。

------------------------------------------------------------------------

# 2. World Model Architecture

整体实体关系：

    World

     |
     |
     +-- Locations

     |
     |
     +-- NPCs

     |     |
     |     +-- Profile
     |     +-- State
     |     +-- Memory
     |     +-- Relationship
     |     +-- Action History

     |
     |
     +-- Events

     |
     |
     +-- Quests

     |
     |
     +-- Player

------------------------------------------------------------------------

# 3. World Entity

World 表示整个模拟世界。

## Attributes

``` json
{
  "id":"aleria-town",
  "name":"晨曦镇",
  "day":1,
  "tick":10,
  "time":"18:00",
  "weather":"sunny"
}
```

## Fields

  Field     Description
  --------- -------------
  id        World ID
  name      世界名称
  day       当前日期
  tick      当前Tick
  time      当前时间
  weather   当前天气

------------------------------------------------------------------------

# 4. Time System

## Definition

    1 Tick = 1 hour

例如：

    Day 1 08:00

    ↓

    Tick

    ↓

    Day 1 09:00

------------------------------------------------------------------------

## Time Impact

时间影响：

-   NPC行为
-   地点状态
-   世界事件
-   任务进度

例如：

晚上：

-   酒馆社交增加
-   居民回家休息

------------------------------------------------------------------------

# 5. Location Entity

Location 描述世界中的空间。

## Example

``` json
{
  "id":"tavern",
  "name":"Star Tavern",
  "description":"冒险者交流地点",
  "capacity":30
}
```

------------------------------------------------------------------------

## Fields

  Field               Description
  ------------------- -------------
  id                  地点ID
  name                名称
  description         描述
  capacity            容量
  available_actions   支持行为

------------------------------------------------------------------------

# 6. NPC Entity

NPC 是世界中的智能实体。

NPC设计采用：

Static Profile + Runtime State

------------------------------------------------------------------------

# 6.1 NPC Profile

描述：

不会频繁变化的信息。

Example:

``` json
{
  "id":"ryan",
  "name":"Ryan",
  "role":"Knight",
  "personality":[
    "optimistic",
    "brave"
  ],
  "background":"Afraid of slime"
}
```

------------------------------------------------------------------------

Fields:

  Field         Description
  ------------- -------------
  id            NPC ID
  name          名称
  role          职业
  personality   性格
  background    背景故事
  traits        特殊特征

------------------------------------------------------------------------

# 6.2 NPC State

描述：

当前运行状态。

Example:

``` json
{
  "npc_id":"ryan",
  "location_id":"park",
  "energy":70,
  "mood":75,
  "social":60,
  "current_action":"rest"
}
```

------------------------------------------------------------------------

Fields:

  Field            Description
  ---------------- -------------
  npc_id           NPC
  location_id      当前地点ID
  energy           体力
  mood             心情
  social           社交需求
  current_action   当前行为
  current_goal     当前目标

------------------------------------------------------------------------

# 7. NPC Need System

NPC拥有基础需求。

三个字段统一使用 0-100 整数；情绪文本若未来需要展示，应作为派生字段，不替代 `mood` 数值。

第一版：

``` json
{
  "energy":80,
  "mood":70,
  "social":50
}
```

------------------------------------------------------------------------

## Energy

影响：

-   工作
-   移动
-   休息

------------------------------------------------------------------------

## Mood

影响：

-   对话风格
-   行为倾向

------------------------------------------------------------------------

## Social

影响：

-   是否主动交流
-   是否寻找其他NPC

------------------------------------------------------------------------

设计原则：

需求系统用于辅助决策。

不是复杂数值游戏。

------------------------------------------------------------------------

# 8. Action Entity

Action表示NPC执行的行为。

## Example

``` json
{
  "npc_id":"ryan",
  "action":"move",
  "target":"tavern",
  "reason":"训练结束想休息"
}
```

------------------------------------------------------------------------

## Action Types

系统定义：

    move

    rest

    work

    eat

    social

------------------------------------------------------------------------

## Action Lifecycle

    Generated

    ↓

    Validated

    ↓

    Executed

    ↓

    Recorded

------------------------------------------------------------------------

# 9. Action History

用于：

-   展示NPC最近行为
-   Agent Memory
-   调试系统

Example:

``` json
{
  "npc":"ryan",
  "tick":10,
  "action":"move",
  "target":"tavern",
  "reason":"想和朋友交流"
}
```

------------------------------------------------------------------------

Fields:

  Field       Description
  ----------- -------------
  id          Action ID
  npc_id      NPC
  tick        Tick
  action      行为
  target      目标
  reason      原因
  timestamp   时间

------------------------------------------------------------------------

# 10. Memory System

Memory用于保存NPC经历。

不是简单聊天记录。

------------------------------------------------------------------------

## Memory Example

``` json
{
  "npc_id":"ryan",
  "event":"玩家帮助寻找史莱姆",
  "emotion":"grateful",
  "importance":8
}
```

------------------------------------------------------------------------

Memory Types:

## Event Memory

发生过的事情。

## Relationship Memory

人与人关系变化。

## Personal Memory

个人经历。

------------------------------------------------------------------------

# 11. Relationship Model

NPC之间存在关系。

Example:

``` json
{
  "from":"ryan",
  "to":"grey",
  "type":"respect",
  "score":80
}
```

------------------------------------------------------------------------

影响：

-   对话
-   行为选择
-   事件

------------------------------------------------------------------------

# 12. Player Entity

玩家作为外部角色。

第一版：

不实现复杂账号系统。

------------------------------------------------------------------------

Fields:

``` json
{
  "id":"player001",
  "name":"David",
  "class":"Mage"
}
```

------------------------------------------------------------------------

Player Class:

不影响战斗。

主要影响：

-   NPC对话
-   玩家身份

------------------------------------------------------------------------

# 13. Event Entity

Event表示世界事件。

Example:

``` json
{
  "type":"monster_attack",
  "location":"forest"
}
```

------------------------------------------------------------------------

事件影响：

-   NPC目标
-   NPC状态
-   世界状态

------------------------------------------------------------------------

# 14. Quest Entity

任务系统预留。

Example:

``` json
{
  "title":"寻找森林药草",
  "status":"active"
}
```

MVP阶段：

只设计模型。

不实现复杂任务链。

------------------------------------------------------------------------

# 15. World Tick State Transition

一次Tick流程：

    World Clock Update

    ↓

    NPC Observe

    ↓

    Decision

    ↓

    Action Validation

    ↓

    Execute

    ↓

    Update State

    ↓

    Create Memory

    ↓

    Save History

------------------------------------------------------------------------

# 16. World Model Design Principles

## Backend Authority

所有状态由后端维护。

------------------------------------------------------------------------

## Deterministic Rules

世界规则优先。

AI不能违反：

-   时间
-   地点
-   Action约束

------------------------------------------------------------------------

## Expandability

当前支持：

MVP AI Town。

未来可以扩展：

-   更多NPC
-   更大地图
-   多玩家
-   更复杂事件

------------------------------------------------------------------------

# End of Document
