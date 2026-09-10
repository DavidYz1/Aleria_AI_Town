# Stage 2 Perception, Memory and Reflection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 每个行为严格执行 RED → GREEN；用户要求每个 Task 完成后立即停止并提交中文 Review 报告，所有修改保持未暂存、未提交，由用户 Review 后手动提交。

**Goal:** 在保持确定性 Agent Runtime、现有同步 Public API 和权威世界写入边界不变的前提下，为 Aleria AI Town 增加来源可追溯的 NPC 感知、长期记忆、权限优先 Hybrid Retrieval、Reflection/Belief，以及 Grey 可见的跨会话记忆闭环。

**Architecture:** 采用已经批准的“权威来源先提交、认知投影后执行”方案。World/Quest/Travel Event 与完整 Conversation Turn 先按现有事务提交；随后由每 NPC 独立 Checkpoint 驱动的有界投影生成 Observation/Memory。Embedding 与 Reflection 是可失败 enrichment；任何失败都不回滚来源事务，也不允许修改 World、Quest、NPC State、Action、Event 或 Run Graph。

**Tech Stack:** Python 3.11+、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、SQLite、PostgreSQL 17、pgvector 0.8.6、httpx、pytest、Vue 3、Pinia、TypeScript、Vitest。

**Spec：** `docs/superpowers/specs/2026-09-09-stage-2-perception-memory-reflection-design-cn.md`

## 全局约束

- 基线提交为 `ba935ae`；开始实现前应确认工作树只有已批准的 Stage 2 Spec、Plan 与当前 Task 的改动。
- 禁止执行 `git add`、`git commit`、`git reset`、`git checkout`、`git switch`；每个 Task 仅给用户建议提交信息。
- 严格使用 Subagent-Driven Development：每个 Task 由实现 subagent 完成，再由独立 spec reviewer 和 code-quality reviewer 检查；Critical/Important 清零后主代理才交付用户 Review。
- 严格 TDD：每项生产行为先写聚焦测试并确认因缺少该行为而失败，再写最小实现，最后运行相关回归。
- 每个 Task 完成后必须停止；未经用户 Review 和手动提交，不得进入下一个 Task。
- SQLite 是完整可用的默认/快速测试路径；PostgreSQL + pgvector 是必须真实验收的完整路径。
- 不修改现有 API 的请求、响应或状态码；只新增 Spec 批准的 `GET /api/npcs/{npc_id}/memory-explanations`。
- 不改变 `world_version`、`clock_tick`、`event_sequence` 的职责；认知写入不递增三者。
- 不向现有 Agent Run Graph 插入认知 Trace；Stage 2 的 Checkpoint 不是通用任务队列。
- 不实现 Goal、Plan、LLM ActionProposal、LangGraph、LangChain、Celery、Redis、Outbox、SSE、NPC 社会传播、知识图谱、Agent Lab、LangSmith 或 MCP Server。
- 不把 Player Claim、Reflection 或 Belief 标记为 World Fact；所有 Memory 都必须能沿来源或 evidence edge 追溯。
- Public DTO 只能由专用投影构造；不得直接返回 ORM、原始聊天、秘密内容、Embedding、内部评分或 Provider 错误。
- Provider 调用必须有短超时和有界输入；日志不得包含玩家原文、秘密 Memory、API Key 或 Authorization Header。
- 测试不得修改 `backend/data/aleria.db`；迁移、Reset 与失败恢复测试全部使用临时数据库。

---

## 文件职责图

| 文件/目录 | 职责 |
| --- | --- |
| `backend/migrations/versions/0004_stage2_cognition.py` | 新来源元数据、Conversation Turn 标识、认知六表和 SQLite/PostgreSQL 向量列 |
| `backend/app/database/models.py` | Stage 2 ORM 与所有数据库约束的同构定义 |
| `backend/app/agents/cognition_contracts.py` | 来源、感知、检索、Reflection 的冻结内部契约与固定分类值 |
| `backend/app/database/world_clock_repository.py` | 在原子 Runtime 写入中保存 Event 的历史感知快照 |
| `backend/app/database/player_quest_repository.py` | 在 Travel/Quest 来源事务中保存地点、参与者、见证者和关键性 |
| `backend/app/database/chat_repository.py` | 原子保存共享 `turn_id`、发生版本/时间完整的双消息 Turn |
| `data/agent_knowledge.json`、`backend/app/schemas/seed.py` | 版本化 authored knowledge 及严格 Seed 校验 |
| `backend/app/services/demo_reset_service.py` | 按 World 清理认知数据并重建 authored knowledge；普通启动不重置 |
| `backend/app/agents/perception.py` | Perception Policy Registry、权限矩阵、注意力预算和 ObservationDraft |
| `backend/app/database/cognition_repository.py` | 来源扫描、Checkpoint、核心投影、enrichment、检索和 evidence 持久化 |
| `backend/app/services/cognition_projection.py` | 每 NPC 有界 catch-up、核心事务和 post-commit 最佳努力协调 |
| `backend/app/llm/embedding_provider.py` | 独立 Fake/OpenAI-compatible Embedding Provider 与工厂 |
| `backend/app/agents/memory_retrieval.py` | 权限先行的 Hybrid/lexical 排序、预算、稳定 tie-break |
| `backend/app/llm/reflection_provider.py` | 独立 Fake/OpenAI-compatible Reflection Provider 与结构化输出解析 |
| `backend/app/agents/reflection.py` | 触发、证据指纹、Draft 验证、Belief 追加版本和有限重试 |
| `backend/app/services/chat_context.py`、`backend/app/services/chat_service.py` | 在当前回复前召回旧 Memory，在完整 Turn 提交后再投影新 Memory |
| `backend/app/services/memory_explanation.py` | 从当前公开 World/Quest 情境生成固定查询和安全解释投影 |
| `backend/app/api/npcs.py`、`backend/app/schemas/npc.py` | 新只读 Memory Explanation API |
| `frontend/src/types/npc.ts`、`frontend/src/api/npc.ts` | 新接口的前端类型和适配器 |
| `frontend/src/stores/npcMemory.ts` | 与 NPC Detail 解耦的加载、错误、竞态和刷新状态 |
| `frontend/src/components/NpcDetailPanel.vue`、`frontend/src/views/TownView.vue` | 默认折叠的“相关记忆”区域及不阻断现有 RPG 的接线 |
| `docs/05_Engineering_Architecture.md`、`docs/06_API_Contract.md`、`docs/07_Database_Schema.md`、`docs/14_Development_Environment.md` | 实现后权威架构、API、Schema 和环境说明 |

## 固定数据契约

实现期间使用以下固定内部分类，不允许 Provider 增加枚举值：

```python
class SourceKind(StrEnum):
    EVENT = "event"
    CONVERSATION_TURN = "conversation_turn"
    AUTHORED_KNOWLEDGE = "authored_knowledge"

class MemoryType(StrEnum):
    EPISODIC = "episodic"
    CONVERSATION = "conversation"
    REFLECTION = "reflection"
    KNOWLEDGE = "knowledge"

class PerceptionMode(StrEnum):
    PARTICIPANT = "participant"
    WITNESSED = "witnessed"
    PROFESSIONAL_CHANNEL = "professional_channel"
    DIRECT_DIALOGUE = "direct_dialogue"

class RetrievalScope(StrEnum):
    PLAYER_DIALOGUE = "player_dialogue"
    INTERNAL_REFLECTION = "internal_reflection"
    PUBLIC_EXPLANATION = "public_explanation"
```

`PUBLIC_EXPLANATION` 是已批准匿名只读接口所需的更窄内部 Scope：它只允许 `secrecy=public + disclosure_scope=public`，不会扩大 Spec 中 `player_dialogue` 或 `internal_reflection` 的权限。

---

### Task 1：建立可迁移的认知 Schema 与完整权威来源

**Files：**

- Create: `backend/migrations/versions/0004_stage2_cognition.py`
- Create: `backend/app/agents/cognition_contracts.py`
- Create: `data/agent_knowledge.json`
- Modify: `backend/app/database/models.py`
- Modify: `backend/app/database/world_clock_repository.py`
- Modify: `backend/app/database/player_quest_repository.py`
- Modify: `backend/app/database/chat_repository.py`
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/schemas/seed.py`
- Modify: `backend/app/services/demo_reset_service.py`
- Modify: `tests/backend/legacy_sqlite_factory.py`
- Modify: `tests/backend/test_schema_migrations.py`
- Modify: `tests/backend/test_chat_repository.py`
- Modify: `tests/backend/test_chat_models.py`
- Modify: `tests/backend/test_chat_service.py`
- Modify: `tests/backend/test_npc_chat_api.py`
- Modify: `tests/backend/test_agent_run_repository.py`
- Modify: `tests/backend/test_world_clock.py`
- Modify: `tests/backend/test_player_quest_repository.py`
- Modify: `tests/backend/test_demo_reset_api.py`
- Modify: `tests/backend/test_seed_world.py`
- Create: `tests/backend/test_cognition_models.py`

**Interfaces：**

- Produces: `EventPerceptionMetadata`、Stage 2 ORM、Alembic `0004`、版本化 `SeedAuthoredKnowledge`
- Changes internally: `ChatRepository.persist_turn(..., turn_id, world_version, world_time)`
- Preserves publicly: 所有现有 Event/Chat/Quest/World DTO 与状态码
- Migration policy: legacy Event/Message 的新字段保持 `NULL`，不得伪造历史来源

- [ ] **Step 1：先写 Migration/ORM RED 测试**

在 `tests/backend/test_schema_migrations.py` 把模型表集合扩展为：

```python
COGNITION_TABLES = {
    "agent_cognition_states",
    "observations",
    "memories",
    "memory_evidence",
    "beliefs",
    "belief_evidence",
}
```

新增从当前 `0003` 写入 Foundation 哨兵数据再升级 head 的测试，明确断言：

```python
assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
assert COGNITION_TABLES.issubset(inspect(engine).get_table_names())
assert connection.execute(text(
    "SELECT location_id, perception_scope, participant_npc_ids_json, "
    "witness_npc_ids_json FROM events WHERE id=:id"
), {"id": legacy_event_id}).one() == (None, None, None, None)
assert connection.execute(text(
    "SELECT turn_id, world_version, world_time FROM conversation_messages "
    "WHERE id=:id"
), {"id": legacy_message_id}).one() == (None, None, None)
```

在 `tests/backend/test_cognition_models.py` 添加 CHECK/FK/UNIQUE 失败用例：非法 `importance/confidence/emotional_valence`、同 owner/source/policy 重复 Observation、非法 Memory 来源组合、重复 evidence ordinal、跨表悬空 FK。

- [ ] **Step 2：运行测试确认 RED**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_schema_migrations.py \
  tests/backend/test_cognition_models.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task1-red
```

Expected：因 `0004`、认知表或新增列不存在而失败；不得把夹具或旧迁移回归当作有效 RED。

- [ ] **Step 3：实现 `0004` 与同构 ORM**

Migration 使用明确命名的约束，并按以下字段落地：

```text
events +=
  location_id nullable FK locations.id
  perception_scope nullable string
  participant_npc_ids_json nullable JSON
  witness_npc_ids_json nullable JSON
  professional_channels_json nullable JSON
  attention_priority nullable float CHECK 0..1
  is_critical nullable integer CHECK NULL/0/1

conversation_messages +=
  turn_id nullable string(36)
  world_version nullable integer CHECK NULL or >= 0
  world_time nullable string(5)
  UNIQUE(conversation_id, turn_id, role)
  INDEX(turn_id, id)

agent_cognition_states:
  PK(world_id, owner_npc_id), FKs world/npc
  last_event_sequence integer default 0 CHECK >= 0
  last_conversation_message_id integer default 0 CHECK >= 0
  reflection_accumulated_importance float default 0 CHECK >= 0
  reflection_memory_count integer default 0 CHECK >= 0
  reflection_pending_critical integer default 0 CHECK 0/1
  last_reflection_source_created_at nullable timezone datetime
  last_reflection_source_memory_id nullable string(36)
  last_reflection_evidence_fingerprint nullable string(64)
  reflection_attempt_fingerprint nullable string(64)
  reflection_attempt_count integer default 0 CHECK 0..2
  reflection_attempt_status string default 'idle' CHECK idle/failed/succeeded
  created_at, updated_at timezone datetime

observations:
  id string(36) PK; world_id FK; owner_npc_id FK
  source_kind string; source_event_id nullable FK events.id
  source_turn_id nullable string(36)
  source_user_message_id nullable FK conversation_messages.id
  source_assistant_message_id nullable FK conversation_messages.id
  source_key string; policy_version string
  occurred_world_version, occurred_clock_tick CHECK >= 0
  occurred_world_time string(5); source_created_at; created_at
  perception_mode; facts_json JSON; related_entity_ids_json JSON
  summary; secrecy; disclosure_scope; lifecycle_state; is_critical CHECK 0/1
  UNIQUE(world_id, owner_npc_id, source_key, policy_version)
  CHECK event source has only event FK; conversation source has turn + both message FKs
  INDEX(world_id, owner_npc_id, occurred_clock_tick, id)

memories:
  id string(36) PK; world_id FK; owner_npc_id FK; memory_type
  source_observation_id nullable UNIQUE FK observations.id
  authored_source_id/version nullable strings
  content; safe_summary; normalized_content_hash string(64)
  related_entity_ids_json JSON
  occurred_world_version, occurred_clock_tick, created_world_version,
  created_clock_tick CHECK >= 0; occurred_world_time string(5)
  source_created_at; created_at
  importance, confidence CHECK 0..1; emotional_valence CHECK -1..1
  secrecy; disclosure_scope; lifecycle_state
  embedding_provider/model/version/input_hash nullable
  embedding_dimensions nullable integer CHECK NULL or > 0
  embedding_status string; embedding nullable dialect-aware vector/JSON
  last_accessed_at nullable; access_count integer default 0 CHECK >= 0
  UNIQUE(world_id, owner_npc_id, authored_source_id, authored_source_version)
  CHECK episodic/conversation use Observation; knowledge uses authored source;
        reflection uses evidence edges and neither direct source field
  INDEX(world_id, owner_npc_id, lifecycle_state, occurred_clock_tick, id)

memory_evidence:
  PK(derived_memory_id, evidence_memory_id); both FKs memories.id
  ordinal integer CHECK >= 0
  UNIQUE(derived_memory_id, ordinal)

beliefs:
  id string(36) PK; world_id FK; owner_npc_id FK
  statement; safe_summary; confidence CHECK 0..1; lifecycle_state
  supersedes_belief_id nullable FK beliefs.id
  source_reflection_memory_id FK memories.id
  created_world_version, created_clock_tick CHECK >= 0; created_at
  UNIQUE(source_reflection_memory_id)
  INDEX(world_id, owner_npc_id, lifecycle_state, created_clock_tick, id)

belief_evidence:
  PK(belief_id, memory_id, evidence_role); FKs belief/memory
  evidence_role CHECK supporting/contradicting
  ordinal integer CHECK >= 0
  UNIQUE(belief_id, evidence_role, ordinal)
```

所有固定分类列都建立命名 CHECK：Event perception scope；Observation source/perception/secrecy/disclosure/lifecycle；Memory type/secrecy/disclosure/lifecycle/embedding status（`ready/failed/unavailable`）；Belief lifecycle（`active/disputed/superseded`）；Evidence role。应用层枚举与数据库 CHECK 必须一一对应。

字段类型固定为：分类/版本/普通 ID 使用 `String`（UUID `String(36)`、SHA-256 `String(64)`、world time `String(5)`），正文与安全摘要使用 `Text`，计数/游标/布尔兼容值使用 `Integer`，评分使用 `Float`，结构化字段使用 `JSON`，时间使用 `DateTime(timezone=True)`。约束和索引名固定如下，ORM 与 Migration 必须相同：

```text
events:
  fk_events_location_id_locations
  ck_events_perception_scope
  ck_events_attention_priority
  ck_events_is_critical

conversation_messages:
  ck_conversation_messages_world_version
  uq_conversation_messages_conversation_turn_role
  ix_conversation_messages_turn_id_id

agent_cognition_states:
  pk_agent_cognition_states
  fk_cognition_states_world_id_world_state
  fk_cognition_states_owner_npc_id_npc_profiles
  ck_cognition_states_event_cursor
  ck_cognition_states_message_cursor
  ck_cognition_states_reflection_importance
  ck_cognition_states_reflection_count
  ck_cognition_states_pending_critical
  ck_cognition_states_attempt_count
  ck_cognition_states_attempt_status

observations:
  pk_observations
  fk_observations_world_id_world_state
  fk_observations_owner_npc_id_npc_profiles
  fk_observations_source_event_id_events
  fk_observations_source_user_message_id_messages
  fk_observations_source_assistant_message_id_messages
  uq_observations_owner_source_policy
  ck_observations_source_kind
  ck_observations_source_reference_shape
  ck_observations_world_version
  ck_observations_clock_tick
  ck_observations_perception_mode
  ck_observations_secrecy
  ck_observations_disclosure_scope
  ck_observations_lifecycle_state
  ck_observations_is_critical
  ix_observations_owner_occurred
  ix_observations_source_event
  ix_observations_source_turn

memories:
  pk_memories
  fk_memories_world_id_world_state
  fk_memories_owner_npc_id_npc_profiles
  fk_memories_source_observation_id_observations
  uq_memories_source_observation
  uq_memories_authored_source
  ck_memories_source_reference_shape
  ck_memories_memory_type
  ck_memories_occurred_world_version
  ck_memories_occurred_clock_tick
  ck_memories_created_world_version
  ck_memories_created_clock_tick
  ck_memories_importance
  ck_memories_confidence
  ck_memories_emotional_valence
  ck_memories_secrecy
  ck_memories_disclosure_scope
  ck_memories_lifecycle_state
  ck_memories_embedding_dimensions
  ck_memories_embedding_status
  ck_memories_access_count
  ix_memories_owner_lifecycle_occurred
  ix_memories_embedding_space

memory_evidence:
  pk_memory_evidence
  fk_memory_evidence_derived_memory_id_memories
  fk_memory_evidence_evidence_memory_id_memories
  uq_memory_evidence_derived_ordinal
  ck_memory_evidence_ordinal
  ck_memory_evidence_no_self_reference

beliefs:
  pk_beliefs
  fk_beliefs_world_id_world_state
  fk_beliefs_owner_npc_id_npc_profiles
  fk_beliefs_supersedes_belief_id_beliefs
  fk_beliefs_source_reflection_memory_id_memories
  uq_beliefs_source_reflection_memory
  ck_beliefs_confidence
  ck_beliefs_lifecycle_state
  ck_beliefs_created_world_version
  ck_beliefs_created_clock_tick
  ix_beliefs_owner_lifecycle_created

belief_evidence:
  pk_belief_evidence
  fk_belief_evidence_belief_id_beliefs
  fk_belief_evidence_memory_id_memories
  uq_belief_evidence_role_ordinal
  ck_belief_evidence_role
  ck_belief_evidence_ordinal
```

跨 World/owner、Reflection 至少一条 evidence、Belief source 必须是 reflection Memory 等跨行语义由 Repository 在同一事务内复验；不能假称普通 FK/CHECK 已覆盖这些规则。

向量列类型必须使用：

```python
embedding_type = (
    Vector()
    if op.get_bind().dialect.name == "postgresql"
    else sa.JSON()
)
```

ORM 使用 `JSON().with_variant(Vector(), "postgresql")`。本阶段不固定 PostgreSQL vector 维度、不建 ANN 索引；应用层保存前验证 dimensions。`downgrade()` 明确拒绝，因为删除 cognition 和 provenance 会丢数据。

- [ ] **Step 4：写权威来源元数据 RED 测试**

测试新写入而非 legacy backfill：

```python
assert user.turn_id == assistant.turn_id == expected_turn_id
assert (user.world_version, user.world_time) == (0, "08:00")
assert (assistant.world_version, assistant.world_time) == (0, "08:00")

assert event.location_id == "castle"
assert event.perception_scope == "location"
assert event.participant_npc_ids_json == ["grey"]
assert event.witness_npc_ids_json == ["grey"]
assert 0.0 <= event.attention_priority <= 1.0
```

World Tick Event 还必须断言 actor 与 NPC target 均进入 participant、见证者来自事件发生时的 NPC location 快照；Travel/Quest Event 断言使用提交时 location，不在未来补偿时读取当前 location。

运行新来源测试确认 RED：

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_chat_repository.py \
  tests/backend/test_agent_run_repository.py \
  tests/backend/test_player_quest_repository.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task1-source-red
```

Expected：新断言因 Turn/Event 感知元数据尚未写入而失败；完成 Step 5 后重跑并转 GREEN。

- [ ] **Step 5：实现冻结来源契约并写入历史快照**

在 `cognition_contracts.py` 定义：

```python
@dataclass(frozen=True)
class EventPerceptionMetadata:
    location_id: str | None
    perception_scope: Literal[
        "world_public", "location", "participants", "professional", "private"
    ]
    participant_npc_ids: tuple[str, ...]
    witness_npc_ids: tuple[str, ...]
    professional_channels: tuple[str, ...]
    attention_priority: float
    is_critical: bool
```

写入规则固定如下：

- `npc_action`：执行后的 actor location；actor 及 NPC target 为 participant；同地点 NPC ID 作为 witness snapshot；scope=`location`；priority=`0.25`；非关键。
- `player_travelled`：目标地点；该地点 NPC 作为 witness snapshot；scope=`location`；priority=`0.35`；非关键。
- `quest_transitioned`：交互地点；`required_npc_id` 若存在则为 participant；同地点 NPC 为 witness snapshot；`inspect_shoe/search_child/return_child` 为关键；对应 priority 为 `0.9/1.0/1.0`，其他为 `0.6`。
- `inspect_shoe` 增加 `scout_network`，`search_child/return_child` 增加 `town_guard` professional channel；角色渠道映射只在 Perception Registry 定义，来源只保存渠道名。

所有 ID 集合在保存前去重并按 ID 排序。不得从 `description` 文本提取地点、参与者或权限。

ChatService 在调用 Repository 前生成一个 UUID `turn_id`，并从已组装的权威 context 传递 `world_version/world_time`；两个 Message 仍在现有单一事务内提交。现有 Chat Response 不增加字段。

- [ ] **Step 6：写 Seed/Reset RED 测试**

新增固定三 NPC 最小知识 fixture，断言：

```python
assert seed.authored_knowledge_version == "stage2-v1"
assert {item.owner_npc_id for item in seed.authored_knowledge} == {
    "ryan", "shir", "grey"
}
assert all(item.source_id and item.safe_summary for item in seed.authored_knowledge)
```

Reset 测试先创建第二 World 的 cognition 哨兵，再 reset `aleria-town`，断言目标 World 六表按 FK 顺序清理、authored knowledge 恰好重建一次、第二 World 未变化。`ensure_demo_world` 在 World 已存在时不得删除或重播 cognition。

运行 Seed/Reset 新测试确认 RED：

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_demo_reset_api.py \
  tests/backend/test_seed_world.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task1-seed-red
```

Expected：因 authored knowledge schema/文件或 cognition Reset 行为尚未实现而失败；完成 Step 7 后重跑并转 GREEN。

- [ ] **Step 7：实现版本化 authored knowledge 和 Reset 顺序**

`data/agent_knowledge.json` 使用以下顶层形状，内容只覆盖 Grey 演示与三 NPC 隔离，不写 Forest Embers 完整秘密：

```json
{
  "version": "stage2-v1",
  "items": [
    {
      "source_id": "grey-ash-war-caution",
      "owner_npc_id": "grey",
      "content": "Grey 亲历过灰烬战争，但残存记录不足以证明所有传闻。",
      "safe_summary": "Grey 对灰烬战争有谨慎且有来源限制的认识。",
      "secrecy": "private",
      "disclosure_scope": "player_dialogue",
      "importance": 0.7,
      "confidence": 0.8,
      "emotional_valence": -0.4,
      "occurred_world_version": 0,
      "occurred_clock_tick": 0,
      "occurred_world_time": "08:00",
      "source_created_at": "2026-09-09T00:00:00Z"
    }
  ]
}
```

每位 NPC 至少一条、总数保持最小。`load_seed_data()` 同时读取该文件并验证 owner 存在。Reset 删除顺序：`belief_evidence → beliefs → memory_evidence → memories → observations → agent_cognition_states`，再删除旧来源记录，最后重建 World 与 authored knowledge；整个显式 Reset 仍为一个事务。普通 `ensure_demo_world` 已存在路径不写 cognition。

- [ ] **Step 8：运行 Task 1 GREEN 和回归**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_schema_migrations.py \
  tests/backend/test_cognition_models.py \
  tests/backend/test_chat_repository.py \
  tests/backend/test_chat_models.py \
  tests/backend/test_chat_service.py \
  tests/backend/test_npc_chat_api.py \
  tests/backend/test_agent_run_repository.py \
  tests/backend/test_world_clock.py \
  tests/backend/test_player_quest_repository.py \
  tests/backend/test_demo_reset_api.py \
  tests/backend/test_seed_world.py \
  -q -rs -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task1-green
```

Expected：零失败；未设置 `TEST_POSTGRES_URL` 时只允许明确标注的 PostgreSQL skip。

- [ ] **Step 9：Task 1 Review Gate**

检查 `git diff --check`、`git status --short`、`git diff --cached --quiet`、`git rev-parse HEAD`；确认 HEAD 仍为 Task 开始时的提交，暂存区为空，legacy 行未伪造来源，Public API 快照未改变。独立 Reviewer 清零 Critical/Important 后停止并等待用户 Review。

建议用户提交信息：`feat: add stage 2 cognition schema and source metadata`

---

### Task 2：实现确定性感知、注意力与幂等核心投影

**Files：**

- Modify: `backend/app/agents/cognition_contracts.py`
- Create: `backend/app/agents/perception.py`
- Create: `backend/app/database/cognition_repository.py`
- Create: `backend/app/services/cognition_projection.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/world_clock_service.py`
- Modify: `backend/app/services/player_quest_service.py`
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/api/world_clock.py`
- Modify: `backend/app/api/player.py`
- Modify: `backend/app/api/quests.py`
- Modify: `backend/app/api/npc_chat.py`
- Create: `tests/backend/test_perception_policy.py`
- Create: `tests/backend/test_cognition_repository.py`
- Create: `tests/backend/test_cognition_projection.py`
- Create: `tests/backend/test_cognition_config.py`
- Modify: `tests/backend/test_chat_service.py`
- Modify: `tests/backend/test_world_clock.py`
- Modify: `tests/backend/test_player_quest_service.py`

**Interfaces：**

- Produces: `PerceptionPolicyRegistry.project_event/project_turn`、`CognitionProjectionService.catch_up_owner/catch_up_world`
- Atomic core: Observation + Memory + Checkpoint 单事务
- Failure boundary: source commit 已完成后认知失败只记录安全分类，不改变来源 API 成功结果

- [ ] **Step 1：写 Perception Registry RED 测试**

构造同一 Event 对 Grey/Ryan/Shir 的矩阵，至少覆盖 participant、witness、professional、secret 和 budget exclusion：

```python
drafts = registry.project_event(event, npc_profiles)
assert [(draft.owner_npc_id, draft.perception_mode) for draft in drafts] == [
    ("grey", PerceptionMode.PARTICIPANT),
    ("shir", PerceptionMode.PROFESSIONAL_CHANNEL),
]
assert all(draft.source_key == f"event:{event.id}" for draft in drafts)
assert all(draft.policy_version == "perception-v1" for draft in drafts)
assert "player_claim" not in drafts[0].facts
```

Conversation Turn 测试必须断言只产生目标 NPC 的 `DIRECT_DIALOGUE`，facts 分开保存 `speaker_kind=player`、`claim_text`、`npc_reply`，安全摘要不复制原文。Registry 传入未知 event type、缺失历史元数据或不完整 Turn 时返回空集/安全拒绝，不猜测。

- [ ] **Step 2：运行 Perception 测试确认 RED**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_perception_policy.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task2-perception-red
```

- [ ] **Step 3：实现纯函数 Registry 与稳定 Draft**

核心契约必须是冻结对象：

```python
@dataclass(frozen=True)
class ObservationDraft:
    owner_npc_id: str
    source_kind: SourceKind
    source_key: str
    policy_version: str
    perception_mode: PerceptionMode
    summary: str
    facts: Mapping[str, JsonValue]
    related_entity_ids: tuple[str, ...]
    secrecy: Literal["public", "private", "secret"]
    disclosure_scope: Literal["public", "player_dialogue", "internal_only"]
    importance: float
    confidence: float
    emotional_valence: float
    is_critical: bool
```

角色职业渠道固定为：

```python
ROLE_CHANNELS = {
    "Knight": frozenset({"town_guard"}),
    "Guardian": frozenset({"town_guard", "archive_guardian"}),
    "Assassin": frozenset({"scout_network"}),
}
```

优先级顺序为 participant、critical、attention_priority 降序、event_sequence 升序、source_key 升序。单来源每 NPC 最多一条 Observation；同批每 NPC 默认最多 12 条。观察被预算排除时不保存隐形记录。

- [ ] **Step 4：写核心投影事务与幂等 RED 测试**

覆盖：

```python
first = projector.catch_up_owner("aleria-town", "grey")
second = projector.catch_up_owner("aleria-town", "grey")

assert first.created_memories > 0
assert second.created_memories == 0
assert count_observations(session, owner="grey") == first.created_observations
assert state.last_event_sequence == source_upper_event_sequence
assert state.last_conversation_message_id == source_upper_message_id
```

故障注入在 Observation flush 后抛出异常，断言 Observation、Memory 和 Checkpoint 全部回滚；重新调用产生完整且不重复的结果。Ryan 的失败不得回滚 Grey 已提交的 owner transaction。legacy null 来源只能推动已扫描游标，不能生成 Memory。

运行确认 RED：

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_cognition_repository.py \
  tests/backend/test_cognition_projection.py \
  tests/backend/test_cognition_config.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task2-projection-red
```

- [ ] **Step 5：实现 Repository 和每 owner 有界事务**

`CognitionRepository` 暴露窄接口：

```python
class CognitionRepository:
    def get_or_create_state(self, world_id: str, owner_npc_id: str) -> AgentCognitionState: ...
    def load_source_batch(self, state: AgentCognitionState, *, event_limit: int, turn_limit: int) -> SourceBatch: ...
    def persist_core_projection(self, state: AgentCognitionState, drafts: tuple[ObservationDraft, ...]) -> ProjectionResult: ...
    def list_npc_ids(self, world_id: str) -> tuple[str, ...]: ...
```

每个 Draft 的 Observation UUID 和 Memory UUID 使用 `uuid5` 从 `world_id/owner/source_key/policy_version` 稳定派生；数据库 UNIQUE 仍是最终幂等防线。episodic/conversation Memory 从 Observation 生成，保留 source time 和 claim speaker，初始 `embedding_status="unavailable"`。Checkpoint 上界只到本次实际扫描批次的末端，不跳过尚未扫描积压。

同一核心事务还要把新 Memory 的 importance/count 累加到 cognition state，并在任一 Draft 为关键时设置 `reflection_pending_critical=1`；只有成功 Reflection 才清零这些字段。`last_reflection_source_created_at + last_reflection_source_memory_id` 构成服务重启后稳定的来源游标。

Task 2 即引入有界配置，后续 Task 复用同一 deadline：

```python
cognition_source_batch_size: int = Field(default=25, ge=1, le=100)
cognition_attention_budget: int = Field(default=12, ge=1, le=50)
cognition_post_commit_budget_seconds: float = Field(default=5.0, gt=0, le=30)
```

`CognitionProjectionService` 在入口用可注入 monotonic clock 计算 deadline；每个 owner、下一批来源和后续 enrichment 前检查预算，耗尽就安全停止并保留游标，不启动超出预算的新工作。单次已开始的 Provider 调用仍受自身更短 timeout 约束。

单 owner 内只提交一次：

```python
try:
    result = repository.persist_core_projection(state, drafts)
    session.commit()
except SQLAlchemyError:
    session.rollback()
    raise CognitionProjectionError("cognition projection unavailable") from None
```

- [ ] **Step 6：写 post-commit 失败隔离 RED 测试**

给 Tick、Travel、Quest、Chat Service 注入抛错 projector，断言：来源 API/Service 仍返回原成功结果、对应 Event/Turn 已提交、世界计数只按原行为变化、认知表无半条数据。再用正常 projector catch-up，断言能补偿同一来源。

运行新失败隔离测试确认 RED：

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_chat_service.py \
  tests/backend/test_world_clock.py \
  tests/backend/test_player_quest_service.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task2-hooks-red
```

- [ ] **Step 7：接入来源提交后的最佳努力协调**

Service 构造器接受可选 `CognitionProjectionService`，生产路由显式提供，旧单元测试可用 `None`。调用顺序固定：

```python
persisted = source_repository.commit_existing_source(...)
try:
    cognition.catch_up_world(persisted.world_id)
except CognitionProjectionError:
    logger.warning("Post-commit cognition projection failed", extra={"category": "core_projection"})
return existing_public_result(persisted)
```

Chat 只在完整 Turn 提交后 `catch_up_owner(context.world_id, npc_id)`；不得在 Provider 生成当前回复前投影当前玩家消息。每次 World catch-up 按 NPC `sort_order,id` 顺序且每 NPC 独立事务。

- [ ] **Step 8：运行 Task 2 GREEN 和 Backend 回归**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_perception_policy.py \
  tests/backend/test_cognition_repository.py \
  tests/backend/test_cognition_projection.py \
  tests/backend/test_cognition_config.py \
  tests/backend/test_chat_service.py \
  tests/backend/test_world_clock.py \
  tests/backend/test_player_quest_service.py \
  tests/backend/test_agent_run_repository.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task2-green
```

- [ ] **Step 9：Task 2 Review Gate**

确认 Registry 不读取自由文本来决定权限，Checkpoint 与核心投影同事务，认知失败不改变来源结果，Run Graph 数量/顺序不变。执行 Git Gate 和独立双 Review，停止等待用户。

建议用户提交信息：`feat: project authoritative sources into npc memories`

---

### Task 3：实现 Embedding、权限优先 Hybrid Retrieval 与跨会话 Chat

**Files：**

- Create: `backend/app/llm/embedding_provider.py`
- Create: `backend/app/agents/memory_retrieval.py`
- Modify: `backend/app/database/cognition_repository.py`
- Modify: `backend/app/services/cognition_projection.py`
- Modify: `backend/app/services/chat_context.py`
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/llm/types.py`
- Modify: `backend/app/llm/openai_compatible.py`
- Modify: `backend/app/llm/mock.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/app/api/npc_chat.py`
- Modify: `backend/app/main.py`
- Modify: `.env.example`
- Modify: `.env.production.example`
- Create: `tests/backend/test_embedding_provider.py`
- Create: `tests/backend/test_memory_retrieval.py`
- Modify: `tests/backend/test_chat_context.py`
- Modify: `tests/backend/test_openai_compatible_provider.py`
- Modify: `tests/backend/test_mock_chat_provider.py`
- Create: `tests/backend/test_stage2_chat_memory.py`
- Modify: `tests/backend/test_chat_config.py`

**Interfaces：**

- Produces: `EmbeddingProvider.embed(text) -> EmbeddingResult`
- Produces: `MemoryRetriever.retrieve(request) -> RetrievalResult`
- Extends internally: `ChatProviderRequest.long_term_memories`; Chat Public API 不变
- Default: deterministic fake embedding；live provider 仅显式配置

- [ ] **Step 1：写 Embedding Provider RED 测试**

固定输入必须跨调用得到相同、有限、归一化的 32 维向量；不同文本不得相同。OpenAI-compatible adapter 测试 `/embeddings` payload、bearer/none auth、短超时、维度/NaN/shape 错误，并确认错误消息不含正文或 Key。

```python
result = DeterministicEmbeddingProvider(dimensions=32).embed("蓝色羽毛")
assert result.dimensions == 32
assert result.provider == "deterministic-fake"
assert result.input_hash == sha256(normalize("蓝色羽毛").encode()).hexdigest()
assert all(math.isfinite(value) for value in result.vector)
```

运行确认 RED：

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_embedding_provider.py \
  tests/backend/test_chat_config.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task3-embedding-red
```

- [ ] **Step 2：实现独立 Provider、工厂与受控配置**

配置字段固定为：

```python
embedding_provider: Literal["fake", "openai_compatible"] = "fake"
embedding_base_url: str = ""
embedding_api_key: str = ""
embedding_model: str = ""
embedding_auth_mode: Literal["bearer", "none"] = "bearer"
embedding_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
embedding_dimensions: int = Field(default=32, ge=8, le=4096)
cognition_enrichment_batch_size: int = Field(default=12, ge=1, le=50)
memory_chat_limit: int = Field(default=6, ge=1, le=12)
memory_chat_char_budget: int = Field(default=1600, ge=200, le=8000)
```

Fake 算法对 casefold/NFKC 后的单词、中文字符和中文 bigram 做稳定 SHA-256 feature hashing，再 L2 normalize；不使用 Python 随机 hash。OpenAI-compatible 模式只有 base URL、model 及认证配置完整时启用，否则安全回退 Fake 并记 provider category，不阻断启动。

- [ ] **Step 3：写权限过滤与排序 RED 测试**

固定 Memory 集合包含 relevant、irrelevant、recent、important、low-confidence、disputed、superseded、secret、future 和 cross-owner。用 spying semantic scorer 证明不可见 ID 从未进入相似度调用：

```python
result = retriever.retrieve(RetrievalRequest(
    world_id="aleria-town",
    owner_npc_id="grey",
    current_world_version=7,
    current_clock_tick=9,
    query_text="蓝色羽毛",
    scope=RetrievalScope.PLAYER_DIALOGUE,
    allowed_memory_types=frozenset(MemoryType),
    limit=6,
    char_budget=1600,
))
assert secret_memory.id not in semantic_spy.seen_ids
assert future_memory.id not in semantic_spy.seen_ids
assert result.memory_ids == expected_order
assert result.scoring_version == "hybrid-v1"
```

另测 Embedding space 不同、query embedding 失败、pgvector 失败时 mode=`lexical_fallback`，仍执行同一硬过滤和稳定 ID tie-break。文本预算按 Python Unicode 字符裁剪，不截断单条摘要。

运行确认 RED：

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_memory_retrieval.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task3-retrieval-red
```

- [ ] **Step 4：实现 Repository 候选边界和确定性排序**

权限矩阵固定为：

```python
SCOPE_RULES = {
    RetrievalScope.PLAYER_DIALOGUE: ScopeRule(
        secrecy=frozenset({"public", "private"}),
        disclosure=frozenset({"public", "player_dialogue"}),
        lifecycle=frozenset({"active", "disputed"}),
    ),
    RetrievalScope.INTERNAL_REFLECTION: ScopeRule(
        secrecy=frozenset({"public", "private", "secret"}),
        disclosure=frozenset({"public", "player_dialogue", "internal_only"}),
        lifecycle=frozenset({"active", "disputed"}),
    ),
    RetrievalScope.PUBLIC_EXPLANATION: ScopeRule(
        secrecy=frozenset({"public"}),
        disclosure=frozenset({"public"}),
        lifecycle=frozenset({"active", "disputed"}),
    ),
}
```

SQL/ORM 查询先过滤 world、owner、时间线、类型、scope 与 lifecycle。SQLite 只对返回的 allowed rows 在 Python 算 cosine；PostgreSQL semantic 分支必须把同样硬过滤放在含 `embedding <=> CAST(:query_vector AS vector)` 的 SQL 内，且限定 provider/model/version/dimensions/input status。不得先全库向量召回再过滤。

评分严格实现 Spec 的两组权重、`0.95 ** delta_tick`、disputed `0.85` 因子，最终按 `(-score, memory.id)`。选择后只有 Chat/Reflection scope 最佳努力更新 access telemetry；`PUBLIC_EXPLANATION` 保持 HTTP GET 只读。

- [ ] **Step 5：把新 Memory 做成可失败 enrichment**

`CognitionProjectionService` 在核心投影提交后调用 `EmbeddingEnrichmentService.enrich_pending(world_id, owner_npc_id, limit)`。每条 Memory 使用短事务更新：成功写完整 embedding metadata + `ready`；失败只写 `failed/unavailable`，不删除 Memory、不回退 Checkpoint、不影响后续来源。

同一 provider/model/version/dimensions 和 input hash 已 ready 时跳过；内容或 space 改变才允许重建。

- [ ] **Step 6：写 Chat 长期记忆 RED 测试**

为 capturing provider 断言上下文顺序与去重：

```python
assert request.conversation_history == recent_two_messages
assert request.long_term_memories[0].source_label == "player_claim"
assert "蓝色羽毛" in request.long_term_memories[0].content
assert active_history_turn_id not in {
    item.source_turn_id for item in request.long_term_memories
}
```

完整验收测试：第一实例与 Grey 提供“蓝色羽毛”线索；继续超过 `chat_history_limit`；销毁并用同一 SQLite 文件创建第二实例；下一轮询问时 provider 仍收到该 conversation Memory。另断言新消息本身不在当前 provider request，只在 Turn 提交后成为下轮候选。

运行确认 RED：

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_stage2_chat_memory.py \
  tests/backend/test_chat_context.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task3-chat-red
```

- [ ] **Step 7：扩展内部 ChatContext 和 Provider 渲染**

新增：

```python
@dataclass(frozen=True)
class ChatMemoryContext:
    memory_id: str
    memory_type: str
    source_label: Literal[
        "authored_knowledge", "observed_event", "player_claim", "reflection"
    ]
    content: str
    occurred_clock_tick: int
    source_turn_id: str | None
```

`ChatContextAssembler` 在读取权威 NPC/World/Quest 与短期 History 后，以当前玩家消息检索 `PLAYER_DIALOGUE`；排除活跃 Conversation 最近 History 中所有非空 `turn_id`。失败返回 `long_term_memories=()` 和安全状态，不阻断 Chat。

OpenAI-compatible system message 增加独立 `[Retrieved NPC memories; non-authoritative]` 段，每条含类型/来源标签/发生 tick；明确 player claim 不是 world fact。Mock Provider 在“还记得/之前的线索”意图下只使用检索结果，并用“你之前说过/我仍把它视为你的说法”措辞证明跨轮次闭环，不把 Claim 升级为事实。

- [ ] **Step 8：运行 Task 3 GREEN 和 Chat 回归**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_embedding_provider.py \
  tests/backend/test_memory_retrieval.py \
  tests/backend/test_stage2_chat_memory.py \
  tests/backend/test_chat_context.py \
  tests/backend/test_chat_service.py \
  tests/backend/test_mock_chat_provider.py \
  tests/backend/test_openai_compatible_provider.py \
  tests/backend/test_chat_acceptance.py \
  tests/backend/test_npc_chat_api.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task3-green
```

- [ ] **Step 9：Task 3 Review Gate**

确认 hard filter 在 semantic 前、不同向量空间不比较、fallback 不扩权、当前消息只影响下一轮、Chat Public Contract 未变化。执行 Git Gate 和独立双 Review后停止。

建议用户提交信息：`feat: add permission-aware memory retrieval to npc chat`

---

### Task 4：实现证据约束 Reflection 与追加式 Belief

**Files：**

- Create: `backend/app/llm/reflection_provider.py`
- Create: `backend/app/agents/reflection.py`
- Modify: `backend/app/agents/cognition_contracts.py`
- Modify: `backend/app/database/cognition_repository.py`
- Modify: `backend/app/services/cognition_projection.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/app/main.py`
- Modify: `.env.example`
- Modify: `.env.production.example`
- Create: `tests/backend/test_reflection_provider.py`
- Create: `tests/backend/test_reflection_engine.py`
- Modify: `tests/backend/test_cognition_repository.py`
- Modify: `tests/backend/test_cognition_projection.py`
- Modify: `tests/backend/test_chat_context.py`

**Interfaces：**

- Produces: `ReflectionProvider.reflect(request) -> ReflectionDraft`
- Produces: `ReflectionEngine.enrich_if_due(world_id, owner_npc_id)`
- Persists atomically: reflection Memory + memory evidence + optional Belief version + belief evidence
- Preserves: Reflection/Belief 只作为 NPC cognition，不进入 Event/Action/Run Graph

- [ ] **Step 1：写触发和 evidence fingerprint RED 测试**

覆盖默认阈值 `2.0`、至少三条新 Memory、关键事件绕过、相同 evidence 指纹不重复、同指纹失败只自动重试一次：

```python
assert engine.is_due(state_with(importance=1.99, count=3, critical=False)) is False
assert engine.is_due(state_with(importance=2.0, count=3, critical=False)) is True
assert engine.is_due(state_with(importance=0.2, count=1, critical=True)) is True
assert engine.should_attempt(fingerprint, failed_attempts=2) is False
```

Fingerprint 为按 Memory ID 排序后以 `\n` 连接的 SHA-256；不得包含文本或非确定性时间。

- [ ] **Step 2：写 Draft 安全验证 RED 测试**

合法 fixture 生成一条 reflection Memory、至少一条 evidence edge 和可选 Belief。分别拒绝：空 evidence、虚构 ID、未提供候选、跨 NPC、跨 World、未来版本、superseded evidence、非法 confidence、超长 insight，以及 `supersedes_belief_id` 不在 Provider 输入 current beliefs。

每个拒绝用例都断言：

```python
assert count(ReflectionMemory) == 0
assert count(MemoryEvidence) == 0
assert count(Belief) == 0
assert world_counters(session) == counters_before
assert run_graph_counts(session) == graph_before
```

运行触发与 Draft 验证测试确认 RED：

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_reflection_provider.py \
  tests/backend/test_reflection_engine.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task4-red
```

- [ ] **Step 3：实现 Provider 契约、Fake 与 OpenAI-compatible adapter**

结构化契约：

```python
class ReflectionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    insight: str = Field(min_length=1, max_length=800)
    confidence: float = Field(ge=0, le=1)
    evidence_memory_ids: tuple[UUID, ...] = Field(min_length=1, max_length=12)
    belief: BeliefDraft | None = None
    provider: str
    model: str
    prompt_version: Literal["reflection-v1"]
```

Fake Provider 只从传入候选 ID 构造稳定结果；OpenAI-compatible adapter 使用独立配置、严格 JSON、temperature 0、3 秒默认超时。配置：

```python
reflection_provider: Literal["fake", "openai_compatible"] = "fake"
reflection_base_url: str = ""
reflection_api_key: str = ""
reflection_model: str = ""
reflection_auth_mode: Literal["bearer", "none"] = "bearer"
reflection_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
reflection_importance_threshold: float = Field(default=2.0, ge=0, le=50)
reflection_min_new_memories: int = Field(default=3, ge=1, le=50)
reflection_memory_limit: int = Field(default=12, ge=1, le=20)
reflection_char_budget: int = Field(default=4000, ge=500, le=12000)
```

配置不完整时回退 Fake；live provider 不成为普通 CI 前提。

- [ ] **Step 4：实现触发、内部检索和严格验证**

`ReflectionEngine` 先用 `INTERNAL_REFLECTION` 检索最多 12 条/4000 字符候选，再生成 fingerprint，并把 candidate IDs 和 current belief IDs 固定为验证白名单。任何 Provider 文本都不能决定 owner、world、source time、lifecycle 或权限。

```python
candidate_ids = frozenset(item.memory_id for item in retrieval.items)
if not set(draft.evidence_memory_ids) <= candidate_ids:
    raise ReflectionValidationError("reflection evidence is invalid")
```

Repository 在一个事务中重新加载并锁定 evidence/current belief，重复校验同 world/owner/time/lifecycle，随后创建 reflection Memory 与 edge。Belief 若修订旧观点：创建新行、旧行标记 `superseded` 或 `disputed`、`supersedes_belief_id` 指向旧行；不覆盖旧 statement/evidence。supporting/contradicting edge 均只能引用白名单 Memory。

Reflection Memory 的 occurred/created version、tick、world time 与 UTC created time 由 Repository 在持久化时读取的权威 World 和服务器时钟填写，不能采用 Provider 返回值；所有 evidence 的发生版本必须不晚于该基准。成功后把本批新来源中最大的 `(created_at, memory_id)` 写入 state 的 reflection source cursor。

- [ ] **Step 5：实现成功状态和有限失败状态**

成功后 state 清零累计 importance/count，写 `last_reflection_evidence_fingerprint`，attempt 状态为 `succeeded`。Provider/validation/db 失败不得生成半条 derived 数据；用独立短事务把同 fingerprint attempt count 加一并标 `failed`。count 达 2 后同 fingerprint 跳过，只有新 Memory 改变 fingerprint 才重新尝试。

Reflection enrichment 放在 core projection 和 embedding enrichment 之后；其异常只记录安全 category，不向 Tick/Quest/Chat 冒泡。

- [ ] **Step 6：写 Chat 中 Reflection/Belief 权限 RED 测试**

验证 `player_dialogue` 只看到允许披露的 reflection safe content；`secret/internal_only` reflection 与 Belief statement 不进入 ChatProvider。Stage 2 Chat 可读取 reflection Memory，但不直接注入 Belief 全文；Belief 主要留给 Stage 3 deliberation。

- [ ] **Step 7：运行 Task 4 GREEN 和认知回归**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_reflection_provider.py \
  tests/backend/test_reflection_engine.py \
  tests/backend/test_cognition_repository.py \
  tests/backend/test_cognition_projection.py \
  tests/backend/test_memory_retrieval.py \
  tests/backend/test_chat_context.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task4-green
```

- [ ] **Step 8：Task 4 Review Gate**

确认 derived 数据可追溯、Provider 不能伪造 evidence、Belief 为追加版本、两次失败后不会热循环、所有世界/Run Graph 计数未变化。执行 Git Gate 和独立双 Review后停止。

建议用户提交信息：`feat: add evidence-bound reflection and beliefs`

---

### Task 5：交付安全解释 UI、双数据库验收与 Stage 2 文档

**Files：**

- Create: `backend/app/services/memory_explanation.py`
- Modify: `backend/app/schemas/npc.py`
- Modify: `backend/app/api/npcs.py`
- Modify: `frontend/src/types/npc.ts`
- Modify: `frontend/src/api/npc.ts`
- Create: `frontend/src/stores/npcMemory.ts`
- Modify: `frontend/src/components/NpcDetailPanel.vue`
- Modify: `frontend/src/views/TownView.vue`
- Create: `tests/backend/test_memory_explanation_service.py`
- Modify: `tests/backend/test_npc_api.py`
- Create: `tests/backend/test_stage2_acceptance.py`
- Modify: `tests/backend/test_postgres_runtime.py`
- Create: `tests/frontend/npcMemory.spec.ts`
- Modify: `tests/frontend/NpcDetailPanel.spec.ts`
- Modify: `tests/frontend/TownView.spec.ts`
- Create: `tests/frontend/stage2Acceptance.spec.ts`
- Modify: `docs/05_Engineering_Architecture.md`
- Modify: `docs/06_API_Contract.md`
- Modify: `docs/07_Database_Schema.md`
- Modify: `docs/14_Development_Environment.md`
- Modify: `README.md`

**Interfaces：**

- Produces: `GET /api/npcs/{npc_id}/memory-explanations`
- UI: NPC Detail 内默认折叠、最多五条、安全失败隔离
- Acceptance: SQLite 重启闭环 + PostgreSQL pgvector 真实查询 + 全量前后端回归

- [ ] **Step 1：写 API Schema/Service RED 测试**

Pydantic DTO 固定为：

```python
class MemoryExplanationSource(BaseModel):
    kind: Literal["world_event", "conversation", "authored_knowledge", "reflection"]
    label: str = Field(min_length=1, max_length=40)

class MemoryExplanationItem(BaseModel):
    id: UUID
    type: Literal["episodic", "conversation", "reflection", "knowledge"]
    summary: str = Field(min_length=1, max_length=240)
    occurred_clock_tick: int = Field(ge=0)
    source: MemoryExplanationSource
    reason_text: str = Field(min_length=1, max_length=120)

class NpcMemoryExplanationsData(BaseModel):
    npc_id: str
    retrieval_mode: Literal["hybrid", "lexical_fallback"]
    fallback_used: bool
    memories: list[MemoryExplanationItem] = Field(max_length=5)
```

Service 测试构造 public、private conversation、secret reflection、cross-owner 和记忆，断言 Repository 在 `PUBLIC_EXPLANATION` hard filter 后只返回 public；不可见内容不产生占位、总数或差异错误。Conversation 对外 summary 固定映射为“这位居民记得与你有过一次相关交谈。”，不使用 `content` 或玩家原文。

运行确认 RED：

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_memory_explanation_service.py \
  tests/backend/test_npc_api.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-task5-api-red
```

- [ ] **Step 2：实现固定情境查询与 API**

`MemoryExplanationService` 使用当前 NPC detail + 当前公开 Quest objective/location 组合查询，不接收 query、owner、scope、limit 或 secrecy 参数。读取前可执行一次有界 `catch_up_owner`；失败返回安全 503，不返回内部错误。

路由：

```python
@router.get(
    "/api/npcs/{npc_id}/memory-explanations",
    response_model=ApiResponse[NpcMemoryExplanationsData],
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_npc_memory_explanations(...): ...
```

API 最多五条，`reason_text` 由已选择的公开评分分量确定性映射为有限模板，不返回数字分数。Npc 不存在沿用 404 风格；认知读取错误统一 503。

- [ ] **Step 3：写前端 Store/Component RED 测试**

覆盖 API URL encoding/envelope、404/普通错误、切换 NPC 时迟到响应、关闭失效、详情成功但记忆失败仍显示详情、默认折叠、空/加载/fallback 状态、来源标签与 tick。

```ts
expect(wrapper.get('button[aria-expanded="false"]').text()).toContain('相关记忆')
await wrapper.get('button').trigger('click')
expect(wrapper.text()).toContain('亲历的世界事件')
expect(wrapper.text()).not.toContain('玩家原始秘密文本')
```

运行确认 RED：

```bash
npm --prefix frontend test -- \
  tests/frontend/npcMemory.spec.ts \
  tests/frontend/NpcDetailPanel.spec.ts \
  tests/frontend/TownView.spec.ts
```

Expected：因 Memory 类型/API/Store/UI 尚不存在或未接线而失败。

- [ ] **Step 4：实现独立 Memory Store 和折叠 UI**

`useNpcMemoryStore` 独立维护 `selectedNpcId/data/loading/error/requestVersion`，避免 Memory API 失败污染 `useNpcDetailStore`。`TownView.selectNpc()` 同时触发两次独立读取；Tick/Quest/Chat 成功后只对当前选中 NPC 最佳努力 refresh Memory。关闭和 Demo Reset 清理两个 Store。

`NpcDetailPanel` 新增 memory props 和 `retry-memory` 事件，在 detail content 内加入 `<section>`；使用原生 button 的 `aria-expanded/aria-controls`，默认 `false`。折叠时仍可显示简短可用/不可用状态，但不渲染列表正文。标签固定：亲历事件、听到的说法、稳定知识、形成的看法；不得显示内部 belief、score、vector 或 error code。

- [ ] **Step 5：写端到端 Stage 2 RED/验收测试**

`tests/backend/test_stage2_acceptance.py` 必须通过 HTTP 完成：

1. Reset Demo。
2. 与 Grey 提供独特线索。
3. 追加足够对话让该 Turn 离开短期 History。
4. 销毁 app/engine，使用同一 SQLite 文件创建新 app。
5. 再询问 Grey，断言 Mock 回复引用线索且称其为玩家说法。
6. 查询解释接口，断言不返回该私有对话原文。
7. 推进 Tick/Quest，断言 public episodic Memory 可解释。
8. 注入 Embedding/Reflection failure，断言 Chat/Tick/Quest 仍成功。
9. 断言三套世界计数与 Foundation Run Graph 保持语义不变。

前端 acceptance 挂载 `TownView`，模拟 Memory API 失败与 fallback，确认地图、详情、Chat、Tick 和 Quest 控件仍工作。

- [ ] **Step 6：完成 PostgreSQL/pgvector 真实测试**

扩展 opt-in PostgreSQL 测试：迁移到 `0004`、Reset、写入 ready Embedding、执行带硬过滤的 `<=>` 查询、验证稳定集合，再把 provider 设置为失败并验证 lexical fallback。测试必须使用现有随机隔离 schema fixture；不得指向业务 public schema。

```bash
export POSTGRES_PASSWORD='aleria-test-only'
export TEST_POSTGRES_PORT='55432'
docker compose -p aleria-stage2-postgres \
  -f compose.yaml -f compose.postgres-test.yaml \
  --env-file .env.production.example up -d --wait --wait-timeout 120 db

export TEST_POSTGRES_URL='postgresql+psycopg://aleria:aleria-test-only@127.0.0.1:55432/aleria'
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_schema_migrations.py \
  tests/backend/test_postgres_runtime.py \
  -q -rs -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-postgres

docker compose -p aleria-stage2-postgres \
  -f compose.yaml -f compose.postgres-test.yaml \
  --env-file .env.production.example down
unset TEST_POSTGRES_URL TEST_POSTGRES_PORT POSTGRES_PASSWORD
```

Docker 不可用时记录真实阻塞，不得宣称 pgvector 已验证；保留 SQLite 完整结果并等待用户决定环境处理。

- [ ] **Step 7：更新四份权威文档和 README**

文档必须与实现逐字段一致：

- Architecture：权威来源 → post-commit cognition、per-owner checkpoint、core/enrichment 边界、Stage 3 LangGraph 接口。
- API Contract：新增 GET 的完整 envelope、404/503、最多五条和隐私边界；现有 Chat/Tick 契约不变。
- Database Schema：`0004` 六表、Event/Message 新列、所有 CHECK/UNIQUE/FK/索引、SQLite JSON/Postgres vector 差异、legacy null 策略。
- Development Environment：Fake 默认、live Embedding/Reflection 环境变量、PostgreSQL test 安全边界与 Smoke 命令。
- README：最短演示脚本——向 Grey 提供独特线索、超过短 history、重启、再次询问、展开相关记忆；说明 Claim 不是事实。

- [ ] **Step 8：运行完整验证矩阵**

```bash
./.venv/Scripts/python.exe -m pytest tests/backend \
  -q -rs -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/stage2-backend-full

npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build

docker-compose.exe --env-file .env.production.example config --quiet
docker-compose.exe -f compose.yaml -f compose.postgres-test.yaml \
  --env-file .env.production.example config --quiet
```

Expected：Backend/Frontend/type-check/build/Compose 全部零失败；无 Key 的默认模式完全工作。已有 Phaser 大 Chunk 警告可记录但不是阻塞项。Live Embedding/Reflection 只在用户提供独立测试配置时做手动 Smoke，未执行不得写成通过。

- [ ] **Step 9：最终范围、隐私与 Git Gate**

执行：

```bash
git diff --check
git status --short
git diff --cached --quiet
git rev-parse HEAD
rg -n "TODO|TBD|placeholder|pass$|NotImplemented" \
  backend/app tests/backend frontend/src tests/frontend \
  docs/05_Engineering_Architecture.md docs/06_API_Contract.md \
  docs/07_Database_Schema.md docs/14_Development_Environment.md README.md
```

人工审计：

- 所有 Memory 可追溯 source/evidence 与发生时间。
- 所有 retrieval 先过滤后相似度；Public GET 不泄露存在性。
- Player Claim 在数据库、Prompt、Mock 回复和文档中始终是 Claim。
- 任意 cognition/provider 故障不改变权威来源成功语义。
- 没有 Goal/Plan/LLM Action/LangGraph/LangChain/Social/Agent Lab/MCP 越界。
- 暂存区为空，HEAD 未被代理改变。

- [ ] **Step 10：Task 5 Review Gate、独立 Review 与用户交付**

Spec reviewer 逐项核对 Stage 2 Spec 第 3–21 节；code-quality reviewer 检查事务、权限、隐私、双数据库差异、失败降级和测试可信度。Critical/Important 清零后给用户简洁中文 Review 报告并停止。

建议用户提交信息：`feat: complete stage 2 perception memory and reflection`

---

## Stage 2 完成后的边界

用户 Review 并手动提交 Task 5 后，Stage 2 才算完成。下一步另写 Stage 3 独立中文 Spec；Stage 3 以 LangGraph 同步编排 Goal → Plan → typed ActionProposal，但必须复用本阶段的权限过滤 Memory/Belief 和现有 Action Registry，不得在 Stage 2 实现中提前埋入不可验证的 LLM 行动路径。
