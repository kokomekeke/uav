<!-- components/spectrum/SpectrumWaterfall.vue -->
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

    <div class="canvas-container">
      <!-- Spectrum Canvas -->
      <canvas
        v-show="showSpectrum"
        ref="spectrumCanvasRef"
        class="spectrum-canvas"
      ></canvas>

      <!-- Waterfall Canvas -->
      <canvas
        v-show="showWaterfall"
        ref="waterfallCanvasRef"
        class="waterfall-canvas"
      ></canvas>
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

const decodeFloat16Array = (base64Data: string): number[] => {
  try {
    // ✅ 1. Base64 padding biztosítása (ha hiányzik)
    let paddedBase64 = base64Data
    while (paddedBase64.length % 4 !== 0) {
      paddedBase64 += '='
    }

    // ✅ 2. Base64 dekódolás
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

    // ✅ 3. KRITIKUS: Ellenőrizzük, hogy páros számú byte-unk van
    if (bytes.length % 2 !== 0) {
      console.error('❌ Invalid FLOAT16 data: odd number of bytes', {
        totalBytes: bytes.length,
        missingBytes: 1
      })
      // Utolsó byte levágása (hiányos adat)
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

// ✅ Külön funkció a FLOAT16 dekódolásra
const decodeFloat16FromBytes = (bytes: Uint8Array): number[] => {
  const dataView = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const floats: number[] = []

  for (let i = 0; i < bytes.length; i += 2) {
    try {
      const half = dataView.getUint16(i, true) // little-endian
      const float = float16ToFloat32(half)

      // ✅ NaN/Infinity szűrés (opcionális)
      if (!isNaN(float) && isFinite(float)) {
        floats.push(float)
      } else {
        floats.push(0) // vagy skip
      }
    } catch (err) {
      console.error(`❌ Error at byte offset ${i}:`, err)
      floats.push(0) // fallback érték
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

// 🔥 FŐ JAVÍTÁS: measurement.data egy ARRAY!
const processSpectrumData = (item: any, itemIndex: number) => {
  const measurement = item?.Measurement

  if (!measurement) {
    console.warn(`⚠️ [${itemIndex}] No Measurement found`)
    return
  }

  // ✅ KRITIKUS: measurement.data egy ARRAY!
  if (!measurement.data || !Array.isArray(measurement.data) || measurement.data.length === 0) {
    console.warn(`⚠️ [${itemIndex}] No data array found`)
    return
  }

  // ✅ Első elem az array-ből
  const dataItem = measurement.data[0]

  if (!dataItem) {
    console.warn(`⚠️ [${itemIndex}] No data item at index 0`)
    return
  }

  // ✅ Most már dataItem.dataType és dataItem.data helyesek
  if (dataItem.dataType !== 'FLOAT16') {
    console.warn(`⚠️ [${itemIndex}] Not FLOAT16 data:`, dataItem.dataType)
    return
  }

  if (!dataItem.data) {
    console.warn(`⚠️ [${itemIndex}] No data string found`)
    return
  }

  console.log(`📊 [${itemIndex}] Processing spectrum:`, {
    uavId: currentSensor.value?.uav_id,
    dataStringLength: dataItem.data.length,
    centerFrequency: dataItem.centerFrequency
  })

  // Dekódolás
  const spectrumData = decodeFloat16Array(dataItem.data)
  if (spectrumData.length === 0) {
    console.warn(`⚠️ [${itemIndex}] Empty spectrum after decode`)
    return
  }

  console.log(`✅ [${itemIndex}] Spectrum decoded:`, {
    samples: spectrumData.length,
    min: Math.min(...spectrumData).toFixed(2),
    max: Math.max(...spectrumData).toFixed(2)
  })

  // Normalizálás
  const normalized = normalizeSpectrum(spectrumData)

  // Rajzolás
  if (showSpectrum.value && spectrumPlot) {
    spectrumPlot.drawSpectrumLine(normalized)
  }

  if (showWaterfall.value && waterfallPlot) {
    waterfallPlot.drawWaterfallRow(normalized)
  }

  // Stats
  dataPointsReceived.value++
  lastDataTimestamp = Date.now()
  isReceivingData.value = true

  console.log(`✅ [${itemIndex}] Complete! Total: ${dataPointsReceived.value}`)
}

// Auto-select első sensor
watch(availableSensors, (sensors) => {
  if (sensors.length > 0 && !selectedUavId.value) {
    selectedUavId.value = sensors[0].uav_id
    console.log('🎯 Auto-selected UAV:', selectedUavId.value)
  }
}, { immediate: true })

// Detections változás figyelése
watch(
  () => currentSensor.value?.detections,
  (newDetections, oldDetections) => {
    if (!newDetections || newDetections.length === 0) return

    const oldLength = oldDetections?.length || 0
    const newLength = newDetections.length

    if (newLength > oldLength) {
      const newItems = newDetections.slice(oldLength)
      console.log(`🔄 Processing ${newItems.length} new items (${oldLength} -> ${newLength})`)

      newItems.forEach((item, idx) => {
        const globalIdx = oldLength + idx
        processSpectrumData(item, globalIdx)
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
      console.log('⏱️ Data timeout')
      isReceivingData.value = false
    }
  }
}

onMounted(() => {
  console.log('🚀 SpectrumWaterfall mounted')

  if (spectrumCanvasRef.value) {
    spectrumPlot = new SpectrumPlot(spectrumCanvasRef.value)
    console.log('✅ Spectrum plot initialized')
  }

  if (waterfallCanvasRef.value) {
    waterfallPlot = new WaterfallPlot(waterfallCanvasRef.value)
    console.log('✅ Waterfall plot initialized')
  }

  dataTimeoutInterval = window.setInterval(checkDataTimeout, 1000)

  if (availableSensors.value.length > 0) {
    selectedUavId.value = availableSensors.value[0].uav_id
    console.log('🎯 Initial UAV selected:', selectedUavId.value)
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

.canvas-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.spectrum-canvas,
.waterfall-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.spectrum-canvas {
  z-index: 2;
}

.waterfall-canvas {
  z-index: 1;
}
</style>
