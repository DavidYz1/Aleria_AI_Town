# Aleria AI Town NPC Agent Design

Version: v1.1

Last Updated: 2026-08-24

## Phase 1D implementation baseline

当前“Agent”采用可审计的混合边界：World Tick 决策仍为纯确定性规则；LLM 仅用于 Chat 表达。三名 NPC 根据 needs、morning/day/evening/night 和角色职责行动：Ryan 在公园训练，Shir 在森林侦察，Grey 在城堡巡逻。低能量/低社交/低心情优先于角色例程。

Prompt v2 为每个角色定义外显性格、内在矛盾、语言风格和信息边界；Mock v2 对“你是谁、这里是哪里、你在哪里、正在做什么、任务是什么”等高频意图给出角色化确定性回答。Chat 读取权威 Player/Quest objective，但不能改变任务、世界或 NPC。

Memory、Relationship、Goal、Reflection 和 LLM Action Decision 在本文仍是未来架构，不代表当前代码已经实现。

# 1. Overview

## 1.1 Purpose

NPC Agent 是 Aleria AI Town 的核心智能模块。

目标：

让 NPC 不再是固定脚本角色，而是能够根据：

-   自身人格
-   当前状态
-   世界环境
-   历史记忆
-   NPC关系

自主决定下一步行动。

------------------------------------------------------------------------

# 2. Agent Design Philosophy

## 2.1 Hybrid Agent Architecture

本项目不采用纯 LLM 驱动。

原因：

纯 LLM 存在：

-   不稳定
-   输出不可控
-   成本高
-   容易违反世界规则

因此采用：

Rule + AI Hybrid Architecture

结构：

                  NPC Agent


                      |

                 Perception


                      |

                  Memory


                      |

                  Goal


                      |

            Decision Engine

              /          \

           Rule          LLM


                      |

                 Validation


                      |

                   Action


                      |

              World Update

------------------------------------------------------------------------

# 3. NPC Agent Components

# 3.1 Perception Module

作用：

让NPC感知当前世界。

输入：

-   当前时间
-   当前地点
-   天气
-   附近NPC
-   自身状态
-   当前事件

Example:

``` json
{
  "time":"18:00",
  "location":"training",
  "weather":"sunny",
  "nearby_npcs":["grey"],
  "energy":60
}
```

输出：

NPC当前环境认知。

------------------------------------------------------------------------

# 3.2 Memory Module

作用：

保存NPC过去经历。

Memory不是简单聊天记录。

而是：

影响未来行为的重要信息。

Example:

``` json
{
  "event":"Grey helped Ryan during training",
  "importance":8,
  "emotion":"respect"
}
```

------------------------------------------------------------------------

Memory类型：

## Event Memory

事件经历。

Example:

玩家帮助NPC。

------------------------------------------------------------------------

## Relationship Memory

关系变化。

Example:

NPC之间建立信任。

------------------------------------------------------------------------

## Personal Memory

个人经历。

Example:

Ryan害怕史莱姆。

------------------------------------------------------------------------

# 3.3 Goal Module

NPC需要拥有目标。

分为：

## Long Term Goal

长期目标。

Example:

Ryan:

成为真正英雄。

------------------------------------------------------------------------

## Short Term Goal

短期目标。

Example:

今天：

完成训练。

------------------------------------------------------------------------

Goal影响：

-   行动选择
-   对话内容
-   记忆解释

------------------------------------------------------------------------

# 3.4 Decision Engine

Decision Engine 是Agent核心。

输入：

    Personality

    +

    State

    +

    Memory

    +

    Goal

    +

    World Context

输出：

Action。

------------------------------------------------------------------------

# 4. Decision Pipeline

一次NPC决策：

    World Tick

    ↓

    Observe Environment

    ↓

    Retrieve Memory

    ↓

    Generate Candidate Actions

    ↓

    Decision

    ↓

    Validate

    ↓

    Execute

    ↓

    Record Memory

------------------------------------------------------------------------

# 5. Candidate Action Generation

系统首先生成候选行为。

例如：

当前：

Ryan

地点：

Training Ground

候选：

    train

    move tavern

    rest

    chat grey

------------------------------------------------------------------------

原因：

避免LLM自由生成。

------------------------------------------------------------------------

# 6. Rule Based Decision

规则层负责确定性行为。

Example:

``` python
if energy < 20:
    action = "rest"
```

------------------------------------------------------------------------

Example:

晚上：

``` python
if time >= 22:
    action = "go_home"
```

------------------------------------------------------------------------

规则优先保证：

-   世界一致性
-   可预测性

------------------------------------------------------------------------

# 7. LLM Decision

当规则无法决定时：

调用LLM。

输入：

    NPC Profile

    Current State

    Memory

    Candidate Actions

    World Context

------------------------------------------------------------------------

LLM输出必须结构化。

Example:

``` json
{
  "action":"social",
  "target":"grey",
  "reason":"想感谢伙伴的帮助"
}
```

------------------------------------------------------------------------

# 8. Action Validation

LLM输出不能直接执行。

必须验证。

------------------------------------------------------------------------

## Action Validation

允许：

    move

    rest

    work

    eat

    social

禁止：

未知行为。

------------------------------------------------------------------------

## Target Validation

例如：

move:

必须移动到：

存在Location。

------------------------------------------------------------------------

## State Validation

例如：

疲惫NPC：

不能执行高消耗行动。

------------------------------------------------------------------------

# 9. Action Execution

验证通过后：

修改World State。

Example:

Before:

``` json
{
"location":"training"
}
```

Action:

    move -> tavern

After:

``` json
{
"location":"tavern"
}
```

同时：

生成Action History。

------------------------------------------------------------------------

# 10. Chat Agent Design

玩家聊天与行动决策共享：

NPC Profile。

但目标不同。

------------------------------------------------------------------------

## Decision Prompt

目标：

决定行动。

输入：

World State。

输出：

Action。

------------------------------------------------------------------------

## Chat Prompt

目标：

生成角色化回复。

输入：

-   NPC人格
-   玩家信息
-   对话历史
-   Memory

输出：

自然语言回复。

------------------------------------------------------------------------

# 11. Prompt Architecture

Prompt分层。

## System Prompt

固定人格。

Example:

    你是Ryan。

    你是一名年轻剑士。

    你乐观、正义。

    你害怕史莱姆。

------------------------------------------------------------------------

## World Context

动态世界。

Example:

    当前时间:
    18:00

    地点:
    酒馆

------------------------------------------------------------------------

## State Context

NPC状态。

Example:

    Energy:
    40

    Mood:
    happy

------------------------------------------------------------------------

## Constraint

输出约束。

Example:

    只能选择：

    move

    rest

    social

------------------------------------------------------------------------

# 12. Mock Mode Design

系统必须支持：

无AI Key运行。

结构：

    Decision Engine


           |

    -----------------

           |

    LLM Provider


           |

    Mock Provider

------------------------------------------------------------------------

Mock不是随机。

基于规则。

Example:

Ryan:

    energy low

    ↓

    rest

Shir:

    night

    ↓

    eat sweet

Grey:

    danger event

    ↓

    protect

------------------------------------------------------------------------

# 13. Agent Interfaces

建议接口：

## Decide Action

``` python
decide_action(
    npc,
    world_state
)
```

返回：

``` json
{
"action":"move",
"target":"park",
"reason":"想散步"
}
```

------------------------------------------------------------------------

## Chat

``` python
chat(
    npc,
    player_message
)
```

返回：

NPC回复。

------------------------------------------------------------------------

# 14. Design Principles

## Personality First

角色人格优先。

------------------------------------------------------------------------

## Safety First

AI不能直接改变世界。

------------------------------------------------------------------------

## Explainable Decision

行动需要reason。

方便：

-   调试
-   展示
-   面试解释

------------------------------------------------------------------------

## Expandable

未来支持：

-   Reflection
-   Long-term Memory
-   Multi-Agent Collaboration

------------------------------------------------------------------------

# End of Document
