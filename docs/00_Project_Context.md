# Aleria AI Town Project Context

Version: v1.1

Last Updated: 2026-08-24

## Phase 1D implementation baseline

当前可运行世界展示名为“曦谷”，包含 `tavern/park/castle/forest` 四个稳定地点和 Ryan、Shir、Grey 三名 NPC。项目已经完成确定性 World Tick、NPC Detail、Mock/compatible Chat、最小 Player 与“失踪的孩子”任务闭环。

Player 仅保存固定 ID、世界和当前位置；Quest 仅实现一个有界状态机。旅行不推进 Tick，Chat 只读 Player/Quest 摘要，只有显式 Quest Interaction 可以推进任务。长期 Memory、Relationship、通用 Quest、地图渲染和多人系统仍是未来方向，不应被下文的概念设计误认为已实现能力。

# 1. Project Overview

## 1.1 Project Name

Aleria AI Town

## 1.2 Project Type

AI Native Simulation Game

## 1.3 Project Goal

本项目面向腾讯 IEG 游戏前沿技术后台开发实习作业。

目标是在有限开发周期内，实现一个可运行、可演示的 Web AI 小镇 MVP。

项目不是复刻 Stanford Generative Agents，也不是开发完整商业 RPG 游戏。

核心目标：

构建一个轻量级 AI Agent 世界模拟系统。

系统中：

-   玩家进入幻想小镇
-   NPC拥有独立人格
-   NPC拥有状态和记忆
-   NPC根据世界状态自主行动
-   玩家可以观察并影响NPC

# 2. Product Vision

## 2.1 Core Idea

Aleria AI Town 是一个 AI Native Fantasy Simulation Game。

核心体验：

玩家进入曦谷

↓

观察NPC生活

↓

推进世界时间

↓

NPC Agent自主决策

↓

世界状态更新

↓

玩家互动

# 3. Core Design Principles

## 3.1 World First

世界状态是系统核心。

系统不是简单：

用户输入

↓

LLM

↓

文本回复

而是：

World State

↓

NPC Perception

↓

Decision

↓

Action

↓

World Update

世界持续运行。

## 3.2 NPC Are Agents

NPC不是普通聊天机器人。

每个NPC应该拥有：

-   Identity
-   Personality
-   Current State
-   Goal
-   Memory
-   Relationship
-   Action History

NPC行为必须体现角色设定。

## 3.3 Backend Is Source Of Truth

后端负责维护：

-   世界状态
-   NPC状态
-   行为执行
-   数据持久化

前端只负责：

-   展示
-   用户输入
-   请求发送

禁止前端直接修改世界状态。

## 3.4 LLM Is Constrained

LLM不能直接控制游戏。

LLM只负责生成候选决策。

例如：

``` json
{
  "action": "move",
  "target": "park",
  "reason": "想去散步"
}
```

后台必须：

1.  校验 action 是否合法
2.  校验 target 是否合法
3.  执行动作

## 3.5 Always Have Fallback

系统必须支持：

-   LLM模式
-   Mock模式

没有配置AI Key时：

主要流程仍然可以运行。

# 4. World Setting

## 4.1 World Name

Aleria

中文：

曦谷

## 4.2 Background

魔王战争结束后的幻想大陆。

战争结束后：

冒险者、居民和旅行者来到曦谷。

玩家作为冒险者进入小镇，与不同背景的NPC相遇。

# 5. Main Characters

## 5.1 Ryan

Role:

Knight

Personality:

-   optimistic
-   brave
-   kind

Hidden Trait:

害怕史莱姆。

Behavior:

-   训练
-   帮助新人
-   与伙伴交流

## 5.2 Shir

Role:

Assassin

Personality:

-   quiet
-   introverted

Hidden Trait:

喜欢甜食。

Behavior:

-   夜间散步
-   购买甜点
-   观察其他人

## 5.3 Grey

Role:

Guardian

Personality:

-   reliable
-   calm

Background:

过去没有保护好重要的人，因此希望保护现在的伙伴。

Behavior:

-   巡逻
-   保护小镇
-   帮助新人

# 6. World Rules

## 6.1 Time System

定义：

1 Tick = 1 hour

时间影响：

-   NPC行动
-   地点状态
-   世界事件

## 6.2 NPC Needs

NPC拥有基础状态：

``` json
{
  "energy": 80,
  "mood": 70,
  "social": 50
}
```

这些状态用于影响Agent决策。

不实现复杂游戏数值系统。

## 6.3 Action Constraints

NPC行动必须来自系统定义。

例如：

-   move
-   rest
-   work
-   eat
-   social

LLM不能创造未知行为。

## 6.4 Relationship System

NPC之间存在关系。

例如：

Ryan -\> Grey

respect

关系影响：

-   对话
-   行为
-   事件

# 7. Technical Direction

## Frontend

Recommended:

Vue 3 + TypeScript + Vite

Responsibilities:

-   世界展示
-   NPC展示
-   玩家交互

## Backend

Recommended:

FastAPI

Responsibilities:

-   API
-   World Simulator
-   NPC Agent
-   数据管理

## Database

Initial:

SQLite

Reason:

-   MVP规模
-   简单部署
-   快速迭代

Future:

PostgreSQL/MySQL

## AI Layer

Architecture:

NPC Agent

↓

Decision Engine

↓

LLM Provider / Mock Provider

# 8. Development Strategy

## Phase 1

完成基础闭环：

查看小镇

↓

查看NPC

↓

推进Tick

↓

NPC行动

↓

NPC聊天

## Phase 2

增加：

-   Memory
-   Relationship
-   Event
-   Quest

## Phase 3

工程增强：

-   Docker
-   部署
-   Canvas/Pixi
-   自动化测试

# 9. Current Status

Current Phase:

Phase 1D complete; preparing Phase 1E delivery engineering

Completed:

-   曦谷四地点、三名 NPC 与确定性 World Tick
-   NPC Detail、Prompt v2、Mock/compatible Chat 与 fallback
-   固定 Player、五步“失踪的孩子”任务与 SQLite 持久化
-   Vue DOM 旅行、任务、对话和错误/冲突处理
-   Backend/Frontend 自动化测试与生产构建

Next:

Phase 1E 部署与交付工程化；随后在 Phase 2 迁移地图展示层

# 10. AI Coding Rules

When AI assistants modify this project:

1.  Read this document first.
2.  Preserve existing product vision.
3.  Avoid unnecessary complexity.
4.  Follow existing architecture.
5.  Any major design change must update Decision Log.
6.  Keep documentation synchronized with implementation.

End of Document
