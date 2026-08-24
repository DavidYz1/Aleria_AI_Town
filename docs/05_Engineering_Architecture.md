# Aleria AI Town Engineering Architecture

Version: v1.3

Last Updated: 2026-08-24

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

## Phase 1B implementation status

Phase 1B 在不修改 Tick Engine 和数据库结构的前提下，增加独立 NPC 只读查询切片：

    GET /api/npcs/{npc_id}
              ↓
    NpcService
              ↓
    NpcRepository + deterministic action explanation
              ↓
    SQLite profile/state/location/world/actions

边界划分：

-   `NpcRepository` 只执行有界读查，不进入 `WorldTickRepository`，不生成 Pydantic DTO 或用户文案。
-   `NpcService` 聚合 Profile、State、World Context 和最近三条 Action，解析目标名称并映射公共 Schema。
-   持久化 `actions.reason` 保持为稳定机器代码；Detail DTO 将其暴露为 `reason_code + reason_text`。
-   `reason_text` 是对已执行确定性规则的可审计摘要，不是 chain-of-thought、隐藏推理或 Agent Trace。

Frontend 继续保持独立状态切片：

    World API → World Store ─┐
                              ├→ TownView → NpcCard / NpcDetailPanel
    NPC API → NPC Detail Store ─┘

`TownView` 只负责跨 Store 协调：选择/关闭 NPC，以及在权威 World Tick 变化时刷新已打开详情。World Store 不导入或修改 NPC Detail Store。

## Phase 1C implementation status

Phase 1C 增加与确定性 World Engine 隔离的 Chat Slice：

    Vue NpcChatPanel
              ↓
    npcChat Pinia Store（per-NPC session）
              ↓
    POST /api/npcs/{npc_id}/chat
              ↓
    ChatService
       ├── ChatContextAssembler
       ├── ChatProvider
       └── ChatRepository
              ↓
    SQLite conversations + conversation_messages

`ChatContextAssembler` 只读取 NPC Profile/State、Location、World、最近 Action、版本化 Prompt 和有界聊天历史。`ChatService` 在 Provider 返回并通过严格校验后，才以一个事务写入完整 User/Assistant 轮次。Chat 不调用 `WorldTickService`，不更新 `world_state`/`npc_states`，也不写入 `actions`/`events`。

Provider 边界为 `ChatProvider`。默认 `MockChatProvider` 无 Key 运行；所有非 Mock 标签复用一个 `OpenAICompatibleChatProvider`，通过 `base_url/api_key/model/auth_mode` 配置腾讯混元、DeepSeek 或本地 Qwen compatible 服务。可预期的 Primary 故障由 `FallbackChatProvider` 降级到 Mock，并在响应和数据库中如实标记。

Frontend 使用第三个独立 `npcChat` Store；World、NPC Detail、NPC Chat 三个 Store 不互相导入，由 `TownView` 协调。切换或关闭 NPC 只隐藏 Chat Panel，不删除页面生命周期内的 per-NPC session；Tick 变化只刷新 Detail。

## Phase 1D implementation status

Phase 1D 在原有三个切片之外增加独立 Player/Quest 纵向切片：

```text
Vue PlayerQuest Store
        ↓
GET /api/player | POST /api/player/travel | POST /api/quests/missing-child/interact
        ↓
PlayerQuestService
        ↓
MissingChildQuestPolicy + PlayerQuestRepository
        ↓
player_states + quest_progress + quest_events
```

`MissingChildQuestPolicy` 是纯状态机和展示派生；Service 校验 interaction、位置和 expected version；Repository 在一个事务中更新 Progress 并写 Quest Event。`ask_grey` 额外读取 Grey 的实时地点，只有玩家与 Grey 同地点时可执行。

Chat Slice 通过 `PlayerQuestChatContextReader` 只读 Player/Quest objective。依赖方向始终是 Chat Context → Reader，而不是 ChatService → Quest update；Chat、Fallback 和真实 Provider 都不能推进任务。旅行也不调用 World Tick，因此玩家移动、NPC 自主行动和任务交互具有明确独立边界。

Provider 仍只有一个 compatible Adapter。`CHAT_LLM_OUTPUT_MODE=structured_json` 严格解析 `reply + emotion`；`text` 模式校验自然文本并根据 NPC/当前 mood 确定性派生 emotion。两种模式都保留同一 ChatProvider、ChatService、Fallback 和 API 契约。

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

以下为模块化单体的目标边界。当前 Phase 1C 已实现 `api/world*`、`api/npcs`、`api/npc_chat`、`world/`、`llm/`、Chat Repository/Context/Service 及相关 Schema；通用 `agent/`、Memory、Relationship 与 Player 模块仍未实现。

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

当前 Chat 关注：

-   NPC Profile、人格 Prompt 与世界背景
-   权威 World/NPC 当前状态和最近三条 Action
-   当前会话的有界持久化历史
-   严格 `reply + emotion` 输出

Action Decision关注：

-   下一步行为。

当前实现刻意不加载 Relationship 或 Agent Memory，也不把聊天自动提升为 Memory。Provider 调用发生在数据库写事务之外；只有合法回复存在后，User 与 Assistant 才在一个事务中完整保存。

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

    ChatProvider Interface
          |
          |---- MockChatProvider
          |
          └---- FallbackChatProvider
                    ├── OpenAICompatibleChatProvider
                    └── MockChatProvider

腾讯混元、DeepSeek、本地 Qwen 通过配置复用同一个 compatible Adapter。未来 Gemini native 或其他非 compatible 协议可以新增 Adapter，但 `ChatService` 不感知供应商。

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

Phase 1C 当前实现使用 `TownView.vue`、`NpcCard.vue`、`NpcDetailPanel.vue`、`NpcChatPanel.vue`，以及独立 `world`/`npcDetail`/`npcChat` Store。三个 API Adapter 复用共享 Axios client。详情与聊天面板都是可访问的响应式 `aside`；Chat 只按文本插值渲染，不解析 HTML/Markdown，不引入遮罩、焦点陷阱或 PixiJS。

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

    Compatible Provider Error
    ↓
    Mock Provider
    ↓
    provider=mock, fallback_used=true

Provider 超时、网络错误、非 2xx、外层响应缺失或严格输出校验失败统一映射为安全错误；不会向 Frontend 泄露 URL、Key 或上游响应正文。

## API失败

返回：

Error Response

## 前端失败

展示：

Loading/Error State

------------------------------------------------------------------------

# 14. Development Roadmap

## Phase 1 MVP

已完成：

-   Vue页面
-   FastAPI
-   SQLite
-   World Tick
-   NPC基础展示与详情
-   最近行动的确定性解释
-   NPC Chat 首轮/续聊、Mock/compatible Provider 与 fallback
-   完整聊天轮次持久化和 per-NPC Frontend session

------------------------------------------------------------------------

## Phase 2 AI Enhancement

增加：

-   LLM驱动的可替换 Action Decision Policy
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
