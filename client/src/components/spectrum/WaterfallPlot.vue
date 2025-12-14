<template>
  <div class="waterfall-wrapper">
    <div class="controls">
      <button @click="toggleConnection">
        {{ isConnected ? 'Disconnect' : 'Connect' }}
      </button>
      <span :class="{ connected: isConnected, disconnected: !isConnected }">
        {{ isConnected ? '🟢 Connected' : '🔴 Disconnected' }}
      </span>
    </div>
    <canvas ref="canvasRef" class="waterfall-canvas"></canvas>
  </div>
</template>

<script lang="ts">
import {
  defineComponent,
  onMounted,
  onBeforeUnmount,
  ref
} from 'vue'
import { WaterfallPlot } from '@/utils/waterfall'

export default defineComponent({
  name: 'WaterfallPlot',
  props: {
    uavId: {
      type: Number,
      default: 17
    }
  },
  setup (props) {
    const canvasRef = ref<HTMLCanvasElement | null>(null)
    const isConnected = ref(false)

    let plot: WaterfallPlot | null = null
    let eventSource: EventSource | null = null
    let waterfallYOffset = 0

    const decodeFloat16Array = (base64Data: string): number[] => {
      try {
        let paddedBase64 = base64Data
        while (paddedBase64.length % 4 !== 0) {
          paddedBase64 += '='
        }

        const binaryString = atob(paddedBase64)
        const bytes = new Uint8Array(binaryString.length)
        for (let i = 0; i < binaryString.length; i++) {
          bytes[i] = binaryString.charCodeAt(i)
        }

        console.log('📦 Decoded bytes:', {
          length: bytes.length,
          isEven: bytes.length % 2 === 0,
          first8bytes: Array.from(bytes.slice(0, 8))
        })

        if (bytes.length % 2 !== 0) {
          console.error('❌ Invalid FLOAT16 data: odd number of bytes', {
            totalBytes: bytes.length,
            missingBytes: 1
          })
          const evenBytes = bytes.slice(0, bytes.length - 1)
          console.warn('⚠️ Truncated to even length:', evenBytes.length)
          return decodeFloat16FromBytes(evenBytes)
        }

        return decodeFloat16FromBytes(bytes)
      } catch (err) {
        console.error('❌ Error decoding FLOAT16:', err)
        return []
      }
    }

    const decodeFloat16FromBytes = (bytes: Uint8Array): number[] => {
      const dataView = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
      const floats: number[] = []

      for (let i = 0; i < bytes.length; i += 2) {
        try {
          const half = dataView.getUint16(i, true)
          const float = float16ToFloat32(half)

          if (!isNaN(float) && isFinite(float)) {
            floats.push(float)
          } else {
            floats.push(0)
          }
        } catch (err) {
          console.error(`❌ Error at byte offset ${i}:`, err)
          floats.push(0)
        }
      }

      return floats
    }

    const float16ToFloat32 = (half: number): number => {
      const sign = (half & 0x8000) >> 15
      const exponent = (half & 0x7C00) >> 10
      const fraction = half & 0x03FF

      if (exponent === 0) {
        return (sign ? -1 : 1) * Math.pow(2, -14) * (fraction / 1024)
      } else if (exponent === 0x1F) {
        return fraction ? NaN : (sign ? -Infinity : Infinity)
      }

      return (sign ? -1 : 1) * Math.pow(2, exponent - 15) * (1 + fraction / 1024)
    }

    const normalizeSpectrum = (data: number[]): number[] => {
      const min = Math.min(...data)
      const max = Math.max(...data)
      const range = max - min

      if (range === 0) return data.map(() => 128)

      return data.map(value =>
        Math.floor(((value - min) / range) * 255)
      )
    }

    const connectToStream = () => {
      if (eventSource) return

      const url = 'http://localhost:5000/v1/stream/comint_detection'
      eventSource = new EventSource(url, { withCredentials: true })

      eventSource.onopen = () => {
        console.log('✅ SSE Connected')
        isConnected.value = true
      }

      eventSource.onmessage = (event) => {
        try {
          const batch = JSON.parse(event.data)

          const measurements = Array.isArray(batch) ? batch : [batch]

          measurements.forEach((item: any) => {
            if (item.id === props.uavId && item.Measurement) {
              const measurement = item.Measurement

              if (measurement.data && measurement.data.dataType === 'FLOAT16') {
                const spectrumData = decodeFloat16Array(measurement.data.data)

                const normalized = normalizeSpectrum(spectrumData)

                if (plot) {
                  plot.drawSpectrumLine(normalized)

                  plot.drawWaterfallRow(normalized, waterfallYOffset)

                  waterfallYOffset = (waterfallYOffset + 1) % (plot.height / 2)
                }
              }
            }
          })
        } catch (err) {
          console.error('Error parsing SSE data:', err)
        }
      }

      eventSource.onerror = (err) => {
        console.error('❌ SSE Error:', err)
        isConnected.value = false
        disconnect()
      }
    }

    const disconnect = () => {
      if (eventSource) {
        eventSource.close()
        eventSource = null
        isConnected.value = false
      }
    }

    const toggleConnection = () => {
      if (isConnected.value) {
        disconnect()
      } else {
        connectToStream()
      }
    }

    onMounted(() => {
      if (canvasRef.value) {
        plot = new WaterfallPlot(canvasRef.value)
        connectToStream()
      }
    })

    onBeforeUnmount(() => {
      disconnect()
    })

    return {
      canvasRef,
      isConnected,
      toggleConnection
    }
  }
})
</script>

<style scoped>
.waterfall-wrapper {
  width: 100%;
  height: 400px;
  display: flex;
  flex-direction: column;
}
.controls {
  padding: 10px;
  display: flex;
  gap: 10px;
  align-items: center;
  background: #222;
}
.connected {
  color: #0f0;
}
.disconnected {
  color: #f00;
}
.waterfall-canvas {
  flex: 1;
  width: 100%;
  background: #000;
}
</style>
