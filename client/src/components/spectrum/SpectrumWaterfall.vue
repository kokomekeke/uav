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

      <div class="view-toggles">
        <button
          @click="showSpectrum = !showSpectrum"
          :class="{ active: showSpectrum }"
        >
          📊 Spectrum
        </button>
        <button
          @click="showWaterfall = !showWaterfall"
          :class="{ active: showWaterfall }"
        >
          🌊 Waterfall
        </button>
      </div>
    </div>

    <!-- ✅ STACKED LAYOUT - egymás alatt! -->
    <div class="plots-container">
      <!-- Spectrum Canvas - felül -->
      <div v-show="showSpectrum" class="spectrum-wrapper">
        <canvas ref="spectrumCanvasRef" class="spectrum-canvas"></canvas>
      </div>

      <!-- Waterfall Canvas - alul -->
      <div v-show="showWaterfall" class="waterfall-wrapper">
        <canvas ref="waterfallCanvasRef" class="waterfall-canvas"></canvas>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { useSensorStore } from '@/stores/sensor'
import { SpectrumPlot } from '@/utils/spectrumPlot'
import { WaterfallPlot } from '@/utils/waterfall'

const sensorStore = useSensorStore()
const { sensors, selectedSensors } = storeToRefs(sensorStore)

const selectedUavId = ref<number | null>(null)
const spectrumCanvasRef = ref<HTMLCanvasElement | null>(null)
const waterfallCanvasRef = ref<HTMLCanvasElement | null>(null)

const showSpectrum = ref(true)
const showWaterfall = ref(true)

const dataPointsReceived = ref(0)
const isReceivingData = ref(false)
let lastDataTimestamp = 0

let spectrumPlot: SpectrumPlot | null = null
let waterfallPlot: WaterfallPlot | null = null

const availableSensors = computed(() => {
  return Object.values(sensors.value).filter(s => s.active)
})

const currentSensor = computed(() => {
  if (!selectedUavId.value) return null
  return sensors.value[selectedUavId.value] || null
})

// ✅ UGYANAZ mint előtte - dekódolás, normalizálás, processSpectrumData
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

  if (showSpectrum.value && spectrumPlot) {
    spectrumPlot.drawSpectrumLine(normalized)
  }

  if (showWaterfall.value && waterfallPlot) {
    waterfallPlot.drawWaterfallRow(normalized)
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
  if (spectrumCanvasRef.value) {
    spectrumPlot = new SpectrumPlot(spectrumCanvasRef.value)
  }

  if (waterfallCanvasRef.value) {
    waterfallPlot = new WaterfallPlot(waterfallCanvasRef.value)
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

.view-toggles {
  display: flex;
  gap: 8px;
}

.view-toggles button {
  padding: 6px 12px;
  background: #2a3142;
  border: 1px solid #3a4152;
  border-radius: 4px;
  color: #8b92a8;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.view-toggles button:hover {
  background: #3a4152;
  border-color: #0ea5e9;
}

.view-toggles button.active {
  background: #0ea5e9;
  border-color: #0ea5e9;
  color: #fff;
}

/* ✅ STACKED LAYOUT */
.plots-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.spectrum-wrapper {
  flex: 1;
  min-height: 0;
  border-bottom: 2px solid #2a3142;
}

.waterfall-wrapper {
  flex: 2;
  min-height: 0;
}

.spectrum-canvas,
.waterfall-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>