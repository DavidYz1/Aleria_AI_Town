import Phaser from 'phaser'

import { TownGameBridge } from '../TownGameBridge'


export const BOOT_SCENE_KEY = 'BootScene'
export const TOWN_SCENE_KEY = 'TownScene'

export class BootScene extends Phaser.Scene {
  private failedResourceKey: string | null = null

  constructor(private readonly bridge: TownGameBridge) {
    super({ key: BOOT_SCENE_KEY })
  }

  preload(): void {
    this.failedResourceKey = null
    this.load.once('loaderror', (file: Phaser.Loader.File) => {
      this.failedResourceKey ??= file.key
    })
    this.load.once('complete', () => {
      if (this.failedResourceKey !== null) {
        this.bridge.emitLoadFailed('地图资源加载失败，请重试。')
        return
      }
      this.scene.start(TOWN_SCENE_KEY)
    })

    this.load.tilemapTiledJSON(
      'town-map',
      '/assets/phase2/maps/town.json',
    )
    this.load.image(
      'town-tiles',
      '/assets/phase2/tiles/tiny-town-32.png',
    )
    for (const adventurerClass of ['mage', 'ranger', 'cleric'] as const) {
      this.load.spritesheet(
        `adventurer-${adventurerClass}`,
        `/assets/phase2/sprites/adventurer-${adventurerClass}.png`,
        { frameWidth: 32, frameHeight: 32 },
      )
    }
    this.load.spritesheet(
      'npc-sprites',
      '/assets/phase2/sprites/npcs.png',
      { frameWidth: 32, frameHeight: 32 },
    )
  }
}
