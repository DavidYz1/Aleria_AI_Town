# Aleria AI Town 开发环境设计文档（Development Environment）

版本：v1.1

更新时间：2026-08-22

# 1. 文档目的

本文档用于统一 Aleria AI Town 的开发环境。

目标：

-   保证本地开发一致性
-   降低环境配置成本
-   方便 AI Coding Agent 理解运行约束
-   支持后续 Docker 部署

------------------------------------------------------------------------

# 2. 项目环境设计原则

## 2.1 优先保证可运行

腾讯作业重点验证：

-   README启动流程
-   前后端通信
-   NPC状态更新
-   AI/Mock模式

因此开发环境优先考虑：

简单。

稳定。

可复现。

------------------------------------------------------------------------

## 2.2 MVP阶段避免过度基础设施

第一阶段不引入：

-   Kubernetes
-   微服务
-   复杂消息队列

原因：

项目核心价值是：

AI Agent + 游戏世界模拟。

------------------------------------------------------------------------

# 3. 技术栈版本规划

# Frontend

技术：

    Vue 3

    +

    TypeScript

    +

    Vite

    +

    Pinia

    +

    Axios

用途：

-   页面组件化
-   世界状态管理
-   API通信

------------------------------------------------------------------------

# Backend

技术：

    Python 3.11

    +

    FastAPI

    +

    Pydantic v2

    +

    SQLAlchemy

    +

    SQLite

用途：

-   API服务
-   World Engine
-   NPC Agent
-   数据持久化

------------------------------------------------------------------------

# AI Layer

采用：

LLM Provider抽象。

结构：

    LLM Provider

    ├── Mock Provider

    ├── Gemini Provider

    ├── OpenAI Provider

    └── Other Provider

------------------------------------------------------------------------

# 4. 推荐目录结构

    Aleria_AI_Town/

    ├── frontend/

    ├── backend/

    ├── docs/

    ├── data/

    ├── prompts/

    ├── tests/

    ├── scripts/

    ├── deployment/

    ├── docker-compose.yml

    └── .env.example

------------------------------------------------------------------------

# 5. 前端环境

## Node版本

推荐：

    Node.js >= 20

检查：

``` bash
node -v
```

------------------------------------------------------------------------

## 安装依赖

进入：

``` bash
cd frontend
```

安装：

``` bash
npm install
```

------------------------------------------------------------------------

## 启动

``` bash
npm run dev
```

默认：

    http://localhost:5173

------------------------------------------------------------------------

# 6. 后端环境

## Python版本

推荐：

    Python >=3.11

------------------------------------------------------------------------

## 创建虚拟环境

Windows:

``` bash
python -m venv .venv

.venv\Scripts\activate
```

Linux/macOS:

``` bash
python -m venv .venv

source .venv/bin/activate
```

------------------------------------------------------------------------

## 安装依赖

``` bash
pip install -r backend/requirements.txt
```

------------------------------------------------------------------------

## 启动服务

``` bash
uvicorn backend.app.main:app --reload
```

默认：

    http://localhost:8000

------------------------------------------------------------------------

# 7. 数据库环境

MVP阶段：

采用 SQLite。

原因：

-   数据量较小
-   部署简单
-   满足世界状态保存

数据库文件：

    backend/data/aleria.db

Phase 0运行时唯一状态源为SQLite。根目录 `data/*.json` 仅作为种子配置。

从仓库根目录执行幂等初始化：

``` bash
python scripts/seed_world.py
```

脚本负责创建Phase 0表并写入晨曦镇、两个地点及Ryan/Shir/Grey；重复执行会恢复声明的初始数据，不产生重复记录。

------------------------------------------------------------------------

# 8. 环境变量设计

根目录：

    .env.example

示例：

``` env
APP_ENV=development


DATABASE_URL=sqlite:///./backend/data/aleria.db


FRONTEND_ORIGIN=http://localhost:5173


LLM_PROVIDER=mock


ENABLE_LLM=false


GEMINI_API_KEY=

OPENAI_API_KEY=
```

------------------------------------------------------------------------

# 9. AI运行模式

系统支持两种模式。

# Mock模式

默认：

    ENABLE_LLM=false

行为：

使用预设NPC决策。

例如：

``` json
{
"action":"move",
"target":"park",
"reason":"天气很好，想散步"
}
```

优势：

-   无需API Key
-   稳定演示
-   支持测试

------------------------------------------------------------------------

# LLM模式

配置：

    ENABLE_LLM=true

调用：

对应Provider。

要求：

所有LLM输出必须经过：

    LLM

    ↓

    Schema Validation

    ↓

    Action Validation

    ↓

    World Update

------------------------------------------------------------------------

# 10. Docker环境

后续支持：

    docker-compose.yml


    services:

     frontend

     backend

目标：

一条命令启动完整项目。

------------------------------------------------------------------------

# 11. 本地启动流程

完整流程：

## Step 1

从仓库根目录初始化SQLite：

``` bash
python scripts/seed_world.py
```

------------------------------------------------------------------------

## Step 2

启动Backend

``` bash
uvicorn backend.app.main:app --reload
```

------------------------------------------------------------------------

## Step 3

启动Frontend

``` bash
cd frontend

npm run dev
```

------------------------------------------------------------------------

## Step 4

访问：

    http://localhost:5173

------------------------------------------------------------------------

# 12. Phase 0验证命令

Backend API测试：

``` bash
pytest tests/backend -v
```

Frontend测试、类型检查和生产构建：

``` bash
cd frontend

npm run test

npm run type-check

npm run build
```

真实闭环检查：

1.  Backend运行在 `http://localhost:8000`。
2.  Frontend运行在 `http://localhost:5173`。
3.  页面展示晨曦镇、Day 1 08:00、星辰酒馆、中央公园以及Ryan/Shir/Grey。
4.  停止Backend并刷新页面时，Frontend展示可理解的接口失败状态。

------------------------------------------------------------------------

# 13. 开发规范

## Git分支

    main

    develop

    feature/*

------------------------------------------------------------------------

## Commit规范

示例：

    feat: add world tick engine

    feat: add npc chat api

    fix: validate llm output

    docs: update architecture

------------------------------------------------------------------------

# 14. AI Coding环境约束

AI Coding Agent开始任务前，应读取：

    00_Project_Context.md

    05_Engineering_Architecture.md

    06_API_Contract.md

    07_Database_Schema.md

    11_Project_Structure.md

    13_Development_Roadmap.md

避免：

-   修改错误模块
-   破坏架构
-   引入无关依赖

------------------------------------------------------------------------

# 15. 后续生产化扩展

未来可以增加：

## 数据库

SQLite

↓

PostgreSQL

## 部署

Docker

↓

云服务器

## 游戏前端

Vue

↓

PixiJS/Cocos

## Agent Memory

SQLite

↓

Vector Database

------------------------------------------------------------------------

# End of Document
