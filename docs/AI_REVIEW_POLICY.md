# Aleria AI Town AI Review Policy

Version: v1.1 · Updated: 2026-09-13

面向 AI coding agent（Claude Code、Codex 等）的**项目级 review 流程规范**。

**阅读规则**：本文严格区分 `现行规范`（第 0–8 章，**立即生效，可手工执行**）与 `Proposed`（第 9 章，`scripts/review_baseline.py` **尚不存在**）。不要 import、调用或假设第 9 章的任何内容存在。

**事实基准**：HEAD `85ce338`；`core.autocrlf = true`；`.superpowers/sdd/` 由嵌套 `.gitignore`（内容为 `*`）忽略；git 2.54.0.windows.1。本文引用的体量数字全部来自本仓库实测，见 §1.3。

---

## 0. 适用范围与非目标

### 0.1 适用范围

本文规范**所有**由 AI agent 产出、需要独立 review 才能交付人类的改动，包括生产代码、测试、权威文档与迁移。

### 0.2 与其他文档的关系

本文管**流程**（谁审、审什么、输入多大、几轮），不管**产物**（要实现什么、契约长什么样）。因此它与 `AGENTS.md` 的文档优先级链**正交**：

```
产物权威：Spec > Plan > Roadmap > docs/0X_*.md > 代码注释
流程权威：AI_REVIEW_POLICY（本文）
```

本文**不得**用于解释或推翻 Spec 的任何产物条款。两者若看似冲突，说明本文写错了，按 Spec 执行并记录 Ruling。

### 0.3 目标

| # | 目标 | 判定标准 |
| --- | --- | --- |
| G1 | 消除已批准内容的重复复核 | 任何一行代码在无修改状态下不得被第二次全量审读 |
| G2 | 定级由风险触发，不由人临时拍板 | 给定同一改动，两个不同 agent 应推导出同一等级 |
| G3 | 固化 review package 的最小必需内容与默认排除项 | package 生成可复现，跨会话一致 |
| G4 | 规定 fix 后的 re-review 范围与席位收敛条件 | 默认 scoped + 单席；升级条件成文可判定 |
| G5 | 适配"agent 不提交"的 Git 约束 | package 从工作树 + 未跟踪文件生成，不依赖 commit range |
| G6 | 保留已被验证有效的质量机制 | 独立性、越界探查权、非空区分度证据、5 轮 breaker 全部保留 |

### 0.4 非目标（防止后续 agent 误读为"省 token 优先"）

- **不**减少独立 reviewer 的判断独立性；reviewer 永远不看 controller 的会话历史。
- **不**允许以"diff 小"作为跳过 review 的理由。
- **不**禁止 reviewer 读 diff 之外的代码——只要求它命名风险并说明检查了什么。
- **不**把 Critical / Important 降级为 Minor 来结束循环。

> 本文所有优化针对的是**重复读取**，不是**判断本身**。席位数量、独立性、探查权、证据强度四项不因任何 token 考量而下降。

---

## 1. 术语

### 1.1 流程术语

| 术语 | 定义 |
| --- | --- |
| **Gate（门）** | 一个必须通过 review 才能继续的检查点。门位有三种：Step Gate、Task Gate、Stage Gate（含 segment 关闭）。 |
| **Level（等级）** | 本次 gate 的 review 强度，取值 R0–R3，由 §2.3 触发表判定。 |
| **Seat（席位）** | 一个独立 reviewer 及其职责面。等级决定席位数量与角色。 |
| **Baseline（基线）** | 一次可复现的仓库状态锚点，用于计算增量。见第 3 章。 |
| **Package（复核包）** | 交给 reviewer 的单一文件，包含身份、完整性证明、变更统计与增量 diff。见第 4 章。 |
| **Delta（增量）** | `基线 → 当前工作树` 的差异。所有 review 的默认输入。 |
| **Drift（漂移）** | 授权范围**之外**的文件发生了改动。增量 review 的否决条件。 |
| **Controller** | 驱动 SDD 流程的主代理。它不做 review，不亲自修 findings。 |

### 1.2 Finding 严重度

沿用 Superpowers 的三档，本文不重新定义，只补充本项目的判定补充：

| 档 | 含义 | 本项目补充 |
| --- | --- | --- |
| **Critical** | 必须立即修复 | 破坏跨 Stage 不变量、数据丢失、权限泄露 |
| **Important** | 修复前该改动不可信 | **包含**"在空集合上恒真的负向测试"（本项目已实际发生并被判为 Important） |
| **Minor** | 可延后 | 记入 ledger 的 deferred minor，永不进入 fix 循环 |

### 1.3 体量基准（实测，用于校准"包是否过大"）

| 场景 | 实测值 |
| --- | --- |
| Stage 2 总 diff（`ba935ae..HEAD`） | 75 文件，+9,407 / −86 |
| 组成 | tests 44%、backend 30%、docs（Spec/Plan 自身）21%、frontend 4% |
| Stage final package（现状） | **740,903 bytes / 15,119 行**，spec + quality **两席各完整读一遍** |
| Task 级 package（现状） | 135,689 / 83,757 / 91,384 / 84,512 bytes |
| scoped fix package（已有正例） | **18,537 bytes / 394 行**，比同 Task 全量包小 **78%** |
| 全 Stage 范围快照体量 | 88 文件 / 1,052,933 bytes ≈ **1.0 MB** |
| `.superpowers/sdd/` 现有体量 | 4.2 MB |

---

## 2. Review Level 分级

### 2.1 为什么不按 diff 大小分级

本项目**禁止**使用"轻量 / 标准 / 架构"这类按体量命名的分级，理由来自本仓库的真实记录：

1. **行数与风险不相关。** 最危险的一条 Important（隐私测试跑在空列表上）出现在 **394 行**的 fix 包里；而 740,903 bytes 的 final 包中，全部 Important 集中在约 5 个函数内。
2. **"架构"在本项目是常态而非例外。** Stage 2 的五个 Task 全部改架构（六张新表、新 Public API、新事务边界）。把它当最高档，结果是所有 Task 都落最高档，分级失效。
3. **风险清单已经存在。** `AGENTS.md` 的"修改架构前必须确认边界"6 条与"跨 Stage 不变量"6 条就是本项目的风险定义。等级必须挂在这份清单上，另造词汇只会让两份清单漂移。

### 2.2 四个等级

| 等级 | 名称 | 定义 |
| --- | --- | --- |
| **R0** | 自检（Self-Check） | 无独立 reviewer；implementer 自检 + controller 核对真实验证输出 |
| **R1** | 聚焦复核（Focused Review） | 1 席独立 reviewer，一次 dispatch 同时给出契约与质量两个 verdict |
| **R2** | 双轨复核（Dual-Track Review） | 2 席独立 reviewer 并行，职责边界互斥 |
| **R3** | 边界评审（Boundary Review） | R2 + 不变量/证据席，覆盖跨 Task 与跨 Stage 断言 |

### 2.3 定级触发表（唯一判据）

**按"命中即升级"取最高档。** 触发条款引用 `AGENTS.md`，不在此复制正文，避免两份清单漂移。

#### R3 触发（任意一条命中）

- Stage 关闭，或 segment 关闭
- 新增 / 修改 Alembic revision，或数据库表、列、约束
- 改变事务边界或 Session 归属
- 改变 `world_version` / `clock_tick` / `event_sequence` 的语义
- 放宽任何权限 scope、secrecy 或 disclosure 规则
- 引入新的第三方框架或基础设施依赖
- 触及 `AGENTS.md`「跨 Stage 不变量」六条中的任意一条

#### R2 触发（未命中 R3，且任意一条命中）

- 新增 / 修改 Public API 的请求、响应或状态码
- 涉及并发、重试、超时、幂等，或 cursor / checkpoint 推进
- 涉及外部 Provider 调用（Chat / Embedding / Reflection）
- 跨栈改动（backend 与 frontend 同时改）
- 修改权威投影或公开 DTO 的构造路径
- 单次改动 > 8 个文件，或触及 > 2 个 backend 分层目录

#### R1 触发（未命中以上，且任意一条命中）

- 单层内的有界实现（仅 `services/`、仅 `agents/`、或仅 `frontend/`）
- 仅测试改动，但改动了断言语义或 mock 边界
- 权威文档改动：`docs/05`、`docs/06`、`docs/07`、`docs/14`、`README.md` 契约段、`docs/ARCHITECTURE.md` 的 Implemented 段

#### R0（以上全部未命中）

- 纯格式化、注释排版
- `CURRENT_STATE.md` / ledger 的状态更新
- 非规范性文档正文（`docs/00–04`、`12`、`15` 的叙事段）
- 新增测试且不改动任何既有断言与 mock 行为

> **权威文档进 R1，不进 R0。** 依据：Stage 2 Step 7 是 docs-only 改动，仍被 spec reviewer 判出 Important（README / API / ARCHITECTURE / CURRENT_STATE 互相矛盾）。R1 对文档的判据是**逐字段对齐实现**，不是文风。

### 2.4 门位下限与向上取整

| 规则 | 内容 |
| --- | --- |
| **门位下限** | Task Gate 最低 R1；Stage Gate 与 segment 关闭最低 R3。等级只能向上，不能向下。 |
| **向上取整** | 定级存疑时取更高档。 |
| **必须记录** | 每次定级写入 ledger：`Ruling: 定级 <R?> — <命中条款> — <若定低了的代价>` |

### 2.5 各等级的完整定义

| 维度 | R0 | R1 | R2 | R3 |
| --- | --- | --- | --- | --- |
| **reviewer 席位** | 0 | 1 | 2（并行） | 3（并行） |
| **独立性** | — | 必须独立 | 必须独立，两席不得互看报告 | 必须独立；不变量席用本 gate 能力最强模型 |
| **输入范围** | 本次 delta + 验证矩阵输出 | scoped delta + binding 条款摘录 | delta + 条款摘录 + 证据索引 + 风险清单 | 自上一次通过 R2/R3 以来的 delta + 证据索引 + 跨 Task 不变量断言表 + 验收命令实测输出 |
| **需要 package** | 否 | 是（Lite） | 是（Standard） | 是（Boundary，**≠ full diff**） |
| **通过条件** | 验证矩阵无新增 skip / warning，且 controller 核对了真实输出 | Critical 0、Important 0 | 两席 Critical 0、Important 0，findings 去重合并 | 三席 Critical 0、Important 0，且不变量席逐条给出「已验证 / 无法从本包验证」 |
| **包体量目标** | — | ≤ 15 KB | ≤ 60 KB | ≤ 120 KB |

### 2.6 席位职责互斥表

依据：Stage 2 Task 5 段 1 中，两席**各自独立报告了同一条 Minor**（`NpcDetailPanel.vue` 悬空 `aria-controls`）。重叠部分的 token 双倍支付且零增量收益。

| 席位 | 拥有 | 明确不拥有 |
| --- | --- | --- |
| **契约席（Spec）** | Spec / Plan 条款符合性、Public API 形状与状态码、权限 scope 与披露边界、DTO 字段逐项对齐、范围越界（多做 / 少做） | 并发、事务、测试有效性、代码结构、a11y |
| **质量席（Quality）** | 正确性、并发 / 事务 / 重试 / 幂等、测试是否验证真实行为、错误处理、结构与重复、UI 行为与 a11y | Spec 条款的解释权——发现疑似冲突应交 controller 裁定，不自行判定 Spec 含义 |
| **不变量席（Boundary，仅 R3）** | `AGENTS.md` 六条跨 Stage 不变量、迁移与 ORM 同构、三套计数器语义、验收证据真实性（命令是否真跑过、数字是否自洽）、文档与实现一致性 | 逐行代码风格、Minor 级建议 |

**边界重叠时**：由触发面的拥有者报告完整 finding；另一席只写一行"交叉观察"，不展开论证。

---

## 3. Baseline Snapshot

### 3.1 为什么需要（Git 不 commit 约束的直接后果）

`AGENTS.md` 规定 agent 不得执行任何 git 写命令，产出停留在未暂存工作树。这条规则本身是正确的且必须保留——Stage 2 的可审查提交粒度正是靠它维持的。但它产生四个连锁后果：

| # | 后果 | 证据 |
| --- | --- | --- |
| 1 | **没有可寻址的基线标识。** Superpowers 的 `review-package PLAN BASE HEAD` 依赖 commit range，而 agent 交付时该区间恒为空 | Task 5 段 2 的 19 个文件全部在 HEAD 之后、commit 之前 |
| 2 | **BASE 只能退到更早的 commit**，于是包里必然含全部已批准的历史内容 | Stage final 包取 BASE = `ba935ae`，结果 740,903 bytes |
| 3 | **未跟踪文件必须整文附上**，且每次重复 | 当前 6 个未跟踪文件中 3 份协作文档合计 55 KB |
| 4 | **无法机器证明"范围外没被动过"**，因此 reviewer 要求 full package 是正当的 | — |

> 结论：问题不是"不 commit"，而是"不 commit 之后没有等价物"。解决方案不是让 agent 去 commit，而是提供一个**与 commit 等价、但不写 git 的内容寻址锚点**——即 baseline snapshot。

### 3.2 Baseline 保存什么

四类内容，每类对应一种失效模式，缺一不可。

#### ① 身份（Identity）

```
baseline_id        B0007（单调递增，跨会话稳定）
created_at         ISO 8601 带时区
plan               docs/superpowers/plans/<...>.md
gate               {kind: step|task|segment|stage, task, segment, round}
kind               approved | before        ← 见 §3.4
form               C（有等价 commit） | W（纯工作树）
```

#### ② Git 状态（Git State）

```
head_sha           完整 SHA + 短 SHA + subject
index_clean        git diff --cached --quiet 的结果
status_porcelain   git status --porcelain -uall 的【原文】，存为 state.txt
status_sha256      上述原文的 sha256
branch             当前分支名
```

`status_porcelain` 必须存**原文**而非仅哈希：它是"当时到底有哪些文件处于什么状态"的唯一权威记录，reviewer 第一步就靠它核对文件计数。

#### ③ 文件层（Files）——分两层，必须分开

**(a) Scope 副本**：只复制本次授权范围内的文件，按仓库相对路径镜像存放（沿用仓库已有布局）：

```
files/backend/app/services/memory_explanation.py
files/tests/backend/test_npc_api.py
```

**(b) 全仓指纹**：**不复制内容，只记哈希**，但覆盖**所有**与 HEAD 不同的文件 + **所有**未跟踪文件：

```
repo_fingerprint:
  tracked_dirty: [{path, blob, bytes}, ...]   # 19 项（当前状态）
  untracked:     [{path, blob, bytes}, ...]   # 6 项（当前状态）
  count_tracked_dirty / count_untracked
```

> **(b) 是增量 review 成立的唯一依据。** 范围内的内容被完整保存以便做增量；范围外的内容虽未复制，但哈希已记录——下一次 gate 重算一遍即可**机器证明**范围外一行未动。没有这一层，§3.1 第 4 条的反对意见成立，reviewer 有权拒绝增量包。
>
> 哈希使用 `git hash-object <path>`（**带** filter，不加 `--no-filters`），使其对 CRLF / LF 差异不敏感。

#### ④ Review 元数据（Review Metadata）

```
level              R0 | R1 | R2 | R3
seats              [{role, model, verdict, critical, important, minor, report_path}, ...]
approved           true | false          ← 闸门，见 §3.4
approved_at
package            本次 gate 使用的包路径
deferred_minors    [{id, one_liner, ledger_line}, ...]
parked             [{finding, ruling}, ...]
verification       {backend, frontend, type_check, build, ...} 的实测字符串
```

### 3.3 存放位置

**基线跨 plan 共享，复核包归 plan 所有。**

```
<repo-root>/.superpowers/sdd/baselines/              ← 基线（跨 plan）
<repo-root>/.superpowers/sdd/<plan-basename>/packages/   ← 复核包（plan 内）
```

> **裁定（v1.1）**：基线最重要的用法是“Stage N 的关闭基线 = Stage N+1 的起点基线”，它的生命周期天然跨 plan。若放在 `<plan-basename>/` 下，新 plan 的 controller 按 Superpowers 的“另一个 plan 的目录不归你读写”规则就拿不到锚点，会直接退回全量 review——恰好重现本规范要解决的问题。复核包不同：它绑定具体 gate，不跨 plan 复用，因此留在 plan 目录内。若该拆分错了，代价是一次目录搬迁加台账路径重写。

| 要求 | 满足情况 |
| --- | --- |
| git-ignored | ✅ `.superpowers/sdd/.gitignore` 内容为 `*`，`git check-ignore -v` 实测命中 |
| 跨会话可恢复 | ✅ 在仓库内随磁盘持久化。**禁止**再使用仓库外路径（历史上用过 `C:/Users/.../ChatGPT/ai小镇全栈/sdd-snapshots/`，换机器即失效） |
| 跨 plan 可用 | ✅ 基线不在任何 plan 的目录内，新 Stage 的 controller 可直接读取，不违反 Superpowers 的 plan 目录隔离规则 |
| 与既有实践一致 | ✅ 仓库已有 `task-*-fix-round-1-before/` 镜像目录，本规范只是给它补上元数据 |
| 体量可接受 | ✅ 全 Stage 范围 1.0 MB；Task 级通常 150–200 KB |

#### 已知隐患（待修）

`.superpowers/sdd/.gitignore` 的内容是 `*`，因此**它把自己也忽略了**——`git ls-files .superpowers` 实测返回 0，这条忽略规则**不在版本控制里**。后果：

- `git clean -fdx` 会同时删掉所有基线**和**这条忽略规则；
- 换机器 clone 后该目录不存在，首次生成基线时全部文件会出现在 `git status` 中，极易被误提交（ledger 含大量绝对路径与内部报告）。

**修复方向**：在**根** `.gitignore`（已被跟踪）增加一行 `/.superpowers/`。该修改尚未执行，需人类批准。

#### 保留策略

| 类型 | 保留期 |
| --- | --- |
| `approved` 基线 | 到该 Stage 关闭后两个 Stage，再归档 |
| `before` 基线 | 该 fix 轮 re-review 通过后即可删除，ledger 保留一行记录 |
| 台账 `baselines/index.md` | **永久保留**（纯文本、极小）；即使快照被清理，历史锚点仍可追溯 |

### 3.4 approved baseline 与 before baseline 的区别

**这是本章最重要的一条规则。**

| | **approved baseline** | **before baseline** |
| --- | --- | --- |
| 何时建立 | gate **通过之后** | fix 轮**开始之前** |
| 目录后缀 | `-approved` | `-<round>-before` |
| 含义 | "这个状态已被独立 review 判定为 Critical 0 / Important 0" | "这是修复动手前的现场，仅用于算出 fix 到底改了什么" |
| 谁可以用它作为增量起点 | **下一个 gate** | **仅该轮的 scoped re-review** |
| `review.json.approved` | `true` | `false` |
| 保留期 | 长期 | 该轮通过即可删 |

**红线：禁止把 `before` 基线当作下一个 gate 的增量起点。**

理由：`before` 基线记录的是一个**已知带缺陷**的状态（它之所以存在，正是因为 review 报了 findings）。若把它当作"已批准"，则后续所有增量都建立在未经批准的内容之上，缺陷会被永久跳过——这正是增量 review 唯一能造成系统性质量损失的路径。

### 3.5 提交无关性（commit-agnostic baseline）

本仓库的节奏是「agent 交付 → 人类 review → 人类手工提交」。人类一提交，HEAD 就变了，但**内容一个字节都没变**。

因此**基线身份必须是内容寻址（blob 哈希），不是 commit 寻址**。当出现"HEAD 从 X 变为 Y，但基线覆盖的内容哈希全部未变"时：

- 判定为**基线依然有效**；
- 将 `form` 从 `W` 升级为 `C`，追加记录新的 `head_sha`；
- **不**宣告基线失效，**不**退回 full review。

> 这一条单独就能消除本仓库最常见的一次全量重审。

### 3.6 漂移判定（verify）

每次 gate 开始前必须对上一个 approved 基线执行漂移检查，四种判定：

| 判定 | 含义 | 后续动作 |
| --- | --- | --- |
| `MATCH` | 范围外零漂移 | 可以做增量 review |
| `HEAD_MOVED_CONTENT_SAME` | 人类提交了，内容未变 | 基线 W→C 升级，**继续有效** |
| `OUT_OF_SCOPE_DRIFT` | 范围外有改动 | 按 §5.4 升级等级，或把漂移文件纳入 scope 后重建基线 |
| `INDEX_DIRTY` | 人类手工 staged 了内容 | 报告给人类，**不自动处理**（agent 不碰 index） |

### 3.7 增量 review 的三层防线

增量 review 唯一的方法论风险是"未改代码因新代码而语义失效"。三层挡：

| 层 | 机制 |
| --- | --- |
| 机器层 | `OUT_OF_SCOPE_DRIFT = 0` 的哈希证明（§3.2 ③b） |
| 规则层 | §2.3 触发表把跨文件不变量类改动强制升 R3；R3 的不变量席专责跨 Task 断言 |
| 人层 | reviewer 保留越界探查权；R3 不变量席可按 §4.3 例外**单席**申请 full package |

---

## 4. Review Package 输入规则

### 4.1 必须提供（四件，缺一不可）

| # | 内容 | 说明 |
| --- | --- | --- |
| 1 | **Scoped diff** | 仅含本次 delta，`-U5`。这是 reviewer 唯一的被审对象。 |
| 2 | **Binding 条款摘录** | 本次改动受约束的 Spec / Plan 条款**原文片段 + `文件:行号` 锚点**。替代整份 Spec / Plan，同时保留"需要时自行 Read 指定行段"的能力。 |
| 3 | **证据索引（Evidence Index）** | 一页表，见 §4.5。 |
| 4 | **风险声明** | implementer 的 `DONE_WITH_CONCERNS` 原文 + controller 已做的 Ruling 列表，防止 reviewer 重新发现已裁定项。 |

### 4.2 默认不提供

| 内容 | 理由 | 替代 |
| --- | --- | --- |
| Spec / Plan 全文 | 已被条款摘录覆盖；在 Stage final 包中它们自身占 2,003 行 | 摘录 + 行号锚点 |
| 上一次 review 已通过且本次未修改的文件 diff | G1 的核心 | approved 基线 |
| implementer report 的叙事段（设计理由、过程复盘） | 22–32 KB 中 reviewer 真正需要的只是证据 | 证据索引 + report 路径（可按需 Read） |
| ledger 全文 | 46 KB 且多数与本次无关 | 指定锚点行（Ruling 与 deferred minor 列表） |
| `README.md` / `docs/*` 全文 | 41 KB README 通常只有个别章节相关 | 仅受影响章节的 diff |
| 二进制、图片、生成物、大 fixture | 无法审且挤占预算 | stat 行 + 一句说明 |
| `-U10` 上下文 | 75 文件规模下是主要膨胀源之一 | `-U5`；hunk 被截断时 reviewer 显式声明并自行 Read |
| 其他 Task 的历史 package | 从不需要 | — |

### 4.3 允许 full package 的四种例外

仅限以下四种，且每次都要在 ledger 记 Ruling：

1. **首次引入子系统**——无历史 review 基线（如 Stage 2 Task 1 的认知 Schema）。此时 delta 天然等于 full。
2. **基线失效**——发生 rebase、大规模重构，或工作树与基线记录不符（`OUT_OF_SCOPE_DRIFT` 无法归并）。
3. **R3 不变量席按需申请**——该席判断某条跨 Task 断言无法从 Boundary package 验证时，**只向它一席**补发 full package，另外两席维持增量。
4. **人类显式要求**。

> **关键区别：R3 的默认输入不是 full diff**，而是「上一次通过的 R2/R3 基线 → 当前」的增量 + 证据索引 + 不变量断言表。Stage 2 final gate 之所以是 740,903 bytes，正是因为把 R3 等同于 full。

### 4.4 包结构

reviewer 实际读到的文件必须是这个结构：

```
# Review Package P0012
## Identity
  baseline:      B0007 (approved, R2, task-5/segment-1)
  current:       工作树 @ 2026-09-13T10:42+08:00
  baseline head: 2253768      current head: 2253768      index_clean: true
## Integrity
  scope files:        19
  out-of-scope drift: 0  ✅
  status fingerprint: MATCH（范围外文件逐一哈希比对通过）
## Files changed
  <git diff --stat>
## Diff
  <git diff -U5>
```

`## Integrity` 是本规范新增且最关键的一段：**它把"你可以只看增量"从 controller 的口头保证变成机器可验证的断言。**

### 4.5 证据索引格式

由 controller 生成，**只放指针，不放结论**（避免 controller 自证）：

```
| 文件:行段 | 改动职责 | 覆盖它的测试(文件::用例) | RED 命令 | RED 输出摘要 | GREEN 数字 | 风险标记 |
```

`风险标记` 取自 §2.3 的触发条款，取值如 `权限` / `事务` / `并发` / `契约` / `迁移`。**reviewer 必须对每个带标记的行给出结论。**

### 4.6 reviewer 的固定动作

写入 reviewer prompt 模板，四步：

1. **先核对 `## Integrity` 段**：`scope files` 计数与 `## Files changed` 是否一致、`out-of-scope drift` 是否为 0。不一致 → 立即回报 controller，**不开始 review**。
2. 只审 `## Diff`。
3. 需要越界探查时，**命名风险 + 说明检查了什么**（Superpowers 已有规定，此处保留并强调）。
4. `⚠️ 无法从本包验证` 的条目照常回报，由 controller 解决。

---

## 5. Incremental Re-review 流程

### 5.1 三种场景的基线选择

| 场景 | 基线 | reviewer 收到 |
| --- | --- | --- |
| **首次 review**（新 Task / 新子系统，无历史基线） | Stage 基线 commit 或 Task 起始 commit | 全量（此时增量即 full，合理） |
| **后续 review**（Task N，前序 Task 已通过） | **最近一个 `approved` 基线** | 仅 `B(approved) → 当前工作树` |
| **fix re-review** | 该轮的 `<round>-before` 基线 | 仅 fix diff |

fix re-review 的收益已在本仓库实测：scoped 包 **18,537 bytes** vs 同 Task 全量包 **84,512 bytes**，降幅 **78%**，且该轮仍然完成了对真实数据的独立复核。

### 5.2 默认形态：scoped + 单席

```
fix 轮输入 = diff(<round>-before 基线 → 当前工作树)
           + 原 findings 逐条列表
           + implementer 的 fix 证据（覆盖测试名、命令、输出）
```

reviewer 只做两件事：

1. 逐条判定 **ADDRESSED / NOT ADDRESSED**；
2. **仅在 fix diff 内**寻找新破坏。

范围外观察一律写成 deferred minor，**不延长轮次**。

#### 硬规则：reviewer 的**读取范围**可以 scoped，implementer 的**验证矩阵**不可以

这是两件事，常被混为一谈，后果已在本仓库实际发生。

| | 允许 scoped？ | 理由 |
| --- | --- | --- |
| reviewer 读取的 diff | ✅ 允许 | 已批准且未修改的代码不需要第二次人工审读 |
| implementer 跑的验证矩阵 | ❌ **禁止** | 机器跑测试的成本接近于零，而接口级改动的影响面人看不全 |

**以下情形任意一条命中时，fix 轮完成后必须跑完整验证矩阵**（后端全量 + 前端全量 + type-check），聚焦子集不得替代：

1. 修改了任何**公开或内部接口的签名**（新增形参、改名、改关键字参数）；
2. 修改了被 **≥ 2 个测试文件构造过替身（test double）** 的任何类型或 Protocol；
3. 修改了共享契约：`cognition_contracts.py`、`schemas/`、`llm/*_provider.py` 的任何 Protocol；
4. fix 跨越了 ≥ 2 个 backend 分层目录。

**实例（Stage 2 Task 5 Fix A–E）**：fix 波给 `EmbeddingProvider.embed` 加了 `timeout_seconds` 关键字参数，`cognition_projection.py:74` 在有 deadline 时改为 `embed(content, timeout_seconds=remaining)`。当时只跑了五个聚焦文件（`77 passed`），未跑全量；仓库里共 19 个 `def embed` 测试替身，只有聚焦文件内的 5 个被同步。结果：Stage 2 关闭提交 `85ce338` 上 **7 个后端测试确定性失败**，且其中 `test_shared_deadline_stops_reflection_after_embedding_consumes_budget` 已不再测 deadline（它现在走的是“provider 抛 TypeError”分支）。

这一条不是对增量 re-review 的否定——当时的增量 re-review 本身是对的，错的是把“reviewer 少读点”错读成了“implementer 少跑点”。

### 5.3 席位重跑规则

固化 Stage 2 Task 4 round 2 的一次性裁定（当时只重跑 quality，spec 沿用 round 1 的 PASS，理由已入 ledger）：

| 情况 | 重跑哪一席 |
| --- | --- |
| **默认** | **只重跑提出该 finding 的那一席** |
| fix 触及 Public 契约 / DTO / 权限 scope / 披露规则 | 必须同时重跑**契约席** |
| fix 触及事务、并发、迁移、计数器语义 | 必须同时重跑**质量席** |
| finding 属于 R3 的不变量类 | 必须重跑**不变量席** |

### 5.4 必须升级回更高等级（不允许 scoped）的条件

任意一条命中即升级：

1. fix 超出原授权文件集合；
2. fix 触发了 §2.3 中更高一档的条款（例如原本 R1，fix 里动了权限判定）；
3. fix 的净新增行 > 原 delta 的 **30%**；
4. **连续两轮**出现**新的** Important（说明 implementer 看不见自己的问题）；
5. 基线失效（§4.3 第 2 条）。

### 5.5 「不泄露 / 不发生」类 finding 的硬判定

来源：本仓库最贵的一条 Important——隐私测试 `test_get_npc_memory_explanations_never_exposes_the_player_claim` 跑在**空列表**上，`all(...)` 与两条 `not in response.text` 全部平凡通过，看起来全绿却什么都没证明。

**规则：re-review 不得接受报告结论，必须看到非空且有区分度的证据。** 判定式写死为：

```
0 < len(返回集合) < len(全集)
```

即证明过滤**确实丢弃了一部分、同时保留了另一部分**。只证明"非空"或只证明"不含 X"都**不算通过**。

### 5.6 轮次、breaker 与 reviewer 中断

| 项 | 规则 |
| --- | --- |
| 轮次上限 | 沿用 Superpowers 的 **5 轮** |
| 第 3 轮起 | **必须**更换 reviewer 模型或换 fresh reviewer，并记 Ruling |
| 第 5 轮后仍有开放项 | controller 逐条裁定（park with ruling / 判定 load-bearing 并做最小修复）。**禁止静默丢弃。** |
| reviewer 中途失败（usage limit 等） | partial 结果**不计为证据**；用**同一个不可变 package 文件**换模型重发 |

> 最后一条正是"package 必须是磁盘上的不可变文件而非即时生成"的原因：Stage 2 Step 10 曾有两个 reviewer 在产出报告前撞到 usage limit，整包重发。

---

## 6. Git 不 commit 约束下的 review 策略

### 6.1 约束复述（不得放宽）

`AGENTS.md` 规定：agent 不得执行 `git add`、`git commit`、`git reset`、`git checkout`、`git switch`、`git clean`、`git stash` 与任何 `git push`。产出保持未暂存、未提交，由人类 review 后手工提交。

**本规范不放宽这条约束。** 所有基线与包的生成**只使用只读 git 命令**：`status`、`diff`、`hash-object`（不加 `-w`）、`rev-parse`、`log`、`check-ignore`。不写 index、不写 HEAD、不写 objects、不触碰工作树。

### 6.2 三类内容的覆盖命令

| 类别 | 命令 | 说明 |
| --- | --- | --- |
| tracked modified（未暂存） | `git diff HEAD -U5 --ignore-cr-at-eol -- <paths>` | ✅ |
| staged（若人类手工暂存） | **同一条命令** | `git diff HEAD` 比较工作树 vs HEAD，天然包含 staged |
| untracked | 不可见于 `git diff`，必须单独处理 | 见 §6.3 |

> **不要用无参数的 `git diff`**（只给 unstaged），**也不要用 `git diff --cached`**（只给 staged）。`git diff HEAD` 一条覆盖两者，这正是本仓库需要的语义：无论人类有没有手工 staging，交付物都是"工作树的最终状态"。
>
> 实测：当前工作树 `git diff HEAD --stat` = 19 文件 / +1,003 −97；`git diff --cached` 为空。

### 6.3 未跟踪文件：统一用快照镜像消除特例

两种可行路径：

**路径 A（形态 C，基线是 commit）**

```
Part A：git diff -U5 --ignore-cr-at-eol <baseline_sha> -- <scope>
Part B：逐个未跟踪文件 git diff --no-index -U5 /dev/null <file>
```

Part B 在 Windows 上头部显示为 `nul => AGENTS.md`（实测），属外观瑕疵。

**路径 B（形态 W，基线是工作树快照）——推荐统一采用**

```
1. 把当前 scope 文件复制成镜像目录：<scratch>/head/<仓库相对路径>
2. git diff --no-index -U5 --ignore-cr-at-eol <baseline>/files <scratch>/head
```

实测结果：**modify / new file / deleted 三种情形全部正确生成**，tracked 与 untracked 完全同构。在快照世界里根本不存在"是否被跟踪"的区别——这是把未跟踪文件这个特例彻底消灭的办法。

**统一实现建议**：两种形态都走路径 B 的机制，形态 C 只是"基线目录的内容恰好等于某个 commit 的内容"。好处是只有一条 diff 代码路径、包头统一；代价是快照时需复制文件（1.0 MB 级，可忽略）。

### 6.4 三个必须处理的工程细节

| # | 细节 | 处理 |
| --- | --- | --- |
| 1 | `git diff --no-index` 有差异时**退出码为 1**（实测） | 脚本不得裸用 `set -e` / `check_call` |
| 2 | `core.autocrlf = true`（实测）。当前工作树实际是 LF，但这是偶然状态——一次 `git checkout` 就会让工作树变 CRLF，届时快照（LF）与工作树（CRLF）会整包全量变红 | 快照写入时做 LF 归一；diff 加 `--ignore-cr-at-eol`；哈希用带 filter 的 `git hash-object` |
| 3 | `git diff --no-index` 默认输出**绝对路径**头（实测未处理时 120+ 字符/行，纯浪费） | 从公共父目录用相对路径调用，或显式给 `--src-prefix` / `--dst-prefix` |

### 6.5 人类提交后的处理

见 §3.5。判定为 `HEAD_MOVED_CONTENT_SAME` 时基线继续有效，**不**退回 full review。

### 6.6 工具就绪前的手工执行流程（**当前现行办法**）

`scripts/review_baseline.py` 尚不存在（见第 9 章）。在它就绪之前，controller **按以下手工步骤执行本规范**，一步不少：

**建立基线**

1. `mkdir -p .superpowers/sdd/baselines/<id>-<gate>-<kind>/files`
2. `git status --porcelain -uall > .../state.txt`
3. 按 scope 清单逐个复制文件到 `files/`，保持仓库相对路径
4. 对**所有** tracked-dirty 与 untracked 文件跑 `git hash-object`，把 `路径 blob 字节数` 写入 `manifest.md`（工具就绪前用 Markdown 表替代 JSON）
5. 在 `manifest.md` 抬头写入 §3.2 ① ② 的字段
6. 向 `baselines/index.md` 追加一行台账
7. 向 ledger 追加：`Baseline <id>: <kind> (<gate>, head <short-sha>, scope <N> files)`

**漂移检查**

8. 重跑 `git status --porcelain -uall` 与全部 `git hash-object`，与基线 `manifest.md` 逐行比对
9. 按 §3.6 给出四种判定之一，写入 ledger

**生成包**

10. 复制当前 scope 文件到 scratchpad 镜像目录
11. `git diff --no-index -U5 --ignore-cr-at-eol <baseline>/files <scratch>/head > <package>.diff`
12. 在包头**手工补写** §4.4 的 `## Identity` 与 `## Integrity` 两段
13. 包落到 `.superpowers/sdd/<plan>/packages/`，**文件名含基线区间**，生成后不再修改

**批准**

14. gate 通过后，建立 `-approved` 基线（重复步骤 1–7，`kind=approved`）
15. 写 `review.md`（§3.2 ④ 的字段）
16. 更新 `CURRENT_STATE.md` 的 `## Review Baseline` 小节（§7.2）

> 手工流程与工具产出的**语义必须一致**。工具上线后，历史手工基线仍然有效，不需要重建。

---

## 7. 与既有体系的接口

### 7.1 `AGENTS.md`

- **单一事实来源**：§2.3 触发表**引用** `AGENTS.md` 的「修改架构前必须确认边界」6 条与「跨 Stage 不变量」6 条，**不复制正文**。修改风险清单只改 `AGENTS.md`。
- **已执行（v1.1）**：`AGENTS.md` 已在「开发前必读」清单加入本文作为第 6 项，并新增 `### Review Baseline` 节（与「验证基线」显式区分，声明交付前必须定级、基线位于 `.superpowers/sdd/baselines/`、只使用只读 git 命令、Git Rules 不放宽）。

### 7.2 `CURRENT_STATE.md`

**已执行（v1.1）**：`CURRENT_STATE.md` 已新增 `## Review Baseline` 小节，作为接手 agent 的第一判据，替代"读 46 KB ledger 重建上下文"。当前实际内容以该文件为准，下面是格式模板：

```markdown
## Review Baseline

| 项 | 值 |
| --- | --- |
| 当前 approved 基线 | B0007（R2，Task 5 段 1） |
| 基线路径 | .superpowers/sdd/baselines/B0007-task5-seg1-approved/ |
| 基线对应 HEAD | 2253768 |
| 基线建立时状态 | 19 tracked dirty + 6 untracked |
| 范围外漂移 | 0（最后一次 verify：<时间>） |
| 未清零 findings | Important <N> |
| 下一个 gate | R3（Stage 关闭 + 事务边界改动） |
```

### 7.3 Plan

新 Plan 的每个 Task 抬头**预声明**三项，使 controller 不必临时拼装：

```markdown
### Task N：<标题>
**Review Level:** R2（触发：Public API 新增 + Provider 调用）
**Binding 条款锚点:** spec:§13.1 L412-L438、spec:§18.5 L701-L716、plan:L1089-L1104
**证据要求:** 并发交错测试必须使用真实 SQLite 独立 Session
```

`superpowers:writing-plans` 生成新 Plan 时把这三行作为 Task 模板固定字段。

### 7.4 Superpowers workflow

**定位：project override，不改写任何 skill 文件。** 本文只填 skill 留白的部分。

| Superpowers 组件 | 本项目取值 |
| --- | --- |
| `scripts/review-package PLAN BASE HEAD` | **替换**为基线增量机制（§6）。原脚本依赖 commit range，在本仓库交付时恒为空，不可用。 |
| `scripts/sdd-workspace` | **沿用**；基线目录挂在它返回的路径下 |
| `task-reviewer-prompt.md`（一次 dispatch 双 verdict） | = **R1** |
| 两次并行 dispatch（spec / quality） | = **R2**，并叠加 §2.6 的职责互斥表 |
| `code-reviewer.md`（final whole-branch review） | = **R3 的不变量席**，但输入换成 Boundary package 而非 full diff |
| `re-review-prompt.md` | = §5 的 scoped re-review，叠加 §5.3 席位重跑规则 |
| `[DIFF_FILE]` 占位符 | 填基线增量包路径 |
| `[GLOBAL_CONSTRAINTS]` 占位符 | 填 Plan 预声明的 binding 条款锚点（§7.3） |
| ledger `progress.md` | **新增一类行**：`Baseline <id>: <kind> (<gate>, head <sha>, drift <N>)` |
| 5 轮 breaker / park with ruling / deferred minor 滚动 | **原样保留** |
| "不得 pre-judge findings" | **原样保留并加粗**——降低 token 不得以"别报这个"实现 |

### 7.5 `docs/10_AI_Coding_Workflow.md`

10 号文档（v1.0）记录的是人工 review 理念（"AI 生成 → 人工阅读 → 提交"）。本文是它在 agent 时代的执行细则。**不重写 10 号文档**，仅建议在其第 7 章加一行指针。

---

## 8. 红线清单

以下九条不得因任何 token 或进度考量而妥协。违反其中任何一条，该 gate 的结论无效。

1. reviewer 永远独立：不得复用 implementer，不得看 controller 的会话历史。
2. 不得在 reviewer prompt 中写 "不要报 X" / "至多 Minor" / "plan 已经选择了" 等预判语句。
3. 不得因 diff 小而跳过 gate。
4. reviewer 保留越界探查权（须命名风险并说明检查了什么）。
5. 「不泄露 / 不发生」类断言必须满足 `0 < 返回集 < 全集`。
6. Critical / Important 未清零，不得进入下一个 Task。
7. 每条裁定必须进 ledger：`Ruling: <决定> — <理由> — <若错的代价>`。
8. 验证矩阵不得新增 skip 或 warning；数字必须是本机实测，不得引用历史。
9. package 必须是磁盘上的**不可变文件**；reviewer 中断后用同一份重发。

**外加基线专属红线：**

10. 禁止把 `before` 基线当作下一个 gate 的增量起点（§3.4）。
11. 禁止在 `out-of-scope drift ≠ 0` 时进行增量 review（§3.6 / §4.6）。
12. 基线与包的生成只使用只读 git 命令（§6.1）。
13. **增量 re-review 只缩小 reviewer 的读取范围，不缩小 implementer 的验证矩阵**（§5.2 硬规则）。
14. **任何 gate 宣布通过前，controller 必须看到本机实测的完整矩阵输出**，不得以 implementer 报告的聚焦数字代替。

---

## 9. Proposed：`scripts/review_baseline.py`（**尚未实现**）

> **本章描述的工具当前不存在。** 不要 import 它、不要调用它、不要写"等它完成后"的占位代码。在它就绪之前，按 §6.6 手工执行。

### 9.1 定位与边界

| 项 | 取值 |
| --- | --- |
| 位置 | `scripts/review_baseline.py` + `scripts/review-baseline.{ps1,sh,cmd}` wrapper（跟随仓库既有 `deploy.py` / `start_dev.py` 惯例） |
| 依赖 | 纯 Python 标准库，**不新增任何第三方依赖** |
| Git 使用 | **只读**：`status` / `diff` / `hash-object`（不加 `-w`）/ `rev-parse` / `log` / `check-ignore` |
| 绝对禁止 | 写 index、写 HEAD、写 objects、修改工作树、执行任何 §6.1 列出的 git 写命令 |
| 输出位置 | 基线 `.superpowers/sdd/baselines/`；复核包 `.superpowers/sdd/<plan-basename>/packages/` |

### 9.2 命令面（草案）

| 命令 | 作用 |
| --- | --- |
| `snap --gate <id> --kind approved\|before --scope-from <锚点>` | 建快照：scope 副本 + 全仓指纹 + manifest |
| `approve --id <B> --level R2 --seat spec=APPROVED --seat quality=APPROVED` | 标记通过，写 `review.json`，更新台账 |
| `delta --from <B> --to WT --out <package>` | 生成增量包（含 `## Identity` 与 `## Integrity` 段） |
| `verify --id <B>` | 漂移检查，输出 §3.6 的四种判定之一 |
| `list` | 打印 `baselines/index.md` 台账 |

### 9.3 目标文件结构

```
<repo-root>/.superpowers/sdd/
├── baselines/                           # 跨 plan 共享
│   ├── index.md                         # 追加式台账（永久保留）
│   ├── B0007-task5-seg1-approved/
│   │   ├── manifest.json                # §3.2 ①②③
│   │   ├── state.txt                    # git status --porcelain -uall 原文
│   │   ├── review.json                  # §3.2 ④
│   │   └── files/                       # scope 副本，镜像仓库相对路径（LF 归一）
│   │       ├── backend/app/services/memory_explanation.py
│   │       └── tests/backend/test_npc_api.py
│   └── B0008-task5-seg2-fix1-before/
│       └── …（同构）
└── <plan-basename>/                     # plan 内
    ├── progress.md                      # 既有 ledger，新增 Baseline 行
    └── packages/
        └── P0012-B0007..WT-20260913T1042.diff
```

工具就绪前的手工版本用 `manifest.md` / `review.md` 替代 `.json`，字段语义相同。

### 9.4 实现前必须裁定的事项

| # | 事项 | 当前建议 |
| --- | --- | --- |
| 1 | 是否允许 `GIT_INDEX_FILE=<临时索引> git add -A && git write-tree` 以获得真正的 git tree 对象作为基线身份 | **建议不采用**。理由：① `AGENTS.md` 禁令逐字明列，绕过字面规则会侵蚀规则权威；② 未被引用的 tree 对象会被 `git gc --prune` 回收，基线可能凭空消失；③ 文件副本方案成本仅 1.0 MB，收益差距不足以换取规则例外。若决定采用，**必须先显式修改 `AGENTS.md`**，不得由 agent 自行放宽。 |
| 2 | 根 `.gitignore` 是否补 `/.superpowers/` | **建议补**。修复 §3.3 的隐患，一行改动。属仓库文件修改，需人类批准。 |
| 3 | `git hash-object` 是否确实对 CRLF 文件应用 clean filter | **待验证**。当前实测 `AGENTS.md` 的 filtered 与 `--no-filters` 哈希相同，但该文件本身是 LF，此结果**不具区分度**。实现时必须补一个真实 CRLF 用例验证，否则 §6.4 细节 2 的行尾无关性不成立。 |
| 4 | 快照是否需要 gzip 压缩 | **建议不压缩**。1.0 MB 可忽略，且未压缩的文本副本可被人类与 agent 直接 Read，这是排障时的主要价值。 |

### 9.5 建议实现顺序

1. `snap` + `verify` — 先把"基线可建、漂移可证"跑通；这两条就绪后，增量 review 的机器前提即成立。
2. `delta` — 生成包，含 `## Integrity` 段。
3. `approve` + `index.md` 台账。
4. 用一次真实 gate 做端到端验证，并把实测降幅写回 §1.3。

**测试要求**（按 `AGENTS.md` 的 TDD 强制流程）：每项行为先 RED；至少覆盖 tracked-modified、staged、untracked、删除文件、CRLF 文件、HEAD 移动但内容未变、范围外漂移七种情形；测试不得写入 `backend/data/aleria.db`，使用 `tmp_path`。

---

## 10. 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.1 | 2026-09-13 | 基线改为跨 plan 共享（§3.3 裁定）；新增 §5.2 硬规则与红线 13/14——增量 re-review 不得缩小验证矩阵（由 `85ce338` 上 7 个确定性失败反推得出）。 |
| v1.0 | 2026-09-12 | 首次发布。定义 R0–R3 分级、baseline snapshot 概念、approved / before 区分、package 输入规则、incremental re-review 流程、不 commit 约束下的策略，并预留 `review_baseline.py` 设计方向。 |
