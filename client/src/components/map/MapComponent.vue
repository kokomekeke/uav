<script setup lang="ts">
import { ref, onMounted, shallowRef, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import { LMap, LTileLayer, LMarker, LPolyline, LCircleMarker, LPopup } from '@vue-leaflet/vue-leaflet'
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
const {
  sensors,
  batchInterval,
  selectedSensors,
  selectedSensorIds,
  hasSelectedSensors,
  geoJsonData,
  geoJsonSettings,
  isGeoJsonEnabled
} = storeToRefs(sensorStore)

// --- MAP STATE ---
const zoom = ref(2)
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
const maxVisiblePoints = ref(50)
const lineLength = ref(0.05)
const planeDisplayPeriod = ref(4)
const showAzimuthLines = ref(true)

// --- GEOJSON SETTINGS (LOCAL) ---
const localGeoJsonSettings = ref({
  limit: 20,
  stride: 1,
  fetchPeriodSec: 1,
  showRaw: true,
  showFiltered: true,
  ttl: 80000,
  maxVisibleGeoJsonPoints: 200  // ✅ ÚJ: Max pontok száma
})

// --- ✅ ÚJ: STABLE GEOJSON BUFFER (NEM VÁLTOZIK MINDEN FRAME-BEN) ---
const geoJsonBuffer = shallowRef<Map<string, any>>(new Map())
let geoJsonUpdateThrottle: number | null = null

// --- DEBUG ---
const debugInfo = ref({
  mapInitialized: false,
  detectionsCount: 0,
  selectedSensorsCount: 0,
  renderTime: 0,
  cacheSize: 0,
  geoJsonCount: 0,
  geoJsonRaw: 0,
  geoJsonFiltered: 0
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

// --- ✅ OPTIMALIZÁLT: STABLE GEOJSON BUFFER UPDATE ---
function updateGeoJsonBuffer () {
  if (geoJsonUpdateThrottle) return

  geoJsonUpdateThrottle = window.setTimeout(() => {
    geoJsonUpdateThrottle = null
    _doUpdateGeoJsonBuffer()
  }, 100) // 100ms throttle
}

function _doUpdateGeoJsonBuffer () {
  const now = Date.now()
  const ttl = localGeoJsonSettings.value.ttl
  const maxPoints = localGeoJsonSettings.value.maxVisibleGeoJsonPoints

  const currentBuffer = geoJsonBuffer.value
  const newBuffer = new Map(currentBuffer)

  // ✅ 1. UPDATE/ADD új pontok
  geoJsonData.value.forEach(point => {
    const stableKey = `${point.id}-${point.type}`
    const age = now - point.timestamp
    const opacity = Math.max(0.1, 1 - (age / ttl))

    // Skip ha lejárt TTL
    if (opacity < 0.1) return

    // Koordináta validáció
    const [lat, lon] = point.coordinate
    if (isNaN(lat) || isNaN(lon)) return

    const existingItem = currentBuffer.get(stableKey)

    if (existingItem) {
      // ✅ CSAK AZ OPACITY ÉS AGE VÁLTOZIK, NEM RENDERELŐDIK ÚJ MARKER!
      existingItem.opacity = opacity
      existingItem.age = age
      existingItem.timestamp = point.timestamp
      newBuffer.set(stableKey, existingItem)
    } else {
      // ✅ ÚJ PONT HOZZÁADÁSA
      newBuffer.set(stableKey, {
        ...point,
        opacity,
        age,
        stableKey
      })
    }
  })

  // ✅ 2. REMOVE lejárt pontok
  for (const [key, item] of newBuffer.entries()) {
    // TODO: ezt a sort rendesen ellenőrizni, időzónák szerint
    const age = now - item.timestamp - 3600000
    if (age > ttl) {
      newBuffer.delete(key)
    }
  }
  // ✅ 3. LRU (Least Recently Used) - ha túl sok pont van
  if (newBuffer.size > maxPoints) {
    // Rendezés timestamp szerint (legrégebbi először)
    const sorted = Array.from(newBuffer.entries())
      .sort((a, b) => a[1].timestamp - b[1].timestamp)

    // Töröljük a legrégebbi pontokat
    const toDelete = sorted.slice(0, newBuffer.size - maxPoints)
    toDelete.forEach(([key]) => newBuffer.delete(key))
  }

  geoJsonBuffer.value = newBuffer

  debugInfo.value.geoJsonCount = newBuffer.size
  debugInfo.value.geoJsonRaw = Array.from(newBuffer.values()).filter(p => p.type === 'raw').length
  debugInfo.value.geoJsonFiltered = Array.from(newBuffer.values()).filter(p => p.type === 'filtered').length
}

// ✅ COMPUTED: Array-re konvertálás (stabil objektumok!)
const geoJsonPointsWithOpacity = computed(() => {
  return Array.from(geoJsonBuffer.value.values())
})

// --- FUNCTIONS ---

function getHeadingFromQuaternion ([q0, q1, q2, q3]: number[]): number {
  if (q0 === undefined || q1 === undefined || q2 === undefined || q3 === undefined) return 0
  const headingRad = Math.atan2(2 * (q0 * q3 + q1 * q2), q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3)
  const deg = headingRad * (180 / Math.PI)
  return deg < 0 ? deg + 360 : deg
}

function getHeading (sensor: Sensor): number {
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
  if (renderThrottle) return
  renderThrottle = setTimeout(() => {
    renderThrottle = null
    _doRenderDetections()
  }, 16)
}

function _doRenderDetections() {
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
      if (!Array.isArray(detection.coordinate)) return
      if (bounds && !bounds.contains(L.latLng(detection.coordinate[0], detection.coordinate[1]))) return

      const stableKey = `${sensorId}-${detection.timestamp || `idx-${idx}`}`
      const existingItem = oldBuffer.get(stableKey)

      if (existingItem) {
        existingItem.coordinate = detection.coordinate
        updatedBuffer.set(stableKey, existingItem)
        return
      }

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

      if (hasAzimuth && showAzimuthLines.value) {
        item.azimuthLine = computeAzimuthLine(detection.coordinate, detection.azimuth, true)
        item.hasAzimuth = true
      }
      updatedBuffer.set(stableKey, item)
    })
  })

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

const detectionBufferArray = computed(() => Array.from(detectionBuffer.value.values()))

// --- GEOJSON FUNCTIONS ---
function updateGeoJsonSettings() {
  console.log('[Map] Updating GeoJSON settings:', localGeoJsonSettings.value)
  sensorStore.updateGeoJsonSettings(localGeoJsonSettings.value)
}

function toggleGeoJsonFetch () {
  console.log('[Map] Toggle GeoJSON fetch, current state:', isGeoJsonEnabled.value)

  if (isGeoJsonEnabled.value) {
    sensorStore.stopGeoJsonFetch()
  } else {
    updateGeoJsonSettings()
    sensorStore.startGeoJsonFetch()
  }
}

// --- SETTINGS HANDLING ---
function updateBatchInterval () {
  const newInterval = Number(batchIntervalLocal.value)
  if (isNaN(newInterval) || newInterval < 0.01 || newInterval > 10) return
  sensorStore.$patch({ batchInterval: newInterval })
}

function updateSettings () {
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
  geoJsonBuffer.value = new Map()  // ✅ GeoJSON buffer is
  debugInfo.value.cacheSize = 0
}

function debugStore() {
  console.log('=== MAP COMPONENT DEBUG ===', debugInfo.value)
  console.log('GeoJSON buffer size:', geoJsonBuffer.value.size)
  console.log('GeoJSON computed points:', geoJsonPointsWithOpacity.value)
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

function onMapReady (mapInstance: any) {
  leafletMap.value = mapInstance
  mapBounds.value = mapInstance.getBounds()
  debugInfo.value.mapInitialized = true
  renderDetections()
  console.log('[Map] Map ready, bounds:', mapBounds.value)
}

// --- REAL-TIME CONFIG ---
const realtimeConfig = ref({
  ...sensorStore.realtimeConfig
})

const updateRealtimeConfig = () => {
  sensorStore.updateRealtimeConfig(realtimeConfig.value)
}

// --- ✅ OPTIMALIZÁLT WATCHERS ---

// ✅ GeoJSON data változás → buffer update
watch(geoJsonData, () => {
  updateGeoJsonBuffer()
}, { deep: false })

// ✅ TTL változás → buffer újraszámolás
watch(() => localGeoJsonSettings.value.ttl, () => {
  updateGeoJsonBuffer()
})

// ✅ Sensors watch
watch(sensors, () => {
  if (hasSelectedSensors.value) {
    renderDetections()
  }
}, { deep: true })

// ✅ Selected sensors watch
watch(selectedSensors, () => {
  renderDetections()
}, { deep: false })

// ✅ Batch interval watch
watch(batchInterval, val => (batchIntervalLocal.value = val), { immediate: true })

// --- LIFECYCLE ---
onMounted(async () => {
  await nextTick()
  updateMapView()
  leafletMap.value?.on('moveend', updateMapView)
  leafletMap.value?.on('zoomend', updateMapView)
  console.log('[Map] Component mounted')
})

onBeforeUnmount(() => {
  if (renderThrottle) clearTimeout(renderThrottle)
  if (geoJsonUpdateThrottle) clearTimeout(geoJsonUpdateThrottle)
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
          <div>GeoJSON: {{ debugInfo.geoJsonCount }} (🔴{{ debugInfo.geoJsonRaw }} 🔵{{ debugInfo.geoJsonFiltered }})</div>
          <div>Fetch: {{ isGeoJsonEnabled ? '✅' : '❌' }}</div>
          <div>Render: {{ debugInfo.renderTime.toFixed(1) }}ms</div>
          <div>Cache: {{ debugInfo.cacheSize }}</div>
        </div>

        <!-- Detection markers (SSE Stream) -->
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

        <!-- ✅ GeoJSON markers - STABLE KEY (nem változik minden frame-ben!) -->
        <template v-for="point in geoJsonPointsWithOpacity" :key="point.stableKey">
          <l-circle-marker
            v-if="point.coordinate?.length === 2"
            :lat-lng="point.coordinate"
            :radius="8"
            :color="point.type === 'raw' ? '#ff0000' : '#0000ff'"
            :fillColor="point.type === 'raw' ? '#ff0000' : '#0000ff'"
            :fillOpacity="point.opacity"
            :opacity="point.opacity"
            :weight="2"
            class="fade-marker"
          >
            <l-popup>
              <div class="text-xs">
                <div><strong>Type:</strong> {{ point.type === 'raw' ? '🔴 RAW' : '🔵 FILTERED' }}</div>
                <div><strong>ID:</strong> {{ point.id }}</div>
                <div v-if="point.roi_id"><strong>ROI:</strong> {{ point.roi_id }}</div>
                <div><strong>Age:</strong> {{ (point.age / 1000).toFixed(1) }}s</div>
                <div><strong>Opacity:</strong> {{ (point.opacity * 100).toFixed(0) }}%</div>
                <div><strong>Coord:</strong> [{{ point.coordinate[0].toFixed(4) }}, {{ point.coordinate[1].toFixed(4) }}]</div>
              </div>
            </l-popup>
          </l-circle-marker>
        </template>
      </l-map>
    </div>

    <!-- Controls -->
    <div class="flex-[1] mt-4 px-4 overflow-auto">
      <!-- EXISTING CONTROLS -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4 bg-slate-800 p-4 rounded-xl shadow-lg border border-slate-700">
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

      <!-- GEOJSON SETTINGS PANEL -->
      <div class="mt-4 bg-slate-800 p-4 rounded-xl border border-slate-700">
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-lg font-bold text-gray-100">🌍 GeoJSON Settings</h3>
          <button
            @click="toggleGeoJsonFetch"
            :class="[
              'px-4 py-2 font-semibold rounded-lg shadow transition',
              isGeoJsonEnabled ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700',
              'text-white'
            ]"
          >
            {{ isGeoJsonEnabled ? '⏸️ Stop' : '▶️ Start' }} GeoJSON Fetch
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          <div>
            <label class="block text-sm mb-1 text-gray-300">Limit (points)</label>
            <input v-model.number="localGeoJsonSettings.limit" type="number" min="1" max="1000"
                   @change="updateGeoJsonSettings"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100 border border-slate-600" />
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">Stride (every n-th)</label>
            <input v-model.number="localGeoJsonSettings.stride" type="number" min="1" max="100"
                   @change="updateGeoJsonSettings"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100 border border-slate-600" />
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">Fetch Period (sec)</label>
            <input v-model.number="localGeoJsonSettings.fetchPeriodSec" type="number" step="0.5" min="0.5" max="10"
                   @change="updateGeoJsonSettings"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100 border border-slate-600" />
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">TTL (ms)</label>
            <input v-model.number="localGeoJsonSettings.ttl" type="number" step="1000" min="1000"
                   @change="updateGeoJsonSettings"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100 border border-slate-600" />
          </div>

          <div class="flex items-center gap-2 mt-6">
            <input v-model="localGeoJsonSettings.showRaw" type="checkbox" @change="updateGeoJsonSettings"
                   class="h-4 w-4 text-red-500 border-slate-600 bg-slate-800 rounded focus:ring-red-500" />
            <span class="text-sm text-gray-300">🔴 Show RAW</span>
          </div>

          <div class="flex items-center gap-2 mt-6">
            <input v-model="localGeoJsonSettings.showFiltered" type="checkbox" @change="updateGeoJsonSettings"
                   class="h-4 w-4 text-blue-500 border-slate-600 bg-slate-800 rounded focus:ring-blue-500" />
            <span class="text-sm text-gray-300">🔵 Show FILTERED</span>
          </div>
        </div>

        <div class="mt-3 text-xs text-gray-400 space-y-1">
          <p>🔴 <strong>RAW:</strong> /comintgeoloc/geojson/raw/list_last/{{ localGeoJsonSettings.limit }}?stride={{ localGeoJsonSettings.stride }}</p>
          <p>🔵 <strong>FILTERED:</strong> /comintgeoloc/geojson/list_last/{{ localGeoJsonSettings.limit }}?stride={{ localGeoJsonSettings.stride }}</p>
          <p class="mt-2 text-cyan-400">
            📍 Max Visible: {{ localGeoJsonSettings.maxVisibleGeoJsonPoints }} points
          </p>
          <p class="mt-2 text-yellow-400" v-if="selectedSensorIds.length > 0">
            📍 Filtering by ROI IDs: {{ selectedSensorIds.join(', ') }}
          </p>
        </div>
      </div>

      <!-- REAL-TIME SETTINGS PANEL -->
      <div class="mt-4 bg-slate-800 p-4 rounded-xl border border-slate-700">
        <h3 class="text-lg font-bold mb-3 text-gray-100">⚡ Real-time Settings (SSE Stream)</h3>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label class="block text-sm mb-1 text-gray-300">Max Latency (ms)</label>
            <input v-model.number="realtimeConfig.maxLatencyMs" type="number" @change="updateRealtimeConfig"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100 border border-slate-600" />
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">Detection TTL (ms)</label>
            <input v-model.number="realtimeConfig.detectionTTL" type="number" @change="updateRealtimeConfig"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100 border border-slate-600" />
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">Buffer Size</label>
            <input v-model.number="realtimeConfig.circularBufferSize" type="number" @change="updateRealtimeConfig"
                   class="w-full px-2 py-1 bg-slate-700 rounded text-gray-100 border border-slate-600" />
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

/* ✅ SMOOTH OPACITY TRANSITION */
.fade-marker {
  transition: opacity 0.8s ease-in-out !important;
}
</style>