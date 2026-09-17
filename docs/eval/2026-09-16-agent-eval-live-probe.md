# Stage 3m Agent Evaluation（Live 探路，5 tick）

> **这是一次探路运行，样本极小，不构成 spec §17.5 的验收。** 5 tick × 3 NPC = 15 个
> NPC-tick，动作合法率的分母只有 13 条。目的是确认当前 HEAD 的 Live 链路可跑通、
> 兜底原因分类能否真的落地，以及真实调用的耗时与 token 量级，据此再决定要不要跑满
> 20 tick。下表数字逐字保留脚本输出，未做任何人工修改。


- 生成时间：2026-09-16 12:04:27 UTC
- Provider：`openai_compatible`　Model：`hy3`
- Tick 数：5　动作空间：6 个动词

| 指标 | 值 | 含义 |
| --- | --- | --- |
| 动作合法率 | 76.9%（10/13） | 未被规则替换的计划步骤 / 所有计划步骤提案；planning + proposal trace |
| 可用决策率 | 75.0%（6/8） | 返回可用 AgentDecision / 实际 Provider 调用；调用计量，失败不等于 Schema 错误 |
| 兜底率 | 33.3%（5/15） | source=fallback / 全部 NPC 提案；proposal trace |
| 计划完成率（状态） | 0.0%（0/6） | status=completed / 创建的计划行；含窗口截尾与过龄结束，非语义目标达成 |
| 行为熵 | 1.237 / 2.585 | actions.action_type 分布的香农熵；n=动作行数，描述多样性 |
| 计划复用率 | 26.7%（4/15） | source=existing_plan / 全部 NPC 提案；proposal trace |
| 模型调用 / NPC-tick | 8/15 = 0.533 | 本次 Provider 调用计量 / 全部 NPC 提案 |
| tick 耗时 | P50 18.177s / P95 20.201s（n=5） | POST /api/world/tick 墙钟耗时，含规划、持久化和认知投影 |
| 模型调用耗时 | P50 15.976s / P95 20.020s（n=8） | Provider.plan 墙钟耗时，成功与失败均计入 |
| 已上报 token | 19012（覆盖 6/8 次调用） | usage.total_tokens 求和；未上报调用的消耗未知 |
| 兜底原因：Provider 失败，原因未区分 | 40.0%（2/5） | 本项次数 / source=fallback 提案数；计量 + trace |
| 兜底原因：动作被规则拒绝 | 60.0%（3/5） | 本项次数 / source=fallback 提案数；计量 + trace |

动作分布：move 11、rest 1、talk 2、wait 1

> 指标口径：`llm` 与 `existing_plan` 都算规划 Provider 产出的提案；`existing_plan` 不调用模型。P50/P95 用 nearest-rank（向上取整名次）。Embedding 与 Reflection 固定使用确定性替身；Fake 结果只验证链路，不代表真实模型可用率。
> 失败归因边界：当前 Live adapter 把超时、HTTP 错误和响应解析错误都转成 `PlanningProviderError`，落盘 trace 也只有 `source=fallback`。因此 Provider 失败只能列为「原因未区分」；不能把它们统称 Schema 失败，也不能据此给出超时或无效响应的精确次数。
> 使用 `--out` 时，同名 `.evidence.json` 保存去内容化的逐 tick、逐调用与逐提案样本，以及分子分母；不会保存 Prompt、模型响应或凭据。

## 读数说明（人工补充，非脚本输出）

**1. 兜底原因第一次被分开计量了。** 5 次兜底里 3 次是「动作被规则拒绝」、2 次是
「Provider 失败，原因未区分」。2026-09-14 的旧报告把这两类混在一起并推断「兜底主要来自
超时」；在这个小样本上，**被规则拒绝反而更多**。这正是把两个分母拆开的意义。

**2. 两次失败的耗时是 20020ms 和 20014ms，精确卡在 20 秒。** 同一次运行里 6 次成功调用
的耗时是 7387 / 8956 / 11711 / 15976 / 18012 / 18050 ms，最长 18.05 秒。耗时分布与
「撞上 20 秒超时上限」高度一致，但**当前 trace 无法确认这一点** —— Live adapter 把超时、
HTTP 错误和响应解析错误都转成同一个 `PlanningProviderError`，所以脚本只能如实标注
`provider_unknown`。**不要把这 2 次写成「2 次超时」**：那是推断，不是观测。这也是快照里
P1 项「保留安全的错误类别」要解决的问题。

**3. 动作合法率 76.9%（10/13）低于 spec §17.5 的 ≥90% 验收线。** 但分母只有 13 条，
远小于 2026-09-14 那次的 41 条。**这既不能说明验收通过，也不能说明验收失败** ——
样本不足以支撑任一结论。要判定 §17.5，需要跑满 20 tick 并固定口径。

**4. 计划完成率 0.0%（0/6）是窗口太短的产物，不是规划质量结论。** 6 条计划里 3 条
`abandoned`（步骤被规则拒绝后按 spec §6 规则 3 放弃）、3 条仍 `active`。5 个 tick 不够
任何一条计划走完。

**5. 计划复用的价值在 tick 4 上直接可见。** 5 个 tick 的墙钟耗时是
20.2 / 20.2 / 18.2 / **0.3** / 11.9 秒 —— tick 4 三个 NPC 全部复用已有计划，零模型调用，
于是整个 tick 只用了 0.3 秒。

**6. token：19012，覆盖 6/8 次调用。** 两次失败的调用没有 token 记录（Provider 未返回
usage），脚本没有让它们继承上一次成功调用的数字。
