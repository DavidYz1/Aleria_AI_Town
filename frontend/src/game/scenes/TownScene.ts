import Phaser from 'phaser'

import type { AdventurerClass } from '../../player/playerProfile'
import type { NpcVisualProjection } from '../contracts'
import {
  installCanvasFocus,
  installMovementKeyGuard,
  resolvePlayerVelocity,
} from '../movement'
import { resolveEnteredPlayerLocationId } from '../playerMapPosition'
import { TownGameBridge } from '../TownGameBridge'
import { TOWN_SCENE_KEY } from './BootScene'


const PLAYER_SPEED = 160
const NPC_FRAMES: Record<string, number> = {
  ryan: 0,
  shir: 1,
  grey: 2,
}

interface DirectionKeys {
  up: Phaser.Input.Keyboard.Key
  down: Phaser.Input.Keyboard.Key
  left: Phaser.Input.Keyboard.Key
  right: Phaser.Input.Keyboard.Key
}

type Facing = 'down' | 'side' | 'up'

export class TownScene extends Phaser.Scene {
  private player: Phaser.Physics.Arcade.Sprite | null = null
  private cursors: DirectionKeys | null = null
  private wasd: DirectionKeys | null = null
  private facing: Facing = 'down'
  private readonly anchors = new Map<string, { x: number, y: number }>()
  private readonly npcSprites = new Map<string, Phaser.GameObjects.Sprite>()
  private unsubscribeNpcs: (() => void) | null = null
  private unsubscribePlayerTeleport: (() => void) | null = null
  private canvas: HTMLCanvasElement | null = null
  private releaseCanvasFocus: (() => void) | null = null
  private releaseMovementKeyGuard: (() => void) | null = null
  private activePlayerLocationId: string | null = null

  constructor(private readonly bridge: TownGameBridge) {
    super({ key: TOWN_SCENE_KEY })
  }

  create(): void {
    const map = this.make.tilemap({ key: 'town-map' })
    const tileset = map.addTilesetImage('tiny-town-32', 'town-tiles')
    if (tileset === null) {
      this.bridge.emitLoadFailed('地图资源加载失败，请重试。')
      return
    }

    const ground = map.createLayer('ground', tileset)
    const decorBelow = map.createLayer('decor-below', tileset)
    const collision = map.createLayer('collision', tileset)
    const decorAbove = map.createLayer('decor-above', tileset)
    if (
      ground === null
      || decorBelow === null
      || collision === null
      || decorAbove === null
    ) {
      this.bridge.emitLoadFailed('地图资源加载失败，请重试。')
      return
    }
    ground.setDepth(0)
    decorBelow.setDepth(1)
    collision.setCollisionByExclusion([-1]).setVisible(false)
    decorAbove.setDepth(4)

    this.readAnchors(map)
    this.createAnimations()
    this.createPlayer(collision)
    this.configureInput()
    this.configureCamera(map)
    this.applyNpcProjections(this.bridge.getInput().npcs)
    this.unsubscribeNpcs = this.bridge.onNpcsUpdated((npcs) => {
      this.applyNpcProjections(npcs)
    })
    this.unsubscribePlayerTeleport = this.bridge.onPlayerTeleport((locationId) => {
      this.teleportPlayer(locationId)
    })

    this.events.on(Phaser.Scenes.Events.PAUSE, this.stopPlayer, this)
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, this.shutdown, this)
    this.game.events.on(Phaser.Core.Events.BLUR, this.stopPlayer, this)
  }

  update(): void {
    if (
      this.player === null
      || this.cursors === null
      || this.wasd === null
    ) {
      this.stopPlayer()
      return
    }

    const velocity = resolvePlayerVelocity({
      up: this.cursors.up.isDown || this.wasd.up.isDown,
      down: this.cursors.down.isDown || this.wasd.down.isDown,
      left: this.cursors.left.isDown || this.wasd.left.isDown,
      right: this.cursors.right.isDown || this.wasd.right.isDown,
    }, PLAYER_SPEED, document.activeElement)
    this.player.setVelocity(velocity.x, velocity.y)
    this.publishPlayerLocationEntry()
    this.updatePlayerAnimation(velocity.x, velocity.y)
  }

  private readAnchors(map: Phaser.Tilemaps.Tilemap): void {
    this.anchors.clear()
    const objectLayer = map.getObjectLayer('objects')
    for (const object of objectLayer?.objects ?? []) {
      if (object.name !== undefined && object.x !== undefined && object.y !== undefined) {
        this.anchors.set(object.name, { x: object.x, y: object.y })
      }
    }
  }

  private createPlayer(collision: Phaser.Tilemaps.TilemapLayer): void {
    const input = this.bridge.getInput()
    const locationAnchor = input.playerLocationId === null
      ? undefined
      : this.anchors.get(`location:${input.playerLocationId}`)
    const spawn = locationAnchor
      ?? this.anchors.get('player_spawn')
      ?? { x: 768, y: 704 }
    const texture = `adventurer-${input.profile.adventurerClass}`
    this.player = this.physics.add.sprite(spawn.x, spawn.y, texture, 1)
      .setDepth(3)
      .setCollideWorldBounds(true)
    const body = this.player.body as Phaser.Physics.Arcade.Body
    body.setSize(18, 20).setOffset(7, 11)
    this.physics.add.collider(this.player, collision)
    this.activePlayerLocationId = locationAnchor === undefined
      ? null
      : input.playerLocationId
  }

  private createAnimations(): void {
    for (const adventurerClass of ['mage', 'ranger', 'cleric'] as const) {
      this.createWalkAnimation(adventurerClass, 'down', 0, 2)
      this.createWalkAnimation(adventurerClass, 'side', 3, 5)
      this.createWalkAnimation(adventurerClass, 'up', 6, 8)
    }
  }

  private createWalkAnimation(
    adventurerClass: AdventurerClass,
    direction: Facing,
    start: number,
    end: number,
  ): void {
    const key = animationKey(adventurerClass, direction)
    if (this.anims.exists(key)) return
    this.anims.create({
      key,
      frames: this.anims.generateFrameNumbers(
        `adventurer-${adventurerClass}`,
        { start, end },
      ),
      frameRate: 8,
      repeat: -1,
    })
  }

  private configureInput(): void {
    const keyboard = this.input.keyboard
    if (keyboard !== null) {
      this.cursors = keyboard.addKeys({
        up: Phaser.Input.Keyboard.KeyCodes.UP,
        down: Phaser.Input.Keyboard.KeyCodes.DOWN,
        left: Phaser.Input.Keyboard.KeyCodes.LEFT,
        right: Phaser.Input.Keyboard.KeyCodes.RIGHT,
      }, false) as DirectionKeys
      this.wasd = keyboard.addKeys({
        up: Phaser.Input.Keyboard.KeyCodes.W,
        down: Phaser.Input.Keyboard.KeyCodes.S,
        left: Phaser.Input.Keyboard.KeyCodes.A,
        right: Phaser.Input.Keyboard.KeyCodes.D,
      }, false) as DirectionKeys
    }

    this.canvas = this.game.canvas
    this.releaseCanvasFocus?.()
    this.releaseCanvasFocus = installCanvasFocus(this.canvas)
    this.releaseMovementKeyGuard?.()
    this.releaseMovementKeyGuard = installMovementKeyGuard(window)
    this.canvas.setAttribute('aria-label', '曦谷 RPG 地图，点击后使用 WASD 或方向键移动')
    this.events.once(Phaser.Scenes.Events.DESTROY, this.shutdown, this)
  }

  private configureCamera(map: Phaser.Tilemaps.Tilemap): void {
    const width = map.widthInPixels
    const height = map.heightInPixels
    this.physics.world.setBounds(0, 0, width, height)
    this.cameras.main
      .setBounds(0, 0, width, height)
      .startFollow(this.player!, true, 0.12, 0.12)
      .setRoundPixels(true)
  }

  private updatePlayerAnimation(x: number, y: number): void {
    if (this.player === null) return
    const adventurerClass = this.bridge.getInput().profile.adventurerClass
    if (x === 0 && y === 0) {
      this.player.anims.stop()
      this.player.setFrame({ down: 1, side: 4, up: 7 }[this.facing])
      return
    }

    if (Math.abs(x) >= Math.abs(y) && x !== 0) {
      this.facing = 'side'
      this.player.setFlipX(x > 0)
    } else if (y < 0) {
      this.facing = 'up'
      this.player.setFlipX(false)
    } else {
      this.facing = 'down'
      this.player.setFlipX(false)
    }
    this.player.anims.play(animationKey(adventurerClass, this.facing), true)
  }

  private applyNpcProjections(npcs: NpcVisualProjection[]): void {
    const activeIds = new Set(npcs.map(({ id }) => id))
    for (const [npcId, sprite] of this.npcSprites) {
      if (activeIds.has(npcId)) continue
      this.tweens.killTweensOf(sprite)
      sprite.destroy()
      this.npcSprites.delete(npcId)
    }

    for (const npc of npcs) {
      const fallback = this.anchors.get('location:fallback') ?? { x: 768, y: 608 }
      const anchor = this.anchors.get(npc.anchorName) ?? fallback
      if (
        npc.anchorName === 'location:fallback'
        && import.meta.env.DEV
      ) {
        console.warn(`Unknown Backend NPC location: ${npc.locationId}`)
      }
      const x = anchor.x + npc.offsetX
      const y = anchor.y + npc.offsetY
      const existing = this.npcSprites.get(npc.id)
      if (existing === undefined) {
        const sprite = this.add.sprite(
          x,
          y,
          'npc-sprites',
          NPC_FRAMES[npc.id] ?? 0,
        )
          .setDepth(2)
          .setInteractive({ useHandCursor: true })
          .setData('npcId', npc.id)
          .setName(npc.name)
        sprite.on('pointerdown', () => this.bridge.emitNpcSelected(npc.id))
        this.npcSprites.set(npc.id, sprite)
      } else if (existing.x !== x || existing.y !== y) {
        this.tweens.killTweensOf(existing)
        this.tweens.add({ targets: existing, x, y, duration: 300 })
      }
    }
  }

  private readonly stopPlayer = (): void => {
    if (this.player?.body) this.player.setVelocity(0, 0)
  }

  private publishPlayerLocationEntry(): void {
    if (this.player === null) return
    const locationId = resolveEnteredPlayerLocationId({
      x: this.player.x,
      y: this.player.y,
    })
    if (locationId === this.activePlayerLocationId) return
    this.activePlayerLocationId = locationId
    if (locationId !== null) this.bridge.emitPlayerLocationEntered(locationId)
  }

  private teleportPlayer(locationId: string): void {
    const anchor = this.anchors.get(`location:${locationId}`)
    if (this.player === null || anchor === undefined) return
    this.stopPlayer()
    this.player.setPosition(anchor.x, anchor.y)
    this.activePlayerLocationId = locationId
    this.updatePlayerAnimation(0, 0)
  }

  private readonly shutdown = (): void => {
    this.stopPlayer()
    this.unsubscribeNpcs?.()
    this.unsubscribeNpcs = null
    this.unsubscribePlayerTeleport?.()
    this.unsubscribePlayerTeleport = null
    this.events.off(Phaser.Scenes.Events.PAUSE, this.stopPlayer, this)
    this.game.events.off(Phaser.Core.Events.BLUR, this.stopPlayer, this)
    this.releaseCanvasFocus?.()
    this.releaseCanvasFocus = null
    this.releaseMovementKeyGuard?.()
    this.releaseMovementKeyGuard = null
    this.activePlayerLocationId = null
    this.canvas = null
    this.npcSprites.clear()
    this.anchors.clear()
  }
}

function animationKey(
  adventurerClass: AdventurerClass,
  direction: Facing,
): string {
  return `adventurer-${adventurerClass}-walk-${direction}`
}
