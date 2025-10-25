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
const maxVisiblePoints = ref(100)
const lineLength = ref(0.05)
const planeDisplayPeriod = ref(4)
const showAzimuthLines = ref(true)

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

// Pre-generate dot icons
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

// --- OPTIMIZED FUNCTIONS ---
function getHeadingFromQuaternion([q0, q1, q2, q3]: number[]): number {
  if (q0 === undefined || q1 === undefined || q2 === undefined || q3 === undefined) return 0

  const headingRad = Math.atan2(2 * (q0 * q3 + q1 * q2), q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3)
  const deg = headingRad * (180 / Math.PI)
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

  if (planeIconsCache.size > CACHE_CLEANUP_THRESHOLD) {
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

  if (azimuthLinesCache.size > CACHE_CLEANUP_THRESHOLD) {
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

function renderDetections() {
  const renderStart = performance.now()
  const visible: any[] = []
  const bounds = mapBounds.value

  if (!hasSelectedSensors.value) {
    detectionBuffer.value = []
    debugInfo.value.detectionsCount = 0
    debugInfo.value.selectedSensorsCount = 0
    return
  }

  // Iterálj csak a kiválasztott szenzorokon
  selectedSensors.value.forEach((sensorId) => {
    const sensor = sensors.value[sensorId]
    if (!sensor || !Array.isArray(sensor.detections)) return

    const recentDetections = sensor.detections.slice(-maxVisiblePoints.value)

    recentDetections.forEach((detection, idx) => {
      if (!detection?.coordinate || !Array.isArray(detection.coordinate) || detection.coordinate.length !== 2) return

      // Viewport culling
      if (bounds && !bounds.contains(L.latLng(detection.coordinate[0], detection.coordinate[1]))) return

      const showPlane = idx % planeDisplayPeriod.value === 0
      const hasAzimuth = detection.azimuth !== undefined && detection.azimuth !== null

      const item: any = {
        key: `${sensorId}-${idx}-${detection.timestamp || idx}`,
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
  debugInfo.value.selectedSensorsCount = selectedSensors.value.length
  debugInfo.value.renderTime = performance.now() - renderStart
}

// --- SETTINGS MANAGEMENT ---
watch(batchInterval, (newVal) => {
  batchIntervalLocal.value = newVal
}, { immediate: true })

function updateBatchInterval() {
  const newInterval = typeof batchIntervalLocal.value === 'string'
    ? parseFloat(batchIntervalLocal.value)
    : Number(batchIntervalLocal.value)

  if (isNaN(newInterval) || newInterval < 0.01 || newInterval > 10) {
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
  renderDetections()
}

function clearMapData() {
  sensorStore.clearDetections()
  planeIconsCache.clear()
  azimuthLinesCache.clear()
  detectionBuffer.value = []
  debugInfo.value.cacheSize = 0
}

function debugStore() {
  console.log('=== MAP COMPONENT DEBUG ===')
  console.log('Performance:', {
    renderTime: debugInfo.value.renderTime,
    visibleDetections: debugInfo.value.detectionsCount,
    cacheSize: debugInfo.value.cacheSize
  })
  console.log('Settings:', {
    maxVisiblePoints: maxVisiblePoints.value,
    planeDisplayPeriod: planeDisplayPeriod.value
  })
  console.log('Selected sensors:', selectedSensors.value)
  console.log('Cache stats:', {
    planeIcons: planeIconsCache.size,
    azimuthLines: azimuthLinesCache.size
  })

  sensorStore.debugReactivity()
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
      } else if ((mapContainer.value as any).webkitRequestFullscreen) {
        (mapContainer.value as any).webkitRequestFullscreen()
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen()
      } else if ((document as any).webkitExitFullscreen) {
        (document as any).webkitExitFullscreen()
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

// Watch sensors reactively
watch(sensors, () => {
  if (hasSelectedSensors.value) {
    renderDetections()
  }
}, { deep: true })

// Watch selectedSensors changes
watch(selectedSensors, () => {
  renderDetections()
}, { deep: true })

// --- LIFECYCLE ---
onMounted(async () => {
  await nextTick()
  updateMapView()

  if (leafletMap.value) {
    leafletMap.value.on('moveend', updateMapView)
    leafletMap.value.on('zoomend', updateMapView)
  }
})

onBeforeUnmount(() => {
  if (leafletMap.value) {
    leafletMap.value.off('moveend', updateMapView)
    leafletMap.value.off('zoomend', updateMapView)
  }

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

        <!-- Debug Info -->
        <div class="absolute top-2 left-2 bg-slate-800/90 text-gray-200 p-2 rounded shadow z-[1000] text-xs border border-slate-600">
          <div>Map: {{ debugInfo.mapInitialized ? '✅' : '❌' }}</div>
          <div>Sensors: {{ debugInfo.selectedSensorsCount }}</div>
          <div>Detections: {{ debugInfo.detectionsCount }}</div>
          <div>Render: {{ debugInfo.renderTime.toFixed(1) }}ms</div>
          <div>Cache: {{ debugInfo.cacheSize }}</div>
          <div>Stream: {{ hasSelectedSensors ? '🟢' : '🔴' }}</div>
        </div>

        <!-- Optimized Marker Rendering -->
        <template v-for="detection in detectionBuffer" :key="detection.key">
          <!-- Plane markers -->
          <l-marker
            v-if="detection.showPlane && detection.planeIcon"
            :lat-lng="detection.coordinate"
            :icon="detection.planeIcon"
          />

          <!-- Azimuth lines -->
          <l-polyline
            v-if="detection.hasAzimuth && detection.azimuthLine"
            :lat-lngs="detection.azimuthLine"
            :color="detection.color"
            :weight="2"
            :opacity="0.7"
          />

          <!-- Detection dots -->
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

        <div>
          <label class="font-semibold text-gray-300 text-sm">Max points</label>
          <input
            type="number"
            v-model.number="maxVisiblePoints"
            @change="updateSettings"
            min="10"
            max="500"
            class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100 text-sm"
          />
        </div>

        <div>
          <label class="font-semibold text-gray-300 text-sm">Plane period</label>
          <input
            type="number"
            v-model.number="planeDisplayPeriod"
            @change="updateSettings"
            min="1"
            max="10"
            class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100 text-sm"
          />
        </div>

        <div>
          <label class="font-semibold text-gray-300 text-sm">Line length</label>
          <input
            type="number"
            v-model.number="lineLength"
            @change="updateSettings"
            step="0.01"
            min="0.01"
            max="1"
            class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100 text-sm"
          />
        </div>

        <div>
          <label class="font-semibold text-gray-300 text-sm">Batch interval (s)</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            max="10"
            v-model.number="batchIntervalLocal"
            @change="updateBatchInterval"
            class="w-full border border-slate-600 rounded px-2 py-1 mt-1 bg-slate-900 text-gray-100 text-sm"
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
              @change="renderDetections"
              class="h-4 w-4 text-cyan-500 border-slate-600 bg-slate-800 rounded focus:ring-cyan-500"
            />
            <label for="azlines" class="text-sm text-gray-300">Azimuth lines</label>
          </div>
        </div>

        <div class="col-span-1 md:col-span-2 lg:col-span-3 grid grid-cols-3 gap-2">
          <button
            @click="clearMapData"
            class="bg-red-600 hover:bg-red-500 text-white px-3 py-2 rounded-xl transition-colors text-sm font-medium"
          >
            Clear Map
          </button>

          <button
            @click="debugStore"
            class="bg-gray-600 hover:bg-gray-500 text-white px-3 py-2 rounded-xl transition-colors text-sm font-medium"
          >
            Debug
          </button>

          <button
            @click="goFullscreen"
            class="bg-cyan-600 hover:bg-cyan-500 text-white px-3 py-2 rounded-xl transition-colors text-sm font-medium"
          >
            Fullscreen
          </button>
        </div>

        <div class="col-span-1 md:col-span-2 lg:col-span-3">
          <div class="text-sm bg-slate-900 p-3 rounded border border-slate-700 text-gray-200">
            <div class="flex items-center gap-2">
              <span class="font-semibold">Stream:</span>
              <span :class="hasSelectedSensors ? 'text-green-400' : 'text-red-400'">
                {{ hasSelectedSensors ? '🟢 Active' : '🔴 Inactive' }}
              </span>
            </div>
            <div class="mt-1">
              <span class="font-semibold">Selected:</span> {{ selectedSensorCount }} sensors
            </div>
            <div class="mt-1 text-xs text-gray-400">
              Interval: {{ sensorStore.batchInterval }}s | Cache: {{ debugInfo.cacheSize }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>