// @vitest-environment node

import { inflateSync } from 'node:zlib'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'


function readRgbaPixels(path: string): Uint8Array {
  const png = readFileSync(path)
  expect(png.subarray(1, 4).toString()).toBe('PNG')

  const compressed: Buffer[] = []
  let width = 0
  let height = 0
  let offset = 8
  while (offset < png.length) {
    const length = png.readUInt32BE(offset)
    const type = png.subarray(offset + 4, offset + 8).toString()
    const data = png.subarray(offset + 8, offset + 8 + length)
    if (type === 'IHDR') {
      width = data.readUInt32BE(0)
      height = data.readUInt32BE(4)
      expect(data[8]).toBe(8)
      expect(data[9]).toBe(6)
    } else if (type === 'IDAT') {
      compressed.push(data)
    }
    offset += 12 + length
  }

  const encoded = inflateSync(Buffer.concat(compressed))
  const stride = width * 4
  const pixels = new Uint8Array(stride * height)
  let sourceOffset = 0
  for (let y = 0; y < height; y += 1) {
    const filter = encoded[sourceOffset]
    sourceOffset += 1
    for (let x = 0; x < stride; x += 1) {
      const raw = encoded[sourceOffset + x]
      const left = x >= 4 ? pixels[y * stride + x - 4] : 0
      const above = y > 0 ? pixels[(y - 1) * stride + x] : 0
      const upperLeft = y > 0 && x >= 4 ? pixels[(y - 1) * stride + x - 4] : 0
      const value = filter === 0
        ? raw
        : filter === 1
          ? raw + left
          : filter === 2
            ? raw + above
            : filter === 3
              ? raw + Math.floor((left + above) / 2)
              : raw + paeth(left, above, upperLeft)
      pixels[y * stride + x] = value & 0xff
    }
    sourceOffset += stride
  }
  return pixels
}

function paeth(left: number, above: number, upperLeft: number): number {
  const prediction = left + above - upperLeft
  const leftDistance = Math.abs(prediction - left)
  const aboveDistance = Math.abs(prediction - above)
  const upperLeftDistance = Math.abs(prediction - upperLeft)
  if (leftDistance <= aboveDistance && leftDistance <= upperLeftDistance) return left
  return aboveDistance <= upperLeftDistance ? above : upperLeft
}

describe('phase 2 sprite assets', () => {
  it.each([
    'adventurer-mage.png',
    'adventurer-ranger.png',
    'adventurer-cleric.png',
    'npcs.png',
  ])('%s uses transparent pixels instead of the source magenta color key', (file) => {
    const pixels = readRgbaPixels(resolve(
      import.meta.dirname,
      '../../frontend/public/assets/phase2/sprites',
      file,
    ))

    let transparentPixels = 0
    let opaqueMagentaPixels = 0
    for (let index = 0; index < pixels.length; index += 4) {
      const [red, green, blue, alpha] = pixels.subarray(index, index + 4)
      if (alpha === 0) transparentPixels += 1
      if (red === 255 && green === 0 && blue === 255 && alpha === 255) {
        opaqueMagentaPixels += 1
      }
    }

    expect(transparentPixels).toBeGreaterThan(0)
    expect(opaqueMagentaPixels).toBe(0)
  })
})
