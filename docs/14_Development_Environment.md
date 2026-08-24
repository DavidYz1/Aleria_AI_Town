# Aleria AI Town 开发环境设计文档（Development Environment）

版本：v1.3

更新时间：2026-08-24

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

    ChatProvider
    ├── MockChatProvider
    └── FallbackChatProvider
        ├── OpenAICompatibleChatProvider
        └── MockChatProvider

腾讯混元、DeepSeek 和本地 Qwen compatible 服务复用同一个 Adapter；当前没有供应商专用实现。

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
npm run dev -- --host 127.0.0.1
```

默认：

    http://127.0.0.1:5173

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

脚本负责创建当前 SQLAlchemy 模型全部表并写入曦谷、四个地点、Ryan/Shir/Grey、固定 Player 和初始 Quest；重复执行会按依赖顺序清除目标世界的 Quest、Chat、Event、Action 历史并恢复种子状态，不产生重复记录。

------------------------------------------------------------------------

# 8. 环境变量设计

根目录：

    .env.example

示例：

``` env
APP_ENV=development


DATABASE_URL=sqlite:///./backend/data/aleria.db


FRONTEND_ORIGIN=http://127.0.0.1:5173


CHAT_PROVIDER=mock


CHAT_LLM_BASE_URL=


CHAT_LLM_API_KEY=

CHAT_LLM_MODEL=


CHAT_LLM_AUTH_MODE=bearer


CHAT_LLM_OUTPUT_MODE=structured_json


CHAT_LLM_TIMEOUT_SECONDS=30


CHAT_HISTORY_LIMIT=10


CHAT_PROMPT_VERSION=v3
```

约束：

-   `CHAT_PROVIDER=mock` 时 URL、Key、model 可以全部为空。
-   非 Mock 必须配置 `CHAT_LLM_BASE_URL` 和 `CHAT_LLM_MODEL`。
-   `CHAT_LLM_AUTH_MODE=bearer` 时 Key 必填，且只保存在 Backend 环境中；文档示例使用 `<backend-only-secret>`。
-   `CHAT_LLM_AUTH_MODE=none` 允许本地服务不配置 Key。
-   `CHAT_LLM_OUTPUT_MODE` 只允许 `structured_json` 或 `text`；前者严格解析 `reply + emotion`，后者兼容自然文本并确定性派生 emotion。
-   timeout 范围 0–120 秒（不含 0），history limit 范围 1–50，Prompt 版本允许 `v1|v2|v3` 且默认 `v3`。

------------------------------------------------------------------------

# 9. AI运行模式

系统支持默认 Mock 和 compatible Primary + Mock fallback 两种运行方式。

# Mock模式

默认：

    CHAT_PROVIDER=mock

行为：

使用确定性的角色化 Mock Chat 回复。World Tick 的 NPC Action 仍由 `backend/app/world/` 规则决定，不由 Chat Provider 控制。

例如：

``` json
{
  "reply":"别担心，只要愿意向前走，我们总能找到办法。",
  "emotion":"cheerful"
}
```

优势：

-   无需API Key
-   稳定演示
-   支持测试

------------------------------------------------------------------------

# Compatible LLM模式

云端 compatible 示例：

``` env
CHAT_PROVIDER=deepseek
CHAT_LLM_BASE_URL=<provider-compatible-base-url>
CHAT_LLM_API_KEY=<backend-only-secret>
CHAT_LLM_MODEL=<compatible-model-name>
CHAT_LLM_AUTH_MODE=bearer
CHAT_LLM_OUTPUT_MODE=structured_json
```

`CHAT_PROVIDER` 是可观测标签，不选择专用代码分支。腾讯混元或其他 compatible 云端服务替换地址与模型即可。

腾讯混元 `hy-role` 角色对话示例（推荐用于更自然的人设演绎）：

``` env
CHAT_PROVIDER=hunyuan
CHAT_LLM_BASE_URL=<hunyuan-compatible-base-url>
CHAT_LLM_API_KEY=<backend-only-secret>
CHAT_LLM_MODEL=hy-role
CHAT_LLM_AUTH_MODE=bearer
CHAT_LLM_OUTPUT_MODE=text
CHAT_LLM_TIMEOUT_SECONDS=30
CHAT_PROMPT_VERSION=v3
```

`hy-role` 的角色表达效果较好，但不稳定遵守 `reply + emotion` JSON 契约，因此使用 `text` 模式更稳妥；Adapter 会校验自然文本并确定性派生 emotion，ChatService 与 Fallback 无需改动。真实 URL、Key 和模型权限只在本地 Backend 环境中配置，禁止提交或记录到日志。

若使用能够稳定遵守 JSON 契约的混元模型（例如项目已验证的 `hy3`），可改回 `CHAT_LLM_OUTPUT_MODE=structured_json`。两种模型仍共用同一个 OpenAI-compatible Adapter。

本地无鉴权 Qwen 示例：

``` env
CHAT_PROVIDER=local
CHAT_LLM_BASE_URL=http://127.0.0.1:8001/v1
CHAT_LLM_API_KEY=
CHAT_LLM_MODEL=qwen-local
CHAT_LLM_AUTH_MODE=none
CHAT_LLM_OUTPUT_MODE=structured_json
```

要求：

所有LLM输出必须经过：

    LLM

    ↓

    Schema Validation

    ↓

    Structured reply + emotion 或 Text reply Validation

    ↓

    Chat Response / Mock Fallback

Chat 不进入 Action Execution 或 World Update。Primary 超时、网络错误、非 2xx 或非法输出时自动尝试 Mock，并通过 `fallback_used` 如实标记。

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

npm run dev -- --host 127.0.0.1
```

------------------------------------------------------------------------

## Step 4

访问：

    http://127.0.0.1:5173

------------------------------------------------------------------------

# 12. 当前工程验证命令

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

1.  Backend运行在 `http://127.0.0.1:8000`。
2.  Frontend运行在 `http://127.0.0.1:5173`。
3.  页面展示曦谷、Day 1 08:00、四地点以及 Ryan/Shir/Grey。
4.  停止Backend并刷新页面时，Frontend展示可理解的接口失败状态。
5.  默认 Mock 下选择 Ryan，发送“你害怕史莱姆吗？”，收到 guarded 回复；续聊复用 conversation ID。
6.  从星辉酒馆接取任务，经 Grey 实时地点、低语森林再回酒馆完成五步流程。
7.  切换 Shir/Grey 时会话互不覆盖；推进 Tick 后 Chat 和 Quest 保留，NPC 状态正常更新。

可选真实 Provider 手动冒烟只在开发者明确配置环境后执行。不得把真实 Key、Authorization Header 或上游错误正文写入终端截图、测试 fixture、Git diff 或文档。

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
