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
const { heatMapPoints } = storeToRefs(sensorStore)

// ✅ Perzisztens pont tároló - megtartja az utolsó N pontot
const persistedPoints = ref<Array<{
  coordinate: [number, number]
  lastUpdate: number
}>>([])

const zoom = ref(12)
const center = ref<[number, number] | null>(null)
let centerInitialized = false
const mapRef = ref<any>(null)
const leafletMap = shallowRef<L.Map | null>(null)
const heatLayer = shallowRef<any>(null)
const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
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
  updateInterval: 500, // ✅ 500ms (gyorsabb update)
  showRealtime: true,
  gridResolution: 4,
  maxPoints: 100 // ✅ Új: max pontszám
})

const stats = ref({
  totalPoints: 0,
  uniqueLocations: 0,
  maxIntensity: 0,
  avgIntensity: 0,
  totalHeatMapPoints: 0
})

const showControlPanel = ref(false)

// ✅ HEATMAP COMPUTED - A perzisztált pontokból dolgozik
const heatmapPoints = computed(() => {
  if (persistedPoints.value.length === 0) return []

  // ✅ Rendezés timestamp szerint (régebbi → újabb)
  const sortedPoints = [...persistedPoints.value].sort((a, b) => a.lastUpdate - b.lastUpdate)

  const locationMap = new Map<string, {
    count: number
    maxIntensity: number
    oldestIndex: number
    latestTimestamp: number
    lat: number
    lon: number
  }>()

  // ✅ Grid aggregáció
  sortedPoints.forEach((p, index) => {
    const [lat, lon] = p.coordinate
    const gridKey = `${lat.toFixed(dataSettings.value.gridResolution)},${lon.toFixed(dataSettings.value.gridResolution)}`

    if (!locationMap.has(gridKey)) {
      locationMap.set(gridKey, {
        count: 0,
        maxIntensity: 0,
        oldestIndex: index,
        latestTimestamp: 0,
        lat,
        lon
      })
    }

    const loc = locationMap.get(gridKey)!
    loc.count++

    // ✅ Intenzitás pozíció alapján: első pont (legrégebbi) = 0.1, utolsó (legújabb) = 1.0
    const positionFactor = sortedPoints.length > 1
      ? (index / (sortedPoints.length - 1)) * 0.9 + 0.1  // 0.1 → 1.0
      : 1.0

    loc.maxIntensity = Math.max(loc.maxIntensity, positionFactor)
    loc.oldestIndex = Math.min(loc.oldestIndex, index)
    loc.latestTimestamp = Math.max(loc.latestTimestamp, p.lastUpdate)
  })

  const newPoints: [number, number, number][] = []
  let globalMaxIntensity = 0
  let totalIntensity = 0

  locationMap.forEach((data) => {
    // ✅ Smooth intensity: count + pozíció faktor kombináció
    const countFactor = Math.min(data.count / 5, 1.0)
    let finalIntensity = (countFactor * 0.3 + data.maxIntensity * 0.7) // 70% pozíció, 30% count
    finalIntensity = Math.max(0.1, Math.min(finalIntensity, 1.0))

    globalMaxIntensity = Math.max(globalMaxIntensity, finalIntensity)
    totalIntensity += finalIntensity
    newPoints.push([data.lat, data.lon, finalIntensity])
  })

  stats.value = {
    totalPoints: newPoints.length,
    uniqueLocations: locationMap.size,
    maxIntensity: parseFloat(globalMaxIntensity.toFixed(3)),
    avgIntensity: newPoints.length > 0 ? parseFloat((totalIntensity / newPoints.length).toFixed(3)) : 0,
    totalHeatMapPoints: persistedPoints.value.length
  }

  return newPoints
})

// ✅ SMOOTH UPDATE: SOHA NEM RECREATE, CSAK SETLATLNGS!
function updateHeatmap(forceRecreate = false) {
  if (!leafletMap.value) return

  const points = heatmapPoints.value

  if (points.length === 0) {
    if (heatLayer.value) {
      heatLayer.value.setLatLngs([])
      heatLayer.value.redraw()
    }
    return
  }

  if (heatLayer.value && !forceRecreate) {
    heatLayer.value.setLatLngs(points)
    heatLayer.value.redraw()
    return
  }

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


function onMapReady() {
  if (mapRef.value?.leafletObject) {
    leafletMap.value = mapRef.value.leafletObject
    setTimeout(() => updateHeatmap(true), 500)
  }
}

// ✅ WATCH: Új adatok hozzáadása a perzisztált tárolóhoz ÉS heatmap frissítés
watch(heatMapPoints, (newPoints) => {
  if (!newPoints || newPoints.length === 0) return

  // Szűrjük ki az érvényes pontokat
  const validNewPoints = newPoints.filter(p => {
    if (!Array.isArray(p.coordinate) || p.coordinate.length !== 2) return false
    const [lat, lon] = p.coordinate
    return lat && lon && !isNaN(lat) && !isNaN(lon)
  })

  if (validNewPoints.length === 0) return

  // ✅ Hozzáadjuk az új pontokat a perzisztált listához
  persistedPoints.value = [
    ...persistedPoints.value,
    ...validNewPoints.map(p => ({
      coordinate: p.coordinate as [number, number],
      lastUpdate: p.lastUpdate
    }))
  ]

  // ✅ Rendezzük timestamp szerint és megtartjuk az utolsó N-et
  persistedPoints.value = persistedPoints.value
    .sort((a, b) => a.lastUpdate - b.lastUpdate)
    .slice(-dataSettings.value.maxPoints)

  console.log(`[Heatmap] 📊 Persisted points: ${persistedPoints.value.length}`)
}, { deep: false, immediate: true })

// ✅ WATCH: Perzisztált pontok változása → heatmap frissítés
watch(persistedPoints, () => {
  if (dataSettings.value.showRealtime) {
    updateHeatmap(false)
  }
}, { deep: false })

// ✅ Settings változás → recreate
watch(() => heatmapSettings.value, () => updateHeatmap(true), { deep: true })
watch(() => dataSettings.value.timeWindow, () => updateHeatmap(false))
watch(() => dataSettings.value.gridResolution, () => updateHeatmap(false))
watch(() => dataSettings.value.maxPoints, (newMaxPoints) => {
  // ✅ Limitáljuk a perzisztált pontokat az új max értékre
  if (persistedPoints.value.length > newMaxPoints) {
    persistedPoints.value = persistedPoints.value
      .sort((a, b) => a.lastUpdate - b.lastUpdate)
      .slice(-newMaxPoints)
    console.log(`[Heatmap] 📉 Limited persisted points to ${newMaxPoints}`)
  }
  updateHeatmap(false)
})

// ✅ Auto-update timer
let updateTimer: number | null = null

function startAutoUpdate() {
  if (updateTimer) clearInterval(updateTimer)
  updateTimer = setInterval(() => {
    if (dataSettings.value.showRealtime) {
      updateHeatmap(false)  // ✅ Smooth update
    }
  }, dataSettings.value.updateInterval)
}

function stopAutoUpdate() {
  if (updateTimer) {
    clearInterval(updateTimer)
    updateTimer = null
  }
}

watch(() => dataSettings.value.updateInterval, () => {
  if (dataSettings.value.showRealtime) {
    stopAutoUpdate()
    startAutoUpdate()
  }
})

watch(() => dataSettings.value.showRealtime, (isRealtime) => {
  isRealtime ? startAutoUpdate() : stopAutoUpdate()
})

// ✅ Center beállítása a perzisztált pontokból
watch(persistedPoints, (points) => {
  if (centerInitialized || points.length === 0) return

  console.log('[Heatmap] Setting center from persisted points:', points.length)

  const firstPoint = points[0]
  if (firstPoint && Array.isArray(firstPoint.coordinate) && firstPoint.coordinate.length === 2) {
    const [lat, lon] = firstPoint.coordinate
    if (!isNaN(lat) && !isNaN(lon)) {
      center.value = [lat, lon]
      centerInitialized = true
      console.log('[Heatmap] 🧭 Center set to first point:', center.value)
    }
  }
}, { deep: false, immediate: true })

function clearHeatmap() {
  if (heatLayer.value && leafletMap.value) {
    leafletMap.value.removeLayer(heatLayer.value)
    heatLayer.value = null
  }
  // ✅ Perzisztált pontok törlése
  persistedPoints.value = []
  console.log('[Heatmap] 🧹 Cleared all persisted points')
}

function manualUpdate() {
  updateHeatmap(true)
}

function exportData() {
  const data = {
    points: heatmapPoints.value,
    stats: stats.value,
    settings: { heatmap: heatmapSettings.value, data: dataSettings.value }
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `heatmap-geojson-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => startAutoUpdate())
onBeforeUnmount(() => {
  stopAutoUpdate()
  clearHeatmap()
})
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
          <span>Source Points:</span><strong class="text-gray-100">{{ stats.totalHeatMapPoints }}</strong>
          <span>Grid Points:</span><strong class="text-gray-100">{{ stats.totalPoints }}</strong>
          <span>Locations:</span><strong class="text-gray-100">{{ stats.uniqueLocations }}</strong>
          <span>Max Int:</span><strong class="text-cyan-400">{{ stats.maxIntensity }}</strong>
          <span>Avg Int:</span><strong class="text-cyan-400">{{ stats.avgIntensity }}</strong>
        </div>
        <div class="pt-1 border-t border-slate-700 text-gray-400">
          Showing: <strong class="text-gray-200">Last {{ dataSettings.maxPoints }} points</strong>
        </div>
      </div>

      <button v-if="props.showControls" @click="showControlPanel = !showControlPanel"
        class="absolute top-2 right-2 bg-slate-800/90 hover:bg-slate-700 text-gray-200 p-2 rounded shadow-lg border border-slate-600 z-10 transition-colors"
        :class="{ 'bg-cyan-600': showControlPanel }">
        ⚙️
      </button>

      <div v-if="props.showControls && showControlPanel"
        class="absolute top-14 right-2 bg-slate-800/95 text-gray-200 p-3 rounded-lg shadow-lg border border-slate-600 z-10 w-72 max-h-[calc(100%-4rem)] overflow-auto">
        <h4 class="font-semibold text-cyan-400 mb-3 text-sm">Heatmap Settings</h4>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-300 block mb-1">Max Points to Show: <strong>{{ dataSettings.maxPoints }}</strong></label>
            <input type="range" min="20" max="500" step="10" v-model.number="dataSettings.maxPoints" class="w-full accent-cyan-500" />
            <p class="text-xs text-gray-400 mt-1">Mindig a legújabb pontokat mutatja</p>
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
            <span class="text-xs text-gray-400">Old → New</span>
          </div>
          <div class="text-xs text-gray-400 text-center">Position-based Intensity</div>
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