# Stage 3m Agent Evaluation

- 生成时间：2026-09-16 16:59:58 UTC
- Provider：`fake`　Model：`fake-planner-1`
- Tick 数：20　动作空间：6 个动词

| 指标 | 值 | 含义 |
| --- | --- | --- |
| 动作合法率 | 100.0%（60/60） | 未被规则替换的计划步骤 / 所有计划步骤提案；planning + proposal trace |
| 可用决策率 | 100.0%（30/30） | 返回可用 AgentDecision / 实际 Provider 调用；调用计量，失败不等于 Schema 错误 |
| 兜底率 | 0.0%（0/60） | source=fallback / 全部 NPC 提案；proposal trace |
| 计划完成率（状态） | 90.0%（27/30） | status=completed / 创建的计划行；含窗口截尾与过龄结束，非语义目标达成 |
| 行为熵 | 1.411 / 2.585 | actions.action_type 分布的香农熵；n=动作行数，描述多样性 |
| 计划复用率 | 50.0%（30/60） | source=existing_plan / 全部 NPC 提案；proposal trace |
| 模型调用 / NPC-tick | 30/60 = 0.500 | 本次 Provider 调用计量 / 全部 NPC 提案 |
| tick 耗时 | P50 0.225s / P95 0.346s（n=20） | POST /api/world/tick 墙钟耗时，含规划、持久化和认知投影 |
| 模型调用耗时 | P50 0.04ms / P95 0.22ms（n=30） | Provider.plan 墙钟耗时，成功与失败均计入 |
| 已上报 token | —（覆盖 0/30 次调用） | Provider 未上报，消耗未知 |

动作分布：eat 3、move 2、rest 28、talk 27

> 指标口径：`llm` 与 `existing_plan` 都算规划 Provider 产出的提案；`existing_plan` 不调用模型。P50/P95 用 nearest-rank（向上取整名次）。Embedding 与 Reflection 固定使用确定性替身；Fake 结果只验证链路，不代表真实模型可用率。
> 失败归因：兜底原因直接读落盘 trace，格式 `<stage>:<code>`。`provider:*` 来自 adapter 按异常类型分的四类（timeout / http_status / transport / parse_error），`rule:*` 是 `ActionRegistry` 与 conflict_resolver 的拒绝码，由 `rule_rejection` trace 记录被替换掉的原始提案。拿不到分类时记 `provider:unknown` 或 `unattributed`，不按异常长相臆造具体原因。
> 使用 `--out` 时，同名 `.evidence.json` 保存去内容化的逐 tick、逐调用与逐提案样本，以及分子分母；不会保存 Prompt、模型响应或凭据。
