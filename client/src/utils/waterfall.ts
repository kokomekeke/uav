// utils/waterfallPlot.ts
export class WaterfallPlot {
  canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  width: number
  height: number
  private currentRow: number = 0

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas context not available')
    this.ctx = ctx
    this.resize()
    this.clear()
  }

  resize() {
    this.width = this.canvas.width = this.canvas.clientWidth
    this.height = this.canvas.height = this.canvas.clientHeight
  }

  clear(color = '#0a0e1a') {
    this.ctx.fillStyle = color
    this.ctx.fillRect(0, 0, this.width, this.height)
    this.currentRow = 0
  }

  // Hőtérkép színezés (viridis-szerű)
  private intensityToColor(intensity: number): [number, number, number] {
    const t = intensity / 255

    if (t < 0.2) {
      // Sötétkék -> Kék
      const ratio = t / 0.2
      return [0, Math.floor(ratio * 100), Math.floor(100 + ratio * 155)]
    } else if (t < 0.4) {
      // Kék -> Cián
      const ratio = (t - 0.2) / 0.2
      return [0, Math.floor(100 + ratio * 155), 255]
    } else if (t < 0.6) {
      // Cián -> Zöld
      const ratio = (t - 0.4) / 0.2
      return [0, 255, Math.floor(255 * (1 - ratio))]
    } else if (t < 0.8) {
      // Zöld -> Sárga
      const ratio = (t - 0.6) / 0.2
      return [Math.floor(ratio * 255), 255, 0]
    } else {
      // Sárga -> Piros
      const ratio = (t - 0.8) / 0.2
      return [255, Math.floor(255 * (1 - ratio)), 0]
    }
  }

  drawWaterfallRow(frequencyData: number[]) {
    const { ctx, width, height } = this

    // Scroll fel (egész canvas másolása 1 pixellel feljebb)
    if (this.currentRow > 0) {
      const imageData = ctx.getImageData(0, 1, width, height - 1)
      ctx.putImageData(imageData, 0, 0)
    }

    // Új sor rajzolása az aljára
    const newRowY = height - 1
    const pixelWidth = width / frequencyData.length

    frequencyData.forEach((value, i) => {
      const x = i * pixelWidth
      const [r, g, b] = this.intensityToColor(value)

      ctx.fillStyle = `rgb(${r},${g},${b})`
      ctx.fillRect(x, newRowY, Math.ceil(pixelWidth), 1)
    })

    this.currentRow++
  }
}