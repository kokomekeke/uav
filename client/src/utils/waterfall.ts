export class WaterfallPlot {
  canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  width: number
  height: number
  private currentRow: number = 0

  private padding = {
    top: 10,
    right: 20,
    bottom: 40,
    left: 60
  }

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

  clear(color = '#1a1a1a') {
    this.ctx.fillStyle = color
    this.ctx.fillRect(0, 0, this.width, this.height)
    this.currentRow = 0
  }

  private intensityToColor(intensity: number): [number, number, number] {
    const t = intensity / 255

    if (t < 0.33) {
      const ratio = t / 0.33
      return [
        Math.floor(ratio * 128), // R: 0 -> 128
        0,
        255 // B: 255
      ]
    } else if (t < 0.66) {
      const ratio = (t - 0.33) / 0.33
      return [
        Math.floor(128 + ratio * 127), // R: 128 -> 255
        Math.floor(ratio * 100), // G: 0 -> 100
        Math.floor(255 * (1 - ratio * 0.5)) // B: 255 -> 127
      ]
    } else {
      const ratio = (t - 0.66) / 0.34
      return [
        255, // R: 255
        Math.floor(100 + ratio * 155), // G: 100 -> 255
        Math.floor(127 * (1 - ratio)) // B: 127 -> 0
      ]
    }
  }

  drawWaterfallRow(frequencyData: number[]) {
    const { ctx, width, height, padding } = this

    const plotWidth = width - padding.left - padding.right
    const plotHeight = height - padding.top - padding.bottom

    if (this.currentRow > 0) {
      const imageData = ctx.getImageData(
        padding.left,
        padding.top + 1,
        plotWidth,
        plotHeight - 1
      )
      ctx.putImageData(imageData, padding.left, padding.top)
    }

    const newRowY = padding.top + plotHeight - 1
    const pixelWidth = plotWidth / frequencyData.length

    frequencyData.forEach((value, i) => {
      const x = padding.left + i * pixelWidth
      const [r, g, b] = this.intensityToColor(value)

      ctx.fillStyle = `rgb(${r},${g},${b})`
      ctx.fillRect(x, newRowY, Math.ceil(pixelWidth), 1)
    })

    this.currentRow++

    this.drawAxes(frequencyData.length)
  }

  private drawAxes(dataLength: number) {
    const { ctx, width, height, padding } = this

    const plotWidth = width - padding.left - padding.right
    const plotHeight = height - padding.top - padding.bottom

    ctx.fillStyle = '#ffffff'
    ctx.font = '11px Arial'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'

    for (let i = 0; i <= 5; i++) {
      const value = -i * 30 // 0, -30, -60, -90, -120, -150
      const y = padding.top + (i / 5) * plotHeight
      ctx.fillText(value.toString(), padding.left - 5, y)
    }

    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#ffffff'

    const numLabels = 4
    for (let i = 0; i <= numLabels; i++) {
      const x = padding.left + (i / numLabels) * plotWidth
      const freqIndex = Math.floor((i / numLabels) * dataLength)
      ctx.fillText(`${freqIndex}`, x, padding.top + plotHeight + 5)
    }

    ctx.save()
    ctx.translate(10, height / 2)
    ctx.rotate(-Math.PI / 2)
    ctx.textAlign = 'center'
    ctx.font = 'bold 12px Arial'
    ctx.fillStyle = '#ffffff'
    ctx.fillText('Packets', 0, 0)
    ctx.restore()

    ctx.font = 'bold 12px Arial'
    ctx.textAlign = 'center'
    ctx.fillStyle = '#ffffff'
    ctx.fillText('Frequency (bins)', width / 2, height - 5)
  }
}