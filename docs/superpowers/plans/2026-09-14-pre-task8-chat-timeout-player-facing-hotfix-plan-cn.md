# Stage 3m Task 8 前稳定性热修 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 NPC Chat 的 5 秒前端超时误报，并纠正 Phaser 玩家左右朝向反转。

**Architecture:** 两项修复均保持既有边界：Chat 仅在 API adapter 的单个请求上覆盖 Axios timeout；Phaser 仅更正 side sprite 的水平翻转判据。后端、数据库、provider 与全局 HTTP 策略不变。

**Tech Stack:** Vue 3、TypeScript、Axios、Phaser 3.90、Vitest。

**Spec:** `docs/superpowers/specs/2026-09-14-pre-task8-chat-timeout-player-facing-hotfix-design-cn.md`

## Global Constraints

- Agent 不执行 `git add`、`git commit`、`git push` 或其他 Git 写操作。
- 不读取或写入 `backend/data/aleria.db`。
- 严格执行 RED → GREEN；无新增 skip 或 warning。
- `openai_compatible` 与 `.env` 不在本次修改范围。

---

### Task 1: NPC Chat 单请求超时覆盖

**Review Level:** R1（前端 API adapter 行为修复；Public API 不变）

**Binding 条款锚点:** 本 spec「设计」第 1–2 条；既有后端 `CHAT_LLM_TIMEOUT_SECONDS=30` 与 `cognition_post_commit_budget_seconds=5`。

**证据要求:** 测试必须观测 `api.post` 的真实第三参数，并证明 timeout 大于后端 35 秒正常窗口。

**Files:**
- Modify: `tests/frontend/chatApi.spec.ts`
- Modify: `tests/frontend/phase2Acceptance.spec.ts`
- Modify: `tests/frontend/TownView.spec.ts`
- Modify: `frontend/src/api/chat.ts`

**Interfaces:**
- Consumes: `api.post(url, payload, config)`
- Produces: `sendNpcChat(npcId, request)` 以 `{ timeout: 60_000 }` 调用既有 Chat 端点。

- [x] **Step 1: 写失败测试**

  将 Chat adapter 与 Phase 2 acceptance 的调用断言扩展到 Axios config：

  ```ts
  expect(post).toHaveBeenCalledWith(
    '/api/npcs/ryan/chat',
    request,
    { timeout: 60_000 },
  )
  expect((post.mock.calls[0]?.[2] as { timeout: number }).timeout)
    .toBeGreaterThan(35_000)
  ```

- [x] **Step 2: 运行 RED**

  Run: `npm --prefix frontend test -- chatApi.spec.ts phase2Acceptance.spec.ts`

  Expected: FAIL，实际调用没有第三个 config 参数。

- [x] **Step 3: 写最小实现**

  在 `frontend/src/api/chat.ts` 内定义 `NPC_CHAT_TIMEOUT_MS = 60_000`，并把
  `{ timeout: NPC_CHAT_TIMEOUT_MS }` 作为 `api.post` 第三个参数。保留错误处理原样。

- [x] **Step 4: 运行 GREEN**

  Run: `npm --prefix frontend test -- chatApi.spec.ts phase2Acceptance.spec.ts`

  Expected: 两个测试文件全绿。

### Task 2: Phaser 水平朝向

**Review Level:** R1（单一渲染判据修复）

**Binding 条款锚点:** 本 spec「设计」第 3 条；用户实测左右方向恰好相反，上下正确。

**证据要求:** 同一测试覆盖 right/left/up/down 四个字面输入与 flip 结果。

**Files:**
- Modify: `tests/frontend/TownSceneInput.spec.ts`
- Modify: `frontend/src/game/scenes/TownScene.ts`

**Interfaces:**
- Consumes: `TownScene.updatePlayerAnimation(x, y)` 与 Phaser Sprite `setFlipX(boolean)`。
- Produces: right→false、left→true、up/down→false。

- [x] **Step 1: 写失败测试**

  ```ts
  it.each([
    ['right', 160, 0, false],
    ['left', -160, 0, true],
    ['up', 0, -160, false],
    ['down', 0, 160, false],
  ])('faces %s while moving', async (_name, x, y, expectedFlipX) => {
    // 构造真实 TownScene，注入最小 Phaser Sprite 边界替身。
    updatePlayerAnimation.call(scene, x, y)
    expect(player.setFlipX).toHaveBeenLastCalledWith(expectedFlipX)
  })
  ```

- [x] **Step 2: 运行 RED**

  Run: `npm --prefix frontend test -- TownSceneInput.spec.ts`

  Expected: right/left 两例失败，上下通过。

- [x] **Step 3: 写最小实现**

  将 `TownScene.ts` 水平分支从 `this.player.setFlipX(x > 0)` 改为
  `this.player.setFlipX(x < 0)`。

- [x] **Step 4: 运行 GREEN**

  Run: `npm --prefix frontend test -- TownSceneInput.spec.ts`

  Expected: 文件全绿。

### Task 3: 回归与交付记录

**Review Level:** R1

**Binding 条款锚点:** `AGENTS.md` 验证基线与交接约定。

**证据要求:** 全量命令输出必须来自当前工作树；不得用历史数字替代。

**Files:**
- Modify: `.superpowers/sdd/2026-09-13-stage-3m-agent-loop-mvp-plan-cn/progress.md`（git ignored）
- Modify: `CURRENT_STATE.md`

**Interfaces:**
- Consumes: 两个 GREEN 结果与完整验证矩阵。
- Produces: Task 8 前热修的 Ruling、真实测试数字和人类手动提交建议。

- [x] **Step 1: 运行完整验证矩阵**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pre-task8-hotfix
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

- [x] **Step 2: 更新状态与 ledger**

  记录 RED/GREEN、全量结果、R1 结论与 deferred 项；不得声称未运行的 Live Chat 通过。

- [x] **Step 3: 保持改动未暂存**

  输出建议提交信息 `fix(frontend): stabilize npc chat and player facing`，由人类 review 后提交。
