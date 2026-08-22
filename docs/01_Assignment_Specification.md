# Aleria AI Town Assignment Specification

Version: v1.0

Source: Tencent IEG AI Town Web Game Full-Stack Development Assignment

Last Updated: 2026-08-22

# 1. Assignment Overview

## 1.1 Objective

本项目需要完成一个可运行、可演示的 Web AI 小镇 MVP。

项目重点考察：

-   基础前后端开发能力
-   AI 工具辅助开发能力
-   问题拆解能力
-   工程实现能力

不要求：

-   复刻 Stanford Generative Agents
-   开发完整商业游戏
-   实现复杂游戏系统

------------------------------------------------------------------------

# 2. Required User Experience

最终用户流程：

    查看小镇

    ↓

    选择 NPC

    ↓

    推进一个回合

    ↓

    NPC 决定并执行行动

    ↓

    玩家查看结果

    ↓

    玩家与 NPC 对话

系统必须形成完整闭环：

Frontend

↓

Backend API

↓

World State Update

↓

NPC Decision

↓

Frontend Refresh

------------------------------------------------------------------------

# 3. Minimum Functional Requirements

## 3.1 Town Page

小镇主页面必须展示：

### World Information

-   小镇名称
-   当前时间或当前回合数

### Location

至少两个地点。

例如：

-   酒馆
-   公园

### NPC

至少两个 NPC。

每个 NPC：

-   显示名称
-   显示当前位置

### Tick Control

提供：

"推进一回合"按钮。

点击后：

后台生成 NPC 下一步行动。

前端更新：

-   NPC位置
-   NPC状态
-   行动描述

页面需要：

-   清晰布局
-   加载状态
-   接口失败处理

------------------------------------------------------------------------

# 4. NPC Information and Interaction

每个 NPC 至少包含：

## Basic Information

-   姓名
-   身份
-   性格

## Runtime State

-   当前地点
-   当前状态
-   当前行为

## History

玩家点击 NPC 后：

查看最近 3 条行动记录。

## Conversation

玩家可以输入一句话：

NPC返回回复。

不同 NPC 的回复和行为：

必须体现人物差异。

------------------------------------------------------------------------

# 5. Backend API Requirements

接口形式可自行设计。

至少支持以下能力：

------------------------------------------------------------------------

## Get World State

Example:

    GET /api/world

功能：

获取：

-   小镇信息
-   地点
-   NPC当前状态

------------------------------------------------------------------------

## World Tick

Example:

    POST /api/world/tick

功能：

推进一个世界回合。

执行：

-   NPC决策
-   NPC行动
-   状态更新

------------------------------------------------------------------------

## Get NPC Detail

Example:

    GET /api/npcs/{id}

功能：

获取：

-   NPC详细信息
-   行动记录

------------------------------------------------------------------------

## NPC Chat

Example:

    POST /api/npcs/{id}/chat

功能：

玩家与指定 NPC 对话。

------------------------------------------------------------------------

# 6. NPC Decision Requirements

NPC行为不能完全由前端写死。

后台需要结合：

-   人物设定
-   当前地点
-   NPC状态
-   时间或回合
-   允许执行行为

生成决策。

------------------------------------------------------------------------

# 7. Recommended Decision Architecture

推荐：

Rule + AI Hybrid Architecture

流程：

    NPC State

    ↓

    Candidate Actions

    ↓

    AI Decision

    ↓

    Action Validation

    ↓

    Execute Action

    ↓

    Update World

------------------------------------------------------------------------

AI建议返回结构化结果：

``` json
{
  "action": "move",
  "target": "park",
  "reason": "工作结束后想去公园放松"
}
```

------------------------------------------------------------------------

# 8. AI Safety Requirements

后台必须验证：

## Action Validation

例如：

允许：

    move
    rest
    work
    chat
    eat

禁止：

未知Action。

------------------------------------------------------------------------

## Target Validation

例如：

允许：

    park
    cafe
    home

禁止：

不存在地点。

------------------------------------------------------------------------

## AI Failure Handling

当：

-   未配置模型密钥
-   AI调用失败
-   返回格式错误

系统必须：

返回预设 Mock 结果。

保证：

主要流程仍然可体验。

------------------------------------------------------------------------

# 9. Technology Requirements

## Frontend

允许：

-   原生 HTML + JavaScript
-   Vue 3 + TypeScript + Vite

推荐：

Vue 3 + TypeScript + Vite

可使用：

-   Pinia
-   Vue Router
-   UI组件库

不强制：

Canvas

游戏引擎

合理使用：

Canvas / Cocos

可以获得加分。

------------------------------------------------------------------------

## Backend

语言不限：

-   Node.js
-   Go
-   Python

框架不限。

推荐：

Python + FastAPI

------------------------------------------------------------------------

## Data Storage

允许：

-   内存
-   JSON文件
-   SQLite

不强制数据库。

------------------------------------------------------------------------

# 10. Engineering Requirements

项目需要：

## README

包含：

-   项目介绍
-   技术选型
-   启动方式
-   接口说明
-   AI模式说明

------------------------------------------------------------------------

## Environment Management

提供：

    .env.example

真实密钥：

禁止提交。

------------------------------------------------------------------------

## Testing

至少：

为一个关键函数或 API：

提供自动化测试。

------------------------------------------------------------------------

## Error Handling

需要处理：

-   前端加载失败
-   API异常
-   AI调用失败

------------------------------------------------------------------------

# 11. Final Deliverables

## Source Code

包含：

-   前端
-   后台
-   初始化数据
-   .env.example

------------------------------------------------------------------------

## README.md

顶部注明：

-   候选人姓名
-   仓库地址
-   体验地址
-   技术栈
-   实际投入时间
-   已完成功能
-   已知问题

------------------------------------------------------------------------

## Demo Material

包含：

-   小镇页面
-   NPC行动
-   玩家对话

------------------------------------------------------------------------

# 12. Evaluation Focus

评审重点：

## Runtime

是否可以按照 README 启动。

## World Display

是否展示：

-   至少2个地点
-   至少2个NPC

## NPC Simulation

推进回合后：

NPC是否根据状态更新行为。

## Interaction

玩家是否可以与不同人格NPC交流。

## AI Capability

无AI密钥：

Mock模式是否可运行。

## Engineering Explanation

候选人是否理解：

-   核心模块
-   AI生成代码
-   技术取舍

------------------------------------------------------------------------

# 13. Scoring Interpretation

总分：

100分

## Function Completeness

25%

关注：

-   小镇
-   NPC
-   Tick
-   对话

## Frontend

20%

关注：

-   Vue组件设计
-   TypeScript
-   状态管理
-   交互

## Backend

20%

关注：

-   API设计
-   数据组织
-   参数校验
-   错误处理

## AI Capability

15%

关注：

-   AI决策
-   NPC人格
-   输出验证
-   Mock降级

## Engineering Quality

10%

关注：

-   目录结构
-   文档
-   配置管理
-   测试

## Analysis Ability

10%

关注：

-   技术取舍
-   AI工具使用
-   项目理解

------------------------------------------------------------------------

# 14. Project Implementation Strategy

根据评分目标，本项目优先级：

## Must Have

-   World页面
-   NPC展示
-   Tick推进
-   NPC行动
-   NPC聊天
-   AI/Mock双模式

## Should Have

-   SQLite持久化
-   Docker
-   自动化测试
-   清晰文档

## Nice To Have

-   Canvas/Pixi地图
-   NPC关系
-   Memory
-   Quest
-   在线部署

------------------------------------------------------------------------

# End of Document
