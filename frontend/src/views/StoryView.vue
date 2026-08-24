<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  displayName: string
  classTitle: string
}>()

defineEmits<{
  complete: []
}>()

const passages = [
  '潮湿的草叶贴在掌心。你在曦谷城外醒来，只记得一道陌生的印记。',
  '名字仍属于你，过去却像被雾吞没。你只能先选择此刻要走的道路。',
  '酒馆的告示、公园的旧痕、城堡的残卷与森林的低语，都指向同一个未解的问题。',
  '先去认识这座小镇的居民。也许他们知道你从哪里来，也许他们同样在寻找答案。',
] as const

const passageIndex = ref(0)
const isLastPassage = computed(() => passageIndex.value === passages.length - 1)

function continueStory(): void {
  if (!isLastPassage.value) passageIndex.value += 1
}
</script>

<template>
  <main class="cinematic-shell" data-scene="story">
    <section class="cinematic-card" aria-labelledby="story-title">
      <p class="cinematic-kicker">{{ classTitle }} · 序章</p>
      <h1 id="story-title">{{ displayName }}，欢迎来到曦谷</h1>
      <p class="story-progress">{{ passageIndex + 1 }} / {{ passages.length }}</p>
      <p class="story-passage">{{ passages[passageIndex] }}</p>
      <div class="story-actions">
        <button type="button" data-action="skip-story" @click="$emit('complete')">跳过</button>
        <button
          v-if="!isLastPassage"
          type="button"
          data-action="continue-story"
          @click="continueStory"
        >
          继续
        </button>
        <button v-else type="button" data-action="complete-story" @click="$emit('complete')">
          进入曦谷
        </button>
      </div>
    </section>
  </main>
</template>
