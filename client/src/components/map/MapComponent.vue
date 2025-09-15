<script setup lang="ts">
import { ref, onMounted, shallowRef, onBeforeUnmount, nextTick, watch } from 'vue'
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
const { sensors, batchInterval } = storeToRefs(sensorStore)

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
const maxVisiblePoints = ref(100)
const lineLength = ref(0.1)
const planeDisplayPeriod = ref(2) // Show every 2nd point
const showAzimuthLines = ref(true)
const renderInterval = ref(150) // ms between renders

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
const CACHE_CLEANUP_INTERVAL = 500 // Clean cache every 500 entries

// Pre-generate dot icons with better performance
const dotIcons = ["blue","red","orange","green","cyan","magenta","yellow","purple"].map(color =>
  L.divIcon({
    className: '',
    html: `<div style="background-color:${color};width:12px;height:12px;border-radius:50%;border:1px solid white;box-shadow:0 0 2px rgba(0,0,0,0.5);"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6]
  })
)

const lineColors = ["red","blue","green","orange","purple","brown","cyan","magenta"]

// --- OPTIMIZED FUNCTIONS ---
function getHeadingFromQuaternion([q0, q1, q2, q3]: number[]): number {
  if (q0 === undefined || q1 === undefined || q2 === undefined || q3 === undefined) return 0

  const headingRad = Math.atan2(2 * (q0 * q3 + q1 * q2), q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3)
  let deg = headingRad * (180 / Math.PI)
  return deg < 0 ? deg + 360 : deg
}

function getHeading(sensor: Sensor): number {
  const lastDetection = sensor.detections?.at(-1)
  if (lastDetection?.quaternion) {
    return getHeadingFromQuaternion([
      lastDetection.quaternion.q0,
      lastDetection.quaternion.q1,
      lastDetection.quaternion.q2,
      lastDetection.quaternion.q3
    ])
  }

  // Fallback to sensor level quaternion
  const { last_pos_q0, last_pos_q1, last_pos_q2, last_pos_q3 } = sensor
  if (last_pos_q0 !== undefined && last_pos_q1 !== undefined &&
      last_pos_q2 !== undefined && last_pos_q3 !== undefined) {
    return getHeadingFromQuaternion([last_pos_q0, last_pos_q1, last_pos_q2, last_pos_q3])
  }

  return 0
}

function getPlaneIconById(id: number): any {
  const sensor = sensors.value[id]
  if (!sensor) return dotIcons[0]

  const heading = getHeading(sensor)
  // Round to 10-degree precision for better caching
  const roundedHeading = Math.round(heading / 10) * 10
  const cacheKey = `${id}_${roundedHeading}`

  if (planeIconsCache.has(cacheKey)) {
    return planeIconsCache.get(cacheKey)
  }

  const icon = L.divIcon({
    className: '',
    html: `<div style="width:48px;height:48px;background:url('${pW}') no-repeat center center;background-size:contain;transform:rotate(${roundedHeading + 90}deg);"></div>`,
    iconSize: [48, 48],
    iconAnchor: [24, 24]
  })

  // Cache management
  if (planeIconsCache.size > CACHE_CLEANUP_INTERVAL) {
    const firstKey = planeIconsCache.keys().next().value
    planeIconsCache.delete(firstKey)
  }

  planeIconsCache.set(cacheKey, icon)
  debugInfo.value.cacheSize = planeIconsCache.size + azimuthLinesCache.size
  return icon
}

function computeAzimuthLine(coord: [number, number], azimuth: number, isRadians: boolean = false): number[][] {
  const cacheKey = `${coord[0].toFixed(4)}_${coord[1].toFixed(4)}_${azimuth.toFixed(3)}_${lineLength.value}`

  if (azimuthLinesCache.has(cacheKey)) {
    return azimuthLinesCache.get(cacheKey)!
  }

  const [lat, lon] = coord
  const distance = lineLength.value
  const azimuthRad = isRadians ? azimuth : azimuth * (Math.PI / 180)

  const endLat = lat + distance * Math.cos(azimuthRad)
  const endLon = lon + distance * Math.sin(azimuthRad)

  const result = [[lat, lon], [endLat, endLon]]

  // Cache management
  if (azimuthLinesCache.size > CACHE_CLEANUP_INTERVAL) {
    const firstKey = azimuthLinesCache.keys().next().value
    azimuthLinesCache.delete(firstKey)
  }

  azimuthLinesCache.set(cacheKey, result)
  return result
}

function getColorByRoiOrSensor(detection: any, sensorId: number): string {
  if (detection.roi_id !== null && detection.roi_id !== undefined) {
    return lineColors[detection.roi_id % lineColors.length]
  }
  return lineColors[sensorId % lineColors.length]
}

// --- MAIN DETECTION BUFFER ---
const detectionBuffer = ref<any[]>([])
let animFrame: number | null = null
let lastRenderTime = 0

function scheduleRender() {
  if (animFrame) cancelAnimationFrame(animFrame)
  animFrame = requestAnimationFrame(renderDetections)
}

function renderDetections() {
  const renderStart = performance.now()
  const visible: any[] = []
  let selectedCount = 0

  // Check viewport bounds for optimization
  const bounds = mapBounds.value

  Object.entries(sensors.value).forEach(([id, sensor]) => {
    if (!sensor?.is_selected || !Array.isArray(sensor.detections)) return

    selectedCount++
    const sensorId = Number(id)
    const recentDetections = sensor.detections.slice(-maxVisiblePoints.value)

    recentDetections.forEach((detection, idx) => {
      if (!detection?.coordinate || !Array.isArray(detection.coordinate) || detection.coordinate.length !== 2) return

      // Viewport culling for performance
      if (bounds && !bounds.contains(L.latLng(detection.coordinate[0], detection.coordinate[1]))) return

      const showPlane = idx % planeDisplayPeriod.value === 0
      const hasAzimuth = detection.azimuth !== undefined && detection.azimuth !== null

      const item: any = {
        key: `${id}-${idx}`,
        coordinate: detection.coordinate,
        showPlane,
        dotIcon: dotIcons[sensorId % dotIcons.length],
        color: getColorByRoiOrSensor(detection, sensorId)
      }

      if (showPlane) {
        item.planeIcon = getPlaneIconById(sensorId)
      }

      if (hasAzimuth && showAzimuthLines.value) {
        item.azimuthLine = computeAzimuthLine(detection.coordinate, detection.azimuth, true)
        item.hasAzimuth = true
      }

      visible.push(item)
    })
  })

  detectionBuffer.value = visible
  debugInfo.value.detectionsCount = visible.length
  debugInfo.value.selectedSensorsCount = selectedCount
  debugInfo.value.renderTime = performance.now() - renderStart
  lastRenderTime = performance.now()
}

// --- SETTINGS MANAGEMENT ---
watch(batchInterval, (newVal) => {
  batchIntervalLocal.value = newVal
}, { immediate: true })

function updateBatchInterval() {
  const newInterval = typeof batchIntervalLocal.value === 'string'
    ? parseFloat(batchIntervalLocal.value)
    : Number(batchIntervalLocal.value)

  if (isNaN(newInterval) || newInterval < 0.1 || newInterval > 10) {
    console.warn('Invalid batch interval value:', batchIntervalLocal.value)
    batchIntervalLocal.value = sensorStore.batchInterval
    return
  }

  sensorStore.$patch({ batchInterval: newInterval })
}

function updateSettings() {
  const size = newDetectionSize.value
  if (!isNaN(size) && size > 0) {
    sensorStore.$patch({ detectionSize: size })
  }
  updateBatchInterval()
  scheduleRender()
}

function clearMapData() {
  sensorStore.clearDetections()
  planeIconsCache.clear()
  azimuthLinesCache.clear()
  detectionBuffer.value = []
  debugInfo.value.cacheSize = 0
}

function debugStore() {
  console.log('=== HYBRID OPTIMIZED DEBUG ===')
  console.log('Performance:', {
    renderTime: debugInfo.value.renderTime,
    visibleDetections: debugInfo.value.detectionsCount,
    cacheSize: debugInfo.value.cacheSize
  })
  console.log('Settings:', {
    maxVisiblePoints: maxVisiblePoints.value,
    planeDisplayPeriod: planeDisplayPeriod.value,
    renderInterval: renderInterval.value
  })
  console.log('Cache stats:', {
    planeIcons: planeIconsCache.size,
    azimuthLines: azimuthLinesCache.size
  })
}

// --- MAP MANAGEMENT ---
function updateMapView() {
  if (mapRef.value?.leafletObject) {
    leafletMap.value = mapRef.value.leafletObject
    mapBounds.value = leafletMap.value.getBounds()
    debugInfo.value.mapInitialized = true
  }
}

function goFullscreen() {
  if (!mapContainer.value) {
    console.warn('Fullscreen not available')
    return
  }

  try {
    if (!document.fullscreenElement) {
      if (mapContainer.value.requestFullscreen) {
        mapContainer.value.requestFullscreen()
      } else if (mapContainer.value.webkitRequestFullscreen) {
        mapContainer.value.webkitRequestFullscreen()
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen()
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen()
      }
    }
  } catch (e) {
    console.error('Fullscreen error:', e)
  }
}

// --- AUTO ZOOM ---
watch(() => detectionBuffer.value, (newBuffer) => {
  if (autoZoom.value && newBuffer.length > 0 && leafletMap.value) {
    const lastDetection = newBuffer[newBuffer.length - 1]
    if (lastDetection?.coordinate) {
      leafletMap.value.setView(lastDetection.coordinate, zoom.value)
    }
  }
}, { deep: false })

// --- LIFECYCLE ---
onMounted(async () => {
  await nextTick()
  updateMapView()

  if (leafletMap.value) {
    leafletMap.value.on('moveend', updateMapView)
    leafletMap.value.on('zoomend', updateMapView)
  }

  // Intelligent render loop - only render when needed
  const renderLoop = setInterval(() => {
    const now = performance.now()
    if (now - lastRenderTime > renderInterval.value) {
      scheduleRender()
    }
  }, renderInterval.value)

  onBeforeUnmount(() => {
    clearInterval(renderLoop)
  })
})

onBeforeUnmount(() => {
  if (animFrame) cancelAnimationFrame(animFrame)

  if (leafletMap.value) {
    leafletMap.value.off('moveend', updateMapView)
    leafletMap.value.off('zoomend', updateMapView)
  }

  // Clear caches
  planeIconsCache.clear()
  azimuthLinesCache.clear()
})
</script>

<template>
  <div class="flex flex-col w-full h-[calc(100vh-5rem)] rounded-xl overflow-hidden">
    <!-- Map Container -->
    <div ref="mapContainer" class="flex-[3] border border-slate-700 rounded-xl overflow-hidden relative">
      <l-map ref="mapRef" :zoom="zoom" :center="center" class="w-full h-full">
        <l-tile-layer :url="url" :attribution="attribution" />

        <!-- Optimized Debug Info -->
        <div class="absolute top-2 left-2 bg-slate-800/90 text-gray-200 p-2 rounded shadow z-10 text-xs border border-slate-600">
          <div>Map: {{ debugInfo.mapInitialized ? '✅' : '❌' }}</div>
          <div>Sensors: {{ debugInfo.selectedSensorsCount }}</div>
          <div>Detections: {{ debugInfo.detectionsCount }}</div>
          <div>Render: {{ debugInfo.renderTime.toFixed(1) }}ms</div>
          <div>Cache: {{ debugInfo.cacheSize }}</div>
        </div>

        <!-- Highly Optimized Marker Rendering -->
        <template v-for="detection in detectionBuffer" :key="detection.key">
          <!-- Plane markers (reduced frequency) -->
          <l-marker
            v-if="detection.showPlane && detection.planeIcon"
            :lat-lng="detection.coordinate"
            :icon="detection.planeIcon"
          />

          <!-- Azimuth lines (conditional) -->
          <l-polyline
            v-if="detection.hasAzimuth && detection.azimuthLine"
            :lat-lngs="detection.azimuthLine"
            :color="detection.color"
            :weight="2"
            :opacity="0.7"
          />

          <!-- Detection dots (always visible) -->
          <l-marker
            :lat-lng="detection.coordinate"
            :icon="detection.dotIcon"
          />
        </template>
      </l-map>
    </div>

    <!-- Streamlined Controls -->
    <div class="flex-[1] mt-4 px-4 overflow-auto">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4 bg-slate-800 p-4 rounded-xl shadow-lg border border-slate-700">

        <div>
          <label class="font-semibold text-gray-300">Max points</label>
          <input
            type="number"
            v-model="maxVisiblePoints"
            @change="updateSettings"
            min="10"
            max="500"
            class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100"
          />
        </div>

        <div>
          <label class="font-semibold text-gray-300">Plane period</label>
          <input
            type="number"
            v-model="planeDisplayPeriod"
            @change="updateSettings"
            min="1"
            max="10"
            class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100"
          />
        </div>

        <div>
          <label class="font-semibold text-gray-300">Line length</label>
          <input
            type="number"
            v-model="lineLength"
            @change="updateSettings"
            step="0.01"
            min="0.01"
            max="1"
            class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100"
          />
        </div>

        <div>
          <label class="font-semibold text-gray-300">Render interval (ms)</label>
          <input
            type="number"
            v-model="renderInterval"
            min="50"
            max="1000"
            step="50"
            class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100"
          />
        </div>

        <div>
          <label class="font-semibold text-gray-300">Batch interval (s)</label>
          <input
            type="number"
            step="0.01"
            min="0.05"
            max="10"
            v-model="batchIntervalLocal"
            @change="updateBatchInterval"
            class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100"
          />
        </div>

        <div class="flex flex-col gap-2">
          <div class="flex items-center gap-2">
            <input
              type="checkbox"
              id="autoz"
              v-model="autoZoom"
              class="h-4 w-4 text-cyan-500 border-slate-600 bg-slate-800 rounded focus:ring-cyan-500"
            />
            <label for="autoz" class="text-sm text-gray-300">Auto zoom</label>
          </div>

          <div class="flex items-center gap-2">
            <input
              type="checkbox"
              id="azlines"
              v-model="showAzimuthLines"
              class="h-4 w-4 text-cyan-500 border-slate-600 bg-slate-800 rounded focus:ring-cyan-500"
            />
            <label for="azlines" class="text-sm text-gray-300">Azimuth lines</label>
          </div>
        </div>

        <div class="col-span-1 md:col-span-2 lg:col-span-3 grid grid-cols-3 gap-2">
          <button
            @click="clearMapData"
            class="bg-red-600 hover:bg-red-500 text-white px-3 py-2 rounded-xl transition-colors text-sm"
          >
            Clear Map
          </button>

          <button
            @click="debugStore"
            class="bg-gray-600 hover:bg-gray-500 text-white px-3 py-2 rounded-xl transition-colors text-sm"
          >
            Debug
          </button>

          <button
            @click="goFullscreen"
            class="bg-cyan-600 hover:bg-cyan-500 text-white px-3 py-2 rounded-xl transition-colors text-sm"
          >
            Fullscreen
          </button>
        </div>

        <div class="col-span-1 md:col-span-2 lg:col-span-3">
          <div class="text-sm bg-slate-900 p-2 rounded border border-slate-700 text-gray-200">
            <div>Stream: {{ sensorStore.selectedSensor ? '🟢 Active' : '🔴 Inactive' }}</div>
            <div>Interval: {{ sensorStore.batchInterval }}s | Render: {{ renderInterval }}ms</div>
            <div>Performance: {{ debugInfo.renderTime.toFixed(1) }}ms | Cache: {{ debugInfo.cacheSize }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
