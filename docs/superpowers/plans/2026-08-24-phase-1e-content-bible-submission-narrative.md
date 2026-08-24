# Phase 1E 内容圣经与提交叙事 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本项目沿用 Inline Execution；每个 Module 完成后必须暂停，由用户人工 Review Diff 并自行提交 Git。

**Goal:** 在不改变现有数据库、API、World Engine 和 Quest 状态机的前提下，建立统一的曦谷内容事实源，升级 Prompt/Mock 与当前任务叙事，并将 README 整理成符合腾讯作业评审路径的作品首页。

**Architecture:** `docs/15_Story_Bible_CN.md` 成为内容事实源；运行时只从中提取 Public Lore、Player Context 和各角色自己的 Character Knowledge，完整 Author Truth 不注入模型。Prompt v3 和 Mock 负责角色表达，既有 Backend Quest Service 与 Frontend 组件只更新展示文案；所有稳定 ID、状态枚举、API DTO、Repository 和 ChatProvider 抽象保持不变。

**Tech Stack:** Markdown、Python 3.11+、pytest、FastAPI/Pydantic Settings、Vue 3、TypeScript、Vitest、Vite、版本化 Prompt 资产。

**Spec:** `docs/superpowers/specs/2026-08-24-phase-1e-content-bible-submission-narrative-design.md`

## Global Constraints

- 正式中文术语只能使用：艾莱瑞亚、曦谷、星辉酒馆、中央公园、晨曦城堡、低语森林、终焉战争、灰烬战争、古族、伊萨尔。
- 终焉战争发生于约五百年前；灰烬战争发生于约二十余年前；Grey 只经历后者。
- 当前玩家固定为 `default-player`，已知事实只有失忆、旅人身份和无法解释的印记；不增加职业、姓名或身世字段。
- `docs/15_Story_Bible_CN.md` 保存 Author Truth；Author Truth 不整体进入 Prompt 或 README 无剧透介绍。
- 不新增数据库表，不修改数据库字段，不修改 API Request/Response 契约。
- 不修改 Location/NPC/Player/Quest 稳定 ID，不修改 QuestStatus、QuestInteraction 或五步迁移顺序。
- Chat 继续只读 World/NPC/Player/Quest，只写聊天记录；不得推进 Tick、移动角色或推进 Quest。
- `ChatProvider`、`ChatService`、OpenAI-compatible Adapter 和 Fallback 设计保持不变。
- `hy-role` 使用 `CHAT_LLM_OUTPUT_MODE=text`；README 只能称其为“本项目 NPC 角色对话实测推荐”，不能作行业级绝对比较。
- 不实现 PixiJS、Cocos、分支剧情、Relationship、复杂 Memory、RAG、多人、Docker 或线上部署。
- 自动测试不读取 `.env`，不访问真实模型，不读取或输出 API Key。
- 每个 Module 遵循 RED → GREEN → Regression → Diff Review；Codex 不执行 Git Commit。

---

## 0. 文件边界与依赖图

### 0.1 新增文件

| 文件 | 单一职责 |
| --- | --- |
| `docs/15_Story_Bible_CN.md` | 曦谷唯一内容事实源、知识矩阵与连续性规则 |
| `prompts/v3/world_lore.md` | 所有 NPC 可知的 Public Lore |
| `prompts/v3/chat_system.md` | Chat 只读、角色扮演、知识边界和输出规则 |
| `prompts/v3/player_context.md` | 失忆玩家已知/未知事实及禁止补全边界 |
| `prompts/v3/characters/ryan.md` | Ryan 的立场、秘密、误解、关系和语言风格 |
| `prompts/v3/characters/shir.md` | Shir 的立场、秘密、误解、关系和语言风格 |
| `prompts/v3/characters/grey.md` | Grey 的灰烬战争经历、沉默动机和语言风格 |
| `tests/backend/test_story_content.py` | Story Bible、正式术语、README 提交叙事的内容契约 |
| `tests/backend/test_phase1e_acceptance.py` | Prompt/Mock/Quest/Chat 只读的跨模块验收 |

### 0.2 修改文件

| 模块 | 文件 | 修改责任 |
| --- | --- | --- |
| Module 1 | `docs/00_Project_Context.md` | 当前世界钩子与 Phase 1E 范围 |
| Module 1 | `docs/02_Product_Design.md` | 当前玩家设定、玩法边界与未来分支区分 |
| Module 1 | `docs/03_World_Model.md` | 两场战争、地点职责与稳定 ID |
| Module 1 | `docs/04_NPC_Agent_Design.md` | 三名 NPC 的知识/矛盾/表达边界 |
| Module 1 | `docs/12_Game_Experience_Design.md` | 当前章节体验与主线伏笔 |
| Module 2 | `backend/app/core/config.py` | 允许并默认 `CHAT_PROMPT_VERSION=v3` |
| Module 2 | `backend/app/services/chat_context.py` | PromptLoader 允许加载 v3 |
| Module 2 | `backend/app/llm/mock.py` | 新高频意图与角色化离线回复 |
| Module 2 | `.env.example` | 默认 Prompt 版本切换为 v3 |
| Module 2 | `docs/08_Prompt_Engineering_CN.md` | Prompt v3 信息分层与防剧透设计 |
| Module 2 | `docs/14_Development_Environment.md` | v3 与 `hy-role` 安全配置 |
| Module 2 | `tests/backend/test_chat_config.py` | v3 配置 RED/GREEN |
| Module 2 | `tests/backend/test_chat_context.py` | v3 资产、知识边界与 Loader 回归 |
| Module 2 | `tests/backend/test_mock_chat_provider.py` | Mock 高频意图、区分度与不泄密 |
| Module 3 | `data/locations.json` | 四地点的故事化描述，不改 ID/排序 |
| Module 3 | `backend/app/quests/missing_child.py` | 既有状态的目标与交互标签文案 |
| Module 3 | `backend/app/services/player_quest_service.py` | 五条 Quest Event 的主线伏笔文案 |
| Module 3 | `frontend/src/components/PlayerLocationPanel.vue` | 失忆旅人与印记钩子 |
| Module 3 | `frontend/src/components/QuestPanel.vue` | 完成态的叙事余韵 |
| Module 3 | `tests/backend/test_seed_world.py` | 地点描述与稳定 ID 断言 |
| Module 3 | `tests/backend/test_missing_child_quest.py` | 目标文案与状态机不变断言 |
| Module 3 | `tests/backend/test_player_quest_service.py` | Event 文案与 Service 输出断言 |
| Module 3 | `tests/backend/test_phase1d_acceptance.py` | 更新文案期望，继续证明隔离性 |
| Module 3 | `tests/frontend/fixtures.ts` | 同步 Backend 权威展示文案 |
| Module 3 | `tests/frontend/PlayerLocationPanel.spec.ts` | 玩家钩子组件测试 |
| Module 3 | `tests/frontend/QuestPanel.spec.ts` | 完成态文案组件测试 |
| Module 4 | `README.md` | 游戏优先的腾讯作业提交首页 |
| Module 4 | `docs/09_Decision_Log.md` | Phase 1E 内容架构与 `hy-role` 决策 |
| Module 4 | `docs/10_AI_Coding_Workflow.md` | 当前实际 AI 协作与人工修正案例 |
| Module 4 | `docs/11_Project_Structure.md` | Story Bible、Prompt v3、测试文件索引 |
| Module 4 | `docs/13_Development_Roadmap.md` | Phase 1E/2/2B/3 的真实顺序 |

### 0.3 明确不修改的接口

- `GET /api/world`
- `POST /api/world/tick`
- `GET /api/npcs/{npc_id}`
- `POST /api/npcs/{npc_id}/chat`
- `GET /api/player`
- `POST /api/player/travel`
- `POST /api/quests/missing-child/interact`
- `ChatProvider.generate_reply(request: ChatProviderRequest) -> ChatProviderResult`
- `MissingChildQuestPolicy.transition(snapshot, command) -> QuestTransition`

---

## Module 1：Story Bible 与文档事实源

**独立交付结果：** 仓库拥有唯一可信的中文内容圣经；当前产品、世界、NPC 和体验文档引用同一套术语、时间线和知识边界。该模块不修改运行时行为。

### Task 1.1：先建立内容契约测试

**Files:**

- Create: `tests/backend/test_story_content.py`
- Read: `docs/superpowers/specs/2026-08-24-phase-1e-content-bible-submission-narrative-design.md`

**Interfaces:**

- Consumes: 仓库根目录下的 Markdown 文件。
- Produces: 可重复执行的内容连续性断言；Module 4 会在同一文件增加 README 验收。

- [ ] **Step 1：写入 Story Bible 缺失时必然失败的测试**

```python
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STORY_BIBLE = REPO_ROOT / "docs" / "15_Story_Bible_CN.md"
SYNCED_DOCS = (
    REPO_ROOT / "docs" / "00_Project_Context.md",
    REPO_ROOT / "docs" / "02_Product_Design.md",
    REPO_ROOT / "docs" / "03_World_Model.md",
    REPO_ROOT / "docs" / "04_NPC_Agent_Design.md",
    REPO_ROOT / "docs" / "12_Game_Experience_Design.md",
)


def test_story_bible_defines_canonical_timeline_and_information_layers():
    content = STORY_BIBLE.read_text(encoding="utf-8")
    required = (
        "艾莱瑞亚",
        "曦谷",
        "晨曦城堡",
        "终焉战争",
        "约五百年前",
        "灰烬战争",
        "约二十余年前",
        "Author Truth",
        "Public Lore",
        "Character Knowledge",
        "Player Context",
    )
    assert all(term in content for term in required)
    assert "Grey 亲历终焉战争" not in content


def test_synced_content_docs_use_canonical_place_names():
    for path in SYNCED_DOCS:
        content = path.read_text(encoding="utf-8")
        assert "阿莱瑞亚" not in content, path
        assert "曦谷城堡" not in content, path
```

- [ ] **Step 2：运行测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_story_content.py -q -p no:cacheprovider
```

Expected: FAIL because `docs/15_Story_Bible_CN.md` does not exist.

### Task 1.2：编写正式 Story Bible

**Files:**

- Create: `docs/15_Story_Bible_CN.md`

**Interfaces:**

- Consumes: 已批准 Phase 1E Design Spec 的正史内容。
- Produces: Prompt、Mock、Quest、Frontend 和 README 唯一内容事实源。

- [ ] **Step 1：按固定章节写入文档骨架**

必须使用以下章节，顺序保持稳定：

```markdown
# Aleria AI Town 内容圣经

## 1. 使用范围与信息层级
## 2. 作品定位与核心命题
## 3. 正式术语表
## 4. Author Truth
## 5. 正史时间线
## 6. Public Lore
## 7. 地点设定
## 8. Player Context
## 9. NPC 角色卡
## 10. NPC 知识矩阵
## 11. NPC 关系与矛盾
## 12. 当前章节：失踪的孩子
## 13. 信息揭示规则
## 14. 连续性检查表
## 15. 未来故事钩子
```

- [ ] **Step 2：写入不可变正史**

正文必须明确：

- 古族能感知衰弱的世界本源，人类依靠规模化魔法维持防御、医疗、生产与秩序；
- 伊萨尔要求限制魔法，后以摧毁人类魔法文明的极端方式阻止继续消耗；
- 约五百年前的终焉战争没有纯粹正邪方，战争进一步撕裂世界本源；
- 部分古族以自身作为“锚”修补裂隙，最后盟约随后被人类统治者隐藏；
- 官方历史将伊萨尔塑造成魔王，将古族统一称为恶魔；
- 约二十余年前，人类重新勘探遗迹触发灰烬战争；
- Grey 参与灰烬战争及遗迹行动，失去同伴，只掌握真相碎片；
- 曦谷位于旧战场与封锁区附近，温暖日常和黑暗历史同时真实存在。

- [ ] **Step 3：写入 Player 与 NPC 的精确边界**

Player 只固定以下事实：失忆、旅人、身有不明印记。姓名、职业、真实身份、印记来源和最终立场必须标为未定义。

NPC 角色卡必须包含以下六项：表层身份、欲望、内在矛盾、错误认知、刻意隐瞒、语言风格。知识矩阵使用四列：`确认知道`、`怀疑`、`错误相信`、`拒绝透露`。

角色事实必须包含：

- Ryan 的父亲曾因保护古族幸存者而被视为叛徒；Ryan 仍相信英雄史，同时害怕父亲真的背叛过一切；
- Shir 接触过守护被删除资料的隐秘组织，只知道档案存在缺口，不知道完整 Author Truth；
- Grey 经历灰烬战争，以沉默保护和平，但没有经历终焉战争；
- Ryan 尊敬 Grey、Shir 怀疑 Grey、Grey 保护 Ryan，三者关系只用于表达，不形成数值系统。

- [ ] **Step 4：写入当前任务的揭示上限**

当前章节只能揭示：旧封锁线、鞋边烧灼符号、该符号与玩家印记轮廓相似、孩子听见林中低语。不得证明玩家身份，不得解释印记来源，不得自动开启新任务或结局选择。

### Task 1.3：同步核心内容文档

**Files:**

- Modify: `docs/00_Project_Context.md`
- Modify: `docs/02_Product_Design.md`
- Modify: `docs/03_World_Model.md`
- Modify: `docs/04_NPC_Agent_Design.md`
- Modify: `docs/12_Game_Experience_Design.md`

**Interfaces:**

- Consumes: `docs/15_Story_Bible_CN.md`。
- Produces: 面向工程、产品、Agent 和体验的无冲突摘要。

- [ ] **Step 1：同步 Project Context 和 Product Design**

- `00` 增加“曦谷表面温暖、历史被改写”的一句话钩子，并明确 Phase 1E 是内容增强，不是新状态机；
- `02` 将当前玩家固定为失忆旅人和印记持有者；职业、关系、Memory、分支结局继续放在未来设想区；
- 两份文档都必须写明当前可玩内容仍是四地点、三 NPC、一个确定性任务。

- [ ] **Step 2：同步 World Model**

- 增加终焉战争与灰烬战争的两段时间线；
- 写明四地点显示名与稳定 ID 不变；
- 区分 Public Lore 和数据库权威状态：剧情事实不成为新的 World State 字段；
- 不修改 Tick、Action 或 Event 定义。

- [ ] **Step 3：同步 NPC Agent Design**

- 为 Ryan、Shir、Grey 增加知识边界表；
- 明确 Deterministic Decision 决定行动，LLM/Mock 只负责语言表达；
- 明确 NPC 不全知、不能从 Story Bible 越权泄露 Author Truth。

- [ ] **Step 4：同步 Game Experience Design**

- 在当前 DOM-first 体验中加入失忆玩家和印记钩子；
- 将失踪任务说明改为“当前章节对主线谜团的第一次轻触”；
- 保留 Phase 2 像素地图为后续展示层，不把它写成当前能力。

- [ ] **Step 5：运行 Module 1 内容测试并确认 GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_story_content.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6：执行人工连续性扫描**

Run:

```powershell
rg -n "阿莱瑞亚|曦谷城堡|Grey.*终焉战争.*亲历|终焉战争.*Grey.*亲历" docs\00_Project_Context.md docs\02_Product_Design.md docs\03_World_Model.md docs\04_NPC_Agent_Design.md docs\12_Game_Experience_Design.md docs\15_Story_Bible_CN.md
```

Expected: no matches. Design Spec 中用于解释废弃词的内容不属于本次扫描范围。

### Module 1 人工 Review 门

- [ ] 展示新增/修改文件列表；
- [ ] 展示 Story Bible 章节、两场战争和 NPC 知识矩阵摘要；
- [ ] 展示 `test_story_content.py` 结果；
- [ ] 展示完整 Diff；
- [ ] 暂停执行，等待用户人工 Review；
- [ ] 用户自行提交 Git。建议 Commit Message：`docs: establish aleria story bible`。

---

## Module 2：Prompt v3 与 Mock 角色化

**独立交付结果：** 默认 Chat 使用信息分层后的 Prompt v3；Mock 能对常见世界、身份和印记问题给出三种不同且不剧透的回答；Provider/Service/Fallback 不变。

### Task 2.1：先扩展 Prompt v3 配置契约

**Files:**

- Modify: `tests/backend/test_chat_config.py`
- Modify: `tests/backend/test_chat_context.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/chat_context.py`
- Modify: `.env.example`

**Interfaces:**

- Consumes: `Settings.chat_prompt_version`、`PromptLoader.load(version, npc_id)`。
- Produces: `Literal["v1", "v2", "v3"]` 和 `SUPPORTED_PROMPT_VERSIONS={"v1", "v2", "v3"}`；v3 为默认值。

- [ ] **Step 1：修改配置测试，先期望 v3**

```python
def test_settings_default_to_mock_and_prompt_v3():
    settings = Settings(_env_file=None)
    assert settings.chat_provider == "mock"
    assert settings.chat_prompt_version == "v3"


@pytest.mark.parametrize("version", ["v1", "v2", "v3"])
def test_settings_accept_supported_prompt_versions(version):
    settings = Settings(_env_file=None, chat_prompt_version=version)
    assert settings.chat_prompt_version == version
```

保留未知版本拒绝测试，但输入改为 `v4`。

- [ ] **Step 2：修改 Loader 测试，要求 v3 三角色资产存在**

```python
def test_prompt_loader_reads_non_empty_versioned_assets_for_known_npcs():
    loader = PromptLoader()
    for version in ("v1", "v2", "v3"):
        for npc_id, npc_name in (
            ("ryan", "Ryan"),
            ("shir", "Shir"),
            ("grey", "Grey"),
        ):
            bundle = loader.load(version=version, npc_id=npc_id)
            assert bundle.world_lore.strip()
            assert bundle.chat_system_prompt.strip()
            assert bundle.player_context.strip()
            assert npc_name in bundle.character_prompt
```

未知版本参数改为 `v4`；目录穿越和空文件测试保持不变。

- [ ] **Step 3：运行两个测试文件并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_chat_config.py tests\backend\test_chat_context.py -q -p no:cacheprovider
```

Expected: FAIL because Settings/Loader still reject v3 and v3 assets do not exist.

- [ ] **Step 4：做最小配置修改**

`backend/app/core/config.py`：

```python
chat_prompt_version: Literal["v1", "v2", "v3"] = "v3"
```

`backend/app/services/chat_context.py`：

```python
SUPPORTED_PROMPT_VERSIONS = {"v1", "v2", "v3"}
```

`.env.example`：

```env
CHAT_PROMPT_VERSION=v3
```

### Task 2.2：编写 Prompt v3 资产

**Files:**

- Create: `prompts/v3/world_lore.md`
- Create: `prompts/v3/chat_system.md`
- Create: `prompts/v3/player_context.md`
- Create: `prompts/v3/characters/ryan.md`
- Create: `prompts/v3/characters/shir.md`
- Create: `prompts/v3/characters/grey.md`
- Modify: `tests/backend/test_chat_context.py`

**Interfaces:**

- Consumes: `PromptLoader` 现有四文件加载顺序和 `PromptBundle`。
- Produces: 不改变任何 Python 类型的 v3 文本资产。

- [ ] **Step 1：先添加信息边界测试**

```python
def test_v3_prompt_separates_public_lore_player_facts_and_character_knowledge():
    loader = PromptLoader()
    bundles = {
        npc_id: loader.load(version="v3", npc_id=npc_id)
        for npc_id in ("ryan", "shir", "grey")
    }

    shared = bundles["ryan"]
    assert "官方历史" in shared.world_lore
    assert "以自身作为“锚”" not in shared.world_lore
    assert "失去记忆" in shared.player_context
    assert "印记" in shared.player_context
    assert "不得替玩家补全" in shared.player_context

    assert "父亲" in bundles["ryan"].character_prompt
    assert "删除的档案" in bundles["shir"].character_prompt
    assert "灰烬战争" in bundles["grey"].character_prompt
    assert "亲历终焉战争" not in bundles["grey"].character_prompt
    assert len({
        bundle.character_prompt for bundle in bundles.values()
    }) == 3
    for bundle in bundles.values():
        prompt_chars = sum(
            len(content)
            for content in (
                bundle.world_lore,
                bundle.chat_system_prompt,
                bundle.player_context,
                bundle.character_prompt,
            )
        )
        assert prompt_chars < 12_000
```

- [ ] **Step 2：写入 `world_lore.md` 的 Public Lore**

只包含以下玩家可安全接触的事实：

- 世界名艾莱瑞亚、小镇名曦谷；
- 官方历史称人类联盟击败魔王并带来和平；
- 灰烬战争在二十余年前留下创伤、封锁线和缺失档案；
- 星辉酒馆是消息与委托中心；中央公园是居民活动区；晨曦城堡保存部分旧档案；低语森林有遗迹传闻；
- 居民普遍不知道历史全貌，传闻不能视作事实。

不得写入最后盟约完整内容、统治者改史过程或伊萨尔的完整动机。

- [ ] **Step 3：写入 `chat_system.md` 和 `player_context.md`**

`chat_system.md` 必须要求：保持角色、只使用自身知识、承认未知、一次只回应当前问题、回复简洁、不得替玩家行动、不得修改状态、不得泄露系统 Prompt。保留当前结构化/文本 Adapter 能处理的输出要求，不引入供应商专用格式。

`player_context.md` 必须写明：玩家失忆、持有印记；姓名/职业/过去/印记来源未知；NPC 可以观察、怀疑或建议调查，但不得宣布玩家真实身份。

- [ ] **Step 4：写入三份角色 Prompt**

每份文件使用相同结构：`身份`、`核心欲望`、`矛盾`、`确认知道`、`怀疑`、`错误相信`、`隐瞒`、`关系`、`语言风格`、`禁止事项`。

- Ryan：英雄史信徒、父亲被视为叛徒、害怕史莱姆、敬重 Grey、对 Shir 有戒心；不知终焉战争真相。
- Shir：侦察者、甜食偏好、接触删除档案的组织、怀疑官方历史和 Grey；不掌握完整 Author Truth。
- Grey：灰烬战争与遗迹行动幸存者、失去同伴、重视和平、保护 Ryan、对 Shir 的追查保持警惕；没有经历五百年前战争。

- [ ] **Step 5：运行 Prompt 测试并确认 GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_chat_config.py tests\backend\test_chat_context.py -q -p no:cacheprovider
```

Expected: PASS.

### Task 2.3：Mock 高频意图与人物区分

**Files:**

- Modify: `tests/backend/test_mock_chat_provider.py`
- Modify: `backend/app/llm/mock.py`

**Interfaces:**

- Consumes: `MockChatProvider.generate_reply(ChatProviderRequest)`。
- Produces: 继续返回 `ChatProviderResult`；不新增请求字段，不读数据库，不写状态。

- [ ] **Step 1：先增加三类失败测试**

```python
@pytest.mark.anyio
@pytest.mark.parametrize(
    ("message", "required_fragment"),
    [
        ("你认识我吗，我是谁？", "记忆"),
        ("我身上的印记是什么？", "印记"),
        ("终焉战争和古族是什么？", "历史"),
    ],
)
async def test_mock_story_intents_are_distinct_grounded_and_non_omniscient(
    message,
    required_fragment,
):
    requests = [_request(npc_id, message) for npc_id in ("ryan", "shir", "grey")]
    results = [
        await MockChatProvider().generate_reply(request)
        for request in requests
    ]

    assert len({result.reply for result in results}) == 3
    assert all(required_fragment in result.reply for result in results)
    assert all("我知道你的真实身份" not in result.reply for result in results)
    assert all("五百年前我亲眼见过" not in result.reply for result in results)
```

另增加确定性测试：同一个角色、同一个请求调用两次，结果完全相等；已有测试保留。

- [ ] **Step 2：运行 Mock 测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_mock_chat_provider.py -q -p no:cacheprovider
```

Expected: FAIL because current Mock lacks player identity、mark and ancient-war intent.

- [ ] **Step 3：扩展 Intent 顺序和关键词**

按更具体到更一般的顺序增加：

```python
("player_identity", ("我是谁", "认识我", "我的记忆", "who am i")),
("mark", ("印记", "烙印", "符号", "mark")),
("ancient_history", ("终焉战争", "古族", "魔王", "伊萨尔")),
("ash_war", ("灰烬战争", "灰烬", "ash war")),
```

`ancient_history` 必须排在一般 `history` 前，避免具体问题被宽泛关键词提前匹配。

- [ ] **Step 4：实现三角色固定回复**

回复语义固定如下，允许为自然度调整标点，不改变知识边界：

| Intent | Ryan | Shir | Grey |
| --- | --- | --- | --- |
| player_identity | 不认识玩家过去；鼓励从现在选择成为谁；提到记忆 | 注意到失忆但不轻信；建议用证据找回记忆 | 承认无法证明身份；先保证安全再调查记忆 |
| mark | 不认识印记但愿意帮助查城堡记录 | 认为印记不像普通纹章，只承认怀疑 | 觉得轮廓令人不安但拒绝无证据定论 |
| ancient_history | 复述英雄史，同时承认父亲事件令自己动摇 | 指出历史档案有缺页，不宣布完整真相 | 承认历史并不完整，警告猜测不能代替证据 |
| ash_war | 只知道公开故事 | 知道旧封锁线和档案缺口 | 承认亲历并失去同伴，不倾倒全部经历 |

每条回复包含对应关键词“记忆”“印记”“历史”或“灰烬战争”，继续使用 `_default_emotion(request)`，不增加随机性。

- [ ] **Step 5：运行 Mock 与 Chat 回归测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_mock_chat_provider.py tests\backend\test_chat_service.py tests\backend\test_npc_chat_api.py tests\backend\test_openai_compatible_provider.py -q -p no:cacheprovider
```

Expected: PASS; no real network calls.

### Task 2.4：同步 Prompt 与运行环境文档

**Files:**

- Modify: `docs/08_Prompt_Engineering_CN.md`
- Modify: `docs/14_Development_Environment.md`

- [ ] **Step 1：更新 Prompt 工程文档**

写清四层信息、v3 目录、Loader 回退、角色知识隔离和不注入 Author Truth 的原因。删除或标记与当前 v3 冲突的旧玩家/世界设定。

- [ ] **Step 2：更新环境文档**

默认值改为 `CHAT_PROMPT_VERSION=v3`；`hy-role` 示例必须同时包含：

```env
CHAT_PROVIDER=hunyuan
CHAT_LLM_MODEL=hy-role
CHAT_LLM_OUTPUT_MODE=text
CHAT_LLM_TIMEOUT_SECONDS=30
CHAT_PROMPT_VERSION=v3
```

保留 Base URL 和 API Key 由用户在本地 `.env` 填写的安全说明；不读取 `.env`。

- [ ] **Step 3：运行 Module 2 全量相关测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_chat_config.py tests\backend\test_chat_context.py tests\backend\test_mock_chat_provider.py tests\backend\test_chat_service.py tests\backend\test_npc_chat_api.py tests\backend\test_openai_compatible_provider.py -q -p no:cacheprovider
```

Expected: PASS.

### Module 2 人工 Review 门

- [ ] 展示 Prompt v3 六个资产及 Loader/Settings Diff；
- [ ] 展示三位 NPC 同题 Mock 回复对照；
- [ ] 说明 Author Truth 未进入运行时 Prompt；
- [ ] 展示相关 Backend 测试结果与完整 Diff；
- [ ] 暂停执行，等待用户人工 Review；
- [ ] 用户自行提交 Git。建议 Commit Message：`feat: add prompt v3 and story-aware mock chat`。

---

## Module 3：任务、地点与前端叙事文案

**独立交付结果：** 不改变任务的六状态、五交互和共址规则，只让现有体验自然出现旧封锁线、鞋边灼痕、玩家印记与林中低语；前端明确玩家是失忆旅人。

### Task 3.1：先固定 Backend 文案契约

**Files:**

- Modify: `tests/backend/test_seed_world.py`
- Modify: `tests/backend/test_missing_child_quest.py`
- Modify: `tests/backend/test_player_quest_service.py`
- Modify: `tests/backend/test_phase1d_acceptance.py`

**Interfaces:**

- Consumes: `Location.description`、`MissingChildQuestPolicy.present()`、`PlayerQuestService._EVENT_DESCRIPTIONS`。
- Produces: 公共 API 结构不变，仅返回新文案。

- [ ] **Step 1：为四地点描述增加关键语义断言**

在 `test_seed_world.py` 中继续精确断言 ID、名称和排序；描述只断言稳定语义片段，避免整段文案变成脆弱契约：

```python
descriptions = {
    location.id: location.description for location in seed.locations
}
required_fragments = {
    "tavern": ("炉火", "委托"),
    "park": ("骑士训练", "战争旧痕"),
    "castle": ("灰烬战争", "残缺档案"),
    "forest": ("古老遗迹", "旧封锁线"),
}
for location_id, fragments in required_fragments.items():
    assert all(
        fragment in descriptions[location_id] for fragment in fragments
    )
```

- [ ] **Step 2：更新任务目标期望，不改状态表**

`VALID_TRANSITIONS` 必须原样保留。只更新 presentation 断言：

```python
EXPECTED_OBJECTIVES = {
    "available": "查看星辉酒馆告示板上的失踪委托。",
    "accepted": "前往晨曦城堡询问 Grey。",
    "briefed_by_grey": "前往低语森林，在灰烬战争旧封锁线附近寻找线索。",
    "shoe_found": "调查鞋边的灼痕，并沿孩子留下的痕迹继续寻找。",
    "child_found": "护送孩子返回星辉酒馆，并记下他提到的林中低语。",
    "completed": "孩子已经安全回家；鞋边印记仍没有答案。",
}
```

accepted 状态在 Grey 移动后仍由现有逻辑动态生成 `前往{target_npc_location_name}询问 Grey。`。

- [ ] **Step 3：更新五条事件的关键语义期望**

```python
EXPECTED_EVENT_FRAGMENTS = {
    "accept_quest": ("星辉酒馆", "接受"),
    "ask_grey": ("Grey", "灰烬战争旧封锁线"),
    "inspect_shoe": ("烧灼符号", "身上的印记"),
    "search_child": ("找到", "林中传来的低语"),
    "return_child": ("安全带回", "印记之谜"),
}
```

测试断言对应事件 description 同时包含该 interaction 的全部片段；实现仍使用 Task 3.2 指定的完整文案。

- [ ] **Step 4：运行 Backend 目标测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_seed_world.py tests\backend\test_missing_child_quest.py tests\backend\test_player_quest_service.py tests\backend\test_phase1d_acceptance.py -q -p no:cacheprovider
```

Expected: FAIL only on changed description/objective/event text; transition、location co-presence and persistence tests remain structurally valid.

### Task 3.2：最小更新 Backend 和种子文案

**Files:**

- Modify: `data/locations.json`
- Modify: `backend/app/quests/missing_child.py`
- Modify: `backend/app/services/player_quest_service.py`

- [ ] **Step 1：替换四地点 description**

使用以下完整文本；不改 `id`、`name` 或 `sort_order`：

- `tavern`：`炉火、消息与委托汇聚的温暖酒馆，许多旅人故事从这里开始`
- `park`：`居民散步与骑士训练的开阔绿地，日常生活掩映着战争旧痕`
- `castle`：`守望曦谷的古老城堡，深处封存着灰烬战争留下的残缺档案`
- `forest`：`林间低语与古老遗迹交织的幽深森林，部分区域仍属于旧封锁线`

- [ ] **Step 2：替换 `_OBJECTIVES` 文案**

使用 `EXPECTED_OBJECTIVES` 中六条文本；保留 `_TRANSITIONS`、动态 Grey 位置和 `_INTERACTION_LABELS` 的行为。

- [ ] **Step 3：替换 `_EVENT_DESCRIPTIONS` 文案**

使用 Task 3.1 语义表对应的以下完整文本；不向 Event 表新增字段：

- `accept_quest`：`你在星辉酒馆接受了寻找失踪孩子的委托。`
- `ask_grey`：`Grey 告诉你，孩子最后出现在低语森林的灰烬战争旧封锁线附近。`
- `inspect_shoe`：`你在鞋旁发现烧灼符号，轮廓与你身上的印记相似。`
- `search_child`：`你沿着痕迹找到了孩子；他反复提到林中传来的低语。`
- `return_child`：`你把孩子安全带回星辉酒馆；委托结束，印记之谜却刚刚开始。`

- [ ] **Step 4：运行 Backend 测试并确认 GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_seed_world.py tests\backend\test_missing_child_quest.py tests\backend\test_player_quest_service.py tests\backend\test_phase1d_acceptance.py -q -p no:cacheprovider
```

Expected: PASS.

### Task 3.3：Frontend 展示失忆钩子和完成余韵

**Files:**

- Modify: `tests/frontend/fixtures.ts`
- Modify: `tests/frontend/PlayerLocationPanel.spec.ts`
- Modify: `tests/frontend/QuestPanel.spec.ts`
- Modify: `frontend/src/components/PlayerLocationPanel.vue`
- Modify: `frontend/src/components/QuestPanel.vue`

**Interfaces:**

- Consumes: 现有 `PlayerData` 和 `QuestData`；不增加 TypeScript 字段。
- Produces: 纯展示文案；Store/API/类型保持不变。

- [ ] **Step 1：先更新 Fixtures 与失败测试**

- 四地点 fixture description 与 `data/locations.json` 一致；
- available/accepted/briefed/completed objective 与 Backend 一致；
- recent event fixture 使用新事件描述。

`PlayerLocationPanel.spec.ts` 增加：

```typescript
expect(wrapper.text()).toContain('失去记忆')
expect(wrapper.text()).toContain('无法解释的印记')
```

`QuestPanel.spec.ts` 完成态增加：

```typescript
expect(wrapper.text()).toContain('孩子安全回到了星辉酒馆')
expect(wrapper.text()).toContain('印记仍没有答案')
```

- [ ] **Step 2：运行 Frontend 目标测试并确认 RED**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\PlayerLocationPanel.spec.ts ..\tests\frontend\QuestPanel.spec.ts
```

Expected: FAIL because components do not yet render the new text.

- [ ] **Step 3：最小更新组件**

`PlayerLocationPanel.vue` 在“旅行者”下显示：

```html
<p class="player-hook">失去记忆，只留下一个无法解释的印记。</p>
```

`QuestPanel.vue` 完成态显示：

```html
任务已经完成，孩子安全回到了星辉酒馆；鞋边的印记仍没有答案。
```

为 `.player-hook` 复用现有次要文字颜色和行高，不重构布局。

- [ ] **Step 4：运行 Frontend 目标测试并确认 GREEN**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\PlayerLocationPanel.spec.ts ..\tests\frontend\QuestPanel.spec.ts
```

Expected: PASS.

- [ ] **Step 5：运行 Module 3 回归**

Backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_seed_world.py tests\backend\test_missing_child_quest.py tests\backend\test_player_quest_service.py tests\backend\test_phase1d_acceptance.py -q -p no:cacheprovider
```

Frontend:

```powershell
Set-Location frontend
npm test
npm run type-check
npm run build
```

Expected: all PASS.

### Module 3 人工 Review 门

- [ ] 展示 Quest 六状态和五迁移没有变化的证据；
- [ ] 对照展示五条 Event 文案与四地点描述；
- [ ] 展示玩家钩子和任务完成态组件 Diff；
- [ ] 展示 Backend/Frontend 测试、类型检查和构建结果；
- [ ] 提醒用户：`seed_world.py` 会重置本地状态，Review 阶段不自动执行真实数据库重置；
- [ ] 暂停执行，等待用户人工 Review；
- [ ] 用户自行提交 Git。建议 Commit Message：`feat: connect missing-child quest to aleria lore`。

---

## Module 4：README 提交叙事、验收与文档收口

**独立交付结果：** README 能先讲清游戏、再让评审零密钥启动、最后解释架构和 AI 工程判断；`hy-role` 推荐准确且不过度承诺；全项目通过 Phase 1E 自动与人工验收。

### Task 4.1：先建立 README 内容契约

**Files:**

- Modify: `tests/backend/test_story_content.py`
- Create: `tests/backend/test_phase1e_acceptance.py`

**Interfaces:**

- Consumes: `README.md`、Prompt v3、Mock、Player/Quest 和 Chat API。
- Produces: 无真实网络的提交级验收。

- [ ] **Step 1：为 README 增加失败测试**

```python
def test_readme_is_game_first_and_recommends_hy_role_with_scope():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    ordered_headings = (
        "## 这是什么游戏",
        "## 当前可以体验什么",
        "## 世界与角色",
        "## 快速启动：Mock 模式",
        "## 真实 AI 与 hy-role 推荐",
        "## 架构、接口与决策流程",
        "## AI 工具使用与人工修正案例",
        "## 测试、限制与路线图",
    )
    positions = [readme.index(heading) for heading in ordered_headings]
    assert positions == sorted(positions)
    assert "本项目 NPC 角色对话实测" in readme
    assert "CHAT_LLM_MODEL=hy-role" in readme
    assert "CHAT_LLM_OUTPUT_MODE=text" in readme
    assert "CHAT_PROMPT_VERSION=v3" in readme
    assert "行业最聪明" not in readme
    assert "计划在 Phase 1E 完成部署" not in readme
```

- [ ] **Step 2：写入完整 Phase 1E 跨模块验收测试**

`tests/backend/test_phase1e_acceptance.py` 使用以下完整结构；helper 定义在本文件，不跨测试文件导入：

```python
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    ConversationMessage,
    Event,
    NpcState,
    PlayerState,
    QuestProgress,
    WorldAction,
    WorldState,
)
from backend.app.main import create_app
from scripts.seed_world import seed_database


def _settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=database_url,
        chat_provider="mock",
        chat_prompt_version="v3",
    )


def _game_snapshot(session_factory):
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        player = session.get(PlayerState, "default-player")
        quest = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        assert world is not None
        assert player is not None
        assert quest is not None
        return {
            "world": (world.day, world.time, world.tick),
            "npcs": tuple(
                (
                    state.npc_id,
                    state.location_id,
                    state.current_action,
                    state.energy,
                    state.mood,
                    state.social,
                )
                for state in session.scalars(
                    select(NpcState).order_by(NpcState.npc_id)
                )
            ),
            "actions": session.scalar(
                select(func.count()).select_from(WorldAction)
            ),
            "events": session.scalar(
                select(func.count()).select_from(Event)
            ),
            "player": player.location_id,
            "quest": (quest.status, quest.version, quest.updated_tick),
        }


def _message_count(session_factory) -> int:
    with session_factory() as session:
        return session.scalar(
            select(func.count()).select_from(ConversationMessage)
        )


async def _interact(
    client: AsyncClient,
    interaction: str,
    version: int,
):
    response = await client.post(
        "/api/quests/missing-child/interact",
        json={"interaction": interaction, "expected_version": version},
    )
    assert response.status_code == 200
    return response.json()["data"]


async def _travel(client: AsyncClient, location_id: str):
    response = await client.post(
        "/api/player/travel",
        json={"target_location_id": location_id},
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.mark.anyio
async def test_phase1e_v3_mock_replies_are_distinct_and_game_state_is_read_only(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    before = _game_snapshot(session_factory)
    app = create_app(database_url, settings=_settings(database_url))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        responses = [
            await client.post(
                f"/api/npcs/{npc_id}/chat",
                json={"message": "历史书可信吗？"},
            )
            for npc_id in ("ryan", "shir", "grey")
        ]

    assert all(response.status_code == 200 for response in responses)
    data = [response.json()["data"] for response in responses]
    replies = [item["turn"]["assistant"]["content"] for item in data]
    assert len(set(replies)) == 3
    assert all(item["provider"] == "mock" for item in data)
    assert all(item["fallback_used"] is False for item in data)
    assert _message_count(session_factory) == 6
    assert _game_snapshot(session_factory) == before


@pytest.mark.anyio
async def test_phase1e_missing_child_story_uses_existing_five_transitions(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    app = create_app(database_url, settings=_settings(database_url))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await _interact(client, "accept_quest", 0)
        await _travel(client, "castle")
        await _interact(client, "ask_grey", 1)
        await _travel(client, "forest")
        await _interact(client, "inspect_shoe", 2)
        await _interact(client, "search_child", 3)
        await _travel(client, "tavern")
        completed = await _interact(client, "return_child", 4)

    quest = completed["quest"]
    descriptions = [
        event["description"] for event in quest["recent_events"]
    ]
    assert (quest["status"], quest["version"]) == ("completed", 5)
    assert len(descriptions) == 5
    assert "旧封锁线" in descriptions[1]
    assert "身上的印记" in descriptions[2]
    assert "林中传来的低语" in descriptions[3]
    assert "印记之谜" in descriptions[4]
    assert "鞋边印记仍没有答案" in quest["objective"]
```

- [ ] **Step 3：运行测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_story_content.py tests\backend\test_phase1e_acceptance.py -q -p no:cacheprovider
```

Expected: README heading contract FAIL. If Module 2/3 已正确完成，Phase 1E API acceptance should already PASS；其失败表示前置模块存在回归。

### Task 4.2：重写 README 为游戏作品首页

**Files:**

- Modify: `README.md`

- [ ] **Step 1：按固定顺序重组一级内容**

README 必须包含 Task 4.1 的八个二级标题，并按该顺序排列。

首屏内容使用无剧透表述：

> 曦谷是一座从战争中恢复的温暖小镇。你是一名失去记忆、身带陌生印记的旅人；一次寻找失踪孩子的委托，将你带向城堡残缺的档案和森林深处的旧封锁线。

核心命题只用一句话呈现，不公开最后盟约完整真相。

- [ ] **Step 2：清楚展示当前玩法和三位 NPC**

当前体验路径必须列出：查看世界与 NPC、推进 Tick、玩家旅行、在 Grey 实时地点询问、森林调查、返回酒馆、Mock/真实 Chat。明确 Chat 不改变世界和任务。

NPC 卡片必须各写一条外显性格和一条矛盾：

- Ryan：相信英雄，却被父亲的“叛徒”过去困扰；
- Shir：追索真相，却不确定所有真相都应立刻公开；
- Grey：保护和平，却知道沉默也可能延续错误。

- [ ] **Step 3：把 Mock 快速启动放在真实模型之前**

保留可直接复制的 Backend、Frontend 启动命令；默认 `CHAT_PROVIDER=mock`、无需 Key。明确 `seed_world.py` 会重置演示数据，`upgrade_schema.py` 才用于保留状态的增量建表。

- [ ] **Step 4：写入 `hy-role` 实测推荐**

使用以下限定表述：

> 基于本项目 NPC 角色对话的实际测试，`hy-role` 在角色一致性、上下文理解和自然表达方面表现最好，因此推荐作为本项目的首选真实模型。该结论只代表本项目场景下的体验，不构成通用模型排名。

配置必须包含 `CHAT_PROVIDER=hunyuan`、`CHAT_LLM_MODEL=hy-role`、`CHAT_LLM_OUTPUT_MODE=text`、`CHAT_PROMPT_VERSION=v3` 和 30 秒超时。Base URL 与 API Key 继续使用安全占位说明，不写真实值。

对话示例遵循以下规则：

- 若用户在 Module 4 开始前提供已确认的真实回复，截取一到两轮并标记“脱敏实测示例”；
- 若没有提供真实回复，使用一轮 Grey 对“历史书可信吗”的短回答，并明确标记“示意对话”，不得伪装成实测；
- 两种情况都不展示完整 Prompt、响应正文日志、Key 或 Header。

- [ ] **Step 5：重写架构、接口、测试和边界部分**

- 架构图区分 deterministic World Engine 与 generative Chat；
- 接口表只列当前七个端点；
- 决策流程写明 Snapshot → Decision → Validation → Persistence；
- AI 修正案例使用真实 `hy-role` 自然文本触发 `response_validation`、随后只在 Adapter 增加 text mode 的过程；
- 当前能力与未来规划分区；Phase 2 才是像素地图，Phase 3 才是部署和 Docker。

- [ ] **Step 6：保留提交信息但不虚构未知值**

候选人姓名、仓库地址和实际开发用时由用户提交前填写；线上体验未部署时明确写 `N/A（Phase 3 计划）`。不得由实现者猜测个人信息、仓库 URL 或开发时长。

### Task 4.3：同步决策、工作流、结构与路线图

**Files:**

- Modify: `docs/09_Decision_Log.md`
- Modify: `docs/10_AI_Coding_Workflow.md`
- Modify: `docs/11_Project_Structure.md`
- Modify: `docs/13_Development_Roadmap.md`

- [ ] **Step 1：Decision Log 追加四条 Phase 1E 决策**

记录：Story Bible 是事实源；Author Truth 不注入运行时；Prompt v3 按角色分知识；`hy-role` 是场景化实测推荐而非供应商耦合。

- [ ] **Step 2：更新 AI Coding Workflow**

保留“人定义目标、AI 加速实现、人工 Review”的主线；将 `hy-role` 修正案例写成 Observation → Diagnosis → Minimal Fix → Regression 四段，并明确没有复制 Hunyuan 专用 Provider。

- [ ] **Step 3：更新 Project Structure**

加入 `docs/15_Story_Bible_CN.md`、`prompts/v3/`、`tests/backend/test_story_content.py` 和 `tests/backend/test_phase1e_acceptance.py` 的职责说明；v1/v2 标记为回退资产。

- [ ] **Step 4：修正 Roadmap**

权威顺序统一为：

```text
Phase 1E：内容圣经与提交叙事
Phase 2：像素 RPG 地图与角色交互
Phase 2B：动画、响应式与体验打磨
Phase 3：Docker、线上部署、截图、演示视频与最终交付
Phase 3+：更多任务、Relationship、有限 Memory 或高级 Agent
```

删除“Phase 1E 是部署工程”的旧说法。

### Task 4.4：运行 Phase 1E 跨模块与全量验证

- [ ] **Step 1：运行内容与跨模块验收并确认 GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_story_content.py tests\backend\test_phase1e_acceptance.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2：运行 Backend 全量测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider
```

Expected: PASS; no real provider request and no API Key access.

- [ ] **Step 3：运行 Frontend 全量验证**

Run:

```powershell
Set-Location frontend
npm test
npm run type-check
npm run build
```

Expected: all PASS.

- [ ] **Step 4：执行最终术语与范围扫描**

Run:

```powershell
rg -n "阿莱瑞亚|曦谷城堡|Grey.*终焉战争.*亲历|计划在 Phase 1E 完成部署|行业最聪明" README.md docs\00_Project_Context.md docs\02_Product_Design.md docs\03_World_Model.md docs\04_NPC_Agent_Design.md docs\08_Prompt_Engineering_CN.md docs\10_AI_Coding_Workflow.md docs\12_Game_Experience_Design.md docs\13_Development_Roadmap.md docs\14_Development_Environment.md docs\15_Story_Bible_CN.md prompts\v3
```

Expected: no matches. `docs/09_Decision_Log.md` 和 Phase 1E Spec/Plan 会保留历史决策或反例表述，不参与无条件禁词扫描。

### Task 4.5：人工体验验收

- [ ] Mock 模式启动 Backend 和 Frontend，不配置 API Key；
- [ ] 确认首屏仍能查看四地点、三 NPC、玩家和任务；
- [ ] 分别询问 Ryan、Shir、Grey：“你是谁”“这里是哪里”“历史书可信吗”“你认识我的印记吗”；
- [ ] 确认三人回答具有区分、没有全知泄密、没有推进状态；
- [ ] 完成失踪孩子五步流程，确认旧封锁线、烧灼符号、相似印记和林中低语依次出现；
- [ ] 推进一次 World Tick，确认 NPC 行动仍由确定性引擎决定；
- [ ] 若用户愿意，使用本地已配置的 `hy-role` 进行一次人工对话验收；不输出 Key/Header/完整 Prompt，真实网络验证不作为自动测试条件；
- [ ] 阅读 README，确认无 Key 用户可以按步骤在本地启动；
- [ ] 确认 README 没有宣称已实现像素地图、分支结局、Docker 或线上地址。

### Module 4 人工 Review 门

- [ ] 展示 README 新旧信息架构对照；
- [ ] 展示 `hy-role` 推荐措辞与对话示例来源标签；
- [ ] 展示 Decision Log、Workflow、Structure、Roadmap 同步内容；
- [ ] 展示 Backend/Frontend 全量测试和构建结果；
- [ ] 展示最终工作区完整 Diff 与未提交文件列表；
- [ ] 暂停执行，等待用户人工 Review；
- [ ] 用户自行提交 Git。建议 Commit Message：`docs: finalize phase 1e submission narrative`。

---

## 最终完成判定

只有同时满足以下条件，Phase 1E 才可标记完成：

- `docs/15_Story_Bible_CN.md` 是唯一内容事实源，时间线和人物经历无冲突；
- Prompt v3 默认启用，v1/v2 仍可加载；
- Mock 对身份、印记、两场战争和任务问题具有角色区分；
- Author Truth 没有整体进入 Prompt 或 README 无剧透介绍；
- Quest 稳定 ID、六状态、五迁移、共址检查和 version 乐观锁全部不变；
- Chat 仍不改变 World、NPC、Player 或 Quest；
- README 覆盖玩法/NPC、技术选型、接口与决策、启动、AI/Mock、AI 工具和人工修正案例；
- `hy-role` 推荐有明确项目场景限定，示例脱敏且来源标签准确；
- Backend 全量 pytest 通过；
- Frontend Vitest、TypeScript 和生产构建通过；
- 用户完成四次 Module Review，并由用户自行提交所有 Git Commit。

## 执行方式

按用户此前确定的方式，默认使用 **Inline Execution**：每次只执行一个 Module，内部严格按 RED → GREEN → Regression 推进；Module 结束立即暂停并汇报修改文件、设计说明、测试结果和 Diff。只有用户明确回复进入下一模块后，才继续执行。
