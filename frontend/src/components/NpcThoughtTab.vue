<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { fetchNpcPlan, type NpcPlanData, type PlanInfo } from '../api/npcPlan'
import { NpcNotFoundError } from '../api/npc'

const props = defineProps<{
  npcId: string | null
  // Advancing the world replans; refetch so the panel never shows a stale tick.
  clockTick: number | null
}>()

type DecisionSource = 'llm' | 'stub' | 'existing_plan' | 'fallback'

const SOURCE_BADGES = {
  llm: { label: 'LLM 规划', note: '本回合由模型生成了一份新计划。' },
  // A fake-provider plan is still ProposalSource.LLM, but calling it "LLM 规划"
  // on screen would claim a model ran when none did.
  stub: {
    label: '替身规划',
    note: '未配置规划 provider，本回合由确定性替身生成计划 —— 流程与真实模型完全一致。',
  },
  existing_plan: { label: '沿用计划', note: '本回合复用已有计划，没有再调用模型。' },
  fallback: {
    label: '确定性兜底',
    note: '规划不可用，本回合由确定性策略接管 —— 模型挂了世界照常推进，这是设计的一部分。',
  },
} as const

const ACTION_LABELS: Record<string, string> = {
  move: '移动',
  rest: '休息',
  work: '工作',
  eat: '用餐',
  talk: '交谈',
  wait: '等待',
}

const FAILURE_MESSAGE = '思考记录暂时无法读取，请稍后重试。'

const data = ref<NpcPlanData | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// A response body is external data, not a compiler guarantee: a shape the API
// contract forbids must read as unavailable rather than as "this resident is
// not thinking about anything".
const current = computed<PlanInfo | null>(() => {
  const plan = data.value?.current
  return plan != null && Array.isArray(plan.steps) ? plan : null
})
const recent = computed<PlanInfo[]>(() => {
  const plans = data.value?.recent
  return Array.isArray(plans) ? plans.filter((plan) => plan.id !== current.value?.id) : []
})
const malformed = computed(
  () =>
    data.value !== null &&
    (!Array.isArray(data.value.recent) ||
      (data.value.current != null && !Array.isArray(data.value.current.steps))),
)

/**
 * `current_step_index` 是「本回合正在执行的步骤序号」：0 表示计划就是本回合新建的。
 *
 * 没有 active plan 只可能是规划失败：`AgentPlanner.decide` 在计划走完的**同一回合**
 * 就立刻重新规划，所以但凡 provider 可用，这里一定有一份计划。既然曾经有过计划
 * （`recent` 非空）却现在没有，本回合就是确定性策略接管的。
 */
const source = computed<DecisionSource | null>(() => {
  if (current.value !== null) {
    if (current.value.current_step_index > 0) return 'existing_plan'
    return current.value.provider === 'fake' ? 'stub' : 'llm'
  }
  return recent.value.length > 0 ? 'fallback' : null
})
const badge = computed(() => (source.value === null ? null : SOURCE_BADGES[source.value]))
const reference = computed<PlanInfo | null>(() => current.value ?? recent.value[0] ?? null)

// 兜底时 `reference` 指向上一份计划，那份计划的引用也属于上一份决策 ——
// 本回合根本没有决策，不该展示任何「本次引用」。
const evidence = computed(() =>
  source.value === 'fallback' || reference.value === null
    ? []
    : Array.isArray(reference.value.evidence)
      ? reference.value.evidence
      : [],
)

const observability = computed(() => {
  const plan = reference.value
  if (plan === null) return []
  return [
    ['provider', plan.provider],
    ['model', plan.model],
    ['latency', plan.latency_ms === null ? '—' : `${plan.latency_ms} ms`],
    ['tokens', plan.tokens_used === null ? '—' : `${plan.tokens_used}`],
  ]
})

function actionLabel(actionType: string): string {
  return ACTION_LABELS[actionType] ?? actionType
}

function stepState(index: number, plan: PlanInfo): 'done' | 'active' | 'pending' {
  if (index < plan.current_step_index) return 'done'
  return index === plan.current_step_index ? 'active' : 'pending'
}

async function load(npcId: string | null): Promise<void> {
  if (npcId === null) {
    data.value = null
    error.value = null
    return
  }
  loading.value = true
  error.value = null
  try {
    data.value = await fetchNpcPlan(npcId)
  } catch (cause) {
    data.value = null
    error.value = cause instanceof NpcNotFoundError ? '这位居民不存在。' : FAILURE_MESSAGE
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.npcId, props.clockTick] as const,
  () => load(props.npcId),
  { immediate: true },
)
</script>

<template>
  <div class="thought-tab">
    <p v-if="loading" class="thought-note" role="status" aria-live="polite">
      正在读取这位居民的思考记录…
    </p>

    <div v-else-if="error !== null || malformed" class="detail-error" role="alert">
      <p>{{ error ?? FAILURE_MESSAGE }}</p>
      <button type="button" @click="load(props.npcId)">重新读取</button>
    </div>

    <p v-else-if="badge === null" class="thought-note">
      这位居民还没有生成过计划。推进世界时间后，这里会显示它的目标、推理与计划步骤。
    </p>

    <template v-else>
      <p class="thought-badge-row">
        <span class="thought-badge" :class="`is-${source}`">{{ badge.label }}</span>
        <span v-if="reference" class="thought-badge-meta">
          {{ source === 'fallback' ? '上一份计划生成于第' : '第' }}
          {{ reference.created_clock_tick }} 回合
        </span>
      </p>
      <p class="thought-note thought-badge-note">{{ badge.note }}</p>
      <p v-if="source === 'fallback'" class="thought-note thought-badge-note">
        下方展示的是它最后一份计划，不是本回合的决策。
      </p>

      <template v-if="reference">
        <section class="thought-goal" aria-labelledby="thought-goal-heading">
          <p class="detail-label">Goal</p>
          <h4 id="thought-goal-heading">{{ reference.goal }}</h4>
          <p class="thought-goal-reason">{{ reference.goal_reason }}</p>
        </section>

        <section class="thought-reasoning" aria-labelledby="thought-reasoning-heading">
          <p class="detail-label">Thought</p>
          <h4 id="thought-reasoning-heading" class="visually-hidden">本回合的推理</h4>
          <blockquote>{{ reference.thought }}</blockquote>
        </section>

        <section class="thought-plan" aria-labelledby="thought-plan-heading">
          <p class="detail-label">Plan</p>
          <h4 id="thought-plan-heading">
            计划步骤
            <span class="thought-progress">
              第 {{ Math.min(reference.current_step_index + 1, reference.steps.length) }} /
              {{ reference.steps.length }} 步
            </span>
          </h4>
          <ol class="thought-steps" aria-label="计划步骤">
            <li
              v-for="(step, index) in reference.steps"
              :key="`${reference.id}-${index}`"
              :class="`is-${stepState(index, reference)}`"
            >
              <span class="thought-step-marker" aria-hidden="true" />
              <p class="thought-step-head">
                <span class="thought-step-action">{{ actionLabel(step.action_type) }}</span>
                <span v-if="step.target_id" class="thought-step-target">
                  → {{ step.target_id }}
                </span>
                <span class="thought-step-state">
                  {{
                    stepState(index, reference) === 'done'
                      ? '已完成'
                      : stepState(index, reference) === 'active'
                        ? '进行中'
                        : '待执行'
                  }}
                </span>
              </p>
              <p class="thought-step-intent">{{ step.intent }}</p>
            </li>
          </ol>
        </section>

        <section
          v-if="evidence.length > 0"
          class="thought-evidence"
          aria-labelledby="thought-evidence-heading"
        >
          <p class="detail-label">Evidence</p>
          <h4 id="thought-evidence-heading">这次决策引用的记忆</h4>
          <ul class="thought-evidence-list" aria-label="引用的记忆">
            <li v-for="item in evidence" :key="item.id">
              <span class="thought-evidence-label">{{ item.label }}</span>
              <span class="thought-evidence-summary">{{ item.summary }}</span>
            </li>
          </ul>
          <p class="thought-note thought-evidence-note">
            只列出可以公开的部分；不可公开的记忆不会出现，也不会以数量差异体现。
          </p>
        </section>

        <dl class="thought-observability" aria-label="规划可观测性">
          <div v-for="[term, value] in observability" :key="term">
            <dt>{{ term }}</dt>
            <dd>{{ value }}</dd>
          </div>
        </dl>
      </template>

      <section v-if="recent.length > 0" class="thought-recent" aria-labelledby="thought-recent-heading">
        <p class="detail-label">History</p>
        <h4 id="thought-recent-heading">近期计划</h4>
        <ol class="thought-recent-list" aria-label="近期计划">
          <li v-for="plan in recent" :key="plan.id">
            <span class="thought-recent-tick">第 {{ plan.created_clock_tick }} 回合</span>
            <span class="thought-recent-goal">{{ plan.goal }}</span>
            <span class="thought-recent-status" :class="`is-${plan.status}`">
              {{ plan.status === 'completed' ? '已完成' : plan.status === 'abandoned' ? '已放弃' : '进行中' }}
            </span>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>

<style scoped>
.thought-tab {
  display: grid;
  gap: 1.25rem;
}

.detail-label {
  margin: 0;
  color: #586b5d;
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.thought-tab h4 {
  margin: 0.35rem 0 0;
  color: #1f3d2a;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.thought-note {
  margin: 0;
  color: #59645c;
  line-height: 1.6;
}

.detail-error {
  margin: 0;
  padding: 0.9rem 1rem;
  border: 1px solid #b36f61;
  border-radius: 0.65rem;
  color: #7d392f;
  background: #f7ece8;
}

.detail-error p {
  margin: 0 0 0.75rem;
}

.thought-badge-row {
  display: flex;
  align-items: baseline;
  gap: 0.7rem;
  margin: 0;
}

.thought-badge {
  padding: 0.32rem 0.7rem;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.thought-badge.is-llm {
  color: #f4f7f1;
  background: #315b45;
}

.thought-badge.is-stub {
  border-color: #7f8f82;
  color: #3d5143;
  background: #eef1ea;
}

.thought-badge.is-existing_plan {
  border-color: #315b45;
  color: #285139;
  background: #e6eadf;
}

.thought-badge.is-fallback {
  border-color: #a8804c;
  color: #6f4d21;
  background: #f6ecdb;
}

.thought-badge-meta {
  color: #7a6348;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.thought-badge-note {
  margin-top: -0.75rem;
  font-size: 0.85rem;
}

.thought-goal,
.thought-reasoning {
  padding: 1rem 1.1rem;
  border: 1px solid #cbd1c6;
  border-radius: 0.65rem;
  background: #f4f5ef;
}

.thought-goal {
  border-left: 0.28rem solid #315b45;
}

.thought-goal h4 {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.3rem;
  font-weight: 500;
  line-height: 1.4;
}

.thought-goal-reason {
  margin: 0.5rem 0 0;
  color: #4b5b50;
  line-height: 1.6;
}

.thought-reasoning blockquote {
  margin: 0.5rem 0 0;
  color: #253027;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.02rem;
  font-style: italic;
  line-height: 1.7;
}

.thought-reasoning blockquote::before {
  content: "「";
  color: #8fa394;
}

.thought-reasoning blockquote::after {
  content: "」";
  color: #8fa394;
}

.thought-plan h4 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
}

.thought-progress {
  color: #7a6348;
  font-size: 0.78rem;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.thought-steps {
  display: grid;
  gap: 0.1rem;
  margin: 0.8rem 0 0;
  padding: 0;
  list-style: none;
}

.thought-steps li {
  position: relative;
  padding: 0.7rem 0.9rem 0.85rem 2.1rem;
  border-radius: 0.55rem;
}

/* The rail joins consecutive markers; the last item has nothing to join to. */
.thought-steps li::before {
  content: "";
  position: absolute;
  top: 1.55rem;
  bottom: -0.1rem;
  left: 1.07rem;
  width: 2px;
  background: #cbd1c6;
}

.thought-steps li:last-child::before {
  display: none;
}

.thought-step-marker {
  position: absolute;
  top: 0.95rem;
  left: 0.75rem;
  width: 0.68rem;
  height: 0.68rem;
  border: 2px solid #aebbac;
  border-radius: 50%;
  background: #fcfcf7;
}

.thought-steps li.is-done .thought-step-marker {
  border-color: #6d8a78;
  background: #6d8a78;
}

.thought-steps li.is-active {
  background: #e6eadf;
  box-shadow: inset 0.2rem 0 0 #315b45;
}

.thought-steps li.is-active .thought-step-marker {
  border-color: #315b45;
  background: #315b45;
  box-shadow: 0 0 0 0.22rem rgb(49 91 69 / 18%);
}

.thought-step-head {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  margin: 0;
}

.thought-step-action {
  color: #1f3d2a;
  font-weight: 700;
}

.thought-steps li.is-pending .thought-step-action {
  color: #59645c;
  font-weight: 600;
}

.thought-step-target {
  color: #7a6348;
  font-size: 0.85rem;
}

.thought-step-state {
  margin-left: auto;
  color: #59645c;
  font-size: 0.73rem;
  letter-spacing: 0.04em;
}

.thought-steps li.is-active .thought-step-state {
  color: #285139;
  font-weight: 700;
}

.thought-step-intent {
  margin: 0.3rem 0 0;
  color: #4b5b50;
  font-size: 0.9rem;
  line-height: 1.55;
}

.thought-steps li.is-done .thought-step-intent {
  color: #77857b;
}

.thought-evidence-list {
  display: grid;
  gap: 0.4rem;
  margin: 0.7rem 0 0;
  padding: 0;
  list-style: none;
}

.thought-evidence-list li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: baseline;
  gap: 0.55rem;
  padding: 0.55rem 0.75rem;
  border-left: 0.18rem solid #cbd1c6;
  border-radius: 0.45rem;
  background: #f4f5ef;
}

.thought-evidence-label {
  color: #7a6348;
  font-size: 0.72rem;
  font-weight: 700;
  white-space: nowrap;
}

.thought-evidence-summary {
  color: #4b5b50;
  font-size: 0.88rem;
  line-height: 1.55;
}

.thought-evidence-note {
  margin-top: 0.5rem;
  font-size: 0.78rem;
}

.thought-observability {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0;
  padding-top: 0.9rem;
  border-top: 1px dashed #cbd1c6;
}

.thought-observability div {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  padding: 0.3rem 0.6rem;
  border-radius: 0.45rem;
  background: #edf0e8;
}

.thought-observability dt {
  color: #7a6348;
  font-size: 0.68rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.thought-observability dd {
  margin: 0;
  color: #253027;
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
}

.thought-recent-list {
  display: grid;
  gap: 0.35rem;
  margin: 0.7rem 0 0;
  padding: 0;
  list-style: none;
}

.thought-recent-list li {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  padding: 0.45rem 0.7rem;
  border-radius: 0.45rem;
  background: #f4f5ef;
  font-size: 0.86rem;
}

.thought-recent-tick {
  color: #7a6348;
  font-size: 0.74rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.thought-recent-goal {
  color: #253027;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thought-recent-status {
  margin-left: auto;
  font-size: 0.73rem;
  white-space: nowrap;
}

.thought-recent-status.is-completed {
  color: #3f6d51;
}

.thought-recent-status.is-abandoned {
  color: #8a6a3c;
}

.thought-recent-status.is-active {
  color: #4b5b50;
}

@media (max-width: 700px) {
  .thought-recent-goal {
    white-space: normal;
  }
}
</style>
