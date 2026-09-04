# Aleria AI Town AI-Native Agent RPG Runtime Design

**Date:** 2026-09-04  
**Status:** Proposed for implementation planning  
**Scope:** Agent runtime, memory, planning, multi-agent social behavior, RPG integration, observability, evaluation, and production execution

## 1. Product Positioning

Aleria AI Town will be presented as a production-oriented AI-native full-stack project whose primary technical story is a reliable, observable, and evaluable multi-agent runtime. Stanford Generative Agents provides the cognitive inspiration; a playable RPG provides the user-facing experience.

The system must demonstrate that NPCs can perceive events, form private memories and beliefs, retrieve relevant experiences, reflect, choose goals, create plans, propose structured actions, communicate with other NPCs, and alter a constrained RPG world. LLMs propose cognition and intent; deterministic domain code remains authoritative for world state, quests, permissions, concurrency, and action execution.

### 1.1 Priority Order

1. Production-grade AI agent engineering.
2. Believable multi-agent social simulation.
3. A coherent, playable RPG chapter.

### 1.2 First Release Scope

The first release retains three NPCs and four semantic locations and implements one deep chapter, **Forest Embers**, derived from the current missing-child quest. It does not add combat, equipment, crafting, multiplayer, large maps, large NPC populations, or numerous shallow side quests.

## 2. Design Principles

1. **Backend authority:** the frontend renders and requests actions; it never owns world rules.
2. **Hybrid cognition:** deterministic rules handle routine behavior and safety; LLM reasoning is event-triggered.
3. **Private knowledge:** world truth, perception, memory, and belief are separate layers.
4. **Structured proposals:** LLM output is a typed draft, never a database mutation.
5. **Single execution path:** deterministic and LLM policies both produce proposals consumed by the same validator and executor.
6. **Snapshot consistency:** all NPC proposals in one run use the same immutable snapshot.
7. **Observable decisions:** every result is traceable to events, memories, goals, plans, validations, and model calls without exposing hidden chain-of-thought.
8. **Graceful degradation:** model, embedding, queue, or streaming failures cannot corrupt the world or make the base RPG unusable.
9. **Bounded emergence:** authors define legal goal and action types plus quest invariants; agents dynamically choose intentions and social paths within those bounds.
10. **Vertical delivery:** complete one Grey evidence-to-action slice before generalizing to every NPC and subsystem.

## 3. System Architecture

The existing modular monolith remains the domain application. A worker process executes long-running cognition, but world, quest, memory, and trace data share the same PostgreSQL authority boundary.

```text
Vue / Phaser RPG              Public Agent Lab
         |                           |
         +----------- FastAPI ------+
                         |
             Agent Run Orchestrator
                         |
        PostgreSQL AgentRun + Outbox
                         |
                  Celery / Redis
                         |
                   Agent Worker
                         |
          LangGraph Deliberation Graph
                         |
              Structured Draft Results
                         |
       Action Registry / Conflict Resolver
                         |
       World + Quest Transactional Commit
                         |
                 Domain Events / Trace
                         |
                   SSE to Frontend
```

### 3.1 Ownership Boundaries

| State | Owner | Purpose |
| --- | --- | --- |
| World state | Aleria PostgreSQL | Objective RPG truth |
| Cognitive state | Aleria PostgreSQL | NPC observations, memories, beliefs, relationships, goals, and plans |
| Workflow state | LangGraph checkpoint | Progress and recovery of one cognitive run |
| Render state | Vue/Phaser | Transient presentation derived from backend state |

LangGraph does not own the world and does not directly execute domain mutations. It receives a serializable immutable context and returns reflection, plan, and action drafts.

## 4. Runtime Modes

All modes share a single action validation and execution pipeline.

| Mode | Behavior | Use |
| --- | --- | --- |
| `AUTO` | Runs existing plans and invokes LLM cognition only for triggered agents | Default gameplay |
| `DETERMINISTIC` | Uses plans and deterministic policy without new LLM reasoning | Offline mode, tests, baseline comparison |
| `FORCE_DELIBERATION` | Forces a full cognitive pass for selected, colocated, or all NPCs | Agent Lab and administrator experiments |

The main RPG exposes one world-time control and uses `AUTO`. Technical mode selection is restricted to Agent Lab. Public Agent Lab is read-only; mutation, model selection, snapshot forking, and paid runs require local or administrator access.

## 5. World Time and Versioning

The current overloaded tick concept is separated:

- `world_version` increments on every authoritative world mutation and is the optimistic concurrency token.
- `clock_tick` increments only when game time advances.
- `world_time` is the human-readable in-world time.
- `event_sequence` provides strict domain-event ordering.

Player dialogue or evidence presentation can change `world_version` without changing `clock_tick`. A wait, long journey, rest, or time-consuming investigation advances both.

### 5.1 Hybrid Event-Turn Loop

Meaningful player actions produce immediate events and a bounded reaction cycle for directly affected NPCs. Time advancement executes plans across the town.

```text
Explore -> interact -> domain event -> bounded reaction cycle
       -> choose next action or advance time -> execute NPC plans
       -> world consequences -> updated quest and social state
```

A reaction cycle permits at most two propagation layers, one run per NPC per world version, and a configured token and latency budget. Movement and time-consuming work are scheduled as plan actions rather than completed instantly inside the reaction cycle.

## 6. Agent Runtime

The domain runtime contains independently testable modules:

```text
agents/
  contracts
  orchestrator
  triggers
  perception
  memory
  reflection
  goals
  planning
  policy
  actions
  social
  tracing
```

This is a responsibility map, not a requirement that every responsibility begin as its own package.

### 6.1 Run Flow

1. Create an `AgentRun` for a fixed `world_version`.
2. Build one immutable world snapshot.
3. Evaluate triggers and select the affected NPC set.
4. Generate authorized observations for each selected NPC.
5. Encode new memories and build retrieval queries.
6. Run selected NPC deliberations concurrently against the same snapshot.
7. Collect reflection, goal, plan, and action drafts.
8. Validate action schemas and domain preconditions.
9. Resolve cross-NPC conflicts deterministically.
10. Recheck `world_version` and atomically commit accepted results.
11. Persist trace and usage metrics and publish frontend progress.

### 6.2 Trigger Conditions

LLM cognition is considered when an NPC receives a salient observation, lacks a valid plan, completes or fails a plan, crosses a schedule boundary, receives a direct player intervention, needs to respond socially, reaches the reflection threshold, or repeatedly fails the same action. Untriggered NPCs execute existing plans or deterministic routines.

## 7. Information and Memory Model

Four layers prevent omniscient NPCs:

```text
World Event -> authorized Observation -> encoded Memory -> current Belief
```

### 7.1 World Event

A world event records type, world version, clock time, location, actor, targets, structured payload, visibility, secrecy, source event, and causality identifier. Structured data is authoritative; prose is presentation.

### 7.2 Observation

Perception derives NPC-specific observations from location, participation, public scope, professional channels, attention, current activity, secrecy permissions, and deduplication. Different NPCs can observe different aspects of the same event.

### 7.3 Memory

The first release supports:

- `episodic`: concrete experiences.
- `conversation`: statements heard in dialogue.
- `reflection`: derived insights supported by evidence.
- `knowledge`: stable authored or acquired knowledge.

Each memory stores owner, content, source event or observation, occurrence and creation time, importance, confidence, emotional valence, secrecy, related entities, embedding, lifecycle status, last access, and access count.

### 7.4 Belief

A belief is an NPC's current proposition and confidence, not objective truth. New evidence may mark a belief disputed or superseded; prior evidence is retained for replay. Hearsay becomes a claim attributed to its speaker, not an automatic fact.

### 7.5 Memory Encoding

Routine events receive deterministic importance scores. Semantically complex conversations, evidence, social changes, and ambiguous events may use an LLM scorer. If scoring fails, the deterministic default is used.

### 7.6 Hybrid Retrieval

Candidates are filtered by NPC ownership, world, validity, secrecy, and timeline before ranking. Retrieval combines semantic relevance, recency, importance, goal relevance, relationship relevance, confidence, and contradiction penalties. Results are deduplicated and trimmed to a token budget while preserving both supporting and conflicting evidence.

PostgreSQL with pgvector is used in deployed environments. SQLite remains supported for fast tests and lightweight offline operation through repository abstractions and deterministic embedding fixtures.

### 7.7 Reflection

Reflection is threshold-triggered rather than run every tick. It selects salient recent memories, generates focal questions, retrieves evidence, and returns an insight draft with evidence memory IDs and confidence. A reflection cannot create objective world facts and cannot directly mutate relationship scores or goals.

Old memories are not physically deleted. Retrieval recency decays, low-value repetition is archived, summaries can replace repeated details in default context, and contradicted content is marked disputed or superseded.

## 8. Goals, Plans, and Actions

```text
Identity and Drives -> Goal Candidates -> Goal Arbitration
                    -> Active Goal -> Plan -> Plan Step
                    -> Action Proposal -> Validation -> Execution
```

### 8.1 Identity and Drives

Identity contains relatively stable personality, occupation, values, aspirations, fears, secrets, social role, and prohibitions. Drives such as safety, duty, affiliation, protection, curiosity, and reputation influence goal priority without becoming actions themselves.

### 8.2 Bounded Dynamic Goals

LLMs may generate dynamic goal descriptions, but every goal maps to a registered `goal_type` with defined success and failure conditions and a finite allowed action set. Each NPC has one primary active goal, optional suspended goals, and maintenance goals.

Goal arbitration combines base priority, urgency, drive and personality alignment, relationship relevance, evidence strength, quest relevance, commitment, switching cost, and risk. Rules make the final selection.

### 8.3 Plans

Planning uses a schedule skeleton plus a rolling horizon of three to five executable steps rather than a fully detailed day. Each step defines action type, target, preconditions, success conditions, failure strategy, estimated ticks, interruptibility, and status.

Replanning occurs when a goal completes, a precondition changes, an action fails, a salient event arrives, a player intervenes, or a schedule boundary is crossed. Cooldowns, failure limits, and repeated-action detection prevent planning loops.

### 8.4 Action Registry

Both deterministic and LLM policies emit an `ActionProposal`. The first release retains `move`, `rest`, `work`, and `eat`, refines social behavior into `talk`, and adds `investigate`, `share_information`, `report`, and `wait`.

Each action type defines an input schema, preconditions, permissions, costs, state effects, emitted events, failure codes, and frontend presentation. The LLM cannot introduce an unregistered action or write arbitrary state.

### 8.5 Conflict Resolution

All proposals in a run are resolved after deliberation. Deterministic policies handle unique-resource contention, reciprocal conversation requests, movement versus conversation, quest-critical events, and compatible parallel actions. The commit is atomic.

## 9. Relationships and Conversation

Relationships are directional. The first release uses familiarity, affinity, trust, and respect. Additional dimensions such as fear or obligation are deferred until required by authored content.

LLMs identify bounded social signals such as promise keeping, deception, sensitive disclosure, help, or refusal. Domain rules translate validated signals into capped relationship deltas based on personality, current relationship, evidence, severity, and cooldown. Every change references its source event.

### 9.1 NPC-to-NPC Dialogue

NPC dialogue uses a conversation manager with two to four alternating turns. Each speaker retrieves private context and sees only what has already been spoken plus publicly observable state. A turn returns an utterance and structured dialogue acts, claims, emotional presentation, secrecy, and continuation intent.

Conversation reservations ensure participants remain colocated and unoccupied. Stale conversations are discarded. Cooldowns, turn limits, and per-run budgets prevent infinite chat.

### 9.2 Knowledge Transfer

NPCs do not copy memories. A speaker chooses a claim to express; the listener stores a conversation memory and evaluates a belief candidate from source trust, confidence, and existing evidence. Information may be withheld, distorted, disputed, corrected, or stopped by secrecy constraints.

### 9.3 Player Dialogue

Player text is treated as untrusted in-world speech. It cannot override system instructions or knowledge permissions. Dialogue returns a `DialogueOutcomeDraft` containing utterance, emotion, player claims heard, NPC claims shared, promises or requests, social signals, and suggested goal triggers. Domain validators convert accepted drafts into events such as `PlayerClaimHeard`, `EvidencePresented`, `InformationShared`, `PromiseMade`, or `RequestAccepted`.

Quests consume validated domain events. Player statements and model output never directly change quest progress.

## 10. LangGraph Deliberation Boundary

The project uses a custom Aleria domain runtime with a LangGraph cognitive workflow. The graph may retrieve context, determine whether to reflect, generate reflection drafts, determine whether to replan, generate a plan draft, propose an action, and validate output structure.

Graph nodes do not update world state. They operate on a serializable `AgentRunState` containing the run, snapshot version, agent identity and state, trigger, observations, retrieved memories, drafts, proposal, validation summary, usage, and errors.

Provider interfaces remain independent:

- `EmbeddingProvider`
- `ReflectionProvider`
- `PlanningProvider`
- `ActionDecisionProvider`
- `ConversationProvider`

This preserves OpenAI-compatible model support, fake providers, task-specific model routing, and per-capability usage measurement.

## 11. Asynchronous Execution

`POST /api/worlds/{world_id}/runs` creates an idempotent `AgentRun` and returns `202 Accepted`. The request includes the expected world version, runtime mode, agent scope, and client idempotency key.

The API transaction writes both `AgentRun` and a transactional outbox event. A dispatcher publishes the outbox event to Celery through Redis. One Celery task owns one world run and internally executes selected NPC deliberations concurrently. This avoids fine-grained distributed graph tasks and preserves one conflict-resolution boundary.

Only one pending, running, or committing advancement run is allowed per world. Duplicate idempotency keys return the existing run. Unique run/action/memory constraints make duplicate task delivery safe.

### 11.1 Progress and Recovery

SSE streams persisted run progress to the browser; `GET /api/agent-runs/{run_id}` provides reconnect and refresh recovery. PostgreSQL, not Redis delivery, is the progress authority.

Transient model and database failures receive bounded backoff retries. Schema repair is attempted once. Embedding failures fall back to keyword and recent-memory retrieval. Budget exhaustion, invalid actions, or exhausted provider retries use the existing plan or deterministic policy. Stale proposals never commit.

Run budgets bound call count, token count, cost, duration, conversation turns, and reflection frequency. Cancellation is allowed before the committing state.

## 12. Observability and Agent Lab

Trace has three layers:

1. **Domain trace:** trigger, observations, memories, goal arbitration, plan changes, proposal, validation, events, relationship, and quest effects.
2. **Workflow trace:** graph steps, checkpoints, retries, failures, stale results, and fallback.
3. **Model trace:** provider, model, prompt version, tokens, latency, retries, schema validity, fallback, and estimated cost.

Traces store factual references and public decision summaries, not hidden chain-of-thought. Public views redact full system prompts, private secrets, credentials, and unauthorized NPC knowledge.

The approved UI architecture has two independent routes:

- The RPG route prioritizes map, story, interaction, world feedback, and a simple time-advance control.
- Agent Lab provides run timeline, decision inspector, memory inspector, world causality, relationship and belief views, deterministic-versus-LLM comparison, and evaluation results.

The initial release prioritizes information architecture and usability. Visual polish, animation, and richer responsive composition are a later dedicated phase.

## 13. Evaluation

Evaluation combines deterministic assertions and bounded model-quality assessment.

### 13.1 Test Layers

1. Deterministic unit tests for perception, secrecy, goal arbitration, action conditions, relationship caps, quest transitions, concurrency, reservations, and fallback.
2. Retrieval tests using fixed memories and expected relevant, irrelevant, and forbidden results.
3. Structured-output tests for schema validity, valid references, registered actions, repair, and fallback.
4. Behavioral scenario tests with invariant-based outcomes rather than one exact utterance.
5. Multi-tick simulations measuring completion, plan churn, loops, invalid actions, information propagation, leakage, cost, and latency.

LLM-as-judge may assess naturalness, role consistency, and plan quality, but it is never the authority for permissions, facts, memory provenance, action legality, or quest correctness.

### 13.2 Baselines

The evaluation compares:

- Existing deterministic policy.
- LLM policy without long-term memory.
- Target memory, reflection, and planning runtime.

Key metrics include retrieval precision and recall, unauthorized-memory leakage, memory-reference validity, structured-output validity, invalid-action rate, goal completion, plan churn, loop rate, quest reachability, fallback survival, token cost, and P50/P95 latency.

Fast CI uses fake models and deterministic embeddings. Integration CI exercises PostgreSQL/pgvector, checkpoints, queues, concurrency, and SSE. Live-model evaluation is manual or scheduled for releases and records prompt and model versions.

## 14. RPG Vertical Slice: Forest Embers

The chapter begins with the existing missing-child quest and burned shoe evidence. Initial private knowledge differs:

- Grey knows the old blockade had anomalies but lacks the full truth.
- Shir saw partial archive evidence and protects its source.
- Ryan trusts the official post-war record and doubts rumors.

The player discovers the shoe and chooses whom to tell, what evidence to present, what to conceal, and whether to exaggerate. These choices create observations and claims rather than direct facts in every NPC mind.

Grey's primary demonstration path is:

```text
EvidencePresented -> Grey Observation -> Grey Memory -> Retrieval
-> investigate_anomaly Goal -> Plan -> move/investigate Action
-> World Event -> Quest/Social Consequence -> Agent Lab Trace
```

The chapter has three valid authored outcomes:

1. **Joint investigation:** sufficient evidence and trust produce coordinated investigation and an archive branch.
2. **Premature lockdown:** uncertain or exaggerated information prompts Ryan to seal the forest and changes trust.
3. **Secret preserved:** the child can be rescued while the blockade truth remains unresolved and an NPC continues investigating in sandbox time.

Authors control legal evidence, invariants, quest conditions, and valid outcomes. Agents control who believes the player, who shares information, whose plan changes, the social propagation path, and which legal branch is reached.

Versioned seeds guarantee a ten-minute portfolio demonstration of trust, rumor, secrecy, and free sandbox behavior without depending on a lucky model run.

## 15. Security and Safety

- Player input is delimited and modeled as untrusted dialogue data.
- Retrieval is filtered by NPC ownership and secrecy before model context construction.
- Output schemas reject invented entity, memory, plan, and action identifiers.
- Secret disclosure is validated after generation.
- Public trace is redacted independently of gameplay authorization.
- Paid run endpoints are rate- and budget-limited.
- No model response directly mutates database rows.
- Stale context, duplicate tasks, partial failures, and cancellation cannot produce partial world commits.

## 16. Delivery Milestones

### M0: Baseline Protection

Freeze current tests, API contracts, deterministic tick behavior, and demo seed.

### M1: Data and Version Foundation

Add PostgreSQL/pgvector, Alembic, SQLite test support, `world_version`, richer event metadata, and AgentRun/Trace foundations without changing behavior.

### M2: Unified Proposal Pipeline

Route existing deterministic behavior through Action Proposal, Action Registry, validation, execution, and Trace.

### M3: Grey Memory Slice

Implement evidence observation, episodic memory, embedding, hybrid retrieval, knowledge isolation, fallback, and trace for Grey.

### M4: Grey Planning Slice

Add LangGraph deliberation, `investigate_anomaly`, rolling plans, `move`, `investigate`, `report`, plan interruption, and deterministic/LLM comparison.

### M5: Async Runtime

Add Celery, Redis, transactional outbox, idempotency, SSE, checkpoints, cancellation, retries, and budgets behind the established run contract.

### M6: Three-NPC Social Runtime

Generalize identity, memory, belief, goals, relationships, conversation, reflection, information transfer, parallel proposals, and conflict resolution.

### M7: Forest Embers Chapter

Integrate immediate reactions, time advancement, three outcomes, post-chapter sandbox, and versioned demo seeds.

### M8: Public Agent Lab and Evaluation

Complete the independent Agent Lab route, evaluation dashboard, security controls, deployment, architecture documentation, benchmark report, and demonstration assets.

## 17. Release Acceptance Criteria

The design is complete when the implementation demonstrates all of the following:

1. Grey changes a plan based on evidence-backed private memory.
2. Ryan and Shir do not know information they have not observed or received.
3. Reflection cites valid evidence memories and cannot create world facts.
4. Dynamic goals map to registered goal types and finite action sets.
5. All policies share the same action validator and executor.
6. Multiple NPCs deliberate on one snapshot and commit through deterministic conflict resolution.
7. Natural-language player interaction produces validated domain events and can affect legal quest branches.
8. Model, embedding, worker, stream, and retry failures preserve a playable deterministic fallback.
9. Duplicate delivery and stale proposals cannot advance the world twice.
10. The three Forest Embers outcomes are reachable and replayable.
11. Agent Lab explains decisions without leaking hidden reasoning, credentials, or unauthorized story secrets.
12. Evaluation compares deterministic, memoryless LLM, and target agent behavior with versioned prompts, costs, and latency.

## 18. Deferred Work

Combat, equipment, crafting, economic simulation, multiplayer, large-scale NPC populations, unrestricted continuous simulation, additional quest chapters, advanced relationship dimensions, dedicated vector databases, and microservice decomposition are explicitly deferred until the first vertical slice and portfolio release are complete.
