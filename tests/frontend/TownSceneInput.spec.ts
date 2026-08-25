import { afterEach, describe, expect, it, vi } from 'vitest'

import * as movement from '../../frontend/src/game/movement'
import { TownGameBridge } from '../../frontend/src/game/TownGameBridge'


type InstallCanvasFocus = (canvas: HTMLCanvasElement) => () => void
type InstallMovementKeyGuard = (target: Window) => () => void
type IsTextEntryElement = (element: Element | null) => boolean
type ResolvePlayerVelocity = (
  input: movement.DirectionInput,
  speed: number,
  activeElement: Element | null,
) => movement.Velocity

function installCanvasFocus(): InstallCanvasFocus {
  const candidate: unknown = Reflect.get(movement, 'installCanvasFocus')
  expect(typeof candidate).toBe('function')
  return candidate as InstallCanvasFocus
}

function isTextEntryElement(): IsTextEntryElement {
  const candidate: unknown = Reflect.get(movement, 'isTextEntryElement')
  expect(typeof candidate).toBe('function')
  return candidate as IsTextEntryElement
}

function installMovementKeyGuard(): InstallMovementKeyGuard {
  const candidate: unknown = Reflect.get(movement, 'installMovementKeyGuard')
  expect(typeof candidate).toBe('function')
  return candidate as InstallMovementKeyGuard
}

function resolvePlayerVelocity(): ResolvePlayerVelocity {
  const candidate: unknown = Reflect.get(movement, 'resolvePlayerVelocity')
  expect(typeof candidate).toBe('function')
  return candidate as ResolvePlayerVelocity
}

afterEach(() => {
  document.body.replaceChildren()
})

describe('TownScene canvas input policy', () => {
  it('makes the canvas focusable and focuses it before existing pointer handlers run', () => {
    const textInput = document.createElement('input')
    const canvas = document.createElement('canvas')
    document.body.append(textInput, canvas)
    canvas.addEventListener('pointerdown', (event) => event.stopImmediatePropagation())
    installCanvasFocus()(canvas)

    textInput.focus()
    canvas.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))

    expect(canvas.tabIndex).toBe(0)
    expect(document.activeElement).toBe(canvas)
  })

  it('removes the capturing focus listener during cleanup', () => {
    const textInput = document.createElement('input')
    const canvas = document.createElement('canvas')
    document.body.append(textInput, canvas)
    const cleanup = installCanvasFocus()(canvas)
    cleanup()

    textInput.focus()
    canvas.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))

    expect(document.activeElement).toBe(textInput)
  })

  it.each([
    ['page body', () => document.body],
    ['button', () => document.createElement('button')],
    ['canvas', () => document.createElement('canvas')],
  ])('allows movement while %s owns focus', (_name, createElement) => {
    const element = createElement()
    expect(isTextEntryElement()(element)).toBe(false)
  })

  it.each([
    ['input', () => document.createElement('input')],
    ['textarea', () => document.createElement('textarea')],
    ['contenteditable', () => {
      const editable = document.createElement('div')
      editable.setAttribute('contenteditable', 'true')
      return editable
    }],
    ['contenteditable child', () => {
      const editable = document.createElement('div')
      editable.setAttribute('contenteditable', 'plaintext-only')
      const child = document.createElement('span')
      editable.append(child)
      return child
    }],
  ])('blocks movement while %s is active', (_name, createElement) => {
    expect(isTextEntryElement()(createElement())).toBe(true)
  })

  it.each([
    ['false', 'false'],
    ['invalid', 'inherit'],
  ])('does not treat contenteditable=%s as an editable root', (_name, value) => {
    const element = document.createElement('div')
    element.setAttribute('contenteditable', value)
    expect(isTextEntryElement()(element)).toBe(false)
  })

  it('inherits an editable ancestor through an invalid contenteditable token', () => {
    const editable = document.createElement('div')
    editable.setAttribute('contenteditable', 'true')
    const invalidChild = document.createElement('div')
    invalidChild.setAttribute('contenteditable', 'inherit')
    const target = document.createElement('span')
    invalidChild.append(target)
    editable.append(invalidChild)

    expect(isTextEntryElement()(target)).toBe(true)
  })

  it('resolves movement for button focus and zero velocity for text focus', () => {
    const direction: movement.DirectionInput = {
      up: true,
      down: false,
      left: false,
      right: false,
    }

    expect(resolvePlayerVelocity()(direction, 160, document.createElement('button')))
      .toEqual({ x: 0, y: -160 })
    expect(resolvePlayerVelocity()(direction, 160, document.createElement('textarea')))
      .toEqual({ x: 0, y: 0 })
  })

  it('prevents movement-key defaults outside text entry and releases the guard', () => {
    const button = document.createElement('button')
    const textInput = document.createElement('input')
    document.body.append(button, textInput)
    const cleanup = installMovementKeyGuard()(window)

    button.focus()
    const movementKey = new KeyboardEvent('keydown', {
      bubbles: true,
      cancelable: true,
      key: 'ArrowUp',
    })
    button.dispatchEvent(movementKey)
    expect(movementKey.defaultPrevented).toBe(true)

    textInput.focus()
    const typingKey = new KeyboardEvent('keydown', {
      bubbles: true,
      cancelable: true,
      key: 'w',
    })
    textInput.dispatchEvent(typingKey)
    expect(typingKey.defaultPrevented).toBe(false)

    cleanup()
    button.focus()
    const releasedKey = new KeyboardEvent('keydown', {
      bubbles: true,
      cancelable: true,
      key: 'ArrowDown',
    })
    button.dispatchEvent(releasedKey)
    expect(releasedKey.defaultPrevented).toBe(false)
  })

  it.each([
    ['Control', { ctrlKey: true }],
    ['Meta', { metaKey: true }],
    ['Alt', { altKey: true }],
  ])('preserves %s movement-key shortcuts', (_name, modifier) => {
    const button = document.createElement('button')
    document.body.append(button)
    button.focus()
    const cleanup = installMovementKeyGuard()(window)
    const shortcut = new KeyboardEvent('keydown', {
      bubbles: true,
      cancelable: true,
      key: 'a',
      ...modifier,
    })

    button.dispatchEvent(shortcut)

    expect(shortcut.defaultPrevented).toBe(false)
    cleanup()
  })

  it('keeps Shift+W as movement input', () => {
    const button = document.createElement('button')
    document.body.append(button)
    button.focus()
    const cleanup = installMovementKeyGuard()(window)
    const movementKey = new KeyboardEvent('keydown', {
      bubbles: true,
      cancelable: true,
      key: 'W',
      shiftKey: true,
    })

    button.dispatchEvent(movementKey)

    expect(movementKey.defaultPrevented).toBe(true)
    cleanup()
  })
})

describe('TownScene semantic player locations', () => {
  it('spawns at Backend location and emits only distinct location entries', async () => {
    const { TownScene } = await import('../../frontend/src/game/scenes/TownScene')
    const bridge = new TownGameBridge({
      profile: {
        version: 1,
        displayName: '洛恩',
        adventurerClass: 'ranger',
        introCompleted: true,
      },
      playerLocationId: 'tavern',
      npcs: [],
    })
    const received: string[] = []
    bridge.onPlayerLocationEntered((locationId) => received.push(locationId))
    const scene = new TownScene(bridge)

    const body = {
      setSize: vi.fn(),
      setOffset: vi.fn(),
    }
    body.setSize.mockReturnValue(body)
    body.setOffset.mockReturnValue(body)
    const player = {
      x: 0,
      y: 0,
      body,
      anims: { stop: vi.fn(), play: vi.fn() },
      setDepth: vi.fn(),
      setCollideWorldBounds: vi.fn(),
      setVelocity: vi.fn(),
      setPosition: vi.fn(),
      setFrame: vi.fn(),
      setFlipX: vi.fn(),
    }
    player.setDepth.mockReturnValue(player)
    player.setCollideWorldBounds.mockReturnValue(player)
    player.setVelocity.mockReturnValue(player)
    player.setPosition.mockImplementation((x: number, y: number) => {
      player.x = x
      player.y = y
      return player
    })
    player.setFrame.mockReturnValue(player)
    player.setFlipX.mockReturnValue(player)
    const sprite = vi.fn((x: number, y: number) => {
      player.x = x
      player.y = y
      return player
    })
    Reflect.set(scene, 'physics', {
      add: { sprite, collider: vi.fn() },
    })
    const anchors = Reflect.get(scene, 'anchors') as Map<
      string,
      { x: number, y: number }
    >
    anchors.set('player_spawn', { x: 768, y: 704 })
    anchors.set('location:tavern', { x: 416, y: 704 })
    anchors.set('location:park', { x: 768, y: 544 })
    anchors.set('location:castle', { x: 1152, y: 288 })

    const createPlayer = Reflect.get(scene, 'createPlayer') as (
      collision: unknown,
    ) => void
    createPlayer.call(scene, {})
    expect(sprite).toHaveBeenCalledWith(416, 704, 'adventurer-ranger', 1)
    expect(received).toEqual([])

    const releasedKeys = {
      up: { isDown: false },
      down: { isDown: false },
      left: { isDown: false },
      right: { isDown: false },
    }
    Reflect.set(scene, 'cursors', releasedKeys)
    Reflect.set(scene, 'wasd', releasedKeys)
    player.x = 768
    player.y = 544
    scene.update()
    expect(received).toEqual(['park'])

    scene.update()
    expect(received).toEqual(['park'])

    player.x = 900
    player.y = 700
    scene.update()
    player.x = 768
    player.y = 544
    scene.update()
    expect(received).toEqual(['park', 'park'])

    const teleportPlayer = Reflect.get(scene, 'teleportPlayer') as (
      locationId: string,
    ) => void
    teleportPlayer.call(scene, 'castle')
    expect(player.setPosition).toHaveBeenCalledWith(1152, 288)
    scene.update()
    expect(received).toEqual(['park', 'park'])
  })
})
