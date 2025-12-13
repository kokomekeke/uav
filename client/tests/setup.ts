import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// ----------------------------------------------------------------------------
// 🧠 URL API – NEM felülírjuk, csak kiegészítjük
// ----------------------------------------------------------------------------

if (typeof URL !== 'undefined') {
  if (!URL.createObjectURL) {
    URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  } else {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url')
  }

  if (!URL.revokeObjectURL) {
    URL.revokeObjectURL = vi.fn()
  } else {
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  }
}

// ----------------------------------------------------------------------------
// 🎨 Canvas mock (SpectrumWaterfall-hoz)
// ----------------------------------------------------------------------------

HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
  fillRect: vi.fn(),
  clearRect: vi.fn(),
  getImageData: vi.fn(() => ({ data: [] })),
  putImageData: vi.fn(),
  createImageData: vi.fn(),
  setTransform: vi.fn(),
  drawImage: vi.fn(),
  save: vi.fn(),
  fillText: vi.fn(),
  restore: vi.fn(),
  beginPath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  closePath: vi.fn(),
  stroke: vi.fn(),
  translate: vi.fn(),
  scale: vi.fn(),
  rotate: vi.fn(),
  arc: vi.fn(),
  fill: vi.fn(),
  measureText: vi.fn(() => ({ width: 0 })),
  transform: vi.fn(),
  rect: vi.fn(),
  clip: vi.fn()
})) as any

// ----------------------------------------------------------------------------
// 🌍 Global Vue test utils
// ----------------------------------------------------------------------------

config.global.stubs = {
  teleport: true
}
