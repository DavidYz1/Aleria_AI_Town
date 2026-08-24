# Aleria AI Town Project Context

Version: v1.2

Last Updated: 2026-08-24

## Phase 1D implementation baseline

当前可运行世界展示名为“曦谷”，包含 `tavern/park/castle/forest` 四个稳定地点和 Ryan、Shir、Grey 三名 NPC。项目已经完成确定性 World Tick、NPC Detail、Mock/compatible Chat、最小 Player 与“失踪的孩子”任务闭环。

Player 仅保存固定 ID、世界和当前位置；Quest 仅实现一个有界状态机。旅行不推进 Tick，Chat 只读 Player/Quest 摘要，只有显式 Quest Interaction 可以推进任务。长期 Memory、Relationship、通用 Quest、地图渲染和多人系统仍是未来方向，不应被下文的概念设计误认为已实现能力。

## Phase 1E content authority

`docs/15_Story_Bible_CN.md` 是当前世界观、玩家、NPC、地点和任务叙事的唯一内容事实源。艾莱瑞亚的曦谷表面温暖而平静，但当前秩序建立在被改写的终焉战争历史之上；约二十余年前的灰烬战争再次触碰了旧遗迹和封锁线。

玩家是固定的失忆旅人，身上带有无法解释的印记。这个事实只用于叙事，不新增数据库字段、职业系统或分支身份。现有“失踪的孩子”任务会轻触印记与旧封锁线谜团，但仍保持既有六状态和五次交互。

Author Truth 只保存在内容圣经和内部设计文档中。Public Lore、Character Knowledge 与 Player Context 必须分层使用，任何 NPC 都不能因为模型掌握世界设定而成为全知叙述者。

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

世界：艾莱瑞亚（Aleria）

当前小镇：曦谷

## 4.2 Background

官方历史称，约五百年前的人类英雄在终焉战争中击败魔王伊萨尔，使大陆重获和平。完整历史则涉及衰弱的世界本源、古族的牺牲、最后盟约和战后的主动改写。

约二十余年前，人类重新勘探遗迹引发灰烬战争。曦谷位于旧战场和近代封锁区附近，居民在战争阴影中恢复了真实而值得保护的日常生活。

玩家作为失去记忆、身带陌生印记的旅人进入小镇，与立场和知识边界不同的 NPC 相遇。

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

Character Conflict:

相信英雄史，却被父亲因保护古族幸存者而被视为叛徒的过去困扰。

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

Character Conflict:

接触过被删除的档案；追索真相，却不确定所有真相都应立刻公开。

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

参与约二十余年前的灰烬战争和遗迹行动，失去同伴，因此希望保护现在的伙伴。

Character Conflict:

知道官方历史并不完整，却担心公开秘密会制造下一场战争。Grey 没有经历约五百年前的终焉战争。

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

-   PixiJS 像素地图
-   角色精灵与移动动画
-   场景交互与响应式体验

## Phase 3

工程增强：

-   Docker
-   部署
-   演示视频与提交资产
-   自动化测试

# 9. Current Status

Current Phase:

Phase 1D complete; Phase 1E content bible and submission narrative in progress

Completed:

-   曦谷四地点、三名 NPC 与确定性 World Tick
-   NPC Detail、Prompt v2、Mock/compatible Chat 与 fallback
-   固定 Player、五步“失踪的孩子”任务与 SQLite 持久化
-   Vue DOM 旅行、任务、对话和错误/冲突处理
-   Backend/Frontend 自动化测试与生产构建

Next:

完成 Phase 1E 内容、Prompt/Mock、任务叙事和 README 收口；随后在 Phase 2 迁移像素地图展示层，Phase 3 再完成部署与交付工程化

# 10. AI Coding Rules

When AI assistants modify this project:

1.  Read this document first.
2.  Preserve existing product vision.
3.  Avoid unnecessary complexity.
4.  Follow existing architecture.
5.  Any major design change must update Decision Log.
6.  Keep documentation synchronized with implementation.

End of Document
