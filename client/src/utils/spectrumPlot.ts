// utils/spectrumPlot.ts
export class SpectrumPlot {
  canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  width: number
  height: number

  // ✅ Padding a tengelyeknek
  private padding = {
    top: 20,
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

  clear(color = '#ffffff') { // ✅ Fehér háttér
    this.ctx.fillStyle = color
    this.ctx.fillRect(0, 0, this.width, this.height)
  }

  drawSpectrumLine(frequencyData: number[]) {
    const { ctx, width, height, padding } = this

    // ✅ Clear - FEHÉR háttér
    this.clear('#ffffff')

    // ✅ Plot area méretei
    const plotWidth = width - padding.left - padding.right
    const plotHeight = height - padding.top - padding.bottom

    // ✅ Fekete keret a plot area körül
    ctx.strokeStyle = '#000000'
    ctx.lineWidth = 2
    ctx.strokeRect(padding.left, padding.top, plotWidth, plotHeight)

    // ✅ Grid vonalak (VILÁGOSSZÜRKE)
    ctx.strokeStyle = '#cccccc'
    ctx.lineWidth = 1

    // Horizontal grid lines (8 darab, Y értékek: 0, -20, -40, -60, -80, -100, -120)
    for (let i = 0; i <= 6; i++) {
      const y = padding.top + (i / 6) * plotHeight
      ctx.beginPath()
      ctx.moveTo(padding.left, y)
      ctx.lineTo(padding.left + plotWidth, y)
      ctx.stroke()
    }

    // Vertical grid lines
    for (let i = 0; i <= 10; i++) {
      const x = padding.left + (i / 10) * plotWidth
      ctx.beginPath()
      ctx.moveTo(x, padding.top)
      ctx.lineTo(x, padding.top + plotHeight)
      ctx.stroke()
    }

    // ✅ Y tengely értékek (0 to -120 dB)
    ctx.fillStyle = '#000000'
    ctx.font = '12px Arial'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'

    for (let i = 0; i <= 6; i++) {
      const value = -i * 20 // 0, -20, -40, -60, -80, -100, -120
      const y = padding.top + (i / 6) * plotHeight
      ctx.fillText(value.toFixed(1), padding.left - 10, y)
    }

    // ✅ X tengely címkék (frequency bins or time)
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'

    const numLabels = 5
    for (let i = 0; i <= numLabels; i++) {
      const x = padding.left + (i / numLabels) * plotWidth
      const freqIndex = Math.floor((i / numLabels) * frequencyData.length)
      ctx.fillText(`${freqIndex}`, x, padding.top + plotHeight + 10)
    }

    // ✅ Y tengely label
    ctx.save()
    ctx.translate(15, height / 2)
    ctx.rotate(-Math.PI / 2)
    ctx.textAlign = 'center'
    ctx.font = 'bold 14px Arial'
    ctx.fillText('dB', 0, 0)
    ctx.restore()

    // ✅ X tengely label
    ctx.font = 'bold 14px Arial'
    ctx.textAlign = 'center'
    ctx.fillText('Frequency (bins)', width / 2, height - 5)

    // ✅ SPEKTRUM VONAL - KÉK
    ctx.beginPath()
    ctx.strokeStyle = '#0000ff' // Kék
    ctx.lineWidth = 2

    frequencyData.forEach((value, i) => {
      const x = padding.left + (i / frequencyData.length) * plotWidth
      // ✅ Invertált Y: 0 dB = top, -120 dB = bottom
      const normalizedValue = value / 255 // 0-1
      const y = padding.top + plotHeight - (normalizedValue * plotHeight)

      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    })

    ctx.stroke()
  }
}