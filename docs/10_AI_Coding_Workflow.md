# Aleria AI Town AI Coding Workflow

版本：v1.0

更新时间：2026-08-22

# 1. AI辅助开发理念

Aleria AI Town 不仅是一个 AI 应用项目，同时也是一个 AI Native
软件开发实践项目。

核心理念：

> 人负责定义目标、架构和规则，AI负责加速实现；通过 Context Engineering
> 保证 AI 理解项目，通过工程验证保证最终质量。

AI 不替代工程设计。

AI 是：

-   架构讨论助手
-   代码实现助手
-   Debug助手
-   文档整理助手

------------------------------------------------------------------------

# 2. AI辅助开发整体流程

传统开发流程：

    需求

    ↓

    设计

    ↓

    编码

    ↓

    测试

    ↓

    部署

AI辅助开发流程：

    需求分析

    ↓

    Context整理

    ↓

    架构设计

    ↓

    任务拆解

    ↓

    Prompt输入

    ↓

    AI生成代码

    ↓

    人工Review

    ↓

    测试验证

    ↓

    持续迭代

------------------------------------------------------------------------

# 3. Context Engineering流程

## 3.1 为什么需要Context Engineering

AI Coding中的主要问题：

-   上下文缺失
-   项目目标理解错误
-   修改范围失控
-   代码风格不一致

因此项目采用文档驱动的上下文管理。

------------------------------------------------------------------------

# 3.2 项目Context体系

    docs/

    00_Project_Context.md

    01_Assignment_Specification.md

    02_Product_Design.md

    03_World_Model.md

    04_NPC_Agent_Design.md

    05_Engineering_Architecture.md

    06_API_Contract.md

    07_Database_Schema.md

    08_Prompt_Engineering.md

    09_Decision_Log.md

    10_AI_Coding_Workflow.md

这些文档共同构成：

Aleria AI Town 的长期上下文。

------------------------------------------------------------------------

# 4. AI工具职责划分

## 4.1 ChatGPT

主要负责：

### 架构设计

例如：

-   World Model设计
-   Agent Pipeline设计
-   Database Schema设计

### 技术方案讨论

例如：

-   SQLite vs PostgreSQL
-   Hybrid Agent vs Pure LLM

### Context维护

生成：

-   设计文档
-   决策记录
-   Prompt设计

------------------------------------------------------------------------

## 4.2 Codex / AI Coding Agent

主要负责：

代码实现。

例如：

读取：

    05_Engineering_Architecture.md

    06_API_Contract.md

    07_Database_Schema.md

实现：

    backend/

    frontend/

    tests/

------------------------------------------------------------------------

## 4.3 IDE AI助手

用于：

-   局部代码补全
-   重构
-   Bug定位

------------------------------------------------------------------------

# 5. AI任务拆解规范

## 错误方式

不要：

    帮我完成整个AI Town项目

原因：

-   上下文过大
-   AI无法保证架构一致
-   难以验证

------------------------------------------------------------------------

## 推荐方式

任务应该：

小范围。

明确。

可验证。

例如：

    请根据：

    05_Engineering_Architecture.md

    06_API_Contract.md


    实现World Tick API。


    要求：

    1. 使用FastAPI

    2. 使用Pydantic校验

    3. 不直接修改数据库

    4. 增加单元测试


    完成后说明：

    修改文件

    设计思路

    测试结果

------------------------------------------------------------------------

# 6. Prompt设计规范

优秀Coding Prompt包含：

## 6.1 Context

说明：

项目背景。

例如：

    这是Aleria AI Town项目。

    NPC采用Hybrid Agent架构。

    World Engine负责最终状态修改。

------------------------------------------------------------------------

## 6.2 Task

明确：

需要完成什么。

例如：

    实现NPC Action Validator模块。

------------------------------------------------------------------------

## 6.3 Constraint

明确限制。

例如：

    LLM输出不能直接修改World State。

    必须经过Validator。

------------------------------------------------------------------------

## 6.4 Output

要求AI说明：

-   修改文件
-   设计原因
-   测试方式

------------------------------------------------------------------------

# 7. AI生成代码审核流程

AI生成代码后，不直接提交。

流程：

    AI生成代码

    ↓

    人工阅读

    ↓

    检查架构一致性

    ↓

    检查安全问题

    ↓

    运行测试

    ↓

    提交代码

------------------------------------------------------------------------

# 8. AI代码Review重点

## 8.1 架构一致性

例如：

错误：

``` python
action = llm.generate()

world.update(action)
```

问题：

LLM直接控制世界。

正确：

    LLM

    ↓

    Action Validator

    ↓

    World Update

------------------------------------------------------------------------

## 8.2 安全性

检查：

-   AI输出校验
-   输入参数验证
-   密钥管理

------------------------------------------------------------------------

## 8.3 边界条件

例如：

-   NPC不存在
-   LLM调用失败
-   数据库异常
-   并发Tick

------------------------------------------------------------------------

# 9. Debug流程

AI项目Debug不采用：

"让AI直接修Bug"。

采用工程排查流程：

    现象

    ↓

    日志分析

    ↓

    定位模块

    ↓

    提出假设

    ↓

    验证

    ↓

    修改

    ↓

    测试

------------------------------------------------------------------------

例如：

NPC没有移动。

排查：

    Frontend

    ↓

    API

    ↓

    World Tick

    ↓

    Agent Decision

    ↓

    Action Validation

    ↓

    Database Update

------------------------------------------------------------------------

# 10. Git协作流程

推荐：

    main

    |

    develop

    |

    feature/*

功能开发：

    feature/world-engine

    feature/npc-agent

    feature/frontend-map

Commit规范：

    feat:
    add npc decision system


    fix:
    validate llm action output

    docs:
    update architecture decision

------------------------------------------------------------------------

# 11. 测试验证流程

AI生成代码必须经过验证。

## 11.1 单元测试

例如：

Action Validator:

输入：

``` json
{
"action":"invalid_action"
}
```

期望：

拒绝。

------------------------------------------------------------------------

## 11.2 API测试

例如：

    POST /api/world/tick

检查：

-   Tick增加
-   NPC状态变化
-   Event生成

------------------------------------------------------------------------

## 11.3 Prompt测试

例如：

Ryan：

输入：

"你害怕史莱姆吗？"

检查：

是否符合角色设定。

------------------------------------------------------------------------

# 12. AI协作经验总结

Aleria AI Town 的开发方式：

不是：

    让AI写项目

而是：

    人设计系统

    ↓

    文档沉淀Context

    ↓

    AI实现模块

    ↓

    人工Review

    ↓

    测试验证

    ↓

    持续优化

------------------------------------------------------------------------

# 13. 面试表达总结

如果被问：

"你如何使用AI辅助开发？"

可以回答：

> 我不会直接让AI一次生成完整项目，而是先通过Context
> Engineering建立项目上下文，包括需求、架构、数据模型和Prompt设计。之后将任务拆解成独立模块交给AI实现，每次生成代码后进行人工Review和测试验证，确保AI输出符合整体架构。

------------------------------------------------------------------------



# 14. Phase 1E 实际协作与人工修正案例

当前项目采用以下闭环：

    人定义目标、范围和不可破坏边界
        ↓
    AI 协助分析、编写测试和最小实现
        ↓
    自动测试、类型检查、构建与 Diff
        ↓
    人工 Review
        ↓
    由开发者手动提交 Git

AI 不被授权自动 commit，也不能将模型输出直接作为 World Action、Quest Command 或数据库写入。

## Observation

接入腾讯混元 hy-role 时，TokenHub 已显示 Token 消耗，但 Frontend 仍提示使用 Mock；Backend 安全日志记录 category=response_validation。

## Diagnosis

请求已经到达模型，网络和鉴权并非主要失败点。真正原因是 hy-role 返回自然文本，而 Adapter 当时只接受 reply + emotion JSON。

## Minimal Fix

没有复制 Hunyuan 专用 Provider，也没有修改 ChatService 或 Fallback。人工确认边界后，只在统一 OpenAI-compatible Adapter 增加 structured_json | text 输出模式；text mode 继续校验正文，并确定性派生 emotion。

## Regression

补充 Adapter、Provider、Fallback、Chat API 和状态隔离测试；重新验证 Mock、结构化模型和自然文本模型共用同一公共契约，且 Chat 不修改 World、NPC、Player 或 Quest。

------------------------------------------------------------------------
# End of Document
