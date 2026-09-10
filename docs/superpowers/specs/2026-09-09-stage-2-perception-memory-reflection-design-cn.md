# Aleria AI Town Stage 2：感知、记忆与反思设计

**日期：** 2026-09-09

**状态：** 待用户 Review

**当前基线：** `ba935ae`（Agent Runtime Foundation 与阶段 2–6 路线图已由用户提交）

**阶段定位：** 权限与来源感知的 Agent Memory RAG；不实现 Goal、Plan 或 LLM Action

## 1. 文档目的

本文定义 Aleria AI Town 第二阶段“感知、记忆与反思”的玩家体验、领域边界、数据来源、持久化模型、检索语义、Reflection/Belief 安全边界、API 演进、失败降级和验收标准。

本文是阶段级 Spec，不是逐文件实施 Plan。用户 Review 并批准本文后，才编写详细实施 Plan；未批准前不进入编码。

本文以下列文档和当前代码为基线：

1. `docs/superpowers/roadmaps/2026-09-09-ai-native-agent-rpg-stages-2-to-6-cn.md`
2. `docs/superpowers/specs/2026-09-04-ai-native-agent-rpg-runtime-design.md`
3. `docs/superpowers/specs/2026-09-08-agent-runtime-foundation-closeout-design-cn.md`
4. `docs/05_Engineering_Architecture.md`
5. `docs/06_API_Contract.md`
6. `docs/07_Database_Schema.md`
7. `docs/14_Development_Environment.md`

发生冲突时，已实现的 Public Contract 和 Foundation 不变量优先；本文只能以明确、增量和兼容的方式扩展它们。

## 2. 当前事实基线

当前 Aleria 是 Vue 3/Pinia + Phaser 3.90.0 + FastAPI + SQLAlchemy 的模块化单体。后端拥有世界事实，SQLite 用于本地轻量模式和快速测试，PostgreSQL 17 + pgvector 0.8.6 用于完整部署与真实集成验收。

现有同步确定性 Runtime 为：

```text
Immutable World Snapshot
→ deterministic ActionProposal
→ Action Registry validation
→ deterministic conflict resolution
→ atomic World / Run / Proposal / Action / Event / Trace commit
```

当前关键事实：

- `world_version`、`clock_tick`、`event_sequence` 已分离。
- `POST /api/world/tick` 同步返回 HTTP 200。
- 所有 NPC 在一次推进中消费同一不可变 Snapshot。
- Action Registry 当前只注册 `move/rest/work/eat/talk/wait`。
- Quest 与实际 Travel 会更新权威世界并产生 Domain Event。
- Chat 独立保存 Conversation/Message，不更新世界版本、时间、Action、Event 或 Quest。
- Run Graph 持久化具有严格结构与效果复算校验。
- PostgreSQL 已启用 vector 扩展，但当前没有 Memory 表或 vector ORM 列。

Stage 2 不改变上述事实。

## 3. 阶段目标

Stage 2 让 NPC 从“仅根据当前数值执行确定性规则”升级为“能够基于自己真正经历过的历史理解当前情境”。

阶段完成后必须具备：

1. 从已提交的 World Event、Quest/Travel Event 和玩家对话派生 NPC-specific Observation，并从版本化 authored knowledge 建立有来源的初始 Memory。
2. 不同 NPC 根据位置、参与、可见范围、职业渠道、秘密权限和注意力获得不同 Observation。
3. 将 Observation 编码为具有完整来源与时间的长期 Memory。
4. 使用 PostgreSQL/pgvector 或 SQLite 确定性实现执行权限优先的 Hybrid Retrieval。
5. 将检索到的长期记忆加入现有 NPC Chat 上下文，使 NPC 能在短期聊天窗口之外回忆玩家经历。
6. 由累计重要度或注册关键事件触发 Reflection，生成必须引用证据 Memory ID 的结构化 Draft。
7. 使用最小 Belief 模型保留当前观点、置信度、支持/反对证据及 disputed/superseded 历史。
8. 在 RPG NPC 面板提供最小、安全、只读的“相关记忆”投影。
9. Embedding 或 Reflection 失败时，World、Quest、Chat 和现有 Agent Run Graph 仍保持可用与一致。

## 4. 玩家体验与演示切片

本阶段的主要玩家可见闭环是 Grey 的跨轮次记忆：

```text
玩家与 Grey 对话并提供一条线索
→ 玩家话语作为 Claim 来源提交
→ Grey 获得私有 Observation
→ 形成 conversation Memory
→ 当前回复完成；该新 Memory 不反向影响当前回复
→ 后续对话按新消息检索长期 Memory
→ Grey 引用或合理回应这段既有经历
```

该闭环必须同时证明：

- 原消息已经超出有界短期 Conversation History 后仍能召回。
- 服务重启后可从持久化 Memory 恢复，不依赖进程内状态。

玩家还可在 NPC 详情区域展开“相关记忆”面板，看到少量经过脱敏的公共来源和来源说明。该面板不是 Agent Lab，不展示秘密、原始 Prompt、Embedding、隐藏 Reflection、完整检索分数或模型推理。

Stage 2 只精调 Grey 的演示内容，但 Schema、Repository、权限和核心算法从第一天支持 Ryan、Shir、Grey 三名 NPC。

## 5. 核心不变量

### 5.1 权威状态不变量

1. World Event 和已提交的 Conversation Message 是事实来源记录；Observation、Memory、Reflection 和 Belief 不是 World Fact。
2. LLM 不参与“谁能感知什么”的权限判断。
3. LLM 输出不能创建或修改 World、Quest、NPC State、Action、Event 或现有 Agent Run Graph。
4. 所有未来行动仍只能通过类型化 `ActionProposal`、Action Registry、冲突处理和权威事务提交；Stage 2 不生成 LLM ActionProposal。
5. 新增认知数据不得改变 `world_version`、`clock_tick` 或 `event_sequence`。

### 5.2 来源与时间不变量

1. 每条 Observation 必须引用一个真实、已提交且与当前 World 匹配的来源。
2. 每条 episodic/conversation Memory 必须引用一个属于同一 NPC 的 Observation。
3. 每条 reflection Memory 必须通过关系表引用至少一个真实 evidence Memory。
4. Authored knowledge 必须引用版本化的 authored source，而不是无来源文本。
5. 每条记录区分来源发生时间与认知记录创建时间。
6. 玩家陈述记录为带 Speaker 的 Claim，不因进入 Memory 或被 LLM 重述而升级为世界事实。

### 5.3 权限不变量

1. 所有 Memory 查询必须显式携带 `world_id + owner_npc_id + RetrievalScope`。
2. 所有权、世界、时间线、生命周期和秘密权限过滤必须在语义相似度计算之前执行。
3. 任意跨 NPC、跨 World、跨时间线或越权 evidence ID 均必须被确定性拒绝。
4. Public API 不能因 ID、总数、错误信息或排序差异泄露不可见 Memory 的存在或内容。

## 6. 总体架构

采用已批准的“权威来源后的幂等认知投影”方案：

```text
Authoritative transaction
  ├─ World / Quest / Travel → Event
  └─ Chat → Conversation Turn
                 │ commit first
                 ▼
        Cognition Projection Service
                 ▼
       Perception Policy Registry
                 ▼
     NPC-specific immutable Observation
                 ▼
        Memory Encoder + Repository
           ├─ durable Memory first
           └─ optional Embedding state
                 ▼
          Hybrid Memory Retriever
                 ▼
       Reflection Provider + Validator
                 ▼
       Reflection Memory / Belief version
```

认知投影与权威来源使用独立事务。来源事务一旦成功，认知投影失败不能回滚来源，也不能使原有成功 API 变为失败。投影通过唯一来源键和持久化 Checkpoint 自动补偿。

Stage 2 不引入消息队列、Outbox、后台 Worker 或分布式调度；这些属于 Stage 4。

## 7. 来源模型与 Event 感知元数据

### 7.1 支持的来源

Stage 2 支持三类来源：

| 来源 | 权威含义 | 可生成的 Memory |
| --- | --- | --- |
| `event` | 已提交的 RPG Domain Event | episodic |
| `conversation_turn` | 已原子提交的玩家/NPC 完整对话轮 | conversation |
| `authored_knowledge` | 随 Seed 版本管理的角色初始知识 | knowledge |

Conversation 不被转换为 World Event，不增加 `event_sequence`。玩家输入始终保留为“玩家向某 NPC 声称的内容”。

为使 `conversation_turn` 在延迟补偿时仍有准确来源，新提交的 User/Assistant Message 必须保存同一个 UUID `turn_id`，以及该 Turn 发生时读取到的 `world_version` 和 `world_time`。现有 `clock_tick` 和 UTC `created_at` 继续保留。Chat 不因记录这些值而增加世界版本。

迁移前的历史 Message 没有可靠的 `world_version`。迁移不得以当前 World 版本、`clock_tick` 或消息顺序伪造该值；这类 legacy Message 继续用于原有短期 Chat History，但不自动转换为 Stage 2 长期 Memory。新提交的完整 Turn 必须具有非空、可验证且两条消息一致的来源键和发生版本。

Stage 2 固定使用以下分类值：

- `source_kind`：`event/conversation_turn/authored_knowledge`。
- `memory_type`：`episodic/conversation/reflection/knowledge`。
- `perception_mode`：`participant/witnessed/professional_channel/direct_dialogue`。
- `secrecy`：`public/private/secret`。
- `disclosure_scope`：`public/player_dialogue/internal_only`。
- 认知记录生命周期：`active/archived/disputed/superseded`。

新增分类值必须先修改阶段级 Spec 或后续版本化契约，不能由 Provider 自由发明。

### 7.2 新 Event 的最小感知元数据

为避免从描述文本或当前状态反推历史，新产生的 Event 需要以兼容方式补充内部感知元数据：

- 发生地点 `location_id`，无法定义时为 null。
- `perception_scope`：`world_public/location/participants/professional/private`。
- 直接参与的 NPC ID 集合。
- 可接收的职业渠道集合。
- `attention_priority` 与是否为注册关键事件。

现有 Event Public DTO 不因这些内部字段而改变。迁移前的历史 Event 若缺少足够信息，不猜测发生地点、参与者或秘密受众，也不自动生成新的私有记忆。Demo Reset 和新写入链必须产生完整元数据。

### 7.3 Perception Policy Registry

Perception Policy Registry 以 `event_type` 和结构化 payload 为输入，输出零到多条 `ObservationDraft`。每个 Policy 必须定义：

- 哪些 NPC 是参与者。
- 哪些 NPC 可按地点或职业渠道观察。
- 来源的哪些字段可以进入 Observation。
- Observation 的感知方式、公开范围、确定性重要度和相关实体。
- 去重键与 Policy 版本。

同一 Event 可对不同 NPC 产生不同摘要，也可对某 NPC 不产生任何 Observation。Registry 只消费结构化字段，不能从自由文本描述推断权限。

### 7.4 注意力

Stage 2 不模拟逐格视觉半径。Aleria 使用语义地点和有限事件，因此注意力采用确定性预算：

1. 参与者与注册关键事件优先。
2. 同地点事件按 `attention_priority`、`event_sequence` 排序。
3. 职业渠道事件在明确注册时进入候选。
4. 单个 catch-up 批次和单 NPC 单来源窗口均有上限。

被注意力预算排除表示该 NPC 没有形成 Observation，不应偷偷保存内容后只在检索时隐藏。

## 8. 持久化概念模型

确切 SQL 类型、约束名和索引在实施 Plan 中逐文件列出，但本文锁定以下表和语义。

### 8.1 `agent_cognition_states`

每个 `world_id + owner_npc_id` 一行，保存：

- 已处理的 Event Sequence。
- 已处理的 Conversation Message/Turn 游标。
- 自上次成功 Reflection 后累计的重要度。
- 最近 Reflection 来源游标、证据指纹和尝试状态。
- 创建与更新时间。

Checkpoint 与对应投影结果在同一事务推进。投影崩溃后重复处理同一来源必须幂等。

### 8.2 `observations`

Observation 使用稳定 UUID，并至少包含：

- `world_id`、`owner_npc_id`。
- `source_kind` 及对应的真实来源引用。
- Event 来源引用 `source_event_id`；Conversation 来源同时引用稳定 Turn 键及真实 User/Assistant Message ID；Authored Knowledge 不伪装为 Conversation 或 Event。
- `source_key`、`policy_version` 和唯一约束。
- 发生时的 `world_version`、`clock_tick`、world time 和来源创建时间。
- Observation 创建时间。
- `perception_mode`、结构化 facts、相关实体和安全摘要。
- `secrecy`、`disclosure_scope`、生命周期状态。

Observation 是 append-only 来源投影。更正通过新来源和后续 Memory/Belief 状态表达，不原地改写其历史内容。

### 8.3 `memories`

Memory 使用稳定 UUID，并至少包含：

- `world_id`、`owner_npc_id`、`memory_type`。
- `source_observation_id` 或版本化 authored source。
- 内容、安全摘要、规范化内容哈希和相关实体。
- 发生与创建的 world version、clock tick 和 UTC 时间。
- `importance`、`confidence`、`emotional_valence`。
- `secrecy`、`disclosure_scope`。
- `active/archived/disputed/superseded` 生命周期状态。
- Embedding provider/model/version、维度、内容哈希和 `ready/failed/unavailable` 状态。
- nullable Embedding 数据。
- `last_accessed_at` 和 `access_count`，仅作观测与维护，不参与 recency 主分数。

Routine Event 的重要度由确定性 Registry 给出。Stage 2 不为每条 Memory 调用 LLM 评分。

`importance` 与 `confidence` 均限制在 0–1，`emotional_valence` 限制在 -1–1。非法范围不得进入持久化层。

Embedding 在 Memory 持久化之后生成；Embedding 失败时 Memory 仍是有效的 lexical/recent 候选。失败或不兼容的 Embedding 可在后续内部 enrichment 尝试中重建，但 Stage 2 不暴露公共重建 API。

### 8.4 `memory_evidence`

该表保存 derived Memory 与 evidence Memory 的多对多关系，至少包含：

- `derived_memory_id`。
- `evidence_memory_id`。
- 证据顺序。

两端必须属于相同 World 和 owner。Reflection Memory 至少有一条 evidence；循环引用被拒绝。

### 8.5 `beliefs`

Belief 是 NPC 的私有观点而不是事实，至少包含：

- `world_id`、`owner_npc_id`。
- statement、安全摘要和置信度。
- `active/disputed/superseded` 状态。
- nullable `supersedes_belief_id`。
- 来源 reflection Memory。
- 创建时的 world version、clock tick 和 UTC 时间。

Belief 采用追加版本。新证据更新观点时创建新行并链接旧行，不覆盖或删除历史。

### 8.6 `belief_evidence`

保存 Belief 与 Memory 的 `supporting/contradicting` 关系。所有引用必须属于相同 World 和 owner。

Stage 2 不建立通用实体图、RDF、Neo4j 或 GraphRAG。上述来源与证据关系为 Stage 5 的 Belief/Claim Knowledge Provenance Graph 提供关系型基础。

## 9. Embedding Provider 与双数据库策略

### 9.1 Provider 边界

Embedding 使用独立 `EmbeddingProvider`，不复用 ChatProvider 的业务接口。Provider 输入是经过规范化和长度限制的 Memory 文本，输出必须包含：

- 定长有限浮点向量。
- provider、model、version 和 dimensions。
- 输入内容哈希。

维度或非有限数值不匹配时拒绝保存该 Embedding，但不删除 Memory。

### 9.2 默认与真实模式

- 快速 CI 与默认无 Key 模式使用确定性 Fake Embedding。
- SQLite 将向量保存为 JSON 兼容表示，并在权限过滤后于 Python 中计算余弦相似度。
- PostgreSQL 使用无 ANN 索引的 pgvector `vector` 类型和距离运算符执行语义候选查询。
- 真实 OpenAI-compatible Embedding Provider 通过独立环境变量显式启用。
- Live Provider 验收为手动或发布 Smoke；它不成为普通模式、快速 CI 或 Demo 启动的前置条件。

Stage 2 允许不同 Provider 具有不同维度，但一次语义比较只在 provider、model、version 和 dimensions 完全一致的 Embedding Space 内进行。切换 Embedding 模型后，尚未重建向量的旧 Memory 只参加 lexical/recent 候选，不执行跨维度比较。

Stage 2 数据规模只有三名 NPC 和有限记忆，不增加独立向量数据库，也不创建复杂 ANN 索引。若后续基准证明需要，再增量添加索引。

## 10. Hybrid Retrieval

### 10.1 请求契约

内部 Retrieval Request 至少包含：

- `world_id`、`owner_npc_id`。
- 当前 `world_version`、`clock_tick`。
- 查询文本与用途。
- `RetrievalScope`。
- 允许的 Memory 类型、结果上限和上下文预算。

Stage 2 定义两个主要 Scope：

- `player_dialogue`：只允许进入玩家可接收回复上下文的记忆；排除 NPC secret/private-only 内容。
- `internal_reflection`：允许当前 NPC 使用自己的私有认知，但仍禁止跨 NPC、跨 World 和未来时间线内容。

### 10.2 检索顺序

检索必须按以下顺序执行：

1. 过滤 World、owner、发生版本/时间、生命周期、Memory 类型和 disclosure 权限。
2. 从允许集合分别取得语义、关键词、近期和高重要度候选。
3. 合并候选并按 Memory ID 去重。
4. 对 semantic relevance、lexical relevance、occurred-time recency、importance 和 confidence 归一化评分。
5. 使用固定权重和稳定 Memory ID tie-break 排序。
6. 在固定记录数和确定性文本预算内裁剪。
7. 返回 evidence ID、来源和评分分量供内部验证与测试使用。

Stage 2 不计算 Goal relevance 或 Relationship relevance；对应权重固定为零并分别留给 Stage 3、Stage 5。

默认 hybrid 分数为：

```text
0.40 * semantic relevance
+ 0.20 * lexical relevance
+ 0.20 * recency
+ 0.15 * importance
+ 0.05 * confidence
```

默认 lexical fallback 分数为：

```text
0.45 * lexical relevance
+ 0.25 * recency
+ 0.20 * importance
+ 0.10 * confidence
```

Recency 默认按 `0.95 ^ max(0, current_clock_tick - occurred_clock_tick)` 计算。`active` Memory 的状态因子为 1，`disputed` 为 0.85；`superseded` 默认不进入普通 Chat，Reflection 可为审查冲突证据显式请求。权重可通过受控 Backend 配置调整，但每次检索必须记录版本，测试固定使用上述默认值。

Chat 默认最多选择六条 Memory，并使用 1600 个 Unicode 字符的确定性预算；Reflection 默认最多选择十二条，并使用 4000 字符预算。字符预算用于跨 Provider、跨 tokenizer 的稳定测试，不声称等同于实际 Token 数；Provider 层仍执行自己的最终输入长度上限。

### 10.3 Fallback

若查询 Embedding 生成失败、Memory Embedding 缺失或 pgvector 查询不可用：

- 使用关键词匹配、发生时间、重要度和置信度完成确定性排序。
- 返回 `retrieval_mode=lexical_fallback` 与安全错误代码。
- Chat 继续生成；若 Primary Chat Provider 也失败，沿用现有 Mock fallback。

Fallback 不扩大候选权限范围。

## 11. Chat 集成

现有 Chat API 请求和响应保持不变。ChatContext 的内部组成扩展为：

```text
NPC/World/Player/Quest authoritative context
+ bounded recent conversation history
+ permission-filtered long-term memories
+ current player message
→ existing ChatProvider
```

规则如下：

1. 在生成回复前，只 catch-up 到当前请求开始前已提交的来源。
2. 当前玩家消息不在当前回复前写入 Memory。
3. Provider 成功并原子保存完整 Turn 后，再投影该 Turn。
4. 当前 Turn 新形成的 Memory 最早影响下一轮回复。
5. 同一活跃 Conversation 的近期消息若已直接进入短期 History，对应长期 Memory 不重复加入 Prompt。
6. 每条 Memory Context 带内部来源标签，Prompt 明确区分 `world fact`、`observed event`、`player claim`、`reflection/belief`。
7. `player_dialogue` Scope 在进入模型前排除不允许向玩家披露的私密内容；Stage 2 不依赖模型自行保密。
8. catch-up、Embedding 或长期 Retrieval 失败时，Chat 使用现有权威上下文和短期 History 继续执行，并记录 `lexical_fallback` 或 `memory_unavailable` 安全状态。

Chat 仍不能修改 World、Quest、NPC State、Action 或 Event。

## 12. Reflection 与 Belief

### 12.1 触发条件

Reflection 不按每 Tick 固定运行。默认触发条件为：

- 自上次成功 Reflection 后，新 Memory 的累计 importance 达到配置阈值；或
- 新来源被 Perception Policy 标记为注册关键事件。

默认累计 importance 阈值为 2.0，并要求至少三条新 Memory。注册关键事件可以绕过数量和累计阈值触发候选生成，但 Provider 输入仍可检索该 NPC 的既有证据。相同 evidence ID 集合的规范化指纹不得重复产生 Reflection。

失败尝试保留安全状态和有限重试信息。同一 evidence 指纹最多自动重试一次；再次失败后必须等到至少一条新 Memory 改变 evidence 指纹，不能在每次普通读取时无限重试。

### 12.2 Provider 输出

独立 `ReflectionProvider` 返回结构化 `ReflectionDraft`，至少包含：

- insight 文本。
- confidence。
- evidence memory IDs。
- 可选的 belief draft。
- provider/model/prompt version 元数据。

快速 CI 使用确定性 Fake ReflectionProvider；真实 OpenAI-compatible Provider 显式启用。

### 12.3 确定性验证

保存前必须验证：

- evidence 非空且 ID 均存在。
- evidence 全部属于当前 World 和 owner。
- evidence 位于本次 Provider 可见候选集合内。
- evidence 未来自未来版本或无效生命周期。
- confidence 和文本长度合法。
- belief revision 只能引用 Provider 输入中提供的当前 Belief ID。

验证通过后只写 reflection Memory、evidence edge 和可选 Belief version。任何 Draft 都不能成为 Event、Action、Quest Fact 或 Observation。

### 12.4 失败语义

Reflection 超时、无效 JSON、虚构 evidence、跨 owner 引用或数据库失败时：

- 拒绝该 Draft。
- 不产生半条 Reflection 或 Belief。
- 不回滚来源 Observation/Memory。
- 不修改 World、Quest、NPC State 或 Agent Run Graph。
- Chat 与 deterministic Tick 继续可用。

## 13. 认知投影一致性与补偿

### 13.1 正常路径

1. 现有 Repository 完成 World/Quest/Travel/Chat 来源事务。
2. Application Service 在来源提交后调用 Cognition Projection Service。
3. Projector 读取从 Checkpoint 到本次来源上界的有界批次。
4. Perception Registry 生成 ObservationDraft。
5. Observation、Memory 与 Checkpoint 在一个认知事务内提交；这是必须成功或整体回滚的核心投影。
6. Embedding 和满足条件的 Reflection 作为可失败 enrichment 执行，并使用独立的短事务更新状态。

### 13.2 失败与恢复

- 来源成功、核心投影失败：原来源 API 仍返回其原有成功结果，记录安全错误，Checkpoint 不越过失败批次。
- 核心投影成功、Embedding/Reflection 失败：Checkpoint 正常推进，Memory 保持可检索，并记录 `failed/unavailable` enrichment 状态供后续有界重试。
- 重复调用：依赖 `(world, owner, source_key, policy_version)` 唯一约束返回已有投影或安全跳过。
- 部分 NPC 成功：每个 NPC 的 Checkpoint 独立；失败 NPC 后续补偿，不回滚其他 NPC 或世界。
- 服务重启：下次 Chat、Tick 后处理或 Memory Explanation 读取执行有界 catch-up。
- 长期积压：单次只处理配置上限，避免普通请求无限阻塞；未处理部分留给后续请求。

Stage 2 不承诺请求外自动执行。真正的异步投递、Outbox、Worker 重试和进度恢复属于 Stage 4。

每个来源 API 的 post-commit cognition 使用有界批次、Provider 超时和总耗时预算。预算耗尽立即停止 enrichment 并返回原来源结果；不得为了等待 Embedding 或 Reflection 无限制延迟现有 Tick、Quest、Travel 或 Chat。

## 14. Public API 演进

### 14.1 保持不变

以下现有契约和语义不变：

- `GET /api/world`
- `POST /api/world/tick` 同步 HTTP 200
- `GET /api/agent-runs/{run_id}`
- `GET /api/npcs/{npc_id}`
- `POST /api/npcs/{npc_id}/chat`
- Player Travel、Quest Interaction、Health 与 Demo Reset
- 当前 Action/Event/Trace Public DTO

### 14.2 新只读接口

新增：

```text
GET /api/npcs/{npc_id}/memory-explanations
```

成功响应继续使用公共 envelope：

```json
{
  "success": true,
  "data": {
    "npc_id": "grey",
    "retrieval_mode": "hybrid",
    "fallback_used": false,
    "memories": [
      {
        "id": "opaque-memory-uuid",
        "type": "episodic",
        "summary": "Grey 记得在低语森林附近发生过一件与当前线索有关的事。",
        "occurred_clock_tick": 2,
        "source": {
          "kind": "world_event",
          "label": "亲历的世界事件"
        },
        "reason_text": "该记忆较新，并与当前公开任务情境相关。"
      }
    ]
  },
  "message": "ok"
}
```

接口规则：

- 固定返回最多五条，不提供任意 query、owner 或 secrecy 参数。
- 查询由 Backend 使用当前公共 World/Quest 情境构造。
- 只返回 `public` 或明确可匿名公开的安全摘要。
- 不返回原始玩家聊天正文、秘密 Memory、hidden reflection、Belief 全文、Embedding、完整分数、Prompt 或 Provider 错误。
- 对话来源最多公开“该 NPC 记得与你有过相关交谈”等非原文说明；跨会话真实召回通过 Chat 行为证明，不通过匿名 GET 泄露聊天历史。
- 不可见内容不能通过总数、占位符或不同错误泄露。
- NPC 不存在返回现有风格 404；认知读取不可用返回安全 503。

本阶段不新增 Memory 写 API、Reflection 触发 API、任意向量搜索 API 或 Agent Lab 调试参数。

## 15. 前端演进

现有 NPC 详情面板增加默认折叠的“相关记忆”区域：

- 选中 NPC 时调用新的只读接口。
- 展示最多五条安全摘要、来源标签和游戏时间。
- 明确区分“亲历事件”“听到的说法”“稳定知识”，不标记为客观真相。
- 空状态、加载状态和 fallback 状态均有简短说明。
- 接口失败不影响 NPC Detail、Chat、地图或世界推进。
- 不提供模型选择、强制 Reflection、原始向量、内部信念图或完整 Trace。

该区域是 RPG 可见反馈，不是 Stage 6 Agent Lab。

## 16. Demo Reset、Seed 与生命周期

### 16.1 Seed

Authored knowledge 使用版本化结构化 Seed，包含 owner、来源版本、内容、秘密级别和发生/创建基准。角色 Prompt 不能被当作无版本 Memory Source。

初始知识只加入支撑 Grey 演示和三 NPC 知识隔离所需的最小内容，不提前写入 Forest Embers 的完整秘密或 Stage 5 传播关系。

### 16.2 Reset

`POST /api/demo/reset` 继续是显式破坏性 Demo 操作，并在同一目标 World 范围内清理新增的 Observation、Memory、Evidence、Belief 和 Cognition State，再重新写入版本化 authored knowledge。其他 World 不受影响。

普通启动、Migration 和 `ensure_demo_world` 不重置认知历史。

### 16.3 生命周期

- Memory 默认 append-only。
- 重复低价值内容通过来源幂等与内容去重控制。
- 低价值或过期内容可标记 archived，不物理删除。
- disputed/superseded 内容保留供重放、冲突检索和审计。
- Stage 2 不实现自动摘要替换或大规模压缩任务。

## 17. 安全与隐私

1. 玩家文本作为不可信数据进入 conversation Observation，并在 Prompt 中与系统指令明确隔离。
2. Player Claim 不得修改权限、Source ID、Memory Type、Belief 状态或 RetrievalScope。
3. 检索前执行权限过滤；不得先向量召回秘密内容再在应用层删除。
4. Public DTO 由专用投影构造，ORM 记录不能直接序列化返回。
5. Provider 输入只包含当前能力所需的最小内容。
6. 日志、错误、测试快照和 Trace 不保存密钥、Authorization Header 或未脱敏的秘密内容。
7. 匿名单玩家 Demo 没有账号级身份，因此新的公共 Memory 接口不返回原始聊天正文。
8. `player_dialogue` RetrievalScope 不向 ChatProvider 提供 private-only/secret Memory；更细粒度的选择性披露验证留给 Stage 5。

## 18. 测试策略

### 18.1 确定性单元测试

- 每种 Event Policy 的参与者、地点、职业渠道、秘密与注意力矩阵。
- 同一 Event 对 Grey/Ryan/Shir 产生不同 Observation 集合。
- Conversation Turn 只投影给目标 NPC。
- 玩家陈述保持 Claim 类型和 Speaker 来源。
- 重要度、置信度、去重键和 source policy version。
- Reflection threshold、证据指纹和重复触发抑制。
- Belief append-only revision、supporting/contradicting evidence。

### 18.2 Repository 与迁移测试

- 空 SQLite 从零升级到新 head。
- 当前 `0003` SQLite 原地升级并保留所有 Foundation 数据。
- 已升级数据库重复运行幂等。
- 所有 FK、CHECK、UNIQUE、索引和 reset 顺序正确。
- Observation/Memory 跨 owner、跨 World 和错误来源写入被拒绝。
- 认知事务失败不改变来源和 Checkpoint。
- Demo Reset 只清理目标 World。

### 18.3 Retrieval 测试

固定 Memory 集合必须覆盖：

- relevant、irrelevant、recent、important、low-confidence、disputed、secret 和 cross-owner 候选。
- 过滤发生在 semantic ranking 之前。
- SQLite Fake Embedding 排序完全可重复。
- PostgreSQL/pgvector 对同一 fixture 返回满足预期集合与稳定 tie-break 的结果。
- Embedding 不可用时 lexical fallback 仍返回合法、有来源且不越权的结果。
- 结果数、文本预算、去重和相同活跃对话 History 排除规则。

### 18.4 Reflection 测试

- 合法 Draft 生成 reflection Memory 和 evidence edge。
- 空 evidence、虚构 ID、跨 NPC、跨 World、未来时间线和未提供候选被拒绝。
- Provider 超时、无效输出、数据库异常均不产生半条 Reflection/Belief。
- Reflection 不能新增 Event、Action、Quest Transition 或世界版本。

### 18.5 API 与玩家场景

- 现有 API 契约回归全部保持通过。
- Memory Explanation 只返回安全摘要且固定上限。
- 不可见 Memory 不通过内容、数量、ID 或错误泄露。
- NPC Chat 在短期 History 之外仍能使用允许的长期 Memory。
- 当前消息只影响下一轮，不影响当前回复。
- Memory、Embedding、Reflection 或解释接口失败时，Chat/Tick/Quest/RPG 页面仍可使用。

### 18.6 真实验收

- SQLite 完整 Backend 回归。
- Frontend tests、type-check 和 production build。
- 独立 PostgreSQL 17 + pgvector 0.8.6 Schema 执行真实迁移、Memory 写入、向量查询和 fallback Smoke。
- 可选真实 Embedding/Reflection Provider 手动 Smoke，记录模型和 Prompt 版本；缺少 Key 不得被宣称为已验证，也不得导致自动化失败。

## 19. 完成标准

Stage 2 只有在以下条件全部满足时才完成：

1. World Event、Conversation Turn 和 Authored Knowledge 均可生成有来源、有时间的合法 Memory。
2. 同一来源在不同权限条件下产生不同 NPC Observation，未授权 NPC 无法检索秘密内容。
3. Grey 能在超出短期聊天窗口后引用玩家曾提供的信息，同时保持其 Claim 属性。
4. 固定数据下 Hybrid Retrieval 排序、去重、预算和 evidence 引用可重复。
5. PostgreSQL/pgvector 完成真实写入与检索验收；SQLite 完整可用。
6. Embedding/Reflection 失败时 lexical/recent fallback 和确定性 RPG 继续工作。
7. Reflection 只引用真实、同 owner 的 evidence Memory，不能创造 World Fact。
8. Belief 通过追加版本保留支持、反对、disputed 和 superseded 历史。
9. 新 Public API 和前端区域不泄露聊天原文、秘密 Memory 或隐藏推理。
10. 所有现有 Runtime、Quest、Chat、API 与前端测试保持通过。
11. 独立代码 Review 无未解决 Critical/Important，用户完成 Review 并手动提交。

## 20. 明确非目标

Stage 2 不实现：

- Goal、Goal Arbitration、Plan 或 Plan Step。
- LLM Action Decision 或 LLM `ActionProposal`。
- 普通/LLM 双推进 UI。
- LangGraph；它已批准在 Stage 3 编排认知、规划和结构化行动。
- LangChain；只有出现可证明的集成需求时才局部采用。
- LangGraph Checkpoint、Celery、Redis、Outbox、Worker、SSE、异步 HTTP 202、重试编排或取消。
- NPC-to-NPC Conversation、Relationship、Claim 传播或完整 Knowledge Graph。
- Neo4j、RDF、GraphRAG 或独立向量数据库。
- Agent Lab、Replay/Eval Dashboard 或 LangSmith 集成；LangSmith 作为 Stage 6 可选脱敏观测与评估出口。
- Aleria MCP Server；已批准在 Stage 6 以现有 Public API 的薄适配层实现。
- Forest Embers 分支扩写、新行动类型、战斗、装备、背包、经济、大地图或更多 NPC。

## 21. 后续阶段接口边界

Stage 2 为后续阶段只提供以下稳定能力：

- Stage 3 可读取经过权限过滤的 Memory、Reflection 和当前 Belief，并用 LangGraph 生成 Goal/Plan/ActionProposal；不得绕过 Registry。
- Stage 4 可把 Cognition Projector 与 LangGraph Run 放入持久化异步执行、Outbox、Worker 和恢复体系；Stage 2 Checkpoint 不冒充通用任务队列。
- Stage 5 可扩展 Claim、Relationship 和 Knowledge Provenance Graph，但必须保留 Stage 2 owner/source/evidence 约束。
- Stage 6 可构建 Agent Lab、Eval、LangSmith Exporter 和薄 Aleria MCP Server；外部工具仍只调用 Public API，不直连数据库。

玩家 Prompt 的产品语义已经确定：玩家通过角色内对话提供 Claim、请求或承诺，NPC 在后续 LLM 推进中自主决定是否行动；RPG 页面不提供直接遥控 NPC 的自由指令框。强制 deliberation 和实验控制只属于后续 Agent Lab。

## 22. Review 决策摘要

本阶段已经获得的架构方向确认如下：

1. 采用权威来源提交后的幂等认知投影，不把不稳定认知塞入现有世界原子提交。
2. Stage 2 将长期 Memory Retrieval 接入现有 NPC Chat。
3. 增加最小前端“相关记忆”区域和独立安全只读接口。
4. Stage 2 明确实现 Memory RAG + pgvector，不引入 LangGraph/LangChain。
5. Stage 3 正式采用 LangGraph；Stage 5 形成关系型 Belief/Claim 来源图；Stage 6 接入可选 LangSmith 与薄 Aleria MCP Server。
6. 玩家以角色内对话影响 NPC，不直接遥控 NPC 行动。
