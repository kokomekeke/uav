<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import { LMap, LTileLayer } from '@vue-leaflet/vue-leaflet'
import L from 'leaflet'
import { useSensorStore } from '@/stores/sensor'
import { storeToRefs } from 'pinia'
import 'leaflet/dist/leaflet.css'
import 'leaflet.heat'

interface Props {
  showControls?: boolean
  compactMode?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  showControls: true,
  compactMode: false
})

const sensorStore = useSensorStore()
const { sensors, selectedSensors, hasSelectedSensors, realtimeConfig } = storeToRefs(sensorStore)

const zoom = ref(12)
const center = ref<[number, number] | null>(null)
let centerInitialized = false
const mapRef = ref<any>(null)
const leafletMap = shallowRef<L.Map | null>(null)
const heatLayer = shallowRef<any>(null)

// MAP SOURCE
// const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
const url = ref('/tiles/{z}/{x}/{y}.png')

const attribution = ref('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

const heatmapSettings = ref({
  radius: 25,
  blur: 15,
  maxZoom: 17,
  max: 1.0,
  minOpacity: 0.4,
  gradient: {
    0.0: 'blue',
    0.3: 'cyan',
    0.5: 'lime',
    0.7: 'yellow',
    1.0: 'red'
  }
})

const dataSettings = ref({
  timeWindow: 60,
  intensityMode: 'count' as 'count' | 'frequency' | 'strength' | 'snr',
  updateInterval: 1000,
  showRealtime: true,
  gridResolution: 4
})

const stats = ref({
  totalPoints: 0,
  uniqueLocations: 0,
  maxIntensity: 0,
  avgIntensity: 0,
  selectedSensorCount: 0,
  totalDetections: 0
})

const showControlPanel = ref(false)

const accumulatedPoints = ref<Map<string, { lat: number; lon: number; intensity: number; timestamp: number }>>(new Map())

const heatmapPoints = computed(() => {
  const now = performance.now()
  const timeWindowMs = dataSettings.value.timeWindow * 1000
  const locationMap = new Map<string, { count: number; totalIntensity: number; maxIntensity: number }>()

  selectedSensors.value.forEach(sensor => {
    if (!sensor.detections?.length) return
    sensor.detections.forEach(detection => {
      const detectionTime = detection.timestamp || 0
      const age = now - detectionTime
      if (age > timeWindowMs) return
      if (!Array.isArray(detection.coordinate) || detection.coordinate.length !== 2) return
      const [lat, lon] = detection.coordinate
      if (!lat || !lon || isNaN(lat) || isNaN(lon)) return
      const gridKey = `${lat.toFixed(dataSettings.value.gridResolution)},${lon.toFixed(dataSettings.value.gridResolution)}`
      if (!locationMap.has(gridKey)) {
        locationMap.set(gridKey, { count: 0, totalIntensity: 0, maxIntensity: 0 })
      }
      const loc = locationMap.get(gridKey)!
      loc.count++
      let intensity = 0
      switch (dataSettings.value.intensityMode) {
        case 'count': intensity = 1; break
        case 'frequency': intensity = detection.frequency ? detection.frequency / 1e9 : 0; break
        case 'strength': intensity = Math.abs(detection.azimuth || 0); break
        case 'snr': intensity = detection.elevation || 0; break
      }
      loc.totalIntensity += intensity
      loc.maxIntensity = Math.max(loc.maxIntensity, intensity)
    })
  })

  const newPoints: [number, number, number][] = []
  let globalMaxIntensity = 0
  let totalIntensity = 0

  locationMap.forEach((data, key) => {
    const [lat, lon] = key.split(',').map(Number)
    const finalIntensity = dataSettings.value.intensityMode === 'count'
      ? Math.min(data.count / 5, 1.0)
      : Math.min(data.maxIntensity, 1.0)
    globalMaxIntensity = Math.max(globalMaxIntensity, finalIntensity)
    totalIntensity += finalIntensity
    newPoints.push([lat, lon, finalIntensity])
  })

  stats.value = {
    totalPoints: newPoints.length,
    uniqueLocations: locationMap.size,
    maxIntensity: parseFloat(globalMaxIntensity.toFixed(3)),
    avgIntensity: newPoints.length > 0 ? parseFloat((totalIntensity / newPoints.length).toFixed(3)) : 0,
    selectedSensorCount: selectedSensors.value.length,
    totalDetections: selectedSensors.value.reduce((sum, s) => sum + (s.detections?.length || 0), 0)
  }

  return newPoints
})

function updateHeatmap(forceRecreate = false) {
  if (!leafletMap.value) return
  const now = performance.now()
  const timeWindowMs = dataSettings.value.timeWindow * 1000
  const newPoints = heatmapPoints.value

  newPoints.forEach(([lat, lon, intensity]) => {
    const key = `${lat.toFixed(dataSettings.value.gridResolution)},${lon.toFixed(dataSettings.value.gridResolution)}`
    const existing = accumulatedPoints.value.get(key)
    if (existing) {
      existing.intensity = Math.min(1.0, existing.intensity + intensity * 0.5)
      existing.timestamp = now
    } else {
      accumulatedPoints.value.set(key, { lat, lon, intensity, timestamp: now })
    }
  })

  accumulatedPoints.value.forEach((v, k) => {
    if (now - v.timestamp > timeWindowMs) accumulatedPoints.value.delete(k)
  })

  const points = Array.from(accumulatedPoints.value.values()).map(p => [p.lat, p.lon, p.intensity])

  if (points.length === 0) {
    if (heatLayer.value) {
      leafletMap.value.removeLayer(heatLayer.value)
      heatLayer.value = null
    }
    return
  }

  if (heatLayer.value && !forceRecreate) {
    heatLayer.value.setLatLngs(points)
    heatLayer.value.redraw()
  } else {
    if (heatLayer.value) {
      leafletMap.value.removeLayer(heatLayer.value)
      heatLayer.value = null
    }
    heatLayer.value = (L as any).heatLayer(points, {
      radius: heatmapSettings.value.radius,
      blur: heatmapSettings.value.blur,
      maxZoom: heatmapSettings.value.maxZoom,
      max: heatmapSettings.value.max,
      minOpacity: heatmapSettings.value.minOpacity,
      gradient: heatmapSettings.value.gradient
    }).addTo(leafletMap.value)
  }
}

function onMapReady() {
  if (mapRef.value?.leafletObject) {
    leafletMap.value = mapRef.value.leafletObject
    setTimeout(() => updateHeatmap(true), 500)
  }
}

watch(selectedSensors, () => { if (dataSettings.value.showRealtime) updateHeatmap(false) }, { deep: false })
watch(sensors, () => { if (dataSettings.value.showRealtime && hasSelectedSensors.value) updateHeatmap(false) }, { deep: true })
watch(() => heatmapSettings.value, () => updateHeatmap(true), { deep: true })
watch(() => dataSettings.value.intensityMode, () => updateHeatmap(false))
watch(() => dataSettings.value.timeWindow, () => updateHeatmap(false))
watch(() => dataSettings.value.gridResolution, () => updateHeatmap(false))

let updateTimer: number | null = null
function startAutoUpdate() {
  if (updateTimer) clearInterval(updateTimer)
  updateTimer = setInterval(() => {
    if (dataSettings.value.showRealtime && hasSelectedSensors.value) updateHeatmap(false)
  }, dataSettings.value.updateInterval)
}
function stopAutoUpdate() { if (updateTimer) { clearInterval(updateTimer); updateTimer = null } }

watch(() => dataSettings.value.updateInterval, () => {
  if (dataSettings.value.showRealtime) { stopAutoUpdate(); startAutoUpdate() }
})
watch(() => dataSettings.value.showRealtime, (isRealtime) => { isRealtime ? startAutoUpdate() : stopAutoUpdate() })

watch(selectedSensors, (newSensors) => {
  if (centerInitialized) return // csak egyszer állítjuk be

  for (const sensor of newSensors) {
    if (sensor.detections?.length) {
      const firstDetection = sensor.detections[0]
      if (
        Array.isArray(firstDetection.coordinate) &&
        firstDetection.coordinate.length === 2
      ) {
        const [lat, lon] = firstDetection.coordinate
        if (!isNaN(lat) && !isNaN(lon)) {
          center.value = [lat, lon]
          centerInitialized = true
          console.log(`[Map] 🧭 Center set to first detection:`, center.value)
          break
        }
      }
    }
  }
}, { deep: true })


function clearHeatmap() {
  accumulatedPoints.value.clear()
  if (heatLayer.value && leafletMap.value) {
    leafletMap.value.removeLayer(heatLayer.value)
    heatLayer.value = null
  }
}

function manualUpdate() { updateHeatmap(true) }

function exportData() {
  const data = {
    points: Array.from(accumulatedPoints.value.values()),
    stats: stats.value,
    settings: { heatmap: heatmapSettings.value, data: dataSettings.value },
    sensors: selectedSensors.value.map(s => ({ id: s.uav_id, label: s.uav_label, detectionCount: s.detections.length }))
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `heatmap-data-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => startAutoUpdate())
onBeforeUnmount(() => { stopAutoUpdate(); clearHeatmap() })
</script>

<template>
  <div class="flex flex-col w-full h-full">
    <div class="flex-1 relative rounded-xl overflow-visible">
      <l-map ref="mapRef" :zoom="zoom" :center="center || [47.4979, 19.0402]" class="w-full h-full z-0" @ready="onMapReady">
        <l-tile-layer :url="url" :attribution="attribution" />
      </l-map>
      <div class="absolute top-2 left-2 bg-slate-800/90 text-gray-200 p-3 rounded-lg shadow-lg border border-slate-600 z-10 text-xs space-y-1">
        <div class="flex items-center gap-2 font-semibold text-cyan-400">
          <span>🔥</span><span>Heatmap Statistics</span>
        </div>
        <div class="grid grid-cols-2 gap-x-3 gap-y-1 text-gray-300">
          <span>Sensors:</span><strong class="text-gray-100">{{ stats.selectedSensorCount }}</strong>
          <span>Detections:</span><strong class="text-gray-100">{{ stats.totalDetections }}</strong>
          <span>Points:</span><strong class="text-gray-100">{{ stats.totalPoints }}</strong>
          <span>Locations:</span><strong class="text-gray-100">{{ stats.uniqueLocations }}</strong>
          <span>Max Int:</span><strong class="text-cyan-400">{{ stats.maxIntensity }}</strong>
          <span>Avg Int:</span><strong class="text-cyan-400">{{ stats.avgIntensity }}</strong>
        </div>
        <div class="pt-1 border-t border-slate-700 text-gray-400">
          Mode: <strong class="text-gray-200">{{ dataSettings.intensityMode }}</strong>
        </div>
      </div>

      <div v-if="!hasSelectedSensors" class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-slate-800/95 text-gray-200 p-6 rounded-lg shadow-xl border border-slate-600 z-10 text-center">
        <div class="text-4xl mb-3">⚠️</div>
        <h3 class="text-lg font-semibold mb-2">No Sensors Selected</h3>
        <p class="text-sm text-gray-400">Please select sensors from the list to view heatmap data.</p>
      </div>

      <button v-if="props.showControls" @click="showControlPanel = !showControlPanel" class="absolute top-2 right-2 bg-slate-800/90 hover:bg-slate-700 text-gray-200 p-2 rounded shadow-lg border border-slate-600 z-10 transition-colors" :class="{ 'bg-cyan-600': showControlPanel }">
        ⚙️
      </button>

      <div v-if="props.showControls && showControlPanel" class="absolute top-14 right-2 bg-slate-800/95 text-gray-200 p-3 rounded-lg shadow-lg border border-slate-600 z-10 w-72 max-h-[calc(100%-4rem)] overflow-auto">
        <h4 class="font-semibold text-cyan-400 mb-3 text-sm">Heatmap Settings</h4>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-300 block mb-1">Intensity Mode</label>
            <select v-model="dataSettings.intensityMode" class="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-gray-100">
              <option value="count">Detection Count</option>
              <option value="frequency">Frequency</option>
              <option value="strength">Signal Strength</option>
              <option value="snr">SNR / Elevation</option>
            </select>
          </div>
          <div>
            <label class="text-xs text-gray-300 block mb-1">Time Window: <strong>{{ dataSettings.timeWindow }}s</strong></label>
            <input type="range" min="10" max="300" step="10" v-model.number="dataSettings.timeWindow" class="w-full accent-cyan-500" />
          </div>
          <div>
            <label class="text-xs text-gray-300 block mb-1">Grid Resolution: <strong>{{ dataSettings.gridResolution }}</strong></label>
            <input type="range" min="2" max="6" step="1" v-model.number="dataSettings.gridResolution" class="w-full accent-cyan-500" />
          </div>
          <div class="border-t border-slate-700 pt-3"><p class="text-xs text-gray-400 mb-2">Visual Settings</p></div>
          <div>
            <label class="text-xs text-gray-300 block mb-1">Radius: <strong>{{ heatmapSettings.radius }}</strong></label>
            <input type="range" min="10" max="50" v-model.number="heatmapSettings.radius" class="w-full accent-cyan-500" />
          </div>
          <div>
            <label class="text-xs text-gray-300 block mb-1">Blur: <strong>{{ heatmapSettings.blur }}</strong></label>
            <input type="range" min="5" max="30" v-model.number="heatmapSettings.blur" class="w-full accent-cyan-500" />
          </div>
          <div>
            <label class="text-xs text-gray-300 block mb-1">Min Opacity: <strong>{{ heatmapSettings.minOpacity }}</strong></label>
            <input type="range" min="0.1" max="1" step="0.1" v-model.number="heatmapSettings.minOpacity" class="w-full accent-cyan-500" />
          </div>
          <div>
            <label class="text-xs text-gray-300 block mb-1">Update Interval: <strong>{{ dataSettings.updateInterval }}ms</strong></label>
            <input type="range" min="500" max="5000" step="100" v-model.number="dataSettings.updateInterval" class="w-full accent-cyan-500" />
          </div>
          <div class="flex items-center gap-2">
            <input type="checkbox" id="realtime-compact" v-model="dataSettings.showRealtime" class="h-3 w-3 text-cyan-500 border-slate-600 bg-slate-700 rounded" />
            <label for="realtime-compact" class="text-xs text-gray-300">Real-time Auto Updates</label>
          </div>
          <div class="pt-2 border-t border-slate-700 space-y-2">
            <button @click="manualUpdate" class="w-full bg-cyan-600 hover:bg-cyan-500 text-white px-3 py-2 rounded text-xs font-semibold transition-colors">🔄 Force Refresh</button>
            <button @click="clearHeatmap" class="w-full bg-slate-700 hover:bg-slate-600 text-white px-3 py-2 rounded text-xs font-semibold transition-colors">🧹 Clear Heatmap</button>
            <button @click="exportData" class="w-full bg-slate-700 hover:bg-slate-600 text-white px-3 py-2 rounded text-xs font-semibold transition-colors">📊 Export Data</button>
          </div>
        </div>
      </div>

      <div class="absolute bottom-2 right-2 bg-slate-800/90 text-gray-200 p-2 rounded shadow-lg border border-slate-600 z-10">
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-2">
            <div class="w-20 h-3 rounded" style="background: linear-gradient(to right, blue, cyan, lime, yellow, red)"></div>
            <span class="text-xs text-gray-400">Low → High</span>
          </div>
          <div class="text-xs text-gray-400 text-center">Intensity: {{ dataSettings.intensityMode }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
input[type="range"] { -webkit-appearance: none; appearance: none; background: transparent; cursor: pointer; }
input[type="range"]::-webkit-slider-track { background: #475569; height: 0.4rem; border-radius: 0.2rem; }
input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; background: #06b6d4; height: 1rem; width: 1rem; border-radius: 50%; margin-top: -0.3rem; }
input[type="range"]::-moz-range-track { background: #475569; height: 0.4rem; border-radius: 0.2rem; }
input[type="range"]::-moz-range-thumb { background: #06b6d4; height: 1rem; width: 1rem; border-radius: 50%; border: none; }
</style>
