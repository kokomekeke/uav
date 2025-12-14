export class CombinedSpectrumWaterfallPlot {
  canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  width: number
  height: number
  private currentRow: number = 0

  private spectrumHeightRatio = 0.20
  private waterfallHeightRatio = 0.80

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

  clear() {
    const spectrumHeight = this.height * this.spectrumHeightRatio
    this.ctx.fillStyle = '#ffffff'
    this.ctx.fillRect(0, 0, this.width, spectrumHeight)

    this.ctx.fillStyle = '#1a1a1a'
    this.ctx.fillRect(0, spectrumHeight, this.width, this.height - spectrumHeight)

    this.currentRow = 0
  }

  private intensityToColor(intensity: number): [number, number, number] {
    const t = intensity / 255

    if (t < 0.33) {
      const ratio = t / 0.33
      return [
        Math.floor(ratio * 128),
        0,
        255
      ]
    } else if (t < 0.66) {
      const ratio = (t - 0.33) / 0.33
      return [
        Math.floor(128 + ratio * 127),
        Math.floor(ratio * 100),
        Math.floor(255 * (1 - ratio * 0.5))
      ]
    } else {
      const ratio = (t - 0.66) / 0.34
      return [
        255,
        Math.floor(100 + ratio * 155),
        Math.floor(127 * (1 - ratio))
      ]
    }
  }

  drawFrame(frequencyData: number[]) {
    const { ctx, width, height, padding } = this

    const spectrumHeight = height * this.spectrumHeightRatio
    const waterfallHeight = height * this.waterfallHeightRatio

    const plotWidth = width - padding.left - padding.right


    const spectrumPlotHeight = spectrumHeight - padding.top - 10

    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, spectrumHeight)

    ctx.strokeStyle = '#e0e0e0'
    ctx.lineWidth = 1

    for (let i = 0; i <= 6; i++) {
      const y = padding.top + (i / 6) * spectrumPlotHeight
      ctx.beginPath()
      ctx.moveTo(padding.left, y)
      ctx.lineTo(padding.left + plotWidth, y)
      ctx.stroke()
    }

    for (let i = 0; i <= 10; i++) {
      const x = padding.left + (i / 10) * plotWidth
      ctx.beginPath()
      ctx.moveTo(x, padding.top)
      ctx.lineTo(x, padding.top + spectrumPlotHeight)
      ctx.stroke()
    }

    ctx.strokeStyle = '#000000'
    ctx.lineWidth = 2
    ctx.strokeRect(padding.left, padding.top, plotWidth, spectrumPlotHeight)

    ctx.fillStyle = '#000000'
    ctx.font = '11px Arial'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'

    for (let i = 0; i <= 6; i++) {
      const value = -i * 20 // 0, -20, -40, -60, -80, -100, -120
      const y = padding.top + (i / 6) * spectrumPlotHeight
      ctx.fillText(value.toFixed(1), padding.left - 5, y)
    }

    ctx.beginPath()
    ctx.strokeStyle = '#0000ff'
    ctx.lineWidth = 1.5

    frequencyData.forEach((value, i) => {
      const x = padding.left + (i / frequencyData.length) * plotWidth
      const normalizedValue = value / 255
      const y = padding.top + spectrumPlotHeight * (1 - normalizedValue)

      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    })

    ctx.stroke()

    const waterfallTop = spectrumHeight + 5
    const waterfallPlotHeight = waterfallHeight - 15 - padding.bottom

    if (this.currentRow > 0) {
      const imageData = ctx.getImageData(
        padding.left,
        waterfallTop + 1,
        plotWidth,
        waterfallPlotHeight - 1
      )
      ctx.putImageData(imageData, padding.left, waterfallTop)
    }

    const newRowY = waterfallTop + waterfallPlotHeight - 1
    const pixelWidth = plotWidth / frequencyData.length

    frequencyData.forEach((value, i) => {
      const x = padding.left + i * pixelWidth
      const [r, g, b] = this.intensityToColor(value)

      ctx.fillStyle = `rgb(${r},${g},${b})`
      ctx.fillRect(x, newRowY, Math.ceil(pixelWidth), 1)
    })

    this.currentRow++

    ctx.fillStyle = '#ffffff'
    ctx.font = '11px Arial'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'

    for (let i = 0; i <= 5; i++) {
      const value = -i * 30 // 0, -30, -60, -90, -120, -150
      const y = waterfallTop + (i / 5) * waterfallPlotHeight
      ctx.fillText(value.toString(), padding.left - 5, y)
    }


    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#000000'
    ctx.font = '11px Arial'

    const numLabels = 4
    for (let i = 0; i <= numLabels; i++) {
      const x = padding.left + (i / numLabels) * plotWidth
      const freqValue = (i / numLabels) * 3000 // 0 - 3000 MHz példa
      ctx.fillText(`${freqValue.toFixed(0)}M`, x, height - padding.bottom + 5)
    }

    ctx.font = 'bold 12px Arial'
    ctx.fillText('Frequency (MHz)', width / 2, height - 15)

    ctx.save()
    ctx.translate(15, spectrumHeight / 2)
    ctx.rotate(-Math.PI / 2)
    ctx.textAlign = 'center'
    ctx.font = 'bold 11px Arial'
    ctx.fillStyle = '#000000'
    ctx.fillText('dB', 0, 0)
    ctx.restore()

    ctx.save()
    ctx.translate(15, spectrumHeight + waterfallPlotHeight / 2)
    ctx.rotate(-Math.PI / 2)
    ctx.textAlign = 'center'
    ctx.font = 'bold 11px Arial'
    ctx.fillStyle = '#ffffff'
    ctx.fillText('Packets', 0, 0)
    ctx.restore()
  }
}