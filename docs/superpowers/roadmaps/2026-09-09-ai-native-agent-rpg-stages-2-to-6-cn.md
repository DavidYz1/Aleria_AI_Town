# Aleria AI Town：AI Native Agent RPG 阶段 2–6 路线图

**日期：** 2026-09-09
**状态：** 待用户 Review
**当前基线：** `9ac8d1f`（Agent Runtime Foundation 已完成并提交）
**项目定位：** 以可信、可解释、可评估的 Agent 行为为主线，以生产级 AI 全栈工程为技术内核，以可游玩的 RPG 世界作为用户体验与演示外壳

## 1. 路线图目的

本路线图定义阶段 2–6 的目标、依赖、玩家效果、技术交付、验收边界和作品化价值。它用于保证后续各阶段沿同一方向演进，但不替代阶段级 Spec 和逐文件实施 Plan。

后续每个阶段都必须单独完成：

1. 读取当前代码和本路线图。
2. 结合上一阶段实际结果讨论架构方案。
3. 编写并由用户 Review 中文 Spec。
4. 编写并由用户 Review 中文实施 Plan。
5. 按少量、边界清晰的 Task 测试驱动实现。
6. 每个 Task 停止供用户 Review；由用户手动提交 Git。

不得因为路线图提到某项能力，就在较早阶段提前实现它。

## 2. 最终目标与预期体验

阶段 6 完成后，Aleria AI Town 应达到可作为 BAT 级 AI 全栈实习核心简历项目的程度：

- 玩家可选择稳定、快速的普通推进，或由 LLM 驱动的 Agent 推进。
- NPC 能根据自身位置、身份和权限感知世界，不具有全知视角。
- NPC 能形成带来源的长期记忆，在相关场景回忆过去，并基于证据产生反思与信念。
- NPC 能形成目标和多步计划，在世界变化、行动失败或玩家介入后调整计划。
- NPC 能在规则允许的 RPG 世界中独立选择行动、推进个人任务和参与剧情，但不能直接修改权威状态。
- NPC 之间能交谈、建立方向性关系并传播带来源和可信度的信息，产生受控的涌现行为。
- 耗时推理具备异步执行、幂等、重试、恢复、预算和并发控制，不因模型失败破坏存档。
- 玩家和面试官可通过 Agent Lab 查看从感知到行动的事实链路、运行指标和评估结果，但看不到隐藏思维链、密钥或无权限的私有记忆。
- 项目具有可复现演示、自动化评估、生产部署说明、架构决策记录和可量化结果。

## 3. 当前稳定基础

Agent Runtime Foundation 已提供后续阶段必须复用的边界：

- `world_version`、`clock_tick`、`event_sequence` 分离并由 Backend 权威维护。
- 所有 NPC 在一次推进中消费同一不可变 World Snapshot。
- 确定性策略生成类型化 `ActionProposal`。
- Action Registry 负责合法动作、目标、前置条件和效果校验。
- accepted proposal 经确定性冲突处理后原子写入 Run、Proposal、Action、Event 和 Trace。
- 过期世界版本、非法动作或持久化失败不会产生半次世界变更。
- SQLite 支持本地和快速测试；PostgreSQL 17 + pgvector 0.8.6 已完成真实集成验收。
- 当前 `POST /api/world/tick` 保持同步 HTTP 200；RPG 只有一个确定性推进入口。

阶段 2–6 应在这些能力上增量扩展，不另建一条绕开 Registry、Snapshot 或事务提交的 LLM 执行链。

## 4. 跨阶段不变量

以下原则在阶段 2–6 中持续有效：

1. **RPG 世界权威属于 Backend。** LLM、工作流引擎、前端和队列均不能直接写世界状态。
2. **事实、感知、记忆、信念分层。** NPC 听到的说法不是世界事实，模型推断也不是事实。
3. **统一行动入口。** 普通策略和 LLM 策略最终都生成相同的类型化 Proposal，并经过同一套校验、冲突处理和提交。
4. **普通模式始终可用。** 模型、Embedding、队列或流式连接失败时，基础 RPG 仍能继续游玩。
5. **可解释不等于暴露思维链。** 只展示事实引用、规则结果、记忆来源、计划摘要、模型元数据和安全错误。
6. **每阶段形成垂直切片。** 技术内核必须对应玩家可感知的 RPG 效果和可复现演示。
7. **Schema 增量演进。** 使用 Alembic、备份和迁移矩阵；不得删库、重建或伪造版本来获得通过。
8. **测试可重复。** 快速 CI 使用 Fake Provider 和确定性 Embedding；真实 Provider/pgvector/队列验收使用独立环境。
9. **成本和涌现均有边界。** 对调用次数、Token、延迟、传播层数、对话轮数、计划重试和重复行动设置上限。
10. **阶段边界优先于框架。** LangGraph、Celery、Redis 或替代方案必须在对应阶段 Spec 中通过需求证明，不因上位文档提到就默认采用。

## 5. 总体阶段关系

```text
Foundation
  → Stage 2：知道发生了什么、记得什么、由此理解什么
  → Stage 3：想完成什么、准备怎么做、下一步做什么
  → Stage 4：如何可靠、异步、可恢复地运行上述认知
  → Stage 5：多个 NPC 如何相互影响并推动 RPG 剧情
  → Stage 6：如何观察、评估、比较、部署和展示整个系统
```

| 阶段 | Agent 能力主问题 | 玩家可见交付 | 技术主线 |
| --- | --- | --- | --- |
| 2 | 感知、记忆、反思 | NPC 记得并引用真实经历 | Memory、Retrieval、Reflection、Belief provenance |
| 3 | 目标、计划、LLM 行动 | 普通/LLM 推进，NPC 独立决策与改计划 | Structured LLM、Goal/Plan、统一 Proposal |
| 4 | 生产级执行 | 非阻塞推进、进度、恢复与降级 | Async Runtime、幂等、Outbox、Worker、SSE |
| 5 | 多智能体社会与剧情 | NPC 主动交互、信息传播、Forest Embers | Relationship、Conversation、Knowledge Flow、Quest |
| 6 | 评估与作品化 | Agent Lab、对比实验、稳定演示 | Replay、Evals、Metrics、Deployment、Portfolio |

## 6. 与 Stanford Generative Agents 的映射

参考项目 `D:/pythonproject/generative_agent` 提供认知思想，不作为可直接复制的生产架构。

| Stanford 思想 | Aleria 的适配方式 | 所属阶段 |
| --- | --- | --- |
| Observation | 从权威 Event/Snapshot 按位置、参与者、可见性和秘密权限派生 NPC 私有 Observation | 2 |
| Memory Stream | 使用结构化来源、发生时间、重要度、置信度、实体关联和生命周期的持久化 Memory | 2 |
| Recency/Relevance/Importance | 先做权限过滤，再组合语义相关、时效、重要度、目标/关系相关和矛盾惩罚 | 2，3 扩展 |
| Reflection | 由累计重要度或关键事件触发，输出必须引用证据 Memory ID，不能创造世界事实 | 2 |
| Planning | 使用注册 Goal Type、滚动计划和可执行 Plan Step，不生成自由文本日程后直接执行 | 3 |
| Agent interaction | 通过位置、忙碌状态、对话预约、有限轮次和社会规则运行 | 5 |
| Sandbox simulation | 保留 RPG Backend、事务、Quest 规则和 Action Registry 作为权威约束 | 全阶段 |

重点借鉴的是认知闭环和可追溯性；不会照搬基于文件的记忆、单进程循环、全知上下文或缺少事务/并发边界的实现。

## 7. Stage 2：感知、记忆与反思

### 7.1 阶段定位

让 NPC 从“只根据当前数值执行规则”升级为“能基于自己真正经历过的历史理解当前情境”。本阶段建立认知数据基础，但不让 LLM 直接决定世界行动。

### 7.2 技术交付

- Perception Pipeline：从 World Event、对话和直接交互派生 NPC-specific Observation。
- 可见性规则：位置、参与者、公开范围、职业渠道、秘密权限、注意力和去重。
- Memory Repository：至少支持 episodic、conversation、reflection、knowledge 四类记忆。
- Memory provenance：记录 owner、source event/observation、occurred/created tick、相关实体、重要度、置信度、情绪、秘密级别和状态。
- Embedding Provider 抽象：PostgreSQL 使用 pgvector；SQLite/Fake Provider 支持快速、确定性测试。
- Hybrid Retrieval：先做所有权、世界、时间线和秘密过滤，再结合语义相关、recency、importance、confidence 等排序。
- Reflection：由累计显著性或关键事件触发，生成带 evidence memory IDs 的 insight draft。
- Belief 最小模型：区分当前观点、置信度、支持/反对证据和 disputed/superseded 状态。
- 最小只读解释投影：允许 RPG NPC 详情或调试视图展示安全的“记得什么/为何相关”，不返回私密内容或隐藏推理。

### 7.3 玩家效果

- NPC 能记住玩家之前说过的话、见过的行动和关键任务事件。
- NPC 的回复或安全解释能引用真实记忆来源。
- 不在场的 NPC 不会自动知道私密事件。
- 新证据能使 NPC 对旧判断产生反思、质疑或更新，而不是覆盖历史。
- Embedding/LLM 不可用时仍能使用关键词、近期记忆和确定性重要度完成基础回忆。

### 7.4 验收边界

- 相同事实在不同可见条件下产生不同 Observation 集合。
- 未授权 NPC 无法检索秘密记忆，且 API/Trace 不泄露内容。
- 固定记忆集合的 retrieval 排序、去重、Token 预算和来源引用可重复测试。
- Reflection 必须引用存在且属于该 NPC 的证据；无证据、跨 NPC 引用或把推断写成事实必须拒绝。
- PostgreSQL/pgvector 做真实写入和检索验收；SQLite 完整回归保持可运行。
- 记忆/反思失败不得改变 World、Quest、NPC State 或已有 Run Graph。

### 7.5 明确后置

Goal/Plan、LLM Action、普通/LLM 双模式、异步队列、NPC-to-NPC 社交和 Agent Lab 均不在 Stage 2 实现。

### 7.6 作品价值

展示 RAG 不只是文档问答，而是具有权限、时间、来源、矛盾和角色所有权的 Agent Memory System。

## 8. Stage 3：目标、计划与 LLM 自主行动

### 8.1 阶段定位

让 NPC 把当前状态、身份、记忆和反思转化为受约束的目标、滚动计划和下一步行动，并让玩家能清楚比较确定性决策与 LLM 决策。

### 8.2 技术交付

- Identity/Drives：职业、价值观、性格、愿望、恐惧、责任和禁令的稳定输入。
- 注册式 Goal Type：LLM 可生成目标描述，但必须映射到有成功/失败条件和允许动作集合的 Goal Type。
- Goal Arbitration：综合紧迫度、人格/驱动力、记忆证据、任务相关、风险和切换成本。
- Rolling Plan：维护三至五个可执行 Plan Step，并定义前置条件、成功条件、失败策略、耗时和可中断性。
- Structured LLM Providers：Reflection、Planning、Action Decision 分离接口，严格 Schema 校验、一次修复和确定性 fallback。
- LLM 只能产生 `ActionProposal`；Registry、冲突处理、CAS 和原子提交继续掌握最终权力。
- Replanning Trigger：目标完成、前置条件变化、行动失败、关键事件、玩家干预和计划循环。
- 防循环机制：重复动作识别、冷却、最大失败次数、计划切换成本和单次预算。

### 8.3 普通推进与 LLM 推进

RPG 的“世界推进”区域增加两个明确选项，但不暴露复杂工程参数：

- **普通推进：** 使用现有 deterministic policy，快速、稳定、离线可用，作为回归与评估基线。
- **LLM 推进：** 使用 AUTO 语义，仅对满足触发条件的 NPC 进行认知；未触发 NPC 执行已有计划或确定性日常行为。

`FORCE_DELIBERATION`、指定模型和指定 NPC 等实验控制继续后置到 Agent Lab。两种推进必须复用相同的 Snapshot、Proposal、Registry、Conflict Resolver 和事务提交链。

这是对上位设计中“RPG 只暴露 AUTO 推进”的产品边界细化：普通玩家可以选择 ordinary 或 LLM 语义，但不能选择模型、强制指定 NPC 或绕过触发器。采用双按钮还是“模式选择 + 单一推进按钮”，由 Stage 3 UI Spec 在不造成误触和重复提交的前提下决定。

### 8.4 玩家效果

- NPC 能形成“今天想完成什么”及可理解的近期步骤。
- NPC 能自主执行工作、移动、休息、调查等合法行为。
- 任务条件变化或玩家提供关键证据后，NPC 会调整计划。
- 玩家能在普通模式和 LLM 模式之间进行可见对比。
- LLM 超时、无效输出或预算耗尽时安全回退，不会卡死世界或损坏存档。

### 8.5 验收边界

- 非法动作、虚构目标引用、过期 Proposal 和越权目标不能提交。
- 固定 Fake Provider 下，Goal/Plan/Proposal 和回退结果可确定性测试。
- 至少一个 NPC 能在无玩家逐步指挥的情况下完成一个有多步前置条件的小型任务。
- 至少一个关键世界变化能触发受控 replanning。
- 两种模式的世界规则和事务不变量完全一致。

### 8.6 明确后置

本阶段仍可同步执行；不提前引入生产队列、SSE、跨 NPC 长对话或完整章节社会系统。

### 8.7 作品价值

展示 LLM Agent 的核心不是“生成一句话”，而是结构化目标/计划、工具约束、状态一致性、失败恢复和可比较基线。

## 9. Stage 4：生产级异步 Agent Runtime

### 9.1 阶段定位

将 Stage 3 的认知和行动链升级为可用于真实产品的非阻塞、幂等、可恢复执行系统。

### 9.2 技术交付

- 异步 Run Submission：创建 pending run 并返回可查询标识；保留现有确定性同步能力或兼容入口。
- Transactional Outbox：Run 创建和待处理事件在同一事务写入，避免请求成功但任务丢失。
- Worker Boundary：一个 Worker Task 负责一个 World Run，NPC 推理可在任务内部受控并发。
- World Concurrency：同一世界只允许一个会推进状态的 pending/running/committing run。
- Idempotency：客户端 key、唯一约束和重复投递防护返回或复用同一 Run。
- Recovery：持久化阶段状态、刷新后查询、断线重连、超时、有限重试、取消和 stale proposal 拒绝。
- Progress Stream：通过 SSE 或经 Spec 证明的等价方案传递持久化进度；数据库仍是状态权威。
- Budget：限制调用次数、Token、估算成本、总时长、重试和反思/规划频率。
- Observability：记录 workflow stage、provider/model、prompt version、latency、token、fallback 和安全错误。

是否采用 LangGraph、Celery、Redis 或更轻的替代方案，必须由 Stage 4 Spec 根据恢复语义、部署复杂度和简历价值比较后决定。

### 9.3 玩家效果

- LLM 推进立即进入可见的运行状态，不长时间阻塞页面。
- 页面展示感知、检索、反思、计划、校验和执行等事实阶段。
- 刷新或短暂断线后能够恢复当前运行视图。
- 失败可以重试、取消或回退；重复点击不会产生重复世界行动。
- 普通推进仍可快速工作，不强依赖队列或模型。

### 9.4 验收边界

- 覆盖重复请求、重复任务投递、Worker 崩溃、模型超时、SSE 重连、取消窗口和世界版本冲突。
- 任何失败都不得留下半次 Action/Event/World 更新。
- PostgreSQL、Worker、队列和前端恢复执行真实集成验收。
- 给出 P50/P95 延迟、失败率、回退率和单次运行成本基线。

### 9.5 明确后置

不在本阶段扩展大量 NPC、复杂社会关系或完整 Forest Embers 内容；先确保已有认知链可靠运行。

### 9.6 作品价值

展示从 Agent Demo 到生产 AI Runtime 的关键工程能力：队列、事务、幂等、并发、恢复、流式体验、成本和可观测性。

## 10. Stage 5：多智能体社会与 Forest Embers RPG 章节

### 10.1 阶段定位

让三个 NPC 不只独立思考，还能在受约束的社会系统中交换信息、形成不同信念和关系，并共同推动一个可玩的 RPG 章节。

### 10.2 技术交付

- Directional Relationship：至少包含 familiarity、affinity、trust、respect，并保留变化来源和上限/冷却规则。
- Social Trigger：同地点、空闲、计划需要、关键消息或玩家行为触发有限社会反应。
- Conversation Manager：参与者预约、轮次上限、私有上下文、结构化 dialogue acts/claims 和终止条件。
- Knowledge Transfer：NPC 不复制彼此记忆；Speaker 表达 Claim，Listener 根据来源信任和已有证据形成 conversation memory/belief candidate。
- Relationship Update：LLM 识别有限社会信号，规则计算最终关系变化。
- Cross-agent Conflict：处理对话互选、移动与对话、独占资源、任务关键行动和传播层数。
- Forest Embers：以现有“失踪的孩子”为基础扩展证据、调查、秘密、误解、关系选择和多结局，但保持三 NPC、四地点的一章深度。
- Quest 只消费验证后的 Domain Event；玩家文字或模型输出不能直接推进任务。

### 10.3 玩家效果

- NPC 能主动交谈、协作、拒绝、隐瞒或纠正信息。
- 同一事件经过不同传播路径后，NPC 可能持有不同且可追溯的观点。
- 玩家帮助、欺骗、守诺或泄密会改变 NPC 对玩家及彼此的关系。
- NPC 可在世界中独立调查或推动章节相关任务，而非等待玩家逐个点击命令。
- Forest Embers 具有可重复进入、可完成、不会因 Agent 自主行为进入死局的主要路径和差异化结局。

### 10.4 验收边界

- 私密信息不能无来源跨 NPC 传播；每次传播可追溯 Speaker、Claim 和 Listener。
- 对话具备位置、占用、轮数、预算和传播深度限制，不出现无限聊天。
- 关系变化由验证事件驱动、有界、可重放，LLM 不能任意写数值。
- 多次模拟覆盖剧情可达性、信息泄漏、行动循环、冲突一致性和 fallback 生存能力。
- 至少提供一条确定性可完成路径和一条受控 Agent 差异路径。

### 10.5 明确后置

不扩展战斗、装备、背包、多人账号、大地图或大量 NPC；优先证明三 NPC 深交互和一章完整故事。

### 10.6 作品价值

展示 Memory、Belief、Planning、Relationship、Conversation 与 RPG Quest 如何在同一权威事件模型中协作，形成可解释而非失控的多智能体涌现。

## 11. Stage 6：Agent Lab、评估与作品化

### 11.1 阶段定位

把已完成的 Agent RPG 变成可观察、可比较、可量化、可部署和可面试讲解的完整作品。

### 11.2 技术交付

- Agent Lab 信息架构：Run Timeline、Decision Inspector、Memory/Retrieval、Belief/Plan、World Causality、Relationship/Knowledge Flow。
- Replay/Evaluation Harness：固定 Seed/Snapshot/Provider 配置重放场景，不回写正式世界。
- 模式对比：普通 deterministic、LLM without memory、目标 Memory/Reflection/Planning Runtime。
- 场景评估：记忆检索、权限泄漏、角色一致、目标完成、计划抖动、非法动作、循环、剧情可达性、降级和恢复。
- 指标：retrieval precision/recall、source validity、invalid-action rate、goal completion、plan churn、leakage、fallback、P50/P95 latency、Token/成本。
- Prompt/Provider Versioning：记录能力、模型、Prompt 版本、Schema 有效率和失败原因；不保存或公开密钥与隐藏思维链。
- 部署与运维：Docker/环境配置、健康检查、迁移/备份、演示数据初始化、日志和故障手册。
- 作品材料：架构图、核心时序、演示脚本、关键指标、技术难点、权衡、简历描述和面试问答。

### 11.3 玩家和演示效果

- RPG 页面保持故事和操作优先，不被工程调试信息淹没。
- Agent Lab 可从一次行为追到 Observation、Memory、Reflection、Goal、Plan、Proposal、Validation、Action 和 Event。
- 可选择同一场景对比普通与 LLM 结果，并展示成本、延迟和质量指标。
- 提供稳定的五至十分钟作品演示流程和失败降级演示。

### 11.4 验收边界

- 回放不会修改正式 World；相同 Fake Provider 输入可复现。
- 权限、事实、状态一致性等硬规则由确定性测试判定，不交给 LLM-as-judge。
- LLM-as-judge 只评估自然度、角色一致性和计划质量等软指标，并保留样本与版本。
- 公共 Agent Lab 默认只读并脱敏；触发付费运行、修改模型或 Fork Snapshot 需要本地/管理员边界。
- 从干净环境可按文档完成部署、初始化、演示和核心验收。

### 11.5 作品完成定义

- 有一条稳定普通模式演示和一条稳定 LLM Agent 演示。
- 有真实 pgvector、异步 Runtime 和多智能体章节证据。
- 有自动化 Eval 报告与至少一组前后对比指标。
- 有清晰的系统边界、失败案例和已知限制，不夸大自主性。
- 面试中能够解释为什么 LLM 不能直接写状态、如何防止幻觉记忆、如何处理并发/幂等、如何评估 Agent，以及 RPG 为什么不是简单聊天壳。

## 12. 数据与 API 演进原则

路线图只约束方向，确切表结构和 endpoint 由阶段 Spec 决定。

- Stage 2 预计新增 Observation、Memory、Reflection/Belief 相关持久化和安全只读投影。
- Stage 3 预计新增 Goal、Plan、Plan Step、Provider Call 元数据和推进模式字段。
- Stage 4 预计扩展 AgentRun 生命周期、幂等/Outbox/Checkpoint/Progress/Usage，并增加异步提交与恢复读取能力。
- Stage 5 预计新增 Relationship、Conversation/Claim/Knowledge Flow 和通用化 Quest/Story 数据。
- Stage 6 预计新增 Evaluation Scenario/Run/Metric、Replay/Fork 引用和 Agent Lab 查询投影。

演进时必须遵守：

1. 当前同步确定性玩法不因新增 LLM 路径失效。
2. 已发布字段不静默改变语义；破坏性变化先在 Spec 中明确迁移与兼容策略。
3. 新表必须有 owner/world/source/version 等必要边界，避免跨 NPC、跨世界或跨时间线串数据。
4. 私有认知数据和公共 RPG DTO 分离，ORM 不直接作为 API 响应。
5. PostgreSQL 是完整部署目标；SQLite 至少保留本地、快速测试和确定性 fallback 所需能力。

## 13. 主要风险与控制

| 风险 | 控制方式 |
| --- | --- |
| Agent 全知或幻觉记忆 | 感知权限、来源 ID、Claim/Fact 分离、跨所有权拒绝测试 |
| LLM 绕过规则 | 类型化输出、Registry 校验、统一执行链、事务与 CAS |
| Memory 越积越多 | 去重、重要度、衰减、归档、摘要和 Token 预算 |
| 计划循环或频繁改目标 | 冷却、切换成本、失败上限、重复动作检测和 Eval |
| 多 Agent 对话失控 | 预约、轮数、传播层数、预算和终止条件 |
| 异步重复执行 | Idempotency、唯一约束、Outbox、单世界运行锁和 stale 拒绝 |
| AI 功能压过 RPG | 每阶段必须有玩家效果；RPG 与 Agent Lab 分路由 |
| 技术栈过度设计 | 每阶段先证明需求，再选择最小能满足恢复/扩展要求的框架 |
| 演示依赖外部模型 | Fake/Mock、普通模式、缓存演示场景和明确 fallback |
| 简历只讲概念无指标 | Stage 6 输出可复现实验、性能/成本/质量指标和失败案例 |

## 14. 阶段实施与 Review 规则

每个阶段开始时重新检查当前 HEAD、工作树、测试基线和上一阶段 Public Contract，不把本路线图当成已实现事实。

阶段级 Spec 至少回答：

- 玩家最终看到什么变化？
- Agent 数据从哪里来，谁有权读取和写入？
- LLM 与确定性代码的边界在哪里？
- Schema/API 如何演进和兼容？
- 失败、重试、降级、成本和安全边界是什么？
- 如何用自动化测试和真实 Smoke 证明完成？
- 本阶段明确不做哪些后续能力？

阶段级 Plan 应尽量拆成少量垂直 Task，优先顺序为：契约与数据基础 → 领域/Agent 内核 → API/运行集成 → RPG 可见切片与真实验收。具体任务数由阶段复杂度决定，不为了形式拆碎。

编码继续采用测试驱动和 Subagent-Driven Review 流程。助手不执行 `git add`、`git commit`、`git reset`、`git checkout` 或 `git switch`；用户在每个 Review Gate 后手动提交。

## 15. Stage 2 新聊天交接入口

用户 Review 并提交本路线图后，新聊天只启动 Stage 2 的架构讨论：

1. 读取本路线图、当前 Agent Runtime 上位设计、工程架构、API、Schema 和开发环境文档。
2. 检查当前提交和实现，不依赖旧聊天中未写入文档的信息。
3. 阅读 `D:/pythonproject/generative_agent` 中与 observation、memory stream、retrieval、reflection 直接相关的实现。
4. 对比 2–3 种适合 Aleria 的 Stage 2 方案，明确 SQLite/PostgreSQL、Embedding、权限和 fallback 取舍。
5. 一次确认一个影响架构的问题；未获批准前不写代码。
6. 讨论通过后创建独立中文 Stage 2 Spec；用户 Review 后再创建逐文件 Plan。

Stage 2 新聊天不得提前实现 Goal、Plan、LLM Action、异步 Runtime、Social Runtime、Forest Embers 或 Agent Lab。

## 16. 路线图完成定义

本路线图完成仅表示阶段 2–6 的顺序与边界获得共同理解，不表示这些能力已经实现。

路线图可提交的条件是：

- 阶段 2–6 均包含目标、玩家效果、技术交付、验收边界、非目标和作品价值。
- 与当前 Foundation 的权威状态、统一 Proposal/Registry 和同步 API 事实不冲突。
- 普通推进、LLM 推进、异步 Runtime 和 Agent Lab 的职责边界清晰。
- Stanford 思想已映射为适合 RPG、事务、权限和可测试性的 Aleria 方案。
- 没有阶段 2 的逐文件实现计划、未决定框架的伪结论或任何代码变更。
- 用户 Review 后手动提交，并在干净新聊天中开始 Stage 2。
