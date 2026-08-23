# Aleria AI Town 项目结构设计（Project Structure）

版本：v1.2

更新时间：2026-08-23

# 1. 文档目的

本文档定义 Aleria AI Town 的代码仓库结构、模块职责和开发边界。

目标：

-   明确前后端职责
-   指导 AI Coding Agent 理解项目结构
-   降低模块耦合
-   支持 MVP 到未来游戏化扩展

------------------------------------------------------------------------

# 2. 总体仓库结构

    Aleria_AI_Town/

    ├── README.md

    ├── docker-compose.yml

    ├── .env.example


    ├── docs/

    │   ├── 00_Project_Context.md

    │   ├── 01_Assignment_Specification.md

    │   ├── ...

    │   └── 11_Project_Structure.md


    ├── frontend/


    ├── backend/


    ├── data/


    ├── prompts/


    ├── tests/


    ├── scripts/


    └── deployment/

------------------------------------------------------------------------

# 3. Frontend结构

技术：

Vue3 + TypeScript + Vite

职责：

负责：

-   世界展示
-   NPC交互
-   玩家操作
-   状态管理

不负责：

-   NPC决策
-   世界规则
-   数据持久化

Phase 1A目录（在Phase 0基础上）：

    frontend/
    └── src/
        ├── api/
        │   └── world.ts
        ├── components/
        │   ├── LocationCard.vue
        │   ├── NpcCard.vue
        │   └── TickPanel.vue
        ├── stores/
        │   └── world.ts
        ├── types/
        │   ├── world.ts
        │   └── worldTick.ts
        ├── views/
        │   └── TownView.vue
        ├── App.vue
        └── main.ts

Frontend保持 `Typed API Adapter -> World Store -> UI / Renderer` 边界。未来迁移开源Vue界面或PixiJS时，只替换展示组件、样式、素材和Renderer，不反向修改Backend领域模型。

------------------------------------------------------------------------

# 3.1 api/

负责后端通信。

例如：

    world.ts

    npc.ts

    player.ts

提供：

-   获取世界状态
-   推进Tick
-   NPC聊天

------------------------------------------------------------------------

# 3.2 components/

UI组件。

例如：

    TownMap.vue

    NPCPanel.vue

    ChatBox.vue

    Timeline.vue

------------------------------------------------------------------------

# 3.3 stores/

使用Pinia管理：

当前世界状态。

例如：

    worldState

    playerState

    selectedNPC

------------------------------------------------------------------------

# 4. Backend结构

技术：

Python + FastAPI

Phase 1A目录（新增Tick模块）：

    backend/
    ├── __init__.py
    ├── requirements.txt
    ├── data/
    │   └── aleria.db
    └── app/
        ├── __init__.py
        ├── main.py
        ├── api/
        │   ├── __init__.py
        │   ├── world.py
        │   └── world_tick.py
        ├── core/
        │   ├── __init__.py
        │   └── config.py
        ├── database/
        │   ├── __init__.py
        │   ├── connection.py
        │   ├── models.py
        │   ├── world_repository.py
        │   └── world_tick_repository.py
        ├── schemas/
        │   ├── __init__.py
        │   ├── common.py
        │   ├── seed.py
        │   ├── world.py
        │   └── world_tick.py
        ├── world/
        │   ├── types.py
        │   ├── clock.py
        │   ├── decision.py
        │   ├── action_rules.py
        │   └── tick_engine.py
        └── services/
            ├── __init__.py
            ├── world_service.py
            └── world_tick_service.py

Phase 1A已创建 `world/` 纯领域包。`agents/` 与 `llm/` 仍延后到对应功能进入实施阶段，不创建空包。

------------------------------------------------------------------------

# 4.1 api/

HTTP接口层。

负责：

-   请求解析
-   参数校验
-   返回响应

不负责：

复杂业务逻辑。

------------------------------------------------------------------------

# 4.2 world/

World Engine。

实施阶段：Phase 1 World Tick。

项目核心。

负责：

-   世界时间推进
-   Tick管理
-   世界规则
-   Event生成

例如：

    world.tick()

------------------------------------------------------------------------

# 4.3 agents/

NPC Agent系统。

实施阶段：Phase 2 Agent增强。

负责：

-   感知
-   Memory检索
-   决策
-   行动生成

结构：

    Agent

    ↓

    Planner

    ↓

    Action

------------------------------------------------------------------------

# 4.4 database/

数据库访问层。

负责：

-   SQLite连接
-   Repository
-   数据初始化

遵循：

    Service

    ↓

    Repository

    ↓

    Database

------------------------------------------------------------------------

# 4.5 llm/

LLM抽象层。

实施阶段：NPC Decision或Chat首次接入模型时。

结构：

    LLM Provider


    ├── Gemini

    ├── OpenAI

    └── Mock

避免业务代码绑定具体模型。

------------------------------------------------------------------------

# 5. Data配置

目录：

    data/

    ├── world.json

    ├── locations.json

    ├── npcs.json

    └── rules.json

用于保存：

-   世界配置
-   地图
-   NPC初始数据
-   行为规则

游戏内容与代码分离。

Phase 0中JSON只作为SQLite种子输入，不作为运行时状态源。

------------------------------------------------------------------------

# 6. Prompt配置

目录：

    prompts/


    ├── world_lore.md


    ├── characters/


    │   ├── ryan.md

    │   ├── shir.md

    │   └── grey.md


    ├── decision_prompt.md

    └── chat_prompt.md

保存：

-   世界背景
-   NPC人格
-   Agent提示词

------------------------------------------------------------------------

# 7. Tests

测试范围：

    tests/
    ├── backend/
    │   ├── conftest.py
    │   ├── test_seed_world.py
    │   ├── test_world_api.py
    │   ├── test_world_engine.py
    │   └── test_world_tick.py
    └── frontend/
        ├── TownView.spec.ts
        ├── TickPanel.spec.ts
        ├── world.spec.ts
        └── worldTick.spec.ts

覆盖：

-   API正确性
-   Tick一致性
-   Agent输出校验
-   角色一致性

World Tick测试已随Phase 1A实现创建；`test_agent.py` 和Prompt测试继续随对应行为实现，不预先建立空测试。

------------------------------------------------------------------------

# 8. Scripts

初始化脚本。

例如：

    seed_world.py

    upgrade_schema.py

负责：

-   创建数据库
-   导入初始世界

`seed_world.py` 创建表并幂等重置种子世界；`upgrade_schema.py` 为已有数据库非破坏性创建缺失表。两者语义不同，因此不合并为模糊的 `init_db.py` 入口。

------------------------------------------------------------------------

# 9. Deployment

未来部署相关。

包含：

-   Docker
-   Nginx
-   云部署配置

------------------------------------------------------------------------

# 10. MVP开发范围

第一阶段：

必须完成：

    frontend

    +

    backend

    +

    SQLite

    +

    World Tick

    +

    NPC Chat

------------------------------------------------------------------------

# 11. 未来扩展方向

## 游戏化地图

增加：

    PixiJS

    Canvas

    Cocos

替换：

当前CSS地图。

------------------------------------------------------------------------

## Quest系统

增加：

    quests/

------------------------------------------------------------------------

## Memory增强

增加：

    Embedding

    Vector Retrieval

------------------------------------------------------------------------

## 多人世界

增加：

-   用户系统
-   权限
-   实时同步

------------------------------------------------------------------------

# 12. AI Coding使用方式

AI Agent读取顺序：

    00_Context

    ↓

    05_Architecture

    ↓

    06_API

    ↓

    07_Database

    ↓

    11_Project_Structure

    ↓

    具体任务

确保：

代码实现符合整体设计。

------------------------------------------------------------------------

# End of Document
