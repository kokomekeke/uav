// utils/spectrumPlot.ts
export class SpectrumPlot {
  canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  width: number
  height: number

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
  }

  drawSpectrumLine(frequencyData: number[]) {
    const { ctx, width, height } = this

    // Clear
    this.clear()

    // Draw grid
    ctx.strokeStyle = '#1a1f2e'
    ctx.lineWidth = 1

    // Horizontal grid lines
    for (let i = 0; i <= 8; i++) {
      const y = (i / 8) * height
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(width, y)
      ctx.stroke()
    }

    // Vertical grid lines
    for (let i = 0; i <= 10; i++) {
      const x = (i / 10) * width
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, height)
      ctx.stroke()
    }

    // Draw spectrum line
    ctx.beginPath()
    ctx.strokeStyle = '#0ea5e9'
    ctx.lineWidth = 2
    ctx.shadowBlur = 10
    ctx.shadowColor = '#0ea5e9'

    frequencyData.forEach((value, i) => {
      const x = (i / frequencyData.length) * width
      const y = height - (value / 255) * height

      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    })

    ctx.stroke()
    ctx.shadowBlur = 0

    // Fill area under curve
    ctx.lineTo(width, height)
    ctx.lineTo(0, height)
    ctx.closePath()

    const gradient = ctx.createLinearGradient(0, 0, 0, height)
    gradient.addColorStop(0, 'rgba(14, 165, 233, 0.3)')
    gradient.addColorStop(1, 'rgba(14, 165, 233, 0.0)')
    ctx.fillStyle = gradient
    ctx.fill()
  }
}