<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import { LMap, LTileLayer } from '@vue-leaflet/vue-leaflet'
import L from 'leaflet'
import { useSensorStore } from '@/stores/sensor'
import { storeToRefs } from 'pinia'
import 'leaflet/dist/leaflet.css'
import 'leaflet.heat'

// --- PROPS ---
interface Props {
  showControls?: boolean
  compactMode?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  showControls: true,
  compactMode: false
})

// --- STORE ---
const sensorStore = useSensorStore()
const { sensors } = storeToRefs(sensorStore)

// --- MAP STATE ---
const zoom = ref(12)
const center = ref([47.4979, 19.0402])
const mapRef = ref<any>(null)
const leafletMap = shallowRef<L.Map | null>(null)
const heatLayer = shallowRef<any>(null)

// MAP SOURCE
const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
// const url = ref('/tiles/{z}/{x}/{y}.png')

const attribution = ref('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

// --- HEATMAP SETTINGS ---
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

// --- DATA SETTINGS ---
const dataSettings = ref({
  timeWindow: 60,
  intensityMode: 'count' as 'count' | 'frequency' | 'signal',
  updateInterval: 1000,
  showRealtime: true
})

// --- STATISTICS ---
const stats = ref({
  totalPoints: 0,
  uniqueLocations: 0,
  maxIntensity: 0,
  avgIntensity: 0
})

// --- SHOW/HIDE CONTROLS ---
const showControlPanel = ref(false)

// --- COMPUTED HEATMAP DATA ---
const heatmapPoints = computed(() => {
  const points: [number, number, number][] = []
  const now = performance.now()
  const timeWindowMs = dataSettings.value.timeWindow * 1000
  const locationMap = new Map<string, { count: number, intensity: number }>()

  console.log('[Heatmap] Computing points, now:', now)

  Object.values(sensors.value).forEach(sensor => {
    if (!sensor.is_selected || !sensor.detections) return

    console.log(`[Heatmap] Sensor ${sensor.uav_id}: ${sensor.detections.length} detections`)

    sensor.detections.forEach(detection => {
      const detectionTime = detection.timestamp || 0
      const age = now - detectionTime

      if (age > timeWindowMs) {
        return
      }

      const [lat, lon] = detection.coordinate
      if (!lat || !lon) {
        console.warn('[Heatmap] Invalid coordinates:', detection.coordinate)
        return
      }

      const gridKey = `${lat.toFixed(4)},${lon.toFixed(4)}`

      if (!locationMap.has(gridKey)) {
        locationMap.set(gridKey, { count: 0, intensity: 0 })
      }

      const location = locationMap.get(gridKey)!
      location.count++

      let intensity = 0
      switch (dataSettings.value.intensityMode) {
        case 'count':
          intensity = location.count
          break
        case 'frequency':
          intensity = detection.frequency ? detection.frequency / 1e9 : 0
          break
        case 'signal':
          intensity = detection.elevation || 0
          break
      }

      location.intensity = Math.max(location.intensity, intensity)
    })
  })

  let maxIntensity = 0
  locationMap.forEach((data, key) => {
    const [lat, lon] = key.split(',').map(Number)
    const normalizedIntensity = Math.min(data.intensity / 5, 1.0)
    maxIntensity = Math.max(maxIntensity, normalizedIntensity)
    points.push([lat, lon, normalizedIntensity])
  })

  console.log('[Heatmap] Total points:', points.length)

  stats.value = {
    totalPoints: points.length,
    uniqueLocations: locationMap.size,
    maxIntensity: parseFloat(maxIntensity.toFixed(2)),
    avgIntensity: points.length > 0
      ? parseFloat((points.reduce((sum, p) => sum + p[2], 0) / points.length).toFixed(2))
      : 0
  }

  return points
})

// --- HEATMAP RENDERING ---
function updateHeatmap(forceRecreate = false) {
  console.log('[Heatmap] updateHeatmap called, forceRecreate:', forceRecreate)

  if (!leafletMap.value) {
    console.warn('[Heatmap] ⚠️ leafletMap not ready yet')
    return
  }

  const points = heatmapPoints.value
  console.log('[Heatmap] Points to render:', points.length)

  // Ha nincs adat, töröljük a layer-t
  if (points.length === 0) {
    if (heatLayer.value) {
      console.log('[Heatmap] No points, removing layer')
      leafletMap.value.removeLayer(heatLayer.value)
      heatLayer.value = null
    }
    return
  }

  try {
    // Ha van layer és nem kell újra létrehozni, csak frissítjük az adatokat
    if (heatLayer.value && !forceRecreate) {
      console.log('[Heatmap] 🔄 Updating existing heat layer data')
      heatLayer.value.setLatLngs(points)
      heatLayer.value.redraw()
    } else {
      // Töröljük a régi layer-t ha van
      if (heatLayer.value) {
        console.log('[Heatmap] Removing old heat layer')
        leafletMap.value.removeLayer(heatLayer.value)
        heatLayer.value = null
      }

      // Új layer létrehozása
      console.log('[Heatmap] Creating new heat layer with settings:', {
        radius: heatmapSettings.value.radius,
        blur: heatmapSettings.value.blur,
        maxZoom: heatmapSettings.value.maxZoom,
        max: heatmapSettings.value.max,
        minOpacity: heatmapSettings.value.minOpacity
      })

      heatLayer.value = (L as any).heatLayer(points, {
        radius: heatmapSettings.value.radius,
        blur: heatmapSettings.value.blur,
        maxZoom: heatmapSettings.value.maxZoom,
        max: heatmapSettings.value.max,
        minOpacity: heatmapSettings.value.minOpacity,
        gradient: heatmapSettings.value.gradient
      }).addTo(leafletMap.value)

      console.log('[Heatmap] ✅ Heat layer created and added to map')
    }
  } catch (error) {
    console.error('[Heatmap] ❌ Error creating/updating heat layer:', error)
  }
}

// --- MAP READY EVENT ---
function onMapReady() {
  console.log('[Heatmap] 🗺️ Map ready event fired')
  if (mapRef.value?.leafletObject) {
    leafletMap.value = mapRef.value.leafletObject
    console.log('[Heatmap] ✅ leafletMap reference set')

    // Kis késleltetés után frissítjük
    setTimeout(() => {
      updateHeatmap(true) // Első betöltéskor létrehozzuk
    }, 500)
  }
}

// --- WATCHERS ---
// Adatok változásakor csak frissítjük a layer-t (nem hozzuk létre újra)
watch(heatmapPoints, (newPoints) => {
  console.log('[Heatmap] heatmapPoints changed, count:', newPoints.length)
  if (dataSettings.value.showRealtime) {
    updateHeatmap(false) // NEM force recreate
  }
}, { deep: false })

// Settings változásakor újra létrehozzuk a layer-t
watch(() => heatmapSettings.value, () => {
  console.log('[Heatmap] heatmapSettings changed - recreating layer')
  updateHeatmap(true) // FORCE recreate
}, { deep: true })

// Intensity mode változásakor frissítjük (nem recreate, mert csak az adatok változnak)
watch(() => dataSettings.value.intensityMode, () => {
  console.log('[Heatmap] intensityMode changed')
  updateHeatmap(false)
})

// Time window változásakor frissítjük (nem recreate)
watch(() => dataSettings.value.timeWindow, () => {
  console.log('[Heatmap] timeWindow changed')
  updateHeatmap(false)
})

// --- AUTO UPDATE ---
let updateTimer: number | null = null

function startAutoUpdate() {
  if (updateTimer) clearInterval(updateTimer)
  updateTimer = setInterval(() => {
    if (dataSettings.value.showRealtime) {
      updateHeatmap(false) // Automatikus frissítés, nem recreate
    }
  }, dataSettings.value.updateInterval)
  console.log('[Heatmap] ⏱️ Auto-update started, interval:', dataSettings.value.updateInterval)
}

function clearHeatmap() {
  if (heatLayer.value && leafletMap.value) {
    leafletMap.value.removeLayer(heatLayer.value)
    heatLayer.value = null
  }
  console.log('[Heatmap] 🧹 Heatmap cleared')
}

// Manual update button
function manualUpdate() {
  console.log('[Heatmap] Manual update triggered')
  updateHeatmap(true) // Force recreate on manual update
}

// --- LIFECYCLE ---
onMounted(() => {
  console.log('[Heatmap] 🚀 Component mounted')
  startAutoUpdate()
})

onBeforeUnmount(() => {
  console.log('[Heatmap] 🛑 Component unmounting')
  if (updateTimer) clearInterval(updateTimer)
  clearHeatmap()
})
</script>

<template>
  <div class="flex flex-col w-full h-full">
    <div class="flex-1 relative rounded-xl overflow-visible">
      <l-map
        ref="mapRef"
        :zoom="zoom"
        :center="center"
        class="w-full h-full z-0"
        @ready="onMapReady"
      >
        <l-tile-layer :url="url" :attribution="attribution" />
      </l-map>

      <!-- Info Panel -->
      <div class="absolute top-2 left-2 bg-slate-800/90 text-gray-200 p-2 rounded shadow-lg border border-slate-600 z-10 text-xs">
        <div class="flex items-center gap-2">
          <span class="text-cyan-400">🔥</span>
          <div class="flex gap-3">
            <span>Points: <strong>{{ stats.totalPoints }}</strong></span>
            <span>Max: <strong>{{ stats.maxIntensity }}</strong></span>
            <span>{{ dataSettings.intensityMode }}</span>
          </div>
        </div>
      </div>

      <!-- Control Panel Toggle -->
      <button
        v-if="props.showControls"
        @click="showControlPanel = !showControlPanel"
        class="absolute top-2 right-2 bg-slate-800/90 hover:bg-slate-700 text-gray-200 p-2 rounded shadow-lg border border-slate-600 z-10 transition-colors"
        :class="{ 'bg-cyan-600': showControlPanel }"
      >
        ⚙️
      </button>

      <!-- Collapsible Control Panel -->
      <div
        v-if="props.showControls && showControlPanel"
        class="absolute top-14 right-2 bg-slate-800/95 text-gray-200 p-3 rounded-lg shadow-lg border border-slate-600 z-10 w-64 max-h-[calc(100%-4rem)] overflow-auto"
      >
        <h4 class="font-semibold text-cyan-400 mb-3 text-sm">Heatmap Settings</h4>
        <!-- Quick Settings -->
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-300 block mb-1">
              Intensity Mode
            </label>
            <select
              v-model="dataSettings.intensityMode"
              class="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-gray-100"
            >
              <option value="count">Count</option>
              <option value="frequency">Frequency</option>
              <option value="signal">Signal</option>
            </select>
          </div>

          <div>
            <label class="text-xs text-gray-300 block mb-1">
              Time Window: {{ dataSettings.timeWindow }}s
            </label>
            <input
              type="range"
              min="10"
              max="300"
              step="10"
              v-model.number="dataSettings.timeWindow"
              class="w-full accent-cyan-500"
            />
          </div>

          <div>
            <label class="text-xs text-gray-300 block mb-1">
              Radius: {{ heatmapSettings.radius }}
            </label>
            <input
              type="range"
              min="10"
              max="50"
              v-model.number="heatmapSettings.radius"
              class="w-full accent-cyan-500"
            />
          </div>

          <div>
            <label class="text-xs text-gray-300 block mb-1">
              Blur: {{ heatmapSettings.blur }}
            </label>
            <input
              type="range"
              min="5"
              max="30"
              v-model.number="heatmapSettings.blur"
              class="w-full accent-cyan-500"
            />
          </div>

          <div>
            <label class="text-xs text-gray-300 block mb-1">
              Opacity: {{ heatmapSettings.minOpacity }}
            </label>
            <input
              type="range"
              min="0.1"
              max="1"
              step="0.1"
              v-model.number="heatmapSettings.minOpacity"
              class="w-full accent-cyan-500"
            />
          </div>

          <div class="flex items-center gap-2">
            <input
              type="checkbox"
              id="realtime-compact"
              v-model="dataSettings.showRealtime"
              class="h-3 w-3 text-cyan-500 border-slate-600 bg-slate-700 rounded"
            />
            <label for="realtime-compact" class="text-xs text-gray-300">
              Real-time Updates
            </label>
          </div>

          <div class="pt-2 border-t border-slate-700">
            <button
              @click="manualUpdate"
              class="w-full bg-cyan-600 hover:bg-cyan-500 text-white px-3 py-1 rounded text-xs transition-colors"
            >
              🔄 Force Refresh
            </button>
          </div>
        </div>
      </div>

      <!-- Legend -->
      <div class="absolute bottom-2 right-2 bg-slate-800/90 text-gray-200 p-2 rounded shadow-lg border border-slate-600 z-10">
        <div class="flex items-center gap-2">
          <div class="w-20 h-3 rounded" style="background: linear-gradient(to right, blue, cyan, lime, yellow, red)"></div>
          <span class="text-xs text-gray-400">Intensity</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";

input[type="range"] {
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  cursor: pointer;
}

input[type="range"]::-webkit-slider-track {
  background: #475569;
  height: 0.4rem;
  border-radius: 0.2rem;
}

input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  background: #06b6d4;
  height: 1rem;
  width: 1rem;
  border-radius: 50%;
  margin-top: -0.3rem;
}

input[type="range"]::-moz-range-track {
  background: #475569;
  height: 0.4rem;
  border-radius: 0.2rem;
}

input[type="range"]::-moz-range-thumb {
  background: #06b6d4;
  height: 1rem;
  width: 1rem;
  border-radius: 50%;
  border: none;
}
</style>