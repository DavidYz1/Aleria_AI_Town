# Aleria AI Town 开发路线规划（Development Roadmap）

版本：v1.4

更新时间：2026-08-24

# 1. 文档目的

本文档用于规划 Aleria AI Town 从设计阶段进入工程实现阶段的开发路线。

目标：

-   在2-3天内完成腾讯AI小镇作业基础要求。
-   保证核心闭环可运行。
-   在基础功能完成后逐步增加游戏化和AI增强能力。

核心原则：

> 先完成可运行MVP，再增加体验和技术亮点。

------------------------------------------------------------------------

# 2. 开发优先级划分

项目分为三个层级：

## P0：必须完成（基础分）

目标：

满足腾讯验收要求。

包含：

-   前后端启动
-   小镇页面
-   NPC展示
-   Tick推进
-   NPC决策
-   NPC聊天
-   Mock模式
-   README

------------------------------------------------------------------------

## P1：重点增强（高性价比加分）

包含：

-   SQLite持久化
-   World Snapshot
-   Event Log
-   Prompt工程
-   Docker
-   自动化测试

------------------------------------------------------------------------

## P2：展示亮点（游戏体验）

包含：

-   PixiJS 2D地图
-   NPC移动动画
-   世界事件展示
-   Quest系统

------------------------------------------------------------------------

# 3. Phase 0：工程初始化

目标：

建立可开发工程，并完成第一个经过测试的前后端纵向闭环。

完成：

    Aleria_AI_Town/

    frontend/

    backend/

    docs/

    data/

    prompts/

    tests/

    scripts/

闭环：

    data/*.json（种子配置）
    ↓
    seed_world.py
    ↓
    SQLite
    ↓
    GET /api/world
    ↓
    Vue TownView

技术：

Frontend:

-   Vue3
-   TypeScript
-   Vite

Backend:

-   FastAPI
-   SQLite

Phase 0功能范围：

-   SQLite创建 `world_state`、`locations`、`npc_profiles`、`npc_states`。
-   JSON只作为种子输入，不作为运行时状态源。
-   `GET /api/world` 返回晨曦镇、Day 1 08:00、两个地点和Ryan/Shir/Grey基础状态。
-   Frontend实现loading、success、empty和error状态。
-   完成Backend API测试、Frontend Store/Component测试、TypeScript检查和生产构建。

Phase 0不实现：

-   World Tick
-   NPC Detail和Chat
-   LLM Provider
-   PixiJS
-   Quest
-   RAG和复杂Memory
-   多人系统

------------------------------------------------------------------------

# 4. Phase 1：基础世界闭环（MVP）

## Phase 1A完成状态（2026-08-23）

已完成确定性World Tick子阶段：

-   `POST /api/world/tick` 与 `expected_tick` 乐观锁。
-   一小时世界时钟及morning/day/evening/night阶段。
-   基于状态、角色、时间阶段的Ryan/Shir/Grey确定性决策。
-   Action校验/执行、0-100状态约束、Event记录。
-   SQLite单事务更新当前状态并写入 `actions`/`events`。
-   Frontend推进控制、错误/冲突处理、Action/Event结果展示。
-   Backend/Frontend行为测试、类型检查和生产构建。


## Phase 1B完成状态（2026-08-23）

已完成 NPC Detail 与确定性行为解释子阶段：

-   `GET /api/npcs/{npc_id}` 权威只读契约，包含 Profile、State 和 World Context。
-   最近三条持久化 Action，按 `tick DESC, id DESC` 排序并解析地点/NPC目标名称。
-   将历史 `reason` 机器代码映射为稳定 `reason_code` 和确定性中文 `reason_text`。
-   响应式 NPC Detail Panel，支持 loading、空历史、错误重试、关闭和快速切换竞态保护。
-   已打开详情在权威 World Tick 变化后自动刷新，World/NPC Detail Store 保持独立。
-   不新增数据库表，不修改 `GET /api/world` 或 `POST /api/world/tick` 公共契约。

## Phase 1C完成状态（2026-08-24）

已完成 NPC Chat 与 Provider 抽象子阶段：

-   `POST /api/npcs/{npc_id}/chat` 首轮/续聊、404/422/503 契约。
-   `conversations` 与 `conversation_messages`，完整 User/Assistant 轮次原子保存。
-   版本化 World/Character/System Prompt、权威状态/Action 和有界历史 Context。
-   `ChatProvider`、一等 Mock、单一 OpenAI-compatible Adapter 与自动 fallback。
-   Ryan/Shir/Grey 角色化 Mock 回复和严格 `reply + emotion` 校验。
-   Frontend per-NPC session、sending、失败重试、fallback 提示、切换/关闭恢复和迟到响应保护。
-   Acceptance 证明 Chat 不改变 World Tick、NPC State、Action 或 Event。

尚未开始的 Phase 1 范围只剩 Player 交互。PixiJS、Quest、RAG、复杂 Memory、Relationship、LLM Tick Decision 和多人系统继续延期。

## 目标

实现：

    查看小镇

    ↓

    查看NPC

    ↓

    推进一回合

    ↓

    NPC行动

    ↓

    查看结果

    ↓

    NPC聊天

------------------------------------------------------------------------

## Backend任务

完成：

### World Read API

`GET /api/world` 已在Phase 0交付。Phase 1保持其公共契约稳定，并在Tick成功后使用相同World DTO刷新Frontend。

------------------------------------------------------------------------

### Tick API

    POST /api/world/tick

实现：

-   时间推进
-   NPC决策
-   状态更新
-   Event生成

------------------------------------------------------------------------

### NPC API

    GET /api/npcs/{id}

已在Phase 1B完成：Profile、权威当前状态、世界阶段与最近三条行动解释。

------------------------------------------------------------------------

### NPC Chat API（已完成）

    POST /api/npcs/{id}/chat

已完成首轮/续聊、Mock/compatible Provider、fallback 与完整轮次持久化。

------------------------------------------------------------------------

## Frontend任务

完成：

-   小镇页面
-   NPC卡片
-   NPC详情
-   Tick按钮
-   Chat窗口
-   三个 NPC 的独立 Chat session、错误重试和 Provider/fallback 状态

------------------------------------------------------------------------

# 5. Phase 2：Agent系统增强

目标：

让NPC真正具有自主行为。

------------------------------------------------------------------------

## Agent Pipeline

实现：

    Current State

    ↓

    Memory Retrieval

    ↓

    Rule Filter

    ↓

    LLM Decision

    ↓

    Action Validation

    ↓

    World Update

------------------------------------------------------------------------

## NPC能力

支持：

-   移动
-   休息
-   工作
-   社交

------------------------------------------------------------------------

# 6. Phase 3：高级持久化与快照

目标：

在已完成的 SQLite 当前状态与 Action/Event 持久化上，增加可回滚快照和更丰富的长期数据。

增加：

## Database

SQLite（计划新增）:

    memory

    relationship

    world_snapshot

------------------------------------------------------------------------

## Snapshot机制

保存：

    Tick Number

    World Time

    NPC State

    Events

方便：

-   回滚
-   调试
-   演示

------------------------------------------------------------------------

# 7. Phase 4：AI能力增强

增加：

## Memory

短期：

最近事件。

长期：

重要经历。

未来：

Embedding Retrieval。

------------------------------------------------------------------------

## Reflection

NPC每天总结：

例如：

Ryan：

    今天认识了一名新的冒险者。

    感觉他值得信任。

------------------------------------------------------------------------

# 8. Phase 5：游戏体验增强

## 目标

从：

Web管理页面

升级：

2D AI Town。

------------------------------------------------------------------------

## 技术路线

推荐：

    Vue3

    +

    PixiJS

    +

    World State API

------------------------------------------------------------------------

增加：

-   Tile Map
-   Sprite
-   Camera
-   NPC移动动画

------------------------------------------------------------------------

# 9. Phase 6：展示级增强

可选：

## Quest系统

例如：

Ryan：

    寻找训练剑

------------------------------------------------------------------------

## Event系统

例如：

    城门附近出现异常魔法波动

前端：

显示：

事件提示。

------------------------------------------------------------------------

## 多NPC互动

例如：

Alice和Bob：

产生关系变化。

------------------------------------------------------------------------

# 10. 推荐开发时间安排

# Day 1

重点：

完成P0。

上午：

-   初始化项目
-   FastAPI
-   Vue

下午：

-   API
-   SQLite
-   World Tick

晚上：

-   NPC展示
-   Chat

目标：

基础闭环运行。

------------------------------------------------------------------------

# Day 2

重点：

AI和工程增强。

完成：

-   Agent Pipeline
-   Prompt
-   Mock模式
-   测试
-   Docker

目标：

达到优秀作业水平。

------------------------------------------------------------------------

# Day 3

重点：

展示优化。

完成：

-   UI优化
-   PixiJS地图（如果时间允许）
-   Demo录制
-   README完善

------------------------------------------------------------------------

# 11. 风险控制

## 风险1：过度开发游戏系统

解决：

优先保证：

AI Agent闭环。

------------------------------------------------------------------------

## 风险2：LLM不稳定

解决：

必须：

Mock Provider。

------------------------------------------------------------------------

## 风险3：前端开发耗时

解决：

先Vue组件化。

PixiJS作为增强。

------------------------------------------------------------------------

# 12. 最终交付目标

最终Demo流程：

    打开Aleria AI Town

    ↓

    进入小镇

    ↓

    查看Ryan、Shir、Grey

    ↓

    推进时间

    ↓

    NPC自主行动

    ↓

    查看事件记录

    ↓

    与NPC交流

    ↓

    发现角色故事

最终体现：

-   全栈能力
-   AI Agent能力
-   游戏设计能力
-   AI Coding能力

------------------------------------------------------------------------

# End of Document
