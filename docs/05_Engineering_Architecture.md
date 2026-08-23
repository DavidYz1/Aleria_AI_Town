# Aleria AI Town Engineering Architecture

Version: v1.1

Last Updated: 2026-08-23

# 1. Architecture Overview

## Phase 1A implementation status

当前已实现的World Tick采用“纯World Engine + Application Service + Transactional Repository”边界：

    Vue TickPanel / Pinia
              ↓
    POST /api/world/tick
              ↓
    WorldTickService
              ↓
    Pure clock + decision + action rules + tick engine
              ↓
    WorldTickRepository（单事务 + expected_tick乐观锁）
              ↓
    SQLite current state + actions + events

确定性决策位于 `backend/app/world/`，Phase 1A不创建LLM/Memory/Agent基础设施。未来Agent增强可以替换Decision Policy，但继续复用时钟、Action校验、事务与API边界。

## 1.1 Design Goal

本项目采用模块化单体架构（Modular Monolith）。

目标：

在有限开发周期内完成一个可运行的 AI Native Simulation Game，同时保证：

-   架构清晰
-   模块可扩展
-   AI能力可演进
-   工程设计可解释

核心思想：

> World Engine 负责世界运行，NPC
> Agent负责智能决策，Frontend负责展示与交互。

------------------------------------------------------------------------

# 2. Overall System Architecture

整体架构：

                        Browser

                           |

                  Vue3 + TypeScript

                           |

                      REST API

                           |

                    FastAPI Backend

                           |

    ================================================

                      Application Layer


                  World Engine

                  NPC Agent System

                  Chat Service

                  Player Service

                  Event System

                  Trace System


    ================================================


                           |

                     Data Layer


                        SQLite


                           |

                     AI Layer


                  LLM Provider

                  Mock Provider

------------------------------------------------------------------------

# 3. Architecture Principles

# 3.1 Backend As Source Of Truth

Backend 是整个世界唯一可信状态源。

Frontend：

负责：

-   展示世界
-   用户输入
-   请求发送

Backend：

负责：

-   世界状态
-   NPC状态
-   行为执行
-   数据保存

禁止：

Frontend直接修改NPC状态。

------------------------------------------------------------------------

# 3.2 World Driven Architecture

系统核心不是Chat。

而是：

World Simulation。

流程：

    World State

    ↓

    NPC Observation

    ↓

    Decision

    ↓

    Action

    ↓

    World Update

    ↓

    Event Record

------------------------------------------------------------------------

# 3.3 Modular Monolith

项目不采用微服务。

原因：

-   项目规模有限
-   开发周期短
-   降低部署复杂度

但是内部保持模块边界。

未来可以拆分：

-   Agent Service
-   World Service
-   Chat Service

------------------------------------------------------------------------

# 4. Repository Structure

    Aleria_AI_Town/


    ├── frontend/

    ├── backend/

    ├── docs/

    ├── docker-compose.yml

    ├── README.md

    └── .env.example

------------------------------------------------------------------------

# 5. Backend Architecture

目录：

    backend/


    app/


    ├── api/

    │   ├── world.py

    │   ├── npc.py

    │   ├── player.py

    │   └── chat.py


    ├── world/

    │   ├── simulator.py

    │   ├── clock.py

    │   ├── rules.py

    │   └── event_engine.py


    ├── agent/

    │   ├── npc_agent.py

    │   ├── perception.py

    │   ├── planner.py

    │   ├── decision.py

    │   ├── validator.py

    │   └── memory.py


    ├── llm/

    │   ├── provider.py

    │   ├── mock.py
    │   └── adapters.py


    ├── database/

    │   ├── models.py
    │   └── repository.py


    ├── services/


    ├── schemas/


    └── main.py

------------------------------------------------------------------------

# 6. Core Module Design

# 6.1 World Engine

World Engine负责：

-   时间推进
-   世界规则执行
-   NPC调度
-   状态更新

核心接口：

``` python
world.tick()
```

Tick流程：

    Update Clock

    ↓

    Process Events

    ↓

    Update NPC Needs

    ↓

    Trigger Agent Decision

    ↓

    Execute Actions

    ↓

    Save State

------------------------------------------------------------------------

# 6.2 NPC Agent System

负责：

NPC智能行为。

流程：

    Perception

    ↓

    Memory Retrieval

    ↓

    Goal Evaluation

    ↓

    Candidate Actions

    ↓

    Rule + LLM Decision

    ↓

    Validation

    ↓

    Action Execution

------------------------------------------------------------------------

# 6.3 Chat Service

负责：

玩家与NPC交流。

区别：

Chat不是Action Decision。

Chat关注：

-   人格
-   关系
-   记忆

Action Decision关注：

-   下一步行为。

------------------------------------------------------------------------

# 6.4 Event System

负责：

世界事件。

例如：

-   森林出现怪物
-   NPC关系变化
-   特殊任务触发

Event影响：

-   NPC目标
-   世界状态
-   行动选择

------------------------------------------------------------------------

# 6.5 Agent Trace System

用于：

观察和调试AI行为。

记录：

    Input State

    ↓

    Memory

    ↓

    Candidate Actions

    ↓

    Decision

    ↓

    Reason

    ↓

    Final Action

作用：

-   Debug
-   Demo展示
-   面试解释

------------------------------------------------------------------------

# 7. World Tick Architecture

采用：

User Driven Tick。

原因：

符合腾讯要求：

"推进一回合"。

流程：

    User Click

    ↓

    POST /api/world/tick

    ↓

    FastAPI

    ↓

    World Simulator

    ↓

    NPC Agents

    ↓

    Action Validation

    ↓

    World Update

    ↓

    Database Save

    ↓

    Return Result

------------------------------------------------------------------------

# 8. LLM Architecture

采用：

Provider Abstraction。

禁止业务代码直接绑定某个模型。

结构：

    LLM Interface


          |

    ------------------

          |

    OpenAI

    Gemini

    DeepSeek

    Mock

优势：

-   支持不同模型
-   支持无Key运行
-   方便测试

------------------------------------------------------------------------

# 9. Database Architecture

初期：

SQLite。

通过Repository Layer隔离。

结构：

    Application

    ↓

    Repository

    ↓

    SQLite

未来：

可以迁移：

SQLite

↓

PostgreSQL/MySQL

------------------------------------------------------------------------

# 10. Frontend Architecture

技术：

Vue3 + TypeScript + Vite

目录：

    frontend/


    src/


    ├── views/

    │   ├── Town.vue

    │   └── PlayerCreate.vue


    ├── components/

    │   ├── TownMap.vue

    │   ├── NPCPanel.vue

    │   ├── ChatPanel.vue

    │   └── Timeline.vue


    ├── api/

    ├── stores/

    ├── types/

    └── main.ts

------------------------------------------------------------------------

# 11. Map Rendering Strategy

## Phase 1

采用：

Vue + CSS Grid 数据驱动地图。

原因：

-   快速实现
-   满足MVP
-   与World Model解耦

------------------------------------------------------------------------

## Phase 2

增加：

Canvas/PixiJS。

架构：

    World State

    ↓

    Renderer Layer

    ↓

    Vue DOM / Pixi Canvas

核心数据不变。

------------------------------------------------------------------------

# 12. Action Lifecycle

Action不直接执行。

生命周期：

    Proposed Action

    ↓

    Validated Action

    ↓

    Executed Action

    ↓

    Recorded Action

确保：

-   世界一致性
-   AI安全
-   可调试

------------------------------------------------------------------------

# 13. Error Handling And Fallback

系统必须处理：

## AI失败

Fallback:

Mock Provider

## API失败

返回：

Error Response

## 前端失败

展示：

Loading/Error State

------------------------------------------------------------------------

# 14. Development Roadmap

## Phase 1 MVP

完成：

-   Vue页面
-   FastAPI
-   SQLite
-   World Tick
-   NPC展示
-   NPC聊天
-   Mock模式

------------------------------------------------------------------------

## Phase 2 AI Enhancement

增加：

-   LLM Provider
-   Memory Retrieval
-   Relationship
-   Event System

------------------------------------------------------------------------

## Phase 3 Experience Enhancement

增加：

-   Pixi Canvas
-   动画
-   Quest
-   在线部署

------------------------------------------------------------------------

## Phase 4 Engineering Enhancement

增加：

-   Agent Trace
-   Automated Test
-   CI/CD
-   Monitoring

------------------------------------------------------------------------

# 15. Architecture Decisions Summary

  Decision       Choice
  -------------- -----------------------
  Architecture   Modular Monolith
  Backend        FastAPI
  Frontend       Vue3 + TypeScript
  Database       SQLite
  Tick           User Driven
  Agent          Rule + LLM Hybrid
  Map            Vue first, Pixi later
  AI Provider    Abstract Interface
  Memory         SQLite first
  Deployment     Docker Compose

------------------------------------------------------------------------

# End of Document
