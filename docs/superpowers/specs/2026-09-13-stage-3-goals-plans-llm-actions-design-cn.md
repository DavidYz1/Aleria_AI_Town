# Aleria AI Town Stage 3：目标、计划与受约束 LLM 行动设计

**日期：** 2026-09-13

**状态：** 已批准（用户 Review，2026-09-13）

**事实基线：** HEAD `32a405d`；Review Baseline `B0002-stage2-close-approved`（HEAD `6a25028`）

**阶段定位：** 在保持同步世界推进和单一权威执行链的前提下，为 NPC 增加稳定 Identity/Drives、注册式 Goal、滚动 Plan、确定性仲裁、受约束的 Planning/Action Decision Provider，以及玩家可比较的普通/LLM 双推进模式。

## 1. 文档目的与权威边界

本文定义 Stage 3 的玩家体验、运行模式、Goal/Plan 领域模型、持久化边界、Provider 契约、回退语义、Public API、前端交互与验收标准。

本文是阶段级 Spec，不是实施 Plan。只有用户 Review 并批准本文后，才能编写逐文件 Plan；Roadmap、本文中的实现方向和示例均不授权提前编码。

本文以下列资料和当前实现为基线：

1. `docs/superpowers/roadmaps/2026-09-09-ai-native-agent-rpg-stages-2-to-6-cn.md` 第 8 节
2. `docs/superpowers/specs/2026-09-04-ai-native-agent-rpg-runtime-design.md`
3. `docs/superpowers/specs/2026-09-09-stage-2-perception-memory-reflection-design-cn.md`
4. `docs/ARCHITECTURE.md` 的 Implemented 段
5. `docs/05_Engineering_Architecture.md`
6. `docs/06_API_Contract.md`
7. `docs/07_Database_Schema.md`
8. 当前 `backend/app/` 与 `frontend/src/` 实现

本文对旧总纲中属于 Stage 3 的内容作三项明确收敛：

- Stage 3 **不采用 LangGraph 或 LangChain**。本阶段使用项目内同步、可测试的显式编排；是否采用工作流框架只能由后续 Stage 4 Spec 基于恢复语义重新论证。
- 主 RPG 允许玩家在**普通推进**与 **LLM 推进**之间选择；`FORCE_DELIBERATION`、模型选择和指定 NPC 仍只属于未来 Agent Lab。
- Stage 3 **不新增行动类型**。只使用当前已注册的 `move/rest/work/eat/talk/wait`；旧总纲中的 `investigate/share_information/report` 后置，除非未来独立 Spec 明确授权。

除上述收敛外，Foundation 与 Stage 2 的已实现契约和跨 Stage 不变量继续有效。冲突时以本 Stage Spec 对 Stage 3 范围的明确条款为准。

## 2. 当前事实基线

当前系统已经具备：

- 同步 `POST /api/world/tick`，请求只含 `expected_world_version`，成功返回 HTTP 200。
- 所有 NPC 在一次推进中消费同一不可变 Snapshot。
- 确定性 World Engine、类型化 `ActionProposal`、Action Registry、冲突处理和原子 Run Graph 持久化。
- `world_version`、`clock_tick`、`event_sequence` 三套独立计数器。
- `ProposalSource` 已预留 `deterministic/existing_plan/llm/fallback`，但生产推进当前只产生 `deterministic`。
- `AgentRun.mode` 已存在，但当前持久化固定为 `deterministic`。
- Stage 2 的 NPC-specific Observation/Memory、权限优先 Retrieval、Reflection、Belief 与逐 NPC checkpoint。
- Chat、Embedding、Reflection 三套独立 Provider；PlanningProvider 与 ActionDecisionProvider 不存在。
- `NpcProfile` 只保存 role 与 personality；完整 Drives 不存在。
- 数据库没有 Goal、Goal Evidence、Plan 或 Plan Step。
- 前端世界推进只有一个“推进 1 小时”按钮，没有模式选择或 Goal/Plan 展示。

`docs/ARCHITECTURE.md` Proposed 段和旧总纲中的 Goal/Plan、LangGraph、异步 Run、Agent Lab 等均不是现有接口。本文不会引用或假设它们已经存在。

## 3. 阶段目标

Stage 3 完成后必须具备：

1. 每个 NPC 从版本化 Identity/Drives、权威状态、允许的 Memory/Belief 和 Quest 情境生成有限 Goal 候选。
2. Goal 候选必须映射到注册式 Goal Type；LLM 不能创造 Goal Type、成功条件、权限或允许动作集合。
3. 规则层以固定版本的评分、切换成本和稳定 tie-break 选择至多一个 primary active Goal。
4. 被选择的 Goal 拥有三至五个可执行 Plan Step，并能跨多个世界推进和服务重启继续执行。
5. PlanningProvider 与 ActionDecisionProvider 只返回结构化 Draft；所有引用、条件和动作由 Backend 重新验证。
6. LLM 产出的最终结果只能成为现有 `ActionProposal`，继续经过同一 Registry、Conflict Resolver、CAS 和原子提交。
7. Goal 完成/失败、前置条件变化、行动失败、关键事件、玩家干预或循环风险会在下一次 LLM 推进时触发受控 replanning。
8. Provider 超时、输出非法、预算耗尽或 Identity/认知不可用时，世界仍通过现有确定性策略安全推进。
9. 玩家可以明确选择普通或 LLM 推进，并安全查看当前 Goal、下一步与有限 Plan 状态。
10. 固定 Fake Provider 下，Goal、Plan、Proposal、replanning 和 fallback 完全可重复。

## 4. 玩家体验与演示切片

### 4.1 普通推进

玩家选择“普通推进”并点击唯一的“推进 1 小时”按钮。Backend 使用 Stage 2 结束时的现有 deterministic policy：不调用 Planning/Action Decision Provider，不创建或推进 Stage 3 Goal/Plan，以此保持离线可用的回归与比较基线。

已存在的 Goal/Plan 在普通推进期间保留但不消费、不改变。玩家切回 LLM 推进后，Backend 会先重新验证其世界版本、前置条件和触发状态，再决定继续或 replan。

### 4.2 LLM 推进

玩家选择“LLM 推进”并点击同一个推进按钮：

1. Backend 仍先构造与普通模式相同语义的决策 Snapshot。
2. 对所有 NPC 确定性检查 deliberation/replanning trigger。
3. 受单次预算限制，只为稳定排序后允许启动的 NPC 调用新 Provider。
4. 未触发 NPC 执行仍有效的现有 Plan；没有有效 Plan 时执行确定性日常行为。
5. Provider 失败的 NPC 使用合法 Plan Step 或现有确定性策略回退。
6. 所有 NPC 的最终 Proposal 一起进入既有冲突处理和原子提交。

玩家能看到本次 Run 是普通还是 LLM 模式、是否发生安全降级；看不到 Prompt、模型推理、原始 Memory/Belief、内部评分或 Provider 错误。

### 4.3 最小演示闭环

Stage 3 使用当前三名 NPC、现有地点、现有 `missing_child` 任务和六种已注册行动构造演示，不新增故事章节。

至少一个 NPC 必须能够：

- 基于自己允许读取的已持久化 Memory/Belief 选择一个注册 Goal；
- 形成三至五步 Plan；
- 在连续多次 LLM 推进中，无需玩家逐步下达动作而继续该 Plan；
- 在现有关键 Quest Event 或新的玩家 Claim 到来后，于下一次 LLM 推进中做出可解释的 replan；
- 在 Provider 故障时仍完成一次合法的确定性世界推进。

## 5. 核心不变量

### 5.1 权威执行

1. Backend 继续拥有 World、Quest、NPC State、Goal、Plan 和 Plan Step 的权威状态。
2. LLM 不能写数据库、推进计数器、改变 Goal/Plan lifecycle 或提交 Action/Event。
3. Goal/Plan 不建立第二条行动执行路径；只有 Registry 接受的 `ActionProposal` 才能产生 Action/Event 和世界效果。
4. 普通与 LLM 模式必须使用同一 Snapshot 语义、被动需求漂移、时钟推进、Registry、Conflict Resolver、CAS 和事务提交。
5. 每次成功世界推进只增加一次 `world_version` 和一次 `clock_tick`；`event_sequence` 只按实际提交的 Event 数增加。
6. Goal/Plan 自身不是 World Fact，也不单独增加三套计数器；它们若在推进中变化，必须与该 Run 的权威提交保持一致。

### 5.2 信息与权限

1. Planning/Action Context 只能读取当前 NPC、当前 World、非未来时间线且权限允许的 Memory/Belief。
2. Stage 3 复用现有 Retrieval scope 与 SQL hard filter，不新增更宽 scope，不直接绕过 Repository 查询认知表。
3. 玩家发言仍是带 Speaker 的 Claim，不因影响 Goal/Plan 而升级为事实或系统指令。
4. Provider 返回的 Memory、Belief、Goal、Plan、Step、NPC、Location 或 Quest 引用必须位于 Backend 提供的白名单。
5. Public Intent DTO 不得通过正文、ID 数量、步骤描述、错误差异或原因文案泄露秘密来源。

### 5.3 确定性与失败隔离

1. 候选生成、Goal 仲裁、trigger、计划验证、成功/失败条件、循环检测、fallback 与 tie-break 全部由确定性代码掌握。
2. Provider 调用不持有数据库事务；返回后必须以新事务重新加载并验证 Snapshot 版本和所有引用。
3. stale Draft、非法 Draft、超时或预算耗尽不能留下 Goal/Plan 半成品。
4. LLM 失败不得让普通 RPG 不可用，也不得把既有成功语义改为 5xx。

## 6. 双推进 UI 决策

采用**分段式单选模式 + 单一推进按钮**：

    推进模式  [ 普通推进 | LLM 推进 ]
                             [ 推进 1 小时 ]

- 页面初次进入和 Demo Reset 后默认普通推进。
- 选择在当前前端会话中保持，直到玩家切换或 Reset；Backend 不保存全局 UI 模式。
- 每个请求显式携带模式，禁止依赖上一次请求或进程内隐式状态。
- 请求进行中同时禁用模式控件和推进按钮，继续复用 `canMutate` 与版本冲突刷新语义。
- 结果区显示“普通推进”或“LLM 推进”；若回退则显示固定安全提示“部分决策已安全降级”。
- 不显示模型、Provider、Token、强制 deliberation、指定 NPC 或内部触发器开关。

不采用双按钮。两个并列世界变更入口会放大误触、重复提交和 loading/disabled 分支；模式选择加单一按钮能保持当前唯一 mutation affordance。

## 7. Runtime Mode 语义

Stage 3 的 Public API 只接受：

- `deterministic`：普通推进，完全沿用当前 deterministic policy，不调用新 Provider，不消费 Goal/Plan。
- `auto`：LLM 推进；仅被触发且预算允许的 NPC 进行新 deliberation，其余 NPC 使用有效 Plan 或确定性日常行为。

`force_deliberation` 虽已在内部枚举中预留，但不属于 Stage 3 Public API。请求传入该值必须按普通 schema validation 拒绝，不能静默映射为 `auto`。

同一 Run 内所有 NPC 看到同一决策 Snapshot。是否调用 Provider 可以逐 NPC 不同，但不能让后处理 NPC 看到前一个 NPC 在本 Run 中拟议或执行的效果。

Stage 3 默认单次最多为一个 NPC 启动新 deliberation。若多个 NPC 同时触发，按 `trigger priority DESC, npc.sort_order ASC, npc.id ASC` 选择；其他 NPC 使用现有 Plan 或确定性 fallback。该上限用于约束同步延迟，不影响所有 NPC 每次仍各自产生一个最终 Proposal。

## 8. Identity 与 Drives

Identity 是版本化 authored input，不是 Memory、Belief 或模型输出。现有 `role` 与 `personality` 保持原字段；`data/npcs.json` 增量增加：

- `identity_version`
- `values`
- `aspirations`
- `fears`
- `responsibilities`
- `prohibitions`
- `drives`

Stage 3 固定 Drive key：

- `safety`
- `duty`
- `affiliation`
- `protection`
- `curiosity`
- `reputation`

`identity_version` 固定为 `identity-v1`。`values/aspirations/responsibilities` 各含一至五项，`fears/prohibitions` 各含零至五项；每项 trim 后为一至 120 个 Unicode 字符，同一列表内不得重复。`drives` 必须且只能包含上述六个 key，每个值为有限的 0–1 数值。Seed loader 必须拒绝未知 key、缺项、越界值、非有限数值、空白或重复文本以及不存在的 NPC owner。

数据库不新增 Identity 表。`npc_profiles` 增加 nullable `identity_version` 与 `identity_json`；新 Seed/Reset 写完整值，迁移前数据库保留 null，不伪造历史 authored identity。缺失 Identity 时 `auto` 安全降级为确定性行为，普通模式照常工作。

Prohibition 同时进入确定性 Goal eligibility 与 Plan Validator，不能只作为 Prompt 提醒。Provider 无权修改或绕过它。

## 9. Goal Type Registry 与候选

Goal Type 是代码内注册定义，不是数据库内容，也不能由 Provider 扩展。每个定义至少提供：

- 稳定 `goal_type` ID 与 policy version；
- 适用角色和 deterministic eligibility；
- 成功、失败条件 evaluator；
- 有限 allowed action set；
- base priority、risk 与 interruptibility；
- 安全公共摘要模板；
- deterministic plan builder；Stage 3 注册的三类 Goal 均必须提供，作为 Fake/Live Provider 失败时的同语义 fallback。

Stage 3 的最小 Registry version 固定为 `goal-types-v1`，且只注册以下三项：

| sort_order | goal_type | 需求 | allowed actions |
| --- | --- | --- | --- |
| 10 | `recover_energy` | 在能量触发阈值以下时恢复至注册完成阈值 | `move/eat/rest/wait` |
| 20 | `perform_role_duty` | 在职责地点完成一次与既有 role 匹配的有效工作 | `move/work/wait` |
| 30 | `follow_up_salient_clue` | 跟进与当前任务有关的显著线索，并返回职责地点 | `move/talk/wait` |

这些 ID、顺序和 action 白名单不能由 Prompt、配置或后续 Plan 临时改变。每一类的 trigger 阈值、职责映射、成功/失败 evaluator、目标解析和 deterministic plan builder 都是同一注册 policy 的确定性部分；数值常量与 role 映射必须复用当前 World Engine 的边界（包括低能量阈值和 `WORK_LOCATION_BY_ROLE`），不得在 Provider、数据库或 UI 中形成第二套规则。第三类 Goal 只能使用 Backend 从权威 Event，或经过 Stage 2 hard filter 后允许的 NPC Memory 中解析出的既有 Location/NPC ID；自由文本中的地名不能直接成为 target。

候选由确定性策略从 Identity/Drives、NPC State、World/Quest、当前 active Goal 和权限过滤后的 evidence 产生。LLM 不负责生成候选集合或选择 winner；它最多在 winner 已确定后，为 Planning Draft 提供受限文案。

只有最终选中的 Goal 被持久化。未选候选的安全评分摘要进入 private Run Trace，不建立大量候选数据库行。

## 10. Goal Arbitration

固定 `goal-arbitration-v1` 使用 0–1 分量：

    positive =
      0.20 * base_priority
    + 0.20 * urgency
    + 0.15 * drive_alignment
    + 0.10 * personality_alignment
    + 0.15 * evidence_strength
    + 0.10 * quest_relevance
    + 0.10 * commitment

    score = clamp(positive - 0.10 * risk - 0.10 * switching_cost, 0, 1)

- 所有分量由注册 policy 计算，Provider 不返回分数。
- `evidence_strength` 只能使用白名单 Memory/Belief；Claim 不获得事实权重。
- `quest_relevance` 只来自权威 Quest 状态和已提交 Quest Event。
- Stage 5 Relationship 尚不存在，因此 relationship relevance 固定为 0，不创建占位接口或表。
- 当前 Goal 未失效时获得 commitment；切换承担 switching cost。
- 除 Goal 已完成/失败或 `critical_event` 触发外，新候选必须比当前 Goal 高至少 0.10 才能切换；只有这三种情况可绕过该差值。
- tie-break 固定为 `score DESC, goal_type.sort_order ASC, candidate_key ASC`，不使用 LLM 文本或创建时间。

每个 `world_id + owner_npc_id` 同时最多一个 primary active Goal。Stage 3 不实现 maintenance/suspended Goal 池；切换时旧 Goal 标记 `superseded`，历史保留。

## 11. Rolling Plan

每个 active Goal 至多一个 active Plan。合法 Plan 必须包含三至五个有序 Step；单次日常行为继续走 deterministic routine，不为凑长度创建无意义 Plan。

每个 Step 必须包含：

- `ordinal`
- 安全、有限长度的 `summary`
- 已注册 `action_type`
- 合法 `target_kind/target_id` 或 null
- 注册式 precondition
- 注册式 success condition
- `failure_strategy`
- `estimated_ticks`
- `interruptible`

Stage 3 不保存或执行任意表达式、Python、SQL、Prompt 片段或自由形式条件。条件使用固定 Registry，例如 `npc_at_location`、`energy_at_least`、`quest_status_is`、`action_executed`，参数必须对照当前 Snapshot 和 allowlist 校验。

Plan 结构在创建后不可原地改写。Replanning 创建新 Plan revision，并把旧 Plan/未完成 Step 标记 `superseded`；已完成 Step 和历史失败仍保留。运行时只允许更新 Step 的 lifecycle、attempt count、last failure code 与完成时间。

## 12. Replanning 与防循环

Replanning 只在下一次 `auto` 世界推进中评估和执行，不由 Chat、Memory GET、Intent GET 或后台任务自动启动。

固定 trigger reason：

- `no_valid_plan`
- `goal_completed`
- `goal_failed`
- `precondition_changed`
- `action_failed`
- `critical_event`
- `player_intervention`
- `loop_detected`

若多个 reason 同时存在，稳定顺序固定为 `critical_event`、`goal_completed`、`goal_failed`、`precondition_changed`、`action_failed`、`loop_detected`、`player_intervention`、`no_valid_plan`；排序不依赖数据库返回顺序。

防循环最小规则：

- 每个 Step 最多两次失败；达到上限后不得再次提交同一步，下一次 `auto` 必须 replan 或 fallback。
- 相同 `plan_step_id + action_type + target` 只有在 success condition 产生进展时才能继续；无进展重复达到三次视为 loop。
- Goal 切换后进入两个 `clock_tick` 的普通冷却；Goal 完成/失败或关键事件可绕过。
- 一次世界推进中每个 NPC 最多产生一个最终 Proposal，不在同一请求内循环“规划—执行—再规划”。
- Provider 调用次数、单次超时和总 wall-clock deadline 受共享预算约束；预算耗尽后不启动新调用。

循环 fingerprint 使用稳定 ID、action type、target 和相关权威条件值，不包含自由文本、UTC 当前时间或 Python 随机 hash。

## 13. Structured Provider

### 13.1 独立接口

Stage 3 新增两个互相独立的 Provider：

- `PlanningProvider.plan(request) -> PlanningDraft`
- `ActionDecisionProvider.decide(request) -> ActionProposalDraft`

它们不复用 ChatProvider，也不改写 Stage 2 的 ReflectionProvider。Reflection 继续由 Stage 2 的 post-commit cognition enrichment 触发；Stage 3 只消费已经成功持久化的 Reflection Memory 和当前 Belief，不在一次 pre-commit deliberation 内临时生成 Reflection。

### 13.2 PlanningRequest 与 Draft

PlanningRequest 是冻结、可序列化、有界的内部契约，至少包含：

- world、owner、base world version 与 clock tick；
- 版本化 Identity/Drives；
- 已由规则选中的 Goal ID、Goal Type 和安全描述；
- trigger reasons；
- 当前 NPC/World/Quest 的权威 Snapshot；
- 权限过滤后的 bounded Memory/Belief context；
- Backend 提供的 allowed action schemas、allowed condition types 和 entity allowlist；
- 共享 deadline 的 remaining budget。

PlanningDraft 只能为请求中的 Goal 生成三至五个 Step。Provider 不能返回新的 owner、world、Goal Type、权限、成功/失败 evaluator 或未注册 action/condition。Draft 中所有 ID 必须来自请求 allowlist。

### 13.3 ActionDecisionRequest 与 Draft

ActionDecisionRequest 至少包含当前 Goal、当前 active Plan、唯一 next executable Step、最新同版本 Snapshot、该 Step 允许的 action/target，以及 bounded cognition context。

Provider 可以选择执行该 Step、在该 Goal Type 与 Step 均允许 `wait` 时显式等待，或声明无法执行；它不能跳到任意 Step、修改 Plan、产生多个 Proposal 或扩大 allowed action set。返回值只是 Draft。只有 Backend 的 validator 成功构造既有 `ActionProposal` 后，才进入冲突处理。

### 13.4 Fake、Live 与确定性接缝

- 快速测试和默认无 Key 开发模式使用固定 Fake Planning/Action Decision Provider。
- Fake 与 live adapter 必须经过完全相同的 Pydantic schema、引用白名单、Plan Validator、Action Registry 和持久化链。
- 确定性 Goal candidate、arbitration、Plan condition evaluator、trigger、loop guard 和 fallback plan builder 均不依赖 Provider。
- `existing_plan -> ActionProposal` 是确定性转换；未触发 NPC 不为执行既有 Step 再调用 LLM。
- Live OpenAI-compatible adapter 使用与 Chat/Embedding/Reflection 分离的配置、模型和短超时。
- 配置明确选择 live 但字段不完整时，不静默伪装成成功的 Fake LLM Run；该 NPC 进入安全 fallback 并设置固定错误类别。

### 13.5 Schema repair 与预算

只有 Provider 已返回响应但 JSON/schema 无效时允许一次 repair。网络错误、超时、取消或预算不足不做 repair，直接 fallback。

每个新 deliberation 的硬上限：

- Planning：首次 1 次 + repair 最多 1 次；
- Action Decision：首次 1 次 + repair 最多 1 次；
- 单次最多一个 deliberating NPC；
- 全 Run 使用一个 wall-clock deadline；每次调用收到 `min(provider_timeout, remaining)`；
- deadline 到期后的成功或失败结果均不得持久化。

默认总 deliberation budget 为 8 秒，配置上限不得超过 30 秒。Stage 3 不记录 Token/成本账本，不做 backoff、请求外重试或异步取消；这些属于 Stage 4。

## 14. Deliberation Context 与隐私

Stage 3 建立专用 Deliberation Context Assembler，消费现有 World/Quest Repository、Identity、Goal/Plan Repository 和 Stage 2 cognition read surface。

规则如下：

1. Snapshot、Memory/Belief 上界在请求开始时固定；晚于该上界的来源不能进入当前 Provider 调用。
2. Memory 使用既有 owner/world/time/lifecycle/secrecy hard filter。Stage 3 不修改 Stage 2 的 Hybrid Retrieval 权重；Goal relevance 在候选仲裁层计算。
3. 当前 Belief 只读同 owner/world 的 active 行，并保留其 evidence provenance；不把 Belief 当作世界事实。
4. 默认最多八条 Memory、三条 current Belief，总文本预算 2400 Unicode 字符；不截断单条记录。
5. 玩家 Claim 以明确 source label 和 speaker 包裹，与系统指令、World Fact、Observation 和 Belief 分区。
6. Provider 输入中的 entity、Memory、Belief、Goal、Plan 和 Step ID 同时形成输出白名单。
7. Provider 调用前结束所有数据库读事务；返回后用新事务重新读取完整 hard filter 和当前版本。
8. 日志与 public trace 不写 Prompt、玩家原文、秘密 Memory、Belief statement、API Key、Authorization Header 或原始 Provider 错误。

Provider 生成的 summary 不直接成为 Public Intent 文案。公开 goal/step 文案由 Goal Type、注册 action 和允许公开的实体标签确定性投影，避免模型把秘密证据复制到 UI。

## 15. 同步运行流程与事务边界

### 15.1 决策流程

一次 `POST /api/world/tick`：

1. 读取 Snapshot 并校验 `expected_world_version`。
2. 按现有语义施加被动需求漂移、推进 world time 和 clock tick，得到一份不可变 decision Snapshot。
3. 若 mode 为 `deterministic`，直接运行现有 policy，跳到第 9 步。
4. 若 mode 为 `auto`，对所有 NPC 在同一 Snapshot 上评估 Goal/Plan 状态和 trigger。
5. 以稳定优先级选择至多一个 NPC 进行新 deliberation。
6. 对该 NPC 生成 Goal candidates、执行 arbitration；需要新 Plan 时调用 PlanningProvider 并验证 Draft。
7. 对新 Plan 的首个 Step 调用 ActionDecisionProvider；未触发 NPC 确定性转换有效 next Step。
8. 任意缺失、超时、非法或预算耗尽按该 NPC 局部 fallback，不影响其他 NPC。
9. 收集每个 NPC 恰好一个最终 `ActionProposal`。
10. 使用现有 Registry 校验全部 Proposal，并由既有 Conflict Resolver 做稳定冲突处理。
11. 计算世界效果、Plan Step 结果、Goal/Plan lifecycle 变化和安全 Trace Draft。
12. 重新检查 CAS，在一个事务中提交 World、Run Graph 与本 Run 的 Goal/Plan 变化。
13. commit 后执行现有 best-effort cognition catch-up；其失败不改变已经成功的 Run。

Provider 调用阶段只持有内存 Draft。任何 Goal、Plan 或 Step 都不能在 CAS/最终验证之前提前 flush 或 commit。

### 15.2 Plan 进度

- 新 Plan、其全部 Step 和首个 Action 必须在同一 Run 事务落地。
- accepted Action 的 success condition 在执行后的拟议 Snapshot 上确定性评估；成功时同事务完成 Step。
- Proposal 被 Registry 或冲突处理拒绝时，不执行世界效果；对应 Step attempt count 与安全 failure code 在同一 Run 事务更新。
- Goal success/failure 只由注册 evaluator 对权威结果判断，不采用 Provider 自报状态。
- 如果事务或 CAS 失败，Run、Proposal、Action、Event、Goal、Plan、Step 变化全部回滚。
- 不同 NPC 的 Plan 不能在当前 Run 中读取彼此刚拟议的状态；跨 NPC 影响只能通过提交后的 Event 在后续推进被感知。

### 15.3 Proposal source

- `deterministic`：普通推进的现有 policy。
- `existing_plan`：`auto` 中未启动新 deliberation、从有效 Plan Step 确定性产生。
- `llm`：ActionDecision Draft 通过全部 schema、引用和 Registry 前置验证。
- `fallback`：`auto` 中因 Provider、context、budget 或 Draft 失败而使用合法 deterministic plan/routine。

无效模型文本不是 `ActionProposal`，只产生安全 Trace 和 fallback；不得为了审计而把未通过 schema 的内容保存进 `action_proposals`。

## 16. 持久化模型

Stage 3 使用新 Alembic revision `0005_stage3_goals_plans`，新增四张表。Goal Type 本身留在版本化 Registry，不新增第五张表。

### 16.1 `agent_goals`

至少保存：

- UUID `id`、`world_id`、`owner_npc_id`；
- `goal_type`、`policy_version`；
- 内部 description 与确定性 safe summary；
- `active/completed/failed/superseded` lifecycle；
- arbitration version、总分和结构化分量；
- 创建/完成时的 world version、clock tick 与 UTC 时间；
- nullable `supersedes_goal_id`。

同一 world/owner 同时最多一个 active Goal。跨方言无法仅靠同构约束表达的“唯一 active”语义由 Repository 在事务内复验并以并发测试证明。

### 16.2 `agent_goal_evidence`

保存 Goal 与 Memory/Belief 的来源关系：

- `goal_id`；
- nullable `memory_id`；
- nullable `belief_id`；
- `supporting/contradicting` role；
- ordinal。

Goal 可以没有 evidence 行；一旦有关联，每行必须恰好引用 Memory 或 Belief 之一。所有引用必须来自该 Goal 的确定性 candidate provenance，并处于本次 arbitration/context whitelist；同时必须与 Goal 属于相同 world/owner、非未来时间线且处于允许 lifecycle。Provider 不能追加 evidence，跨 owner/world、虚构或白名单外 ID 一律拒绝。

### 16.3 `agent_plans`

至少保存：

- UUID `id` 与 `goal_id`；
- 单 Goal 单调递增 revision；
- `deterministic/llm/fallback` generation source；
- `active/completed/failed/superseded` lifecycle；
- 固定 replan reason；
- 创建时 world version、clock tick、world time、UTC 时间；
- nullable `supersedes_plan_id`。

每个 active Goal 同时最多一个 active Plan。Replan 追加新 revision，不覆盖旧 Plan。

### 16.4 `agent_plan_steps`

至少保存：

- UUID `id`、`plan_id`、ordinal；
- safe summary；
- action type、target kind/id；
- 注册式 precondition type/params；
- 注册式 success condition type/params；
- `retry/replan/fallback` failure strategy；
- estimated ticks、interruptible；
- `pending/active/completed/failed/skipped/superseded` lifecycle；
- attempt count、last failure code、完成版本/tick/time。

每个 Plan 的 ordinal 唯一且连续，Step 数固定为三至五。action/target/condition 必须与 Goal Type、Registry 和创建时 allowlist 相容。

### 16.5 现有表的增量

- `npc_profiles`：增加 nullable `identity_version`、`identity_json`。
- `agent_runs`：现有 mode 写入 `deterministic/auto`，增加成功 Run 的 `fallback_used` 布尔值。
- `action_proposals`：增加 nullable `goal_id` 与 `plan_step_id`，建立执行事实到持久化意图的可追溯关系。

Run Graph 继续保存“一次推进发生了什么”，不能替代跨 Run 的 Goal/Plan：

    Goal -> Plan -> Plan Step
                         |
                         v
                  ActionProposal
                         |
                         v
           Registry -> Action/Event/Run Graph

把 Goal/Plan 塞进 trace 或 proposal JSON 会失去 active lifecycle、revision、FK、并发校验和原子 Step 推进，因此禁止作为零新表捷径。

### 16.6 Migration、Reset 与双数据库

- ORM 与 migration 的 FK、CHECK、UNIQUE、索引和固定 vocabulary 必须同构。
- SQLite 与 PostgreSQL 使用相同领域语义；所有 PostgreSQL 并发/约束路径做真实集成验收。
- legacy `npc_profiles` 的 Identity 字段保持 null；升级不得伪造 authored content。
- `downgrade()` 明确拒绝，因为 Goal/Plan provenance 丢失不可逆。
- Demo Reset 先删除引用 Goal/Plan 的 Run Graph 行，再按 Step、Plan、Goal Evidence、Goal 顺序清理，随后才能清理 Stage 2 Belief/Memory；只影响目标 World。
- 普通启动、migration 与 `ensure_demo_world` 不重置 Goal/Plan 历史。

## 17. Public API 演进

### 17.1 世界推进请求

继续使用同步端点：

    POST /api/world/tick

请求增量为：

    {
      "expected_world_version": 12,
      "mode": "deterministic"
    }

- `mode` 只允许 `deterministic/auto`，默认值为 `deterministic`，因此现有客户端保持普通推进语义。
- 不新增异步 Run submission、202、polling、SSE、idempotency key、agent scope 或模型字段。
- 成功仍为 HTTP 200；版本冲突仍为 409；世界/事务不可用仍为安全 503。
- Planning/Action Provider 失败、Draft 非法或预算耗尽通过 fallback 返回 200，不新增模型专属 5xx。

`AgentRunSummary.mode` 收紧为上述 Public enum，并新增 `fallback_used: bool`。该字段表示本 Run 至少一个 NPC 因 Stage 3 context/provider/draft/budget 失败走了 fallback；配置明确使用 Fake Provider 不算 fallback。

Run detail 中既有 Proposal source 继续用于说明 `deterministic/existing_plan/llm/fallback`。不返回 repair 原文、模型输出或 Provider error。

### 17.2 NPC 当前意图

新增只读端点：

    GET /api/npcs/{npc_id}/intent

成功响应继续使用公共 envelope，data 的规范形状为：

    {
      "npc_id": "grey",
      "goal": {
        "id": "opaque-goal-uuid",
        "type": "follow_up_salient_clue",
        "summary": "Grey 打算核实一条与当前任务有关的线索。",
        "status": "active",
        "reason_text": "当前任务情境使这件事更紧迫。",
        "created_clock_tick": 4
      },
      "plan": {
        "id": "opaque-plan-uuid",
        "revision": 2,
        "status": "active",
        "next_step_ordinal": 2,
        "steps": [
          {
            "ordinal": 1,
            "summary": "前往相关地点",
            "status": "completed",
            "estimated_ticks": 1,
            "interruptible": true
          },
          {
            "ordinal": 2,
            "summary": "向相关人物核实线索",
            "status": "active",
            "estimated_ticks": 1,
            "interruptible": true
          },
          {
            "ordinal": 3,
            "summary": "返回职责地点",
            "status": "pending",
            "estimated_ticks": 1,
            "interruptible": true
          }
        ]
      }
    }

约束：

- 当前没有 active Goal/Plan 时，`goal` 与 `plan` 同时为 null；不能出现 active Goal 没有 active Plan 的公开状态。
- 最多返回一个 Goal 与一个 Plan，Plan 最多五个 Step；不提供历史、任意 owner、query、scope 或 include-secret 参数。
- `summary/reason_text/step.summary` 由 Backend 安全投影，不直接使用 Provider 文本。
- 不返回 arbitration score、Drive 数值、prohibition、evidence ID/数量、Memory/Belief 正文、condition params、失败次数、Prompt、模型或隐藏 reasoning。
- 基于 private/secret evidence 的目标使用 Goal Type 的通用安全文案；不可见证据不能通过文本、数量、空占位或错误差异泄露。
- 读取不触发 cognition catch-up、planning、replanning、Provider 调用或 access telemetry，不修改任何数据库行。
- NPC 不存在返回 404；Intent Repository 不可用返回固定安全 503。Intent 失败不影响 NPC Detail、Memory、Chat、地图或世界推进。

## 18. 前端演进

### 18.1 世界推进区域

现有 TickPanel 增加可访问的模式单选组，保留唯一推进按钮。模式状态进入 world store，API adapter 每次显式发送；loading、409 刷新、普通失败与 `canMutate` 行为保持现有语义。

结果区显示 Run mode；`fallback_used=true` 时显示一条固定降级说明，但不显示哪个 Provider、哪个 NPC、具体错误或调用次数。

### 18.2 当前意图区域

NPC Detail 中增加独立的“当前打算”区域：

- Goal summary 与 next Step 始终可见；
- 其余 Step 可展开查看，最多五条；
- 每条只显示安全 summary、status、estimated ticks 和 interruptible；
- 无 Goal、加载、失败均有独立状态；
- Intent 请求失败不污染既有 npcDetail、npcMemory 或 npcChat store。

新增独立 npcIntent store，至少具有 selected NPC、data、loading、error 和 request-version 竞态守卫。选中 NPC 时读取；任意成功世界推进后只刷新当前选中 NPC；关闭详情和 Demo Reset 时使旧请求失效并清空。

不把 Goal/Plan 业务状态放入 Phaser。Phaser 继续只负责地图渲染与输入，后端 NPC semantic location 仍是权威。

## 19. 失败与降级矩阵

| 失败 | Stage 3 行为 |
| --- | --- |
| mode 非法 | schema validation 拒绝；不触碰世界 |
| Identity 缺失/非法 | 该 NPC 使用 deterministic fallback；普通模式不受影响 |
| cognition read 不可用 | 不向 Provider发送不完整/越权 context；该 NPC fallback |
| Planning 网络错误/超时 | 不 repair，fallback |
| Planning JSON/schema 非法 | 最多 repair 一次；仍失败则 fallback |
| Plan 引用虚构 ID、非法条件或未授权 action | Draft 拒绝，最多一次 schema repair；仍失败则 fallback |
| Action Decision 网络错误/超时 | 不 repair，从已验证 Step 生成 deterministic fallback |
| Action Draft 非法或偏离当前 Step | 最多 repair 一次；仍失败则 fallback |
| deadline 耗尽 | 不启动新调用；迟到结果不持久化；未决 NPC fallback |
| existing Plan 失效但无预算 replan | 本 Run 使用 deterministic routine；保留安全 trigger 供下次 auto 重试 |
| Registry/Conflict 拒绝 Proposal | 不执行效果；同事务记录 Step 失败尝试 |
| CAS 冲突 | HTTP 409；Run Graph 和 Goal/Plan 全部不写 |
| Goal/Plan/Run 持久化失败 | 全事务 rollback，HTTP 503，世界不改变 |
| post-commit cognition 失败 | 已成功世界 Run 保持 200；checkpoint 后续补偿 |
| Intent GET 失败 | 仅该区域 503/错误态，其余 RPG 功能继续 |

日志只记录固定 category、run/owner 的安全标识和 timing；不得插入玩家文本、秘密内容或 Provider 原始响应。

## 20. 安全与披露

1. Player Claim 进入 Provider 前必须作为不可信数据分区，不能携带系统权限或覆盖 schema。
2. Goal Type、conditions、allowed actions、entity allowlist、owner/world/version 全部由 Backend 固定。
3. Provider 文本不能成为 Public Intent 文案，也不能进入公开 Event description。
4. `internal_only` evidence 不能成为公开 action target 的唯一授权来源；注册 Goal policy 必须确定性证明该 target 可行动且不会直接披露受保护正文。
5. Stage 3 的 `follow_up_salient_clue` 只允许使用 public 或当前 owner 的 `player_dialogue` evidence 产生具体 target；secret/internal-only evidence 只能影响不披露内容的通用 priority。
6. 所有 Public DTO 由专用投影构造，禁止直接序列化 Goal/Plan ORM。
7. Public Trace 只保存 trigger code、Goal Type、Plan revision、Proposal source、validation/fallback code；不保存 chain-of-thought、Prompt 或秘密 evidence。
8. 无认证单玩家 Demo 不提供任意 Goal/Plan 搜索、写入、强制 replan 或 provider 控制 API。

## 21. 测试策略

### 21.1 纯确定性单元测试

- Identity/Drives schema、unknown key、数值边界和 prohibition enforcement。
- Goal Type 注册、候选 eligibility、三类最小 Goal 和未知 Goal Type 拒绝。
- `goal-arbitration-v1` 每个分量、clamp、0.10 切换阈值和稳定 tie-break。
- Plan 三至五步、ordinal、registered condition、allowed action/target 和 lifecycle。
- 全部 replan reasons、优先级、冷却、失败上限、无进展重复 fingerprint。
- deterministic/existing_plan/llm/fallback Proposal source。

### 21.2 Provider 与安全验证

- Fake Provider 固定输入得到固定 Draft。
- OpenAI-compatible payload、认证、短 timeout、总 deadline 和响应大小上限。
- 首次 schema 失败后一次 repair；网络/timeout 不 repair；第二次失败立即 fallback。
- 虚构 Goal/Plan/Step/Memory/Belief/NPC/Location/Quest ID 全部拒绝。
- 玩家 prompt injection 不能改变 owner、Goal Type、action set、mode 或 disclosure。
- 迟到成功和迟到失败都不产生 Goal/Plan/状态写入。

### 21.3 Repository、Migration 与事务

- 空 SQLite 升级至 `0005`，当前 `0004` 原地升级并保留全部数据。
- 四表与现有表增量的 FK/CHECK/UNIQUE/index 同构。
- active Goal/Plan 唯一、Plan revision 单调、Step ordinal 连续。
- Goal Evidence 恰好一个引用、同 world/owner、非未来和生命周期约束。
- 新 Plan + Steps + Proposal + Action/Event + lifecycle 单事务成功。
- 任意 flush/commit/CAS 故障不留半条 Goal/Plan/Run Graph。
- 两个独立 Session 的并发 auto 请求只有一个 CAS 成功，失败方不留 intent。
- Reset 只清理目标 World，其他 World 与历史来源不受影响。
- PostgreSQL 17 上真实运行迁移、约束、并发和 rollback 验收。

### 21.4 API 与前端

- 省略 mode 仍是 deterministic；`auto` 显式启用；`force_deliberation` 拒绝。
- 两种模式均同步 200、共享 409/503 语义和三套计数器。
- deterministic mode 对固定 fixture 的 Action/Event 与 Stage 2 基线一致，且零 Provider 调用、零 Goal/Plan 改动。
- auto provider 失败仍 200，`fallback_used=true`，Action 合法且世界只推进一次。
- Intent DTO 上限、null 对称、404/503、只读和隐私。
- 所有“不泄露”测试必须在非空、有区分度集合上证明 `0 < visible < total`。
- 模式单选 + 单按钮、请求中禁用、默认普通、Reset、409 refresh、fallback 文案。
- npcIntent 独立错误、切换 NPC 的迟到响应和关闭失效。

### 21.5 完整验证

每个实现 Task 的相关 RED/GREEN 之外，触及内部签名、Provider、事务或跨层边界的 fix 后必须跑 Backend 全量、Frontend 全量和 type-check，不得以聚焦子集替代。

Stage 3 关闭前还必须跑 production build 与真实 PostgreSQL 验收。Live Planning/Action Provider Smoke 为显式配置的手动验收；没有 Key 时不得宣称通过，也不得导致普通/Fake 自动化失败。不得新增 skip 或 warning。

## 22. 阶段验收标准

Stage 3 只有在以下条件全部满足时才完成：

1. 普通模式在固定 Seed 下保持现有 deterministic Action/Event 结果，不调用新 Provider，不消费 Goal/Plan。
2. LLM 模式的所有 NPC 仍消费同一 Snapshot，并通过同一 Registry、Conflict Resolver、CAS 和原子提交。
3. 固定 Fake Provider 下，一个 NPC 能形成注册 Goal 和三至五步 Plan，跨多个推进与服务重启继续执行。
4. 同一 NPC 无玩家逐步指挥即可完成至少一个有前置条件的多步 Goal。
5. 一个现有关键 Quest Event 或新玩家 Claim 会在下一次 auto 推进触发受控 replan，并保留旧 Plan 历史。
6. Goal Evidence 均可追溯到同 owner/world 的真实 Memory/Belief；虚构、未来和越权引用无法保存。
7. Planning/Action Draft 不能创造 Goal Type、condition、action、entity 或世界效果。
8. Provider timeout、非法输出、repair 失败和预算耗尽均产生合法 fallback，世界不中断、不重复推进。
9. Step 失败、repetition 和切换冷却能阻止循环；固定输入下结果可重复。
10. Intent UI 只显示安全 Goal/Plan 投影，不泄露秘密 evidence 或 hidden reasoning。
11. SQLite 与 PostgreSQL 的 migration、事务、并发和重启路径真实通过。
12. 全量 Backend、Frontend、type-check、build 无失败、无新增 skip/warning。
13. 独立 review 清零 Critical/Important，用户完成 Review 并手动提交。

## 23. 明确后置到 Stage 4

Stage 3 不实现：

- 异步 HTTP 202 Run Submission；
- Transactional Outbox、Worker、Celery、Redis；
- 同 World pending/running/committing 分布式锁；
- 客户端 idempotency key 与重复任务投递恢复；
- SSE、刷新/断线后的 in-flight Run 恢复；
- 请求外自动 deliberation 或 replanning；
- 持久化 provider stage、backoff retry、异步取消；
- Token/成本账本、P50/P95、跨 Worker 总预算；
- LangGraph、LangChain 或任何工作流框架。

是否采用上述框架或更轻实现，由 Stage 4 Spec 基于恢复语义、部署复杂度和可验证收益重新决定。Stage 2 cognition checkpoint 不得冒充 Run queue，Stage 3 Goal/Plan lifecycle 也不得冒充 workflow recovery state。

## 24. 其他非目标

- 不新增 `investigate/share_information/report` 或其他 action。
- 不增加 NPC-to-NPC 长对话、Relationship、Claim 传播或社会图。
- 不改写 Stage 2 Retrieval 权限或把 Goal relevance 塞回既有 Memory 排序公式。
- 不增加 Agent Lab、强制指定 NPC、模型选择、Prompt 编辑或 raw trace。
- 不扩写 Forest Embers、战斗、装备、经济、大地图或更多 NPC。
- 不引入独立向量数据库。

## 25. Review 与后续流程

本阶段同时命中 migration、事务边界、Public API、Provider、跨栈和跨 Stage 不变量，Stage Gate 必须按 `AI_REVIEW_POLICY.md` 定级为 R3。

后续 Plan 必须：

- 每个 Task 预声明 Review Level、binding 条款锚点和证据要求；
- 尽量控制每个 Task 不超过八个文件且只命中一类主要风险；超过时拆分；
- 对迁移/事务、Provider/timeout、Public API/UI 分别设置独立 gate；
- 以 B0002 和台账记录的三处已知漂移为起点重新执行 drift check；
- 保持 agent 不提交、用户 Review 后手动提交的 Git 流程。

本文获用户批准前，不创建 Plan，不实现任何 Stage 3 代码。
