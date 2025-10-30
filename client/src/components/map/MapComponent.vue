<script setup lang="ts">
import { ref, onMounted, shallowRef, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import { LMap, LTileLayer, LMarker, LPolyline } from '@vue-leaflet/vue-leaflet'
import L from 'leaflet'
import pW from '@/assets/dir1.png'
import { useSensorStore } from '@/stores/sensor'
import { storeToRefs } from 'pinia'
import 'leaflet/dist/leaflet.css'
import 'leaflet.fullscreen'
import 'leaflet.fullscreen/Control.FullScreen.css'
import { Sensor } from '@/types/sensor'

// --- STORE ---
const sensorStore = useSensorStore()
const { sensors, batchInterval, selectedSensors, hasSelectedSensors } = storeToRefs(sensorStore)

// --- MAP STATE ---
const zoom = ref(10)
const center = ref([47.4979, 19.0402])
const mapRef = ref(null)
const leafletMap = shallowRef(null)
const mapBounds = shallowRef(null)
const mapContainer = ref(null)

const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
const attribution = ref('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

// --- SETTINGS ---
const newDetectionSize = ref(Math.abs(sensorStore.detectionSize))
const batchIntervalLocal = ref(sensorStore.batchInterval)
const autoZoom = ref(false)
const maxVisiblePoints = ref(50)
const lineLength = ref(0.05)
const planeDisplayPeriod = ref(4)
const showAzimuthLines = ref(true)

// --- REAL-TIME CONFIG ---
const realtimeConfig = ref({
  ...sensorStore.realtimeConfig
})

const updateRealtimeConfig = () => {
  sensorStore.updateRealtimeConfig(realtimeConfig.value)
}

// --- DEBUG ---
const debugInfo = ref({
  mapInitialized: false,
  detectionsCount: 0,
  selectedSensorsCount: 0,
  renderTime: 0,
  cacheSize: 0
})

// --- PERFORMANCE CACHES ---
const planeIconsCache = new Map<string, any>()
const azimuthLinesCache = new Map<string, number[][]>()
const CACHE_CLEANUP_THRESHOLD = 500

// --- ICONS, COLORS ---
const dotIcons = ['blue', 'red', 'orange', 'green', 'cyan', 'magenta', 'yellow', 'purple'].map(color =>
  L.divIcon({
    className: '',
    html: `<div style="background-color:${color};width:12px;height:12px;border-radius:50%;border:1px solid white;box-shadow:0 0 2px rgba(0,0,0,0.5);"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6]
  })
)
const lineColors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'cyan', 'magenta']

// --- COMPUTED ---
const selectedSensorCount = computed(() => selectedSensors.value.length)

// --- FUNCTIONS (heading, icons, lines stb.) ---

/**
 * ✅ Heading számítás quaternion-ből
 * A Measurement.quaternion egy repeated float (tömb)
 */
function getHeadingFromQuaternion([q0, q1, q2, q3]: number[]): number {
  if (q0 === undefined || q1 === undefined || q2 === undefined || q3 === undefined) return 0
  const headingRad = Math.atan2(2 * (q0 * q3 + q1 * q2), q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3)
  const deg = headingRad * (180 / Math.PI)
  return deg < 0 ? deg + 360 : deg
}

/**
 * ✅ Szenzor heading lekérése
 * 1. Először a legutóbbi detectionből próbálja (worker által feldolgozott quaternion)
 * 2. Ha nincs, akkor a szenzor utolsó ismert quaternion-jéből
 */
function getHeading(sensor: Sensor): number {
  // 1. Legutóbbi detection quaternion-ja (feldolgozott adat a workerből)
  const lastDetection = sensor.detections?.at(-1)
  if (lastDetection?.quaternion) {
    return getHeadingFromQuaternion([
      lastDetection.quaternion.q0,
      lastDetection.quaternion.q1,
      lastDetection.quaternion.q2,
      lastDetection.quaternion.q3
    ])
  }

  // 2. Szenzor saját quaternion-ja (fallback)
  const { last_pos_q0, last_pos_q1, last_pos_q2, last_pos_q3 } = sensor
  if ([last_pos_q0, last_pos_q1, last_pos_q2, last_pos_q3].every(v => v !== undefined)) {
    return getHeadingFromQuaternion([last_pos_q0, last_pos_q1, last_pos_q2, last_pos_q3])
  }

  return 0
}

function getPlaneIconById(id: number): any {
  const sensor = sensors.value[id]
  if (!sensor) return dotIcons[0]
  const heading = getHeading(sensor)
  const roundedHeading = Math.round(heading / 10) * 10
  const cacheKey = `${id}_${roundedHeading}`
  if (planeIconsCache.has(cacheKey)) return planeIconsCache.get(cacheKey)

  const icon = L.divIcon({
    className: '',
    html: `<div style="width:48px;height:48px;background:url('${pW}') no-repeat center center;background-size:contain;transform:rotate(${roundedHeading + 90}deg);"></div>`,
    iconSize: [48, 48],
    iconAnchor: [24, 24]
  })
  if (planeIconsCache.size > CACHE_CLEANUP_THRESHOLD) {
    planeIconsCache.delete(planeIconsCache.keys().next().value)
  }
  planeIconsCache.set(cacheKey, icon)
  debugInfo.value.cacheSize = planeIconsCache.size + azimuthLinesCache.size
  return icon
}

/**
 * ✅ Azimut vonal számítása
 * Az azimuth már radiánban jön a detectionből (azimuth mező)
 */
function computeAzimuthLine(coord: [number, number], azimuth: number, isRadians = false): number[][] {
  const cacheKey = `${coord[0].toFixed(4)}_${coord[1].toFixed(4)}_${azimuth.toFixed(3)}_${lineLength.value}`
  if (azimuthLinesCache.has(cacheKey)) return azimuthLinesCache.get(cacheKey)!

  const [lat, lon] = coord
  const distance = lineLength.value
  const azimuthRad = isRadians ? azimuth : azimuth * (Math.PI / 180)
  const endLat = lat + distance * Math.cos(azimuthRad)
  const endLon = lon + distance * Math.sin(azimuthRad)
  const result = [[lat, lon], [endLat, endLon]]

  if (azimuthLinesCache.size > CACHE_CLEANUP_THRESHOLD) {
    azimuthLinesCache.delete(azimuthLinesCache.keys().next().value)
  }
  azimuthLinesCache.set(cacheKey, result)
  return result
}

function getColorByRoiOrSensor(detection: any, sensorId: number): string {
  if (detection.roi_id != null) return lineColors[detection.roi_id % lineColors.length]
  return lineColors[sensorId % lineColors.length]
}

// --- DETECTION BUFFER (OPTIMIZED) ---
const detectionBuffer = shallowRef<Map<string, any>>(new Map())
let renderThrottle: number | null = null

function renderDetections() {
  // Throttle render to max 60 FPS
  if (renderThrottle) return
  renderThrottle = setTimeout(() => {
    renderThrottle = null
    _doRenderDetections()
  }, 16) // ~60 FPS
}

function _doRenderDetections () {
  if (!leafletMap.value || !mapBounds.value) return
  const renderStart = performance.now()
  const bounds = mapBounds.value
  const oldBuffer = detectionBuffer.value
  const updatedBuffer = new Map(oldBuffer)

  if (!hasSelectedSensors.value) {
    debugInfo.value.selectedSensorsCount = 0
    return
  }

  selectedSensors.value.forEach(sensor => {
    if (!sensor?.detections) return
    const recentDetections = sensor.detections.slice(-maxVisiblePoints.value)
    const sensorId = sensor.uav_id

    recentDetections.forEach((detection, idx) => {
      // ✅ A coordinate már a workerben ki van számítva
      if (!Array.isArray(detection.coordinate)) return
      if (bounds && !bounds.contains(L.latLng(detection.coordinate[0], detection.coordinate[1]))) return

      const stableKey = `${sensorId}-${detection.timestamp || `idx-${idx}`}`
      const existingItem = oldBuffer.get(stableKey)

      // Már létező pont → csak pozíciófrissítés
      if (existingItem) {
        existingItem.coordinate = detection.coordinate
        updatedBuffer.set(stableKey, existingItem)
        return
      }

      // Új pont
      const showPlane = idx % planeDisplayPeriod.value === 0
      const hasAzimuth = detection.azimuth != null
      const color = getColorByRoiOrSensor(detection, sensorId)
      const dotIcon = dotIcons[sensorId % dotIcons.length]

      const item: any = {
        key: stableKey,
        coordinate: detection.coordinate,
        showPlane,
        dotIcon,
        color,
        lastUpdate: Date.now()
      }

      if (showPlane) item.planeIcon = getPlaneIconById(sensorId)

      // ✅ Az azimuth már radiánban van
      if (hasAzimuth && showAzimuthLines.value) {
        item.azimuthLine = computeAzimuthLine(detection.coordinate, detection.azimuth, true)
        item.hasAzimuth = true
      }

      updatedBuffer.set(stableKey, item)
    })
  })

  // Opcionális TTL (régi detekciók eltávolítása)
  const ttlMs = realtimeConfig.value.detectionTTL || 10000
  const now = Date.now()
  for (const [key, item] of updatedBuffer.entries()) {
    if (now - (item.lastUpdate ?? 0) > ttlMs) {
      updatedBuffer.delete(key)
    }
  }

  detectionBuffer.value = updatedBuffer

  debugInfo.value.detectionsCount = updatedBuffer.size
  debugInfo.value.selectedSensorsCount = selectedSensors.value.length
  debugInfo.value.renderTime = performance.now() - renderStart
}

// Computed property a template számára
const detectionBufferArray = computed(() => Array.from(detectionBuffer.value.values()))

// --- SETTINGS HANDLING ---
function updateBatchInterval() {
  const newInterval = Number(batchIntervalLocal.value)
  if (isNaN(newInterval) || newInterval < 0.01 || newInterval > 10) return
  sensorStore.$patch({ batchInterval: newInterval })
}

function updateSettings() {
  const size = newDetectionSize.value
  if (!isNaN(size) && size > 0) sensorStore.$patch({ detectionSize: size })
  updateBatchInterval()
  renderDetections()
}

function clearMapData() {
  sensorStore.clearDetections()
  planeIconsCache.clear()
  azimuthLinesCache.clear()
  detectionBuffer.value = new Map()
  debugInfo.value.cacheSize = 0
}

function debugStore() {
  console.log('=== MAP COMPONENT DEBUG ===', debugInfo.value)
  sensorStore.debugReactivity()
}

// --- MAP SETUP ---
function updateMapView() {
  if (mapRef.value?.leafletObject) {
    leafletMap.value = mapRef.value.leafletObject
    mapBounds.value = leafletMap.value.getBounds()
    debugInfo.value.mapInitialized = true
  }
}

function goFullscreen() {
  if (!mapContainer.value) return
  const el: any = mapContainer.value
  if (!document.fullscreenElement) el.requestFullscreen?.()
  else document.exitFullscreen?.()
}

function onMapReady (mapInstance: any) {
  leafletMap.value = mapInstance
  mapBounds.value = mapInstance.getBounds()
  debugInfo.value.mapInitialized = true
  renderDetections()
}

// --- WATCHERS (OPTIMIZED) ---
watch(sensors, () => {
  if (hasSelectedSensors.value) {
    renderDetections() // throttled
  }
}, { deep: true })

watch(selectedSensors, () => {
  renderDetections()
}, { deep: false })

watch(batchInterval, val => (batchIntervalLocal.value = val), { immediate: true })

onMounted(async () => {
  await nextTick()
  updateMapView()
  leafletMap.value?.on('moveend', updateMapView)
  leafletMap.value?.on('zoomend', updateMapView)
})

onBeforeUnmount(() => {
  if (renderThrottle) clearTimeout(renderThrottle)
  leafletMap.value?.off('moveend', updateMapView)
  leafletMap.value?.off('zoomend', updateMapView)
  planeIconsCache.clear()
  azimuthLinesCache.clear()
})
</script>

<template>
  <div class="flex flex-col w-full h-[calc(100vh-5rem)] rounded-xl overflow-hidden">
    <!-- Map Container -->
    <div ref="mapContainer" class="flex-[3] border border-slate-700 rounded-xl overflow-hidden relative">
      <l-map ref="mapRef" :zoom="zoom" :center="center" @ready="onMapReady" class="w-full h-full">
        <l-tile-layer :url="url" :attribution="attribution" />

        <!-- Debug Info -->
        <div class="absolute top-2 left-2 bg-slate-800/90 text-gray-200 p-2 rounded shadow z-[1000] text-xs border border-slate-600">
          <div>Map: {{ debugInfo.mapInitialized ? '✅' : '❌' }}</div>
          <div>Sensors: {{ debugInfo.selectedSensorsCount }}</div>
          <div>Detections: {{ debugInfo.detectionsCount }}</div>
          <div>Render: {{ debugInfo.renderTime.toFixed(1) }}ms</div>
          <div>Cache: {{ debugInfo.cacheSize }}</div>
        </div>

        <!-- Detection markers - OPTIMIZED -->
        <template v-for="detection in detectionBufferArray" :key="detection.key">
          <l-marker
            v-if="detection.showPlane && detection.planeIcon"
            :lat-lng="detection.coordinate"
            :icon="detection.planeIcon"
          />
          <l-polyline
            v-if="detection.hasAzimuth && detection.azimuthLine"
            :lat-lngs="detection.azimuthLine"
            :color="detection.color"
            :weight="2"
            :opacity="0.7"
          />
          <l-marker
            :lat-lng="detection.coordinate"
            :icon="detection.dotIcon"
          />
        </template>
      </l-map>
    </div>

    <!-- Controls -->
    <div class="flex-[1] mt-4 px-4 overflow-auto">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4 bg-slate-800 p-4 rounded-xl shadow-lg border border-slate-700">
        <!-- existing controls -->
        <div>
          <label class="font-semibold text-gray-300 text-sm">Max points</label>
          <input type="number" v-model.number="maxVisiblePoints" @change="updateSettings"
                 class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100 text-sm" />
        </div>
        <div>
          <label class="font-semibold text-gray-300 text-sm">Plane period</label>
          <input type="number" v-model.number="planeDisplayPeriod" @change="updateSettings"
                 class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100 text-sm" />
        </div>
        <div>
          <label class="font-semibold text-gray-300 text-sm">Line length</label>
          <input type="number" v-model.number="lineLength" @change="updateSettings"
                 step="0.01" min="0.01" max="1"
                 class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100 text-sm" />
        </div>
        <div>
          <label class="font-semibold text-gray-300 text-sm">Batch interval (s)</label>
          <input type="number" step="0.01" min="0.01" max="10"
                 v-model.number="batchIntervalLocal" @change="updateBatchInterval"
                 class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100 text-sm" />
        </div>
        <div class="flex items-center gap-2">
          <input v-model="showAzimuthLines" type="checkbox" @change="updateSettings"
                 class="h-4 w-4 text-cyan-500 border-slate-600 bg-slate-800 rounded focus:ring-cyan-500" />
          <span class="text-sm text-gray-300">Show Azimuth Lines</span>
        </div>
        <div>
          <button
            @click="debugStore"
            class="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow transition text-sm"
          >
            🔍 Debug
          </button>
        </div>
      </div>

      <!-- REAL-TIME SETTINGS PANEL -->
      <div class="mt-4 bg-slate-800 p-4 rounded-xl border border-slate-700">
        <h3 class="text-lg font-bold mb-3 text-gray-100">Real-time Settings</h3>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label class="block text-sm mb-1 text-gray-300">Max Latency (ms)</label>
            <input v-model.number="realtimeConfig.maxLatencyMs" type="number" @change="updateRealtimeConfig"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100" />
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">Detection TTL (ms)</label>
            <input v-model.number="realtimeConfig.detectionTTL" type="number" @change="updateRealtimeConfig"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100" />
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">Buffer Size</label>
            <input v-model.number="realtimeConfig.circularBufferSize" type="number" @change="updateRealtimeConfig"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100" />
          </div>

          <div class="flex items-center gap-2 mt-6">
            <input v-model="realtimeConfig.enableStrictRealtime" type="checkbox" @change="updateRealtimeConfig"
                   class="h-4 w-4 text-cyan-500 border-slate-600 bg-slate-800 rounded focus:ring-cyan-500" />
            <span class="text-sm text-gray-300">Enable Strict Real-time Mode</span>
          </div>
        </div>

        <div class="mt-4 flex justify-end">
          <button
            @click="clearMapData"
            class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg shadow border border-red-800 transition"
          >
            🧹 Clear All Detections
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>