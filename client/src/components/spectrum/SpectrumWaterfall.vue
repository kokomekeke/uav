<template>
  <div class="spectrum-waterfall-container">
    <div class="controls">
      <div class="sensor-selector">
        <label>Select UAV:</label>
        <select v-model="selectedUavId" class="select-dropdown">
          <option :value="null" disabled>-- Choose UAV --</option>
          <option
            v-for="sensor in availableSensors"
            :key="sensor.uav_id"
            :value="sensor.uav_id"
          >
            UAV #{{ sensor.uav_id }} - {{ sensor.uav_label }}
          </option>
        </select>
      </div>

      <div class="status">
        <span :class="{ connected: isReceivingData, disconnected: !isReceivingData }">
          {{ isReceivingData ? '🟢 Receiving Data' : '🔴 No Data' }}
        </span>
        <span class="data-counter">{{ dataPointsReceived }} samples</span>
      </div>
    </div>

    <div class="plot-container">
      <canvas ref="combinedCanvasRef" class="combined-canvas"></canvas>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { useSensorStore } from '@/stores/sensor'
import { CombinedSpectrumWaterfallPlot } from '@/utils/combinedPlot'

const sensorStore = useSensorStore()
const { sensors } = storeToRefs(sensorStore)

const selectedUavId = ref<number | null>(null)
const combinedCanvasRef = ref<HTMLCanvasElement | null>(null)

const dataPointsReceived = ref(0)
const isReceivingData = ref(false)
let lastDataTimestamp = 0

let combinedPlot: CombinedSpectrumWaterfallPlot | null = null

const availableSensors = computed(() => {
  return Object.values(sensors.value).filter(s => s.active)
})

const currentSensor = computed(() => {
  if (!selectedUavId.value) return null
  return sensors.value[selectedUavId.value] || null
})

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

    if (bytes.length % 2 !== 0) {
      const evenBytes = bytes.slice(0, bytes.length - 1)
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
  if (data.length === 0) return []

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min

  if (range === 0) return data.map(() => 128)

  return data.map(value =>
    Math.floor(((value - min) / range) * 255)
  )
}

const processSpectrumData = (item: any, itemIndex: number) => {
  const measurement = item?.Measurement

  if (!measurement) return

  if (!measurement.data || !Array.isArray(measurement.data) || measurement.data.length === 0) {
    return
  }

  const dataItem = measurement.data[0]

  if (!dataItem || dataItem.dataType !== 'FLOAT16' || !dataItem.data) {
    return
  }

  const spectrumData = decodeFloat16Array(dataItem.data)
  if (spectrumData.length === 0) return

  const normalized = normalizeSpectrum(spectrumData)

  // ✅ Rajzolás a combined plotra
  if (combinedPlot) {
    combinedPlot.drawFrame(normalized)
  }

  dataPointsReceived.value++
  lastDataTimestamp = Date.now()
  isReceivingData.value = true
}

watch(availableSensors, (sensors) => {
  if (sensors.length > 0 && !selectedUavId.value) {
    selectedUavId.value = sensors[0].uav_id
  }
}, { immediate: true })

watch(
  () => currentSensor.value?.detections,
  (newDetections, oldDetections) => {
    if (!newDetections || newDetections.length === 0) return

    const oldLength = oldDetections?.length || 0
    const newLength = newDetections.length

    if (newLength > oldLength) {
      const newItems = newDetections.slice(oldLength)
      newItems.forEach((item, idx) => {
        processSpectrumData(item, oldLength + idx)
      })
    }
  },
  { deep: false }
)

let dataTimeoutInterval: number | null = null

const checkDataTimeout = () => {
  const now = Date.now()
  if (now - lastDataTimestamp > 2000) {
    if (isReceivingData.value) {
      isReceivingData.value = false
    }
  }
}

onMounted(() => {
  if (combinedCanvasRef.value) {
    combinedPlot = new CombinedSpectrumWaterfallPlot(combinedCanvasRef.value)
  }

  dataTimeoutInterval = window.setInterval(checkDataTimeout, 1000)

  if (availableSensors.value.length > 0) {
    selectedUavId.value = availableSensors.value[0].uav_id
  }
})

onBeforeUnmount(() => {
  if (dataTimeoutInterval) {
    clearInterval(dataTimeoutInterval)
  }
})
</script>

<style scoped>
.spectrum-waterfall-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: #0a0e1a;
  border-radius: 8px;
  overflow: hidden;
}

.controls {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: #1a1f2e;
  border-bottom: 1px solid #2a3142;
  flex-shrink: 0;
}

.sensor-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sensor-selector label {
  font-size: 14px;
  color: #8b92a8;
}

.select-dropdown {
  padding: 6px 12px;
  background: #0a0e1a;
  border: 1px solid #2a3142;
  border-radius: 4px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

.select-dropdown:hover {
  border-color: #0ea5e9;
}

.status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.connected {
  color: #10b981;
  font-weight: 500;
}

.disconnected {
  color: #ef4444;
  font-weight: 500;
}

.data-counter {
  color: #8b92a8;
  font-size: 13px;
}

.plot-container {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.combined-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>