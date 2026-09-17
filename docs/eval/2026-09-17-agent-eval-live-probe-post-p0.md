# Stage 3m Agent Evaluation（Live 探路，5 tick · failure taxonomy 落地后）

> **探路运行，样本极小，不构成 spec §17.5 验收。** 5 tick × 3 NPC = 15 个 NPC-tick。
> 与 [2026-09-16 的探路](2026-09-16-agent-eval-live-probe.md)**不是受控 A/B**：两次相隔约一小时、
> 外部服务状态不可控、样本都太小。下表数字逐字保留脚本输出。


- 生成时间：2026-09-16 17:02:23 UTC
- Provider：`openai_compatible`　Model：`hy3`
- Tick 数：5　动作空间：6 个动词

| 指标 | 值 | 含义 |
| --- | --- | --- |
| 动作合法率 | 100.0%（7/7） | 未被规则替换的计划步骤 / 所有计划步骤提案；planning + proposal trace |
| 可用决策率 | 27.3%（3/11） | 返回可用 AgentDecision / 实际 Provider 调用；调用计量，失败不等于 Schema 错误 |
| 兜底率 | 53.3%（8/15） | source=fallback / 全部 NPC 提案；proposal trace |
| 计划完成率（状态） | 66.7%（2/3） | status=completed / 创建的计划行；含窗口截尾与过龄结束，非语义目标达成 |
| 行为熵 | 1.555 / 2.585 | actions.action_type 分布的香农熵；n=动作行数，描述多样性 |
| 计划复用率 | 26.7%（4/15） | source=existing_plan / 全部 NPC 提案；proposal trace |
| 模型调用 / NPC-tick | 11/15 = 0.733 | 本次 Provider 调用计量 / 全部 NPC 提案 |
| tick 耗时 | P50 20.225s / P95 20.607s（n=5） | POST /api/world/tick 墙钟耗时，含规划、持久化和认知投影 |
| 模型调用耗时 | P50 20.016s / P95 20.024s（n=11） | Provider.plan 墙钟耗时，成功与失败均计入 |
| 已上报 token | 8904（覆盖 3/11 次调用） | usage.total_tokens 求和；未上报调用的消耗未知 |
| 兜底原因：Provider·调用超时（`provider:timeout`） | 100.0%（8/8） | 本项次数 / source=fallback 提案数；落盘 trace |

动作分布：move 3、rest 1、talk 2、work 9

> 指标口径：`llm` 与 `existing_plan` 都算规划 Provider 产出的提案；`existing_plan` 不调用模型。P50/P95 用 nearest-rank（向上取整名次）。Embedding 与 Reflection 固定使用确定性替身；Fake 结果只验证链路，不代表真实模型可用率。
> 失败归因：兜底原因直接读落盘 trace，格式 `<stage>:<code>`。`provider:*` 来自 adapter 按异常类型分的四类（timeout / http_status / transport / parse_error），`rule:*` 是 `ActionRegistry` 与 conflict_resolver 的拒绝码，由 `rule_rejection` trace 记录被替换掉的原始提案。拿不到分类时记 `provider:unknown` 或 `unattributed`，不按异常长相臆造具体原因。
> 使用 `--out` 时，同名 `.evidence.json` 保存去内容化的逐 tick、逐调用与逐提案样本，以及分子分母；不会保存 Prompt、模型响应或凭据。

## 读数说明（人工补充，非脚本输出）

**1. 失败归因第一次是可复核的观测，不再是推断。** 8 次兜底**全部**是
`provider:timeout`，由 adapter 按异常类型分类后落进 `planning` trace。对照
2026-09-14 报告里那句无法复核的「19 次超时」——同样的结论，这次有 trace 支撑。

**2. 超时上限配得太紧，这次有数据说话了。** 配置是 20 秒
（`PLANNING_PROVIDER_TIMEOUT_SECONDS`），而 8 次超时全部精确落在 20007–20024ms，
3 次成功是 **12622 / 18600 / 18521 ms**。成功调用已经贴着上限，说明相当一部分超时
可能「再等几秒就能返回」。这是先补观测、再谈优化的直接回报：把上限调到 30 秒是
一个**有依据**的下一步（代价是失败时 tick 更慢），而不是猜测。

**3. 规则拒绝归零，`work` 首次出现 —— 有信号，但不能声称因果。**
上一轮 3 次 `rule_rejected`、`work` 出现 0 次；本轮 0 次规则拒绝、动作分布里
`work 9`。这与「模型现在知道自己的岗位在哪、且工具描述写明了位置前置条件」一致，
但动作合法率的分母只有 7 条，**7 个样本不足以确认因果**。上一轮那 3 次拒绝的具体
原因当时也没落盘（正是本轮要解决的问题），所以两轮无法做严格对比。

**4. 可用决策率从 75%（6/8）掉到 27.3%（3/11），原因未确定。**
一个可以排除的假设是「prompt 变长拖慢了模型」：本轮成功调用平均 **2968** token
（2572/3012/3320），上一轮是 **3169**（19012/6）——请求并没有变大。剩下的可能性
主要是外部服务当时更慢，但 5 tick 无法区分。**不要把这个下降写成本轮改动的后果，
也不要写成与改动无关。**

**5. 计划完成率 66.7%（2/3）分母极小**，无解释价值，仅列出以保持口径完整。
