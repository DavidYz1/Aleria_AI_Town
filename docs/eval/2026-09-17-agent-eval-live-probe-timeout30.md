# Stage 3m Agent Evaluation（Live 探路，5 tick · 超时上限 30 秒）

> **探路运行，样本极小，不构成 spec §17.5 验收。** 5 tick × 3 NPC = 15 个 NPC-tick。
> 唯一改动是 `PLANNING_PROVIDER_TIMEOUT_SECONDS` 20 → 30。**本次运行时**只改了本地
> `.env`，`Settings` 默认值仍是 20.0；结果确认后，默认值与 `.env.example` 也已同步
> 改为 30（见 `CURRENT_STATE.md`）。与前两次探路**不是受控 A/B**，但本轮有一条
> **不依赖对比**的直接证据，见下方读数说明第 1 条。


- 生成时间：2026-09-17 05:40:33 UTC
- Provider：`openai_compatible`　Model：`hy3`
- Tick 数：5　动作空间：6 个动词

| 指标 | 值 | 含义 |
| --- | --- | --- |
| 动作合法率 | 100.0%（14/14） | 未被规则替换的计划步骤 / 所有计划步骤提案；planning + proposal trace |
| 可用决策率 | 85.7%（6/7） | 返回可用 AgentDecision / 实际 Provider 调用；调用计量，失败不等于 Schema 错误 |
| 兜底率 | 6.7%（1/15） | source=fallback / 全部 NPC 提案；proposal trace |
| 计划完成率（状态） | 50.0%（3/6） | status=completed / 创建的计划行；含窗口截尾与过龄结束，非语义目标达成 |
| 行为熵 | 1.930 / 2.585 | actions.action_type 分布的香农熵；n=动作行数，描述多样性 |
| 计划复用率 | 53.3%（8/15） | source=existing_plan / 全部 NPC 提案；proposal trace |
| 模型调用 / NPC-tick | 7/15 = 0.467 | 本次 Provider 调用计量 / 全部 NPC 提案 |
| tick 耗时 | P50 20.382s / P95 30.302s（n=5） | POST /api/world/tick 墙钟耗时，含规划、持久化和认知投影 |
| 模型调用耗时 | P50 20.113s / P95 30.018s（n=7） | Provider.plan 墙钟耗时，成功与失败均计入 |
| 已上报 token | 20168（覆盖 6/7 次调用） | usage.total_tokens 求和；未上报调用的消耗未知 |
| 兜底原因：Provider·调用超时（`provider:timeout`） | 100.0%（1/1） | 本项次数 / source=fallback 提案数；落盘 trace |

动作分布：eat 1、move 7、rest 2、talk 1、work 4

> 指标口径：`llm` 与 `existing_plan` 都算规划 Provider 产出的提案；`existing_plan` 不调用模型。P50/P95 用 nearest-rank（向上取整名次）。Embedding 与 Reflection 固定使用确定性替身；Fake 结果只验证链路，不代表真实模型可用率。
> 失败归因：兜底原因直接读落盘 trace，格式 `<stage>:<code>`。`provider:*` 来自 adapter 按异常类型分的四类（timeout / http_status / transport / parse_error），`rule:*` 是 `ActionRegistry` 与 conflict_resolver 的拒绝码，由 `rule_rejection` trace 记录被替换掉的原始提案。拿不到分类时记 `provider:unknown` 或 `unattributed`，不按异常长相臆造具体原因。
> 使用 `--out` 时，同名 `.evidence.json` 保存去内容化的逐 tick、逐调用与逐提案样本，以及分子分母；不会保存 Prompt、模型响应或凭据。

## 读数说明（人工补充，非脚本输出）

**1. 直接证据：6 次成功调用里有 3 次耗时超过 20 秒。**

```
成功调用耗时：10162 / 13446 / 15015 / 20113 / 20970 / 23959 ms
                                     ^^^^^^^^^^^^^^^^^^^^^^^^
                                     这 3 次在旧的 20s 上限下必然被判超时
```

这条**不依赖与上一轮的对比**：它证明旧上限确实在切掉本来会成功返回的调用。
上一轮「8 次超时全部精确落在 20007–20024ms」只能说明「撞到了上限」，本轮才
回答了「撞上限的那些，再等一会儿会不会成功」——会。

**2. 二阶效应：提高超时反而减少了模型调用。** 调用数从 0.733 降到 0.467 次/NPC-tick，
计划复用率从 26.7% 升到 53.3%。机制是一个被打断的恶性循环：超时 → 兜底 → 本 tick
没有产生计划 → 下个 tick 必须重新规划 → 更多调用、更多超时机会。成功的规划会产出
可跨 tick 复用的计划，于是调用次数自然下降。**这一点在设计超时策略时容易被忽略。**

**3. 代价落在 P95，不在 P50。** tick 耗时 P50 20.225s → 20.382s（几乎不变），
P95 20.607s → 30.302s（失败时要等满 30 秒）。逐 tick 看是
`30.3 / 24.1 / 10.3 / 0.1 / 20.4` 秒——其中 0.1s 那个 tick 三个 NPC 全部复用计划、
零调用。**平均体感实际上是改善的**，变差的是最坏情况。

**4. 行为多样性同步改善**：熵 1.555 → 1.930，动作分布从 4 种
（`move/rest/talk/work`）变成 5 种（`eat 1、move 7、rest 2、talk 1、work 4`）。
这是可用决策率提高的自然结果——兜底策略的动作种类本来就比模型规划少。

**5. 仍然不能声称的：** 5 tick、单次运行、外部服务状态不可控。第 1 条是直接观测，
但「可用决策率 27.3% → 85.7%」这个幅度里有多少来自超时调整、多少来自服务端波动，
**本轮数据无法区分**。要给出可靠结论需要固定种子与环境、交替运行多组。
