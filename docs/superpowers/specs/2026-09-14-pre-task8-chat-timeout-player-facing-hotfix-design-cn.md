# Stage 3m Task 8 前稳定性热修设计

> **状态：已批准（2026-09-14）**
>
> 用户批准在 Task 8 前修复 NPC Chat 的前端超时误报与 Phaser 水平朝向反转；
> `openai_compatible` 的展示不在本次范围，由用户自行调整 `.env`。

## 目标

1. NPC Chat 不再因 Axios 全局 5 秒超时而在后端仍正常处理时提前失败。
2. 玩家向右移动时保持素材默认朝右，向左移动时水平翻转；上下方向保持现状。

## 设计

- 保留 Axios 全局 `5000ms`，仅在 `POST /api/npcs/{id}/chat` 上覆盖为 `60000ms`。
  当前本地配置的 Chat provider 超时为 `30s`，回复提交后认知处理预算默认 `5s`；
  60 秒只扩大浏览器等待窗口，不会改变后端的超时或执行时长。
- 保留现有 Chat 错误归一化与请求/响应契约，不新增重试，避免首轮请求已落库时自动重试制造重复会话。
- Phaser 的 `side` 帧素材默认朝右，因此 `x > 0` 应 `setFlipX(false)`，
  `x < 0` 应 `setFlipX(true)`；上下移动继续 `setFlipX(false)`。

## 边界与验证

- 不修改 `.env`、provider 标识、后端 API、数据库、Session 或世界推进逻辑。
- 为 Chat 出站请求的超时覆盖补回归测试；为四个方向的 sprite flip 补表驱动测试。
- 严格执行 RED → GREEN，并运行前端全量测试、type-check 与项目要求的后端全量基线。

