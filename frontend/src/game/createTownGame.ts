import Phaser from 'phaser'

import type {
  NpcVisualProjection,
  TownGameCallbacks,
  TownGameController,
  TownGameInput,
} from './contracts'
import { BootScene } from './scenes/BootScene'
import { TownScene } from './scenes/TownScene'
import { TownGameBridge } from './TownGameBridge'


export function createTownGame(
  parent: HTMLElement,
  input: TownGameInput,
  callbacks: TownGameCallbacks,
): TownGameController {
  const bridge = new TownGameBridge(input)
  const unsubscribeSelected = bridge.onNpcSelected(callbacks.onNpcSelected)
  const unsubscribePlayerLocation = bridge.onPlayerLocationEntered(
    callbacks.onPlayerLocationEntered,
  )
  const unsubscribeLoadFailed = bridge.onLoadFailed(callbacks.onLoadFailed)
  const game = new Phaser.Game({
    type: Phaser.AUTO,
    parent,
    backgroundColor: '#18251f',
    pixelArt: true,
    roundPixels: true,
    scale: {
      mode: Phaser.Scale.RESIZE,
      autoCenter: Phaser.Scale.CENTER_BOTH,
      width: 960,
      height: 540,
    },
    physics: {
      default: 'arcade',
      arcade: { debug: false },
    },
    scene: [new BootScene(bridge), new TownScene(bridge)],
  })
  let destroyed = false

  return {
    updateNpcs(npcs: NpcVisualProjection[]): void {
      if (!destroyed) bridge.updateNpcs(npcs)
    },
    teleportPlayer(locationId: string): void {
      if (!destroyed) bridge.teleportPlayer(locationId)
    },
    destroy(): void {
      if (destroyed) return
      destroyed = true
      unsubscribeSelected()
      unsubscribePlayerLocation()
      unsubscribeLoadFailed()
      bridge.clear()
      game.destroy(true)
    },
  }
}
