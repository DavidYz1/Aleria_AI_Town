<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  destinationAfterBoot,
  destinationAfterProfileCreated,
  destinationAfterStory,
} from './gameFlow'
import type { GameStage } from './gameFlow'
import type { AdventurerClass } from './player/playerProfile'
import { ADVENTURER_CLASSES } from './player/playerProfile'
import { usePlayerProfileStore } from './stores/playerProfile'
import BootView from './views/BootView.vue'
import CharacterCreationView from './views/CharacterCreationView.vue'
import StoryView from './views/StoryView.vue'
import TownView from './views/TownView.vue'

const profileStore = usePlayerProfileStore()
const stage = ref<GameStage>('boot')

profileStore.hydrate()

const classTitle = computed(() => {
  const adventurerClass = profileStore.profile?.adventurerClass
  return ADVENTURER_CLASSES.find(({ id }) => id === adventurerClass)?.title ?? ''
})

function continueFromBoot(): void {
  stage.value = destinationAfterBoot(profileStore.profile)
}

function createPlayer(name: string, adventurerClass: AdventurerClass): void {
  profileStore.createProfile(name, adventurerClass)
  stage.value = destinationAfterProfileCreated()
}

function completeStory(): void {
  profileStore.completeIntro()
  stage.value = destinationAfterStory()
}

function restartAdventure(): void {
  profileStore.resetProfile()
  stage.value = 'boot'
}
</script>

<template>
  <BootView
    v-if="stage === 'boot'"
    :has-profile="profileStore.profile !== null"
    @continue="continueFromBoot"
  />
  <template v-else-if="stage === 'create'">
    <p v-if="profileStore.storageWarning" class="storage-warning" role="status">
      {{ profileStore.storageWarning }}
    </p>
    <CharacterCreationView @created="createPlayer" />
  </template>
  <template v-else-if="stage === 'story'">
    <p v-if="profileStore.storageWarning" class="storage-warning" role="status">
      {{ profileStore.storageWarning }}
    </p>
    <StoryView
      :display-name="profileStore.profile?.displayName ?? ''"
      :class-title="classTitle"
      @complete="completeStory"
    />
  </template>
  <div v-else class="app-town-stage">
    <p v-if="profileStore.storageWarning" class="storage-warning" role="status">
      {{ profileStore.storageWarning }}
    </p>
    <TownView @restart="restartAdventure" />
  </div>
</template>
