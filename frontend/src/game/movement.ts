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
