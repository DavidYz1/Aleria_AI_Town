export interface DirectionInput {
  up: boolean
  down: boolean
  left: boolean
  right: boolean
}

export interface Velocity {
  x: number
  y: number
}

const MOVEMENT_KEYS = new Set([
  'ArrowUp',
  'ArrowDown',
  'ArrowLeft',
  'ArrowRight',
  'w',
  'a',
  's',
  'd',
])

export function installCanvasFocus(canvas: HTMLCanvasElement): () => void {
  const focusCanvas = (): void => canvas.focus({ preventScroll: true })
  canvas.tabIndex = 0
  canvas.addEventListener('pointerdown', focusCanvas, true)
  return () => canvas.removeEventListener('pointerdown', focusCanvas, true)
}

export function isTextEntryElement(element: Element | null): boolean {
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    return true
  }
  let editableRoot = element?.closest('[contenteditable]') ?? null
  while (editableRoot !== null) {
    const value = editableRoot.getAttribute('contenteditable')?.trim().toLowerCase()
    if (value === 'false') return false
    if (value === '' || value === 'true' || value === 'plaintext-only') return true
    editableRoot = editableRoot.parentElement?.closest('[contenteditable]') ?? null
  }
  return false
}

export function installMovementKeyGuard(target: Window): () => void {
  const preventMovementKeyDefault = (event: KeyboardEvent): void => {
    if (event.ctrlKey || event.metaKey || event.altKey) return
    if (isTextEntryElement(target.document.activeElement)) return
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key
    if (MOVEMENT_KEYS.has(key)) event.preventDefault()
  }
  target.addEventListener('keydown', preventMovementKeyDefault)
  return () => target.removeEventListener('keydown', preventMovementKeyDefault)
}

export function resolvePlayerVelocity(
  input: DirectionInput,
  speed: number,
  activeElement: Element | null,
): Velocity {
  if (isTextEntryElement(activeElement)) return { x: 0, y: 0 }
  return resolveVelocity(input, speed)
}

export function resolveVelocity(
  input: DirectionInput,
  speed: number,
): Velocity {
  const x = Number(input.right) - Number(input.left)
  const y = Number(input.down) - Number(input.up)
  const length = Math.hypot(x, y)
  if (length === 0) return { x: 0, y: 0 }

  const scale = speed / length
  return { x: x * scale, y: y * scale }
}
