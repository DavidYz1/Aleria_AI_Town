# Aleria AI Town · 曦谷

> 游戏 AI 小镇全栈开发 · 可在线体验的 2D 叙事 RPG Demo

曦谷是一座从战争中恢复的温暖小镇。你是一名失去记忆、身带陌生印记的旅人；一次寻找失踪孩子的委托，将你带向城堡残缺的档案和森林深处的旧封锁线。

这个故事想追问：当和平建立在残缺记忆之上，寻找真相究竟是在修复世界，还是再次撕开伤口？


## 目录

- [90 秒体验路线](#90-秒体验路线)
- [记忆闭环演示](#记忆闭环演示)
- [Agent Loop：NPC 自己决定做什么](#agent-loopnpc-自己决定做什么)
- [项目定位与核心设计](#项目定位与核心设计)
- [世界观与当前章节](#世界观与当前章节)
- [NPC 设定](#npc-设定)
- [玩法与范围](#玩法与范围)
- [技术选型](#技术选型)
- [系统架构](#系统架构)
- [接口与决策流程](#接口与决策流程)
- [运行方式与端口](#运行方式与端口)
- [方法一：Docker Compose，推荐](#方法一docker-compose推荐)
- [方法二：一键启动开发环境](#方法二一键启动开发环境)
- [方法三：分别启动前后端](#方法三分别启动前后端)
- [环境变量与 AI/Mock 模式](#环境变量与-aimock-模式)
- [云服务器部署与维护](#云服务器部署与维护)
- [Demo 重置](#demo-重置)
- [AI 开发工具与人工修正案例](#ai-开发工具与人工修正案例)
- [测试、限制与文档](#测试限制与文档)

## 90 秒体验路线

1. 快速部署，从启动页开始冒险。
2. 输入玩家名字，在法师、游侠、牧师中选择职业，观看或跳过剧情过场。
3. 进入曦谷地图后，使用 WASD、方向键或地点卡片的“快速前往”移动。
4. 点击地图上的 Ryan、Shir、Grey，查看状态、最近行动并开始交流。
5. 点击“推进 1 小时”，观察世界时间、NPC 地点、状态与行动记录变化。
6. 前往星辉酒馆接受“失踪的孩子”，按照 Backend 返回的目标推进任务。
7. 分别询问三位 NPC 关于战争、档案或玩家印记的问题，比较他们的知识边界和立场。
8. 点击 NPC 详情里的“相关记忆”，展开查看他记得哪些事、来源是什么、发生在第几刻。
9. 如需重新演示，点击“重新开始冒险”恢复初始世界并重新创建角色。

## 记忆闭环演示

这是 Stage 2 最短、最能说明问题的一条演示路径：**NPC 在聊天窗口早已放不下那句话之后，依然记得它，并且始终把它当作“你说的”而不是“事实”。**

1. **提供一条独特线索。** 找到 Grey，告诉他一个只有你知道的细节，比如「我在低语森林的石堆旁捡到过一根蓝色羽毛」。用具体、不常见的说法，便于之后辨认他到底是真的记得，还是在泛泛地应付。
2. **把这句话挤出短期窗口。** 继续和他聊若干轮别的话题，直到刚才那轮对话超出 `CHAT_HISTORY_LIMIT`（默认 10 条）。此时它已经不在传给模型的对话历史里了。
3. **重启后端。** 停止服务再启动，或直接重开一个进程。内存中的一切都没了，只剩数据库。
4. **再问一次。** 回到 Grey，问他关于蓝色羽毛或那个石堆的事。
5. **看他怎么说。** 他能引用这条线索——但会把它表述成**你告诉他的说法**，而不是他亲眼所见、也不是曦谷的既定事实。
6. **展开“相关记忆”。** 在 NPC 详情面板里打开该区域，可以看到他当前被允许公开的记忆、每条的来源标签（亲历事件 / 听到的说法 / 稳定知识 / 形成的看法）和发生时刻。

### 这条演示想证明什么

**Claim 不是事实。** 玩家说的话进入系统时，被明确标记为「玩家的说法」这一类来源，和「NPC 亲历的世界事件」「作者写定的稳定知识」「NPC 自己形成的看法」分属不同类别，在数据库里、在 Prompt 里、在 NPC 的回答措辞里都保持这个区分。

这意味着：你可以告诉 Grey 任何事，他可能会记住、会在后续对话里提起、甚至会基于它产生看法——但**它永远不会因此变成曦谷的事实**。玩家的陈述不能修改世界状态、不能改变权限、不能把自己提升为世界真相。NPC 记得你说过什么，和 NPC 认为那是真的，是两件被刻意分开的事。

### 关于“相关记忆”区域

它展示的是**已经被允许公开**的内容，不是 NPC 的全部内心活动：

- 最多五条，只包含公开级别的记忆。
- 不显示你和 NPC 的私人对话原文——跨会话的真实记忆通过上面第 4 步的**对话行为**来证明，而不是通过这个面板泄露聊天记录。
- 不显示秘密记忆、隐藏推理、信念全文、向量或内部评分。
- 看不到的内容不会以占位符、总数差异或不同的报错形式暴露出来——它就是不出现。

如果模型或 Embedding 不可用，这个区域会退化成关键词匹配并给出说明，但地图、详情、对话、推进和任务都照常可用。

## Agent Loop：NPC 自己决定做什么

记忆闭环证明的是 NPC **记得**什么。这一节是它的另一半：NPC 拿这些记忆**做什么**。

推进世界时间时，每个 NPC 会形成一个目标、生成一份多步计划，并通过受校验的工具修改世界。整个过程在「思考」Tab 上逐步可见——目标、推理、计划进度，以及这一步到底是模型决定的还是引擎兜底的。

```mermaid
flowchart LR
    Snapshot["不可变世界快照"]
    Context["Context 组装<br/>八段分层"]
    Retrieval["Hybrid Retrieval<br/>语义+词面+时近+重要度"]
    Plan[("agent_plans<br/>Procedural Memory")]
    Provider["PlanningProvider<br/>native tool calling"]
    Decision["AgentDecision<br/>Pydantic 契约"]
    Registry["ActionRegistry<br/>二次校验"]
    Fallback["decide_action<br/>确定性兜底"]
    Engine["冲突处理 → 原子提交"]

    Snapshot --> Context
    Retrieval --> Context
    Plan -->|有活跃计划就复用，不调模型| Registry
    Context --> Provider --> Decision --> Registry
    Decision -->|写入| Plan
    Provider -.超时 / 非法 schema.-> Fallback
    Registry -.提案被拒.-> Fallback
    Fallback --> Engine
    Registry --> Engine
    Engine --> Snapshot
```

### 模型负责判断，引擎负责执行

这条分界线是整个设计的核心：**模型只能提出类型化的行动提案，不能直接写世界状态。**

提案经过 `ActionRegistry` 的二次校验才可能执行——`work` 必须在该角色的职责地点、`eat` 必须在酒馆、`talk` 的目标必须是同地点的另一个 NPC。模型说了不算，规则说了算。

### 工具是自描述的，与 MCP 对齐

动作不是 prompt 里的一段自然语言说明，而是注册表里的类型化定义。`ActionRegistry.to_tool_manifest()` 输出的结构就是 MCP `tools/list` 的响应体形状，直接作为 OpenAI 原生 tool calling 的 `tools` 传给模型：

```json
{
  "name": "move",
  "description": "移动到地图上的另一个地点。目标必须是当前世界中存在的地点 id。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "reason_code": { "type": "string", "description": "本次动作的简短原因码" },
      "target_id": { "type": "string", "description": "目标地点 id" }
    },
    "required": ["reason_code", "target_id"]
  }
}
```

收益是工具说明与校验规则写在同一处，不会漂移；模型只能调已注册的工具，调了别的直接被拒。**本轮不实现 MCP 传输层**（stdio / SSE），只对齐契约形状。

### Memory 四层

| 层 | 落点 | 作用 |
| --- | --- | --- |
| Working | `planner.build_context()` 的单 tick 上下文 | 本次决策看到的全部信息 |
| Episodic | `observations` + `memories(episodic/conversation)` | 亲历的事件与听到的说法 |
| Semantic | `memories(knowledge)` + `beliefs` | 稳定知识与带生命周期的信念（active / disputed / superseded） |
| Procedural | `agent_plans` + `ActionRegistry` | 会做什么、怎么做 |

Context 按八段组装，而不是把所有东西塞进 prompt：

```
[Identity]   角色与性格
[Needs]      体力 / 心情 / 社交 + 阈值提示
[World]      当前位置、同场 NPC、可达地点
[Episodic]   检索出的相关经历（有预算上限）
[Semantic]   已确立的信念
[Procedural] 当前计划与进度
[Tools]      注册表导出的工具清单
[LastOutcome] 上一步动作的执行结果
```

### Plan-and-Execute × ReAct

tick 制世界天然构成跨 tick 的 ReAct 循环，两种范式在 tick 边界上结合而不是二选一：

- **Plan-and-Execute 提供长程一致性**：一次规划产出 1–4 步，存进 `agent_plans` 跨 tick 续用。有活跃计划时**不调用模型**——这既是成本控制，也让 NPC 的行为有连贯脉络而不是每回合重新起意。
- **ReAct 提供单步反应性**：每一步执行后的结果回流成 Observation，下一次规划时进入 `[LastOutcome]` 段。

计划在三种情况下终止：步骤走完（`completed`）、某一步被引擎拒绝（`abandoned`）、或超过 8 个 tick 未完成（强制重规划，防止 NPC 抱着过期计划不放）。

### 韧性：LLM 挂了，世界照常运转

这是整个 Stage 的唯一不变量：

> **无论模型超时、返回非法 schema、还是提案被 `ActionRegistry` 拒绝，世界一定能推进。**

任一环节失败都落到确定性策略 `decide_action()`，提案标记为 `source=fallback` 写入 trace，UI 上显示琥珀色「确定性兜底」徽章。降级是可见的，不是静默的——玩家和开发者都能看出这一步是谁决定的。

「思考」Tab 的徽章有四种：

| 徽章 | 含义 |
| --- | --- |
| **LLM 规划** | 本回合由真实模型生成了新计划 |
| **替身规划** | 未配置规划 provider，由确定性替身生成计划（流程完全一致） |
| **沿用计划** | 复用已有计划，本回合没有调用模型 |
| **确定性兜底** | 规划不可用，由确定性策略接管 |

### 评估

`scripts/eval_agent.py` 在隔离的临时数据库里跑 N 个 tick，输出 markdown 指标表，支持 Fake / Live 双 provider 对照。它**绝不写入 `backend/data/aleria.db`**。

```bash
python scripts/eval_agent.py --ticks 20 --provider fake
python scripts/eval_agent.py --ticks 20 --provider live --out docs/eval/report.md
```

下面是 2026-09-14 的真实运行结果，20 个 tick、三个 NPC。Fake 一列是基线对照，Live 一列跑在腾讯混元 `hy3` 上（完整报告见 [`docs/eval/2026-09-14-agent-eval.md`](docs/eval/2026-09-14-agent-eval.md)）：

| 指标 | Fake | Live（`hy3`） | 含义 |
| --- | --- | --- | --- |
| 动作合法率 | 100.0%（60/60） | **90.2%（37/41）** | 模型产出的提案中未被引擎替换的比例 |
| Schema 有效率 | 100.0%（30/30） | 59.6%（28/47） | 调用模型的 tick 中一次返回合法 `AgentDecision` 的比例 |
| 兜底率 | 0.0%（0/60） | 38.3%（23/60） | 实际由确定性策略执行的提案占比 |
| 目标达成率 | 90.0%（27/30） | 85.7%（24/28） | `completed` 计划占全部计划的比例 |
| 行为熵 | 1.411 / 2.585 | 1.871 / 2.585 | 动作类型分布的香农熵 |
| 平均规划延迟 | 0 ms | 12666 ms | 单次模型调用的平均耗时 |
| 累计 token | — | 83183（28 次调用） | 本次评估的总消耗 |

三点如实说明：

- **动作合法率 90.2% 刚好压在验收线上**，样本 41 条偏小，不宜当作稳定结论。
- **Schema 有效率 59.6% 是最弱的一项**：47 次调用里 19 次超时。平均延迟 12.7 秒而超时上限配在 20 秒，长尾会被切掉。调高超时能直接改善，代价是 tick 更慢。
- **兜底率 38.3% 主要来自超时，而不是模型选错动作。** 把这两件事分开统计正是「Schema 有效率」与「动作合法率」并列的意义：前者衡量拿没拿到结果，后者衡量拿到的对不对。

Live 下单个 tick 24.6 秒（最慢 50 秒），因为三个 NPC 是**串行**调用模型；有活跃计划的 tick 不调模型，只要几百毫秒。

行为熵用来防「NPC 一直吃饭」的行为坍缩：6 个动词的满熵是 `log2(6) ≈ 2.585`，低于 1.0 会被标注风险。

## 项目定位与核心设计

Aleria AI Town 是一个“**确定性世界模拟 + 生成式角色对话**”的小型叙事 RPG。它不是让大模型决定游戏规则，而是让大模型在明确的世界规则、角色知识和任务上下文内扮演 NPC。

### 核心原则

1. **Backend 是唯一事实来源**：World、NPC、玩家语义地点和 Quest 状态均由 FastAPI 与数据库维护（本地 SQLite，Docker PostgreSQL）。
2. **Phaser 负责游戏表现**：地图、碰撞、移动、镜头与 Sprite 由 Phaser 管理，但 Phaser 不独立完成任务状态迁移。
3. **键盘与点击移动归一**：WASD 进入地点区域和“快速前往”最终都会同步到同一个 Backend 地点状态，避免输入设备限制阻断任务。
4. **模型负责判断，引擎负责执行**：模型决定 NPC 说什么、以及**提议**做什么，但它只能产出类型化的 `ActionProposal`，不能推进 Tick、移动 NPC、完成任务或写入任何世界状态。所有提案都要再过一遍 `ActionRegistry` 校验和确定性冲突处理才可能落地。
5. **确定性规则优先**：World Tick、行为校验和 Quest 状态机均使用可测试、可复现的普通业务逻辑。模型不可用时它们就是全部逻辑。
6. **可降级、可重置**：对话失败回退 Mock，规划失败回退确定性策略并在 UI 上标注来源；地图不可用时保留 DOM 交互入口；Demo 可以恢复到初始状态。
7. **事实、感知、记忆、信念分层**：世界事实、NPC 感知到的内容、玩家的说法和 NPC 自己的推断是四类不同的东西。每条记忆都能沿来源或证据链追溯，NPC 没有全知视角——同一件事对在场者、旁观者和不在场的人产生不同的记忆，甚至不产生记忆。
8. **认知永远是从属的**：权威世界写入先提交，感知与记忆随后投影。Embedding、Reflection 或记忆检索失败只会让 NPC 表现得"想不起来"，不会让世界推进、任务或对话失败。

## 世界观与当前章节

### 曦谷

曦谷位于艾莱瑞亚大陆的旧交通线与低语森林边缘。官方历史说，人类联盟约五百年前在终焉战争中击败魔王；二十多年前，灰烬战争又在小镇附近留下封锁线、失踪者和互相矛盾的档案。

居民共享的是公开历史，传闻、个人记忆和被保存下来的证据，这些和世界真相并不是一致的。玩家失忆和未知印记是固定的叙事起点，职业选择只表示失忆后的行事方式，不会替玩家定义失忆前的身份或命运。

| 地点 | 稳定 ID | 叙事职责 |
| --- | --- | --- |
| 星辉酒馆 | `tavern` | 炉火、消息与委托汇聚处，也是当前任务起点和终点 |
| 中央公园 | `park` | 居民生活与骑士训练交错，表现曦谷正在恢复的日常 |
| 晨曦城堡 | `castle` | Grey 守望和档案保管之地，记录并不等于完整真相 |
| 低语森林 | `forest` | 古老遗迹与灰烬战争旧封锁线交叠，长期谜团首次浮现 |

地点 ID 不随显示文案变化，避免叙事文案演进破坏数据库、API 和 Frontend Store。

### 当前章节：失踪的孩子

玩家在星辉酒馆接受委托，向 Grey 询问线索，进入低语森林旧封锁线寻找鞋子和失踪的孩子，再把孩子安全带回酒馆。这个任务首先是一件具体而温暖的救援，同时留下三个长期问题：

- 为什么封锁线附近出现了与玩家相似的印记？
- 孩子听见的低语来自什么？
- Grey 是否曾在灰烬战争中见过相同符号？

README 只介绍玩家可知的 Public Lore，不公开完整幕后真相。含剧透的内容事实源见 [`docs/15_Story_Bible_CN.md`](docs/15_Story_Bible_CN.md)。

## NPC 设定

三位 NPC 不只是更换名称和 Prompt。他们对同一段历史拥有不同知识、欲望和错误认知，构成“**相信—追问—沉默**”的认知三角。

| NPC | 表面性格 | 内在矛盾与反差 | 对真相的态度 | 对话特点 |
| --- | --- | --- | --- | --- |
| **Ryan / Knight** | 热情、直接、乐观，渴望成为真正的骑士 | 崇尚英雄主义，却背负父亲“叛徒”的污名；努力表现勇敢，却不愿承认自己害怕史莱姆 | 相信过去存在真正的英雄，希望父亲只是被误解 | 短句、坦率、有行动感；紧张时会故作镇定 |
| **Shir / Assassin** | 冷静、敏锐、克制，熟悉森林和隐秘行动 | 把真相视作对抗权力的武器，却担心未经准备的公开会伤害无辜；冷淡外表下藏着对甜食的偏爱 | 质疑官方记录，持续寻找被删除的证据 | 精确、试探性强，经常用反问和细节观察对方 |
| **Grey / Guardian** | 沉稳、可靠、谨慎，是灰烬战争老兵 | 为保护小镇而保持沉默，却逐渐意识到沉默也在延续错误 | 知道部分记录互相矛盾，但不愿轻易公开危险碎片 | 言辞简洁、有分量，先确认事实和风险，很少下绝对结论 |

### 关系与知识边界

- **Ryan 相信**英雄故事，但无法调和骑士信仰与父亲的污名。
- **Shir 追问**故事为何出现缺口，但并不知道完整的 Author Truth。
- **Grey 知道碎片却沉默**，因为他既见过历史被隐瞒，也见过遗迹力量造成真实死亡。
- 三人都不知道玩家失忆前的身份，也不能仅凭印记替玩家补全过去。
- Chat Prompt 只提供角色应该知道的内容，不把完整世界真相直接塞给 NPC。

## 玩法与范围

### 当前可体验内容

- 启动页、失忆冒险者创建、剧情过场、2D RPG 小镇四个场景。
- 玩家取名和法师、游侠、牧师三选一；选择保存在浏览器 `localStorage`。
- 职业影响外观、称谓和 NPC 对话上下文，不增加战斗数值。
- 单张室外地图展示酒馆、公园、城堡和森林入口。
- WASD、方向键自由移动，包含碰撞、镜头跟随和地点区域识别。
- 点击地点卡片快速前往；Backend 确认语义地点后，地图角色才会移动到对应区域，失败时不会出现界面与任务状态不一致。
- 查看三位 NPC 的身份、状态、当前位置、当前行为和最近三条行动。
- 推进 World Tick，观察 NPC 基于同一世界快照做出确定性行为。
- 与 NPC 进行多轮对话；对话上下文包含当前 World、NPC、玩家称谓和 Quest 摘要。
- 完成“失踪的孩子”六状态、五迁移任务闭环。
- 重新开始冒险，恢复初始世界并清理 Demo 数据。

任务状态机：

```text
available → accepted → briefed_by_grey
          → shoe_found → child_found → completed
```

错误地点、跳步和过期版本会被 Backend 拒绝。旅行只修改玩家语义地点，不推进 World Tick；Chat 只保存聊天记录，不推进任务或世界。

### 当前不做

- 战斗、技能、背包、装备和奖励系统。
- 多张独立地图或室内地图切换。
- 账号、多人世界和复杂权限系统。
- 长期 Memory、Relationship 数值、RAG 或 LLM 驱动 World Tick。

这些边界让作业重点集中在可解释的 NPC 行为、AI 对话、状态一致性和完整体验闭环。

## 技术选型

| 层级 | 技术 | 选择原因 |
| --- | --- | --- |
| 游戏与业务前端 | Vue 3、TypeScript、Pinia、Axios | 组件化展示业务状态，类型约束清晰，便于拆分 World、Player/Quest 和 Chat Store |
| 2D 游戏层 | Phaser 3.90.0 | 已提供 Scene、Sprite、输入、碰撞、摄像机和游戏循环，适合快速实现 2D RPG |
| Backend | FastAPI、Pydantic v2 | API 契约明确、校验能力完整，并自动提供 Swagger 文档 |
| 持久化 | SQLAlchemy、Alembic、SQLite / PostgreSQL + pgvector | 本地轻量运行，Docker 持久部署；版本化迁移和原子 Runtime 记录 |
| AI 接入 | OpenAI-compatible Adapter | 通过配置复用腾讯混元、Gemini 等兼容服务，业务层不依赖具体供应商 |
| 部署 | Docker Compose、Nginx | 保持 Frontend + Backend 当前架构，支持环境隔离、健康检查和服务器迁移 |

### 为什么选择 Phaser，而不是直接使用 PixiJS

PixiJS 更接近高性能 2D 渲染引擎，场景管理、输入系统和游戏循环需要自行组织。Phaser 在渲染之上直接提供轻量游戏框架能力，更符合本项目的 RPG 场景和开发周期。项目仍由 Vue 负责业务界面，Phaser 只负责地图与游戏表现，避免把整个 Web 应用塞进游戏 Canvas。

## 系统架构

```mermaid
flowchart LR
    Browser["Browser"]
    Vue["Vue 3<br/>角色创建 · World/NPC/Quest UI"]
    Phaser["Phaser 3<br/>地图 · 移动 · 碰撞 · Sprite"]
    API["FastAPI REST API"]

    subgraph Services["业务服务层"]
        WorldService["WorldTickService"]
        NPCService["NPCService"]
        QuestService["PlayerQuestService"]
        ChatService["ChatService"]
        ResetService["DemoResetService"]
    end

    Rules["确定性规则<br/>World Engine · Quest Policy · Validation"]
    Context["权威上下文构建<br/>World · NPC · Player · Quest · History"]
    Provider["ChatProvider"]
    Compatible["OpenAI-compatible Adapter<br/>hy-role · hy3 · Gemini"]
    Mock["Character-aware Mock"]
    SQLite[("SQLite / PostgreSQL")]

    Browser --> Vue
    Browser --> Phaser
    Phaser -->|地点进入 / 快速前往结果| Vue
    Vue --> API
    API --> WorldService --> Rules --> SQLite
    API --> NPCService --> SQLite
    API --> QuestService --> Rules
    QuestService --> SQLite
    API --> ResetService --> SQLite
    API --> ChatService --> Context
    Context -.只读.-> SQLite
    ChatService --> Provider
    Provider --> Compatible
    Provider --> Mock
    ChatService -->|只保存聊天记录| SQLite
```

架构中有两条明确隔离的运行链：

- **确定性游戏链**：`Snapshot → ActionProposal → Registry validation → deterministic resolution → atomic world/run/action/event/trace commit`。
- **生成式对话链**：`Authoritative Context → Prompt v3 → Provider → Validation → Chat Persistence`。

AI 对话不能进入 Action Execution、Quest Transition 或 World Update。

## 接口与决策流程

成功响应统一为：

```json
{
  "success": true,
  "data": {},
  "message": "ok"
}
```

### 主要接口

| 方法 | 路径 | 用途 | 关键校验或失败行为 |
| --- | --- | --- | --- |
| `GET` | `/api/health` | 检查 API、数据库和当前 Chat Provider | 数据库不可用返回 `503` |
| `GET` | `/api/world` | 获取时间、地点与 NPC 基础状态 | 世界不存在或数据库异常时返回错误响应 |
| `POST` | `/api/world/tick` | 以 `expected_world_version` 同步推进一小时并返回 run | 过期世界版本返回 `409`，事务失败返回 `503` |
| `GET` | `/api/agent-runs/{run_id}` | 查看持久化 proposal、event 与有序事实 trace | 不存在返回 `404`，非法 UUID 返回 `422` |
| `GET` | `/api/npcs/{npc_id}` | 获取 NPC 档案、状态与最近行动 | NPC 不存在返回 `404` |
| `POST` | `/api/npcs/{npc_id}/chat` | 创建或继续 NPC 多轮对话 | 校验 NPC、conversation、输入与模型输出；Primary 失败自动尝试 Mock |
| `GET` | `/api/player` | 获取玩家地点、Quest objective、版本与事件 | 玩家或任务不存在返回 `404` |
| `POST` | `/api/player/travel` | 更新玩家权威语义地点，不推进时间 | 携带 `expected_world_version`；未知地点返回 `404`，过期返回 `409` |
| `POST` | `/api/quests/missing-child/interact` | 按 interaction、`expected_version` 与 `expected_world_version` 推进任务 | 错误地点、跳步或版本冲突返回 `409` |
| `POST` | `/api/demo/reset` | 恢复 Demo 初始数据 | 在单事务中重建种子状态，失败返回 `503` |

完整请求与响应字段见 [`docs/06_API_Contract.md`](docs/06_API_Contract.md)，数据库结构见 [`docs/07_Database_Schema.md`](docs/07_Database_Schema.md)。

### World Tick 决策流程

```text
Frontend 提交 expected_world_version
    ↓
Backend 校验乐观锁版本
    ↓
创建本回合不可变 World Snapshot
    ↓
每个 NPC 根据角色、地点、状态、时间和允许行为选择下一步
    ↓
Registry validation → deterministic resolution
    ↓
同一数据库事务保存 World、NPC、Run、Proposal、Action、Event 与 Trace
    ↓
同步 HTTP 200 返回新的权威世界状态与 Run 摘要
```

NPC 决策不由前端写死，所有 NPC 从同一不可变快照决策。Registry 初始行为为 `move/rest/work/eat/talk/wait`；`social` 仍是需求数值，不再是 action ID。

`world_version` 是世界推进、实际旅行和任务迁移共享的乐观并发版本；`clock_tick` 只在推进时间时增加；`event_sequence` 对同一世界的事件连续排序。Chat 不改变这三个计数。Trace 只记录结构化引用与简短事实，不记录隐藏推理。Memory 已通过权威来源提交后的 post-commit cognition 落地；LLM 规划、Agent Lab、异步 202、Celery/Redis/SSE 留给后续阶段。

### NPC Chat 决策流程

```text
玩家输入
    ↓
读取权威 World / NPC / Player / Quest / History
    ↓
按 Prompt v3 注入人物性格、知识边界和当前上下文
    ↓
调用配置的 OpenAI-compatible Provider
    ↓
校验结构化 JSON 或自然文本
    ↓
成功：保存完整 User / Assistant 轮次
失败：Character-aware Mock 生成兜底回复并标记 fallback_used
```

### Quest 决策流程

```text
玩家在当前地点发起 interaction + expected_version
    ↓
Backend 校验玩家地点、任务版本、当前状态和可用交互
    ↓
MissingChildQuestPolicy 执行确定性状态迁移
    ↓
同一事务保存 Quest Progress 与 Quest Event
    ↓
返回下一 objective 和 available_interactions
```

Frontend 不复制任务迁移规则，只渲染 Backend 返回的目标与可执行交互。

## 运行方式与端口

| 运行方式 | 页面地址 | Backend / 调试地址 | 适用场景 |
| --- | --- | --- | --- |
| 线上 Demo |  | 页面同域访问 `/api` | 直接体验 |
| 本地 Docker | <http://127.0.0.1:8080/> | 页面同域访问 `/api` | 最推荐的本地复现方式 |
| 一键开发启动 | <http://127.0.0.1:5173/> | <http://127.0.0.1:8000/docs> | 日常开发 |
| 分别启动前后端 | <http://127.0.0.1:5173/> | <http://127.0.0.1:8000/docs> | 调试单个服务 |

> 本地 Docker 推荐使用 `8080`，避免 Windows 上端口 80 被占用或需要额外权限。服务器部署则使用 `80`，通过 `http://公网IP/` 访问。

## 方法一：Docker Compose，推荐

这种方式只需要 Git 和 Docker，不需要在宿主机安装 Node.js、项目 Python 依赖或数据库。

Docker 基础拓扑包含 `pgvector/pgvector:0.8.6-pg17-bookworm`，只向宿主机发布 Web 端口。`.env.production.example` 由 PostgreSQL 变量生成 Psycopg 3 URL；示例密码只供 Demo，部署前必须替换。URL 中的用户名/密码需 URL-safe；使用保留字符时显式设置正确 percent-encoded `DATABASE_URL`。

数据库迁移 `0004` 已加入六张认知表与 `memories.embedding`：PostgreSQL 使用 pgvector `vector`，SQLite 使用 JSON 向量等价物。迁移与 PostgreSQL loopback 测试 override 的完整命令见 [开发环境](docs/14_Development_Environment.md)。

PostgreSQL 验收必须把 backend 容器启动 Smoke 与迁移/Runtime 测试放在不同的 Compose project/volume 中；后者只启动 db，并要求 public 无应用表。2026-09-09 已完成容器健康检查及独立数据库的 13 项迁移/Runtime 测试；不要将 `TEST_POSTGRES_URL` 指向已有业务数据库。

### Windows PowerShell

1. 安装 [Git](https://git-scm.com/download/win) 和 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，启动 Docker Desktop。
2. 打开 PowerShell，执行：

```powershell
git clone https://github.com/DavidYz1/Aleria_AI_Town.git
Set-Location Aleria_AI_Town
Copy-Item .env.production.example .env.production
notepad .env.production
```

3. 在记事本中替换示例 `POSTGRES_PASSWORD`，把 `HTTP_PORT=80` 改为 `HTTP_PORT=8080`。默认已经是 Mock 模式，不需要填写 API Key。保存并关闭文件，然后执行：

```powershell
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production ps
```

4. 浏览器访问 <http://127.0.0.1:8080/>。验证 Backend：

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/health
```

### Linux / macOS Bash

1. 安装 Git、Docker Engine 与 Docker Compose Plugin；macOS 也可以使用 Docker Desktop。
2. 打开终端，执行：

```bash
git clone https://github.com/DavidYz1/Aleria_AI_Town.git
cd Aleria_AI_Town
cp .env.production.example .env.production
```

3. 使用文本编辑器打开 `.env.production`，替换示例 `POSTGRES_PASSWORD`，把 `HTTP_PORT=80` 改成 `HTTP_PORT=8080`，然后执行：

```bash
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production ps
curl http://127.0.0.1:8080/api/health
```

4. 浏览器访问 <http://127.0.0.1:8080/>。

### 常用 Docker 命令

Windows PowerShell 与 Bash 可以使用相同的 Compose 命令：

```bash
# 查看日志；Ctrl+C 只退出日志，不停止容器
docker compose --env-file .env.production logs -f

# 停止并移除容器，PostgreSQL 与旧 SQLite 命名卷仍然保留
docker compose --env-file .env.production down

# 再次启动
docker compose --env-file .env.production up -d

# 修改源码或依赖后重新构建
docker compose --env-file .env.production up -d --build
```

不要随意执行 `docker compose down -v`；`-v` 会删除保存持久数据的 Docker Volume。

仓库还提供 `scripts/deploy.cmd` 与 `scripts/deploy.sh` 一键部署包装器。它们会检查 Compose 配置、构建容器并等待健康检查，但宿主机需要额外安装 Python 3.11+。只安装 Docker 时，直接使用上面的 `docker compose` 命令即可。

## 方法二：一键启动开发环境

`start-dev.cmd` 和 `start-dev.sh` 会升级数据库表、仅在数据库为空时写入 Demo 种子，并同时启动 Backend 与 Frontend。它们不会自动安装 Python、Node.js 或项目依赖，所以首次运行需要先完成下面的准备。

### Windows：Git Bash（推荐）

安装 Git、Python 3.11+、Node.js 20+ 并完成项目依赖准备后，在 Git Bash 中执行：

```bash
cd /d/pythonproject/Aleria_AI_Town
./scripts/start-dev.sh --check
./scripts/start-dev.sh
```

`--check` 只检查依赖，不修改数据或启动服务。脚本优先使用项目的 `.venv/Scripts/python.exe`，无需先激活 venv；其他系统会使用 `.venv/bin/python`。启动顺序为 **Migration → seed-if-empty → Backend/Frontend**，已有世界保留，空世界才写入种子。

首次升级重要 SQLite 数据前，先停止使用该数据库的服务并备份；以下命令遇到同名备份或复制失败会停止，不覆盖已有备份：

```bash
cd /d/pythonproject/Aleria_AI_Town
backup="backend/data/aleria.before-upgrade-$(date +%Y%m%d-%H%M%S).db"
test ! -e "$backup" || exit 1
cp -- backend/data/aleria.db "$backup" || exit 1
./scripts/start-dev.sh
```

推荐从 Git Bash 或 PowerShell 终端启动，保留完整错误信息；双击窗口是否停留不是成功标准。升级失败时保留数据库和日志，禁止手工修改 `alembic_version`、删库或 Demo Reset 来伪造升级成功。启动后检查 `http://127.0.0.1:8000/api/health`、`/api/world` 与前端 5173；在启动终端按 `Ctrl+C` 停止两项服务。

### Windows：PowerShell + `start-dev.cmd`

1. 安装 Git、Python 3.11+、Node.js 20+。
2. 打开 PowerShell：

```powershell
git clone https://github.com/DavidYz1/Aleria_AI_Town.git
Set-Location Aleria_AI_Town

python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
npm --prefix frontend install
Copy-Item .env.example .env

.\scripts\start-dev.cmd
```

看到两个服务启动后访问：

- 游戏页面：<http://127.0.0.1:5173/>
- Backend Swagger：<http://127.0.0.1:8000/docs>

在启动脚本所在终端按 `Ctrl+C`，脚本会停止前后端进程。

### Linux / macOS：Bash + `start-dev.sh`

1. 安装 Git、Python 3.11+、Node.js 20+、npm。
2. 打开终端：

```bash
git clone https://github.com/DavidYz1/Aleria_AI_Town.git
cd Aleria_AI_Town

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
npm --prefix frontend install
cp .env.example .env

sh scripts/start-dev.sh
```

访问 <http://127.0.0.1:5173/>；Swagger 位于 <http://127.0.0.1:8000/docs>。按 `Ctrl+C` 停止两个服务。

## 方法三：分别启动前后端

这种方式最适合查看 Backend 日志、调试 API 或单独重启 Frontend。

### Windows PowerShell

首次准备：

```powershell
git clone https://github.com/DavidYz1/Aleria_AI_Town.git
Set-Location Aleria_AI_Town
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
npm --prefix frontend install
Copy-Item .env.example .env
```

终端 A，启动 Backend：

```powershell
Set-Location Aleria_AI_Town
.\.venv\Scripts\Activate.ps1
python -m scripts.upgrade_schema
python -m scripts.ensure_demo_world
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

终端 B，启动 Frontend：

```powershell
Set-Location Aleria_AI_Town\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### Linux / macOS Bash

首次准备：

```bash
git clone https://github.com/DavidYz1/Aleria_AI_Town.git
cd Aleria_AI_Town
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
npm --prefix frontend install
cp .env.example .env
```

终端 A，启动 Backend：

```bash
cd Aleria_AI_Town
source .venv/bin/activate
python -m scripts.upgrade_schema
python -m scripts.ensure_demo_world
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

终端 B，启动 Frontend：

```bash
cd Aleria_AI_Town/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Frontend 开发模式默认请求 `http://127.0.0.1:8000`。需要使用其他 Backend 地址时，可设置 `VITE_API_BASE_URL`。

## 环境变量与 AI/Mock 模式

### 环境文件的作用

| 文件 | 用途 | 是否提交 Git |
| --- | --- | --- |
| `.env.example` | 本地开发模板，默认 Mock | 是 |
| `.env` | 本地开发实际配置 | 否 |
| `.env.production.example` | Docker/服务器部署模板，默认 Mock | 是 |
| `.env.production` | Docker/服务器实际配置，可能包含 API Key | 否 |

`compose.yaml` 中的 `${NAME:-default}` 表示：优先读取 `--env-file .env.production` 提供的值，未配置时才使用冒号后的默认值。`.env.production.example` 只是安全模板，不会被 Compose 自动当作生产密钥文件；实际部署命令显式传入 `.env.production`。

真实 API Key 只进入 Backend 容器，不会写入前端构建产物，也不会发送到浏览器。修改环境变量后需要完整重启 Backend 或重新创建容器。

以下四个配置块可以替换 `.env` 或 `.env.production` 中对应的 `CHAT_` 配置。不要在同一文件保留重复变量。

### 默认配置：Mock，无需 API Key

```env
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

Mock 会根据 NPC、玩家输入、世界状态和 Quest 上下文返回确定性的角色化回复，而不是只返回统一的“服务不可用”。World Tick 和 Quest 在 Mock 模式下仍然完整运行。

Stage 2 的两个认知 Provider 与 Chat **相互独立**，默认同样不需要 Key：

```env
EMBEDDING_PROVIDER=fake
REFLECTION_PROVIDER=fake
```

`fake` Embedding 是确定性的特征哈希实现，不发起网络请求，排序结果完全可复现；`fake` Reflection 产出结构合法、可被证据校验拒绝或接受的草稿。因此**记忆闭环演示在零配置下即可完整体验**。切换真实 Provider 时把对应项改为 `openai_compatible` 并补齐 base URL、model 与 Key；配置不完整会回退 fake 而不是启动失败。完整的认知配置项见 [`docs/14_Development_Environment.md`](docs/14_Development_Environment.md)。

### 推荐配置：腾讯混元 hy-role

```env
CHAT_PROVIDER=hunyuan
CHAT_LLM_BASE_URL=https://tokenhub.tencentmaas.com/v1
CHAT_LLM_API_KEY=
CHAT_LLM_MODEL=hy-role
CHAT_LLM_AUTH_MODE=bearer
CHAT_LLM_OUTPUT_MODE=text
CHAT_LLM_TIMEOUT_SECONDS=30
CHAT_HISTORY_LIMIT=10
CHAT_PROMPT_VERSION=v3
```

将 Key 填在 `CHAT_LLM_API_KEY=` 后面，不要添加引号或多余空格。`hy-role` 在当前 NPC 场景中角色表达更自然，但不稳定遵守 `reply + emotion` JSON 契约，因此推荐 `text`。Adapter 会验证正文并确定性派生 emotion。

如果 Key 留空，Backend 会安全地直接使用 Mock。

### 腾讯混元 hy3

```env
CHAT_PROVIDER=hy3
CHAT_LLM_BASE_URL=https://tokenhub.tencentmaas.com/v1
CHAT_LLM_API_KEY=
CHAT_LLM_MODEL=hy3
CHAT_LLM_AUTH_MODE=bearer
CHAT_LLM_OUTPUT_MODE=structured_json
CHAT_LLM_TIMEOUT_SECONDS=30
CHAT_HISTORY_LIMIT=10
CHAT_PROMPT_VERSION=v3
```

`hy3` 使用结构化 JSON 模式，仍复用同一个 OpenAI-compatible Adapter，不存在独立的 Hunyuan 业务分支。


### Primary Provider 与 Mock Fallback

```text
Provider 配置完整
    ↓
调用 Primary（hy-role / hy3 / Gemini）
    ├── 成功且响应合法 → 保存 Primary 回复，fallback_used=false
    └── 超时 / 网络错误 / 非 2xx / 输出非法
                          ↓
                     Mock 回复
                          ↓
                 provider=mock, fallback_used=true
```

Frontend 会显示“AI：provider”“Mock 模式”或“AI 服务异常，已使用 Mock”。`GET /api/health` 可以确认 Backend 和数据库可用，并显示当前 Provider 标签；一次对话是否真正调用成功，应以 Chat 响应中的 `provider` 与 `fallback_used` 为准。

## 云服务器部署与维护

当前线上 Demo 使用 Ubuntu、Docker Compose、Nginx 和公网 IP 的 HTTP 80 端口。下面以 Ubuntu 为例。

### 首次部署

1. 准备一台 Linux 云服务器，安装 Git、Docker Engine 和 Docker Compose Plugin。
2. 在云厂商安全组中开放 TCP 80；SSH 管理通常使用 TCP 22。
3. 连接服务器并执行：

```bash
git clone https://github.com/DavidYz1/Aleria_AI_Town.git
cd Aleria_AI_Town
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production
```

4. 至少确认下面几项：

```env
APP_ENV=production
POSTGRES_DB=aleria
POSTGRES_USER=aleria
POSTGRES_PASSWORD=<replace-with-url-safe-password>
FRONTEND_ORIGIN=http://你的公网IP
HTTP_PORT=80
```

必须替换 POSTGRES_PASSWORD 占位值。Compose 会使用这些变量生成 PostgreSQL 连接地址；仅在需要覆盖连接地址或使用保留字符凭据时，另设正确 percent-encoded 的 `postgresql+psycopg://` DATABASE_URL，并保持数据库实际密码一致。

然后从前面的 AI 配置中选择 Mock 或真实 Provider。真实 Key 只写入服务器上的 `.env.production`，不要提交 Git、发送到前端或放进截图。

5. 构建、启动并检查：

```bash
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production ps
curl http://127.0.0.1/api/health
```

最后访问 `http://你的公网IP/`。

### 更新、日志与重启

```bash
# 查看运行状态和日志
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs -f --tail=200

# 拉取新代码并重新构建
git pull
docker compose --env-file .env.production up -d --build

# 普通重启
docker compose --env-file .env.production restart
```

数据库、Backend 与 Web 均有健康检查和重启策略。PostgreSQL 使用 `aleria_postgres_data` 命名卷；Backend 等待数据库健康并执行 Alembic 升级后启动，Web 等待 Backend 健康。重建容器不会清除数据；迁移服务器需要备份私有配置和 PostgreSQL 数据。旧 SQLite 的 `aleria_data` 卷保留，但不会自动导入 PostgreSQL；已有部署切换前需单独规划数据迁移。

当前线上入口是 HTTP，不适合传输隐私数据或用于正式生产服务。API Key 不会经过浏览器，Backend 到模型服务仍使用 HTTPS；但浏览器与服务器之间的游戏请求和聊天内容没有 TLS 保护。正式对外运营应增加域名与 HTTPS，并补充认证、限流和重置权限控制。

## Demo 重置

Town 页面右上角的“重新开始冒险”会：

- 恢复初始 World 时间与 NPC 状态；
- 恢复 Player 和“失踪的孩子”任务状态；
- 清除聊天、Agent Run/Proposal/Trace、NPC Action、World Event 和 Quest Event；
- 清除浏览器中的本地角色名字与职业；
- 销毁旧 Phaser 实例并返回角色创建流程。

Backend 接口为：

```http
POST /api/demo/reset
```

直接调用 API 只重置 Backend；通过页面按钮操作时，Frontend 还会清理 `localStorage` 并重新创建游戏实例。

这是为作业演示提供的全局重置能力。当前项目没有账号隔离，公开服务器上的访客共享同一个世界，任何访客触发重置都会影响其他访客，因此不应把该接口原样用于正式多用户产品。

## AI 开发工具与人工修正案例


### Codex + Superpowers 工作流

项目使用 **Codex** 读取仓库上下文、辅助方案分析、实现、测试、Diff 审查和部署排错，并使用 **Superpowers** 将协作过程约束为可审查的工程步骤：

```text
人工提出目标、范围和不可破坏边界
    ↓
Brainstorming：讨论方案与风险，未经确认不进入实现
    ↓
Specification / Writing Plans：把模块、接口与验收标准写清楚
    ↓
Test-Driven Development：先建立失败测试，再做最小实现
    ↓
Systematic Debugging：根据现象、日志和可验证假设定位根因
    ↓
Verification Before Completion：运行测试、类型检查、构建并检查 Diff
    ↓
人工逐模块 Review
    ↓
开发者手动提交 Git
```

Codex 不被授权自动提交 Git，也不能扩大已经确认的模块范围。人工负责：

- 决定产品范围与架构边界；
- 判断 AI 建议是否符合当前代码和作业目标；
- 审查每个模块的修改文件、测试结果和 Diff；
- 决定是否接受实现并亲自提交；
- 保护 API Key 等敏感配置。

### 人工修正案例：hy-role 已消耗 Token，但页面仍回退到 Mock

**1. 现象**

TokenHub 显示请求已经消耗 Token，但 Frontend 仍提示使用 Mock；Backend 安全日志记录 `category=response_validation`。

**2. 定位**

请求已经到达模型，说明网络和鉴权不是主要失败点。问题发生在响应解析：共享 Adapter 当时强制要求模型返回 `reply + emotion` JSON，而 `hy-role` 返回的是质量良好的自然文本。

**3. 人工判断**

没有为 Hunyuan 复制一套专用 Provider，也没有直接关闭全部响应校验。人工确认应把供应商差异限制在协议 Adapter 层，避免渗入 ChatService、API 和业务状态。

**4. 最小修正**

在统一 OpenAI-compatible Adapter 中增加 `structured_json | text` 两种输出模式。Text 模式仍验证正文长度，并根据文本确定性派生 emotion；公共 Chat API 和 Fallback 契约不变。

**5. 回归验证**

补充 Adapter、Provider、Fallback、Chat API 和状态隔离测试，重新验证：

- Mock、结构化模型和自然文本模型共用同一公共契约；
- Primary 失败后正确标记 `provider=mock` 与 `fallback_used=true`；
- Chat 不修改 World、NPC、Player 或 Quest。

这个案例体现了实际协作原则：AI 可以加速分析和实现，但最终由人根据日志证据确认失败层、选择最小架构改动并验收结果。

## 测试、限制与文档

### 自动验证

Windows PowerShell：

```powershell
# Backend
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider

# Frontend
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build

# Docker Compose 配置（需要 Docker）
docker compose --env-file .env.production.example config --quiet
```

Linux / macOS Bash：

```bash
# Backend
.venv/bin/python -m pytest tests/backend -q -p no:cacheprovider

# Frontend
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build

# Docker Compose 配置（需要 Docker）
docker compose --env-file .env.production.example config --quiet
```

默认自动测试使用临时 SQLite、Mock 或假 Provider，不读取真实 API Key，也不发起外部模型请求。PostgreSQL 集成测试只在显式设置 `TEST_POSTGRES_URL` 时运行，且使用独立可丢弃数据库中的测试 schema；缺失时明确 skip。真实 Provider 验证属于显式、手动的 Smoke Test。

### 已知限制

- 当前公开部署是共享单世界、无账号的作业 Demo，不适合多人同时修改状态。
- Demo Reset 是全局接口，尚未增加认证和权限控制。
- 本地 SQLite 为轻量单实例模式；Docker 使用 PostgreSQL，但异步提交、后台调度和多 worker Runtime 协调仍未实现。
- NPC 记忆是 append-only 的，只做来源幂等与内容去重，没有自动摘要压缩；长时间演示会持续累积记忆行。
- Reflection 由累计重要度与新增记忆数触发，失败后最多自动重试一次；它只能引用真实存在的同 owner 证据，不能创造世界事实。
- 记忆解释接口是匿名只读的，没有账号级身份，因此它不返回任何聊天原文；跨会话记忆要通过对话行为来验证。
- NPC 之间可以 `talk`，但不会传播信息：交谈产生的是行动与事件，不会把一个 NPC 的记忆搬到另一个 NPC 身上。多 Agent 协商与消息总线属于后续阶段。
- 规划是**串行**的：三个 NPC 依次调用模型，真实 provider 下单个 tick 约 30–50 秒。前端已为该接口单独放宽超时，但体感仍然偏慢；并行化需要先解决共用 tick Session 的线程安全问题。
- 计划的动作空间锁定在 6 个动词（`move / work / eat / talk / rest / wait`）。NPC 的智能体现在选择与排序，不在可做事情的种类。
- 不做 schema repair 重试：模型返回非法结构即判失败并降级，不会二次追问补救。
- `agent_plans.tokens_used` 只记录消耗，没有预算约束或熔断。
- 当前线上入口为 HTTP，没有域名和 TLS。
- Phaser 像素坐标不持久化；Backend 只保存任务需要的语义地点。
- 职业只影响外观、称谓和对话上下文，没有战斗数值差异。
- 当前只有一张室外地图和一条主线任务。
- `gemini-3.7-flash` 需要在最终提交前执行一次有真实权限的网络 Smoke Test。

### 文档导航

- [`docs/01_Assignment_Specification.md`](docs/01_Assignment_Specification.md)：腾讯作业要求整理。
- [`docs/05_Engineering_Architecture.md`](docs/05_Engineering_Architecture.md)：工程架构与边界。
- [`docs/06_API_Contract.md`](docs/06_API_Contract.md)：API 请求与响应契约。
- [`docs/07_Database_Schema.md`](docs/07_Database_Schema.md)：SQLite / PostgreSQL、Alembic 与 Runtime 数据结构。
- [`docs/08_Prompt_Engineering_CN.md`](docs/08_Prompt_Engineering_CN.md)：Prompt 版本与角色上下文设计。
- [`docs/10_AI_Coding_Workflow.md`](docs/10_AI_Coding_Workflow.md)：AI 辅助开发与人工 Review 流程。
- [`docs/12_Game_Experience_Design.md`](docs/12_Game_Experience_Design.md)：四场景游戏体验设计。
- [`docs/15_Story_Bible_CN.md`](docs/15_Story_Bible_CN.md)：完整世界观、人物知识矩阵和连续性规则（含剧透）。

---

Aleria AI Town 的目标不是堆叠完整 RPG 系统，而是用一个可以启动、可以解释、可以测试、可以降级、可以重置和可以部署的 Demo，证明 AI 角色表达能够安全地嵌入确定性游戏世界。
