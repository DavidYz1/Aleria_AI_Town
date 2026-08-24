import type { LocalPlayerProfileV1 } from './player/playerProfile'

export type GameStage = 'boot' | 'create' | 'story' | 'town'

export function destinationAfterBoot(
  profile: LocalPlayerProfileV1 | null,
): Exclude<GameStage, 'boot'> {
  if (profile === null) return 'create'
  return profile.introCompleted ? 'town' : 'story'
}

export const destinationAfterProfileCreated = (): GameStage => 'story'

export const destinationAfterStory = (): GameStage => 'town'
