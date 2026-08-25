import { afterEach, describe, expect, it } from 'vitest'

import * as movement from '../../frontend/src/game/movement'


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
