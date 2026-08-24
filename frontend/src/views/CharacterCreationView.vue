<script setup lang="ts">
import { ref } from 'vue'

import {
  ADVENTURER_CLASSES,
  isValidDisplayName,
} from '../player/playerProfile'
import type { AdventurerClass } from '../player/playerProfile'

const displayName = ref('')
const selectedClass = ref<AdventurerClass>('mage')
const validationError = ref<string | null>(null)

const emit = defineEmits<{
  created: [displayName: string, adventurerClass: AdventurerClass]
}>()

function submit(): void {
  if (!isValidDisplayName(displayName.value)) {
    validationError.value = '名称需为 1～16 个中文、字母、数字或常用分隔符。'
    return
  }

  validationError.value = null
  emit('created', displayName.value, selectedClass.value)
}
</script>

<template>
  <main class="cinematic-shell" data-scene="create">
    <section class="cinematic-card" aria-labelledby="creation-title">
      <p class="cinematic-kicker">01 · 新的身份</p>
      <h1 id="creation-title">写下你的名字</h1>
      <p class="cinematic-lede">它会成为曦谷居民记住你的方式。</p>

      <form class="creation-form" @submit.prevent="submit">
        <label for="display-name">冒险者姓名</label>
        <input
          id="display-name"
          v-model="displayName"
          name="displayName"
          autocomplete="nickname"
          maxlength="16"
          :aria-describedby="validationError ? 'display-name-error' : undefined"
        >
        <p v-if="validationError" id="display-name-error" class="form-error" role="alert">
          {{ validationError }}
        </p>

        <fieldset>
          <legend>选择道路</legend>
          <div class="class-choice-grid">
            <button
              v-for="adventurerClass in ADVENTURER_CLASSES"
              :key="adventurerClass.id"
              type="button"
              class="class-choice"
              :class="{ 'is-selected': selectedClass === adventurerClass.id }"
              :data-class="adventurerClass.id"
              :aria-pressed="selectedClass === adventurerClass.id"
              @click="selectedClass = adventurerClass.id"
            >
              <strong>{{ adventurerClass.title }}</strong>
              <span>{{ adventurerClass.description }}</span>
            </button>
          </div>
        </fieldset>

        <button type="submit">开始这段旅程</button>
      </form>
    </section>
  </main>
</template>
