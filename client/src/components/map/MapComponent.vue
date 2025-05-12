<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick, shallowRef, onBeforeUnmount } from 'vue'
import { LMap, LTileLayer, LMarker, LPolyline } from '@vue-leaflet/vue-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import pW from '@/assets/p3.png'
import { useSensorStore } from '@/stores/sensor'
import { storeToRefs } from 'pinia'
import { useWebWorkerFn } from '@vueuse/core'

const zoom = ref(10)
const center = ref([47.4979, 19.0402])
const sensorStore = useSensorStore()
const { sensors } = storeToRefs(sensorStore)

// Használjunk shallowRef-et a lokális detekciók számára
const localDetections = shallowRef([])

// Csak az alapvető tulajdonságokat figyeljük, ne az egész objektumot
const sensorsList = computed(() => {
  return Object.values(sensors.value || {}).filter(s => s.is_selected)
})

// Map referencia
const mapRef = ref(null)
const leafletMap = shallowRef(null)

// Alapvető térkép beállítások
const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
const attribution = ref('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

// Ikonok létrehozása és memóriában tartása
const planeIcon = L.icon({
  iconUrl: pW,
  iconSize: [64, 64],
  iconAnchor: [32, 32]
})

// Színek előre definiálása
const lineColors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'cyan']
const dotColors = ['blue', 'red', 'orange', 'green', 'cyan', 'magenta', 'yellow']

// Dot ikonokat előre létrehozzuk minden színben
const dotIcons = dotColors.map(color => L.divIcon({
  className: '',
  html: `<div style="
    background-color: ${color};
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 1px solid white;
    box-shadow: 0 0 2px rgba(0,0,0,0.5);
  "></div>`,
  iconSize: [12, 12],
  iconAnchor: [6, 6]
}))

// Beállítások
const newDetectionSize = ref(Math.abs(sensorStore.detectionSize))
const autoZoom = ref(false)
const mapBounds = shallowRef(null)
const maxVisiblePoints = ref(100) // Alapértelmezetten maximum ennyi pontot jelenítünk meg szenzoronként

// Nagyobb méretű adatok esetén csökkentsük a frissítési gyakoriságot
const updateThrottle = ref(500) // ms

let updateTimer = null

// Optimalizált számításokhoz cache
const azimuthLineCache = new Map()

// Láthatatlan pontok nem kerülnek feldolgozásra
const isInViewport = (coords) => {
  if (!mapBounds.value || !coords || coords.length !== 2) return false
  return mapBounds.value.contains(L.latLng(coords[0], coords[1]))
}

// Kombinált detekciós lista létrehozása az összes aktív szenzorból
const visibleDetections = computed(() => {
  const selectedSensors = sensorsList.value
  if (!selectedSensors || selectedSensors.length === 0) return []

  // Csak a kiválasztott szenzorok detekcióit gyűjtjük össze
  let allDetections = []

  selectedSensors.forEach(sensor => {
    if (!sensor.detections || !Array.isArray(sensor.detections)) return

    // Szűrjük és limitáljuk a szenzoronkénti pontokat
    const sensorDetections = sensor.detections
      .slice(-maxVisiblePoints.value) // Csak a legutolsó N pont
      .filter(d => d && d.coordinate && isInViewport(d.coordinate)) // Csak a látható területen lévők

    allDetections = [...allDetections, ...sensorDetections]
  })

  // Rendezzük időbélyeg szerint
  allDetections.sort((a, b) => a.timestamp - b.timestamp)

  // Korlátozzuk a teljes pontszámot a teljesítmény érdekében
  return allDetections.slice(-maxVisiblePoints.value * 2)
})

// Metódus a térkép nézet frissítésére
function updateMapView () {
  if (!mapRef.value || !mapRef.value.leafletObject) return

  leafletMap.value = mapRef.value.leafletObject
  mapBounds.value = leafletMap.value.getBounds()
}

function computeAzimuthLine (coord: [number, number], azimuth: number, id: number): [number, number][] {
  if (
    !coord ||
    coord.length !== 2 ||
    typeof coord[0] !== 'number' ||
    typeof coord[1] !== 'number' ||
    typeof azimuth !== 'number' ||
    isNaN(coord[0]) || isNaN(coord[1]) || isNaN(azimuth)
  ) {
    return []
  }

  const roundedLat = Math.round(coord[0] * 1000) / 1000
  const roundedLon = Math.round(coord[1] * 1000) / 1000
  const roundedAzimuth = Math.round(azimuth)
  const cacheKey = `${roundedLat}_${roundedLon}_${roundedAzimuth}_${id}`

  if (azimuthLineCache.has(cacheKey)) {
    return azimuthLineCache.get(cacheKey)
  }

  const lat = coord[0]
  const lon = coord[1]
  const distance = 0.1
  const azimuthRad = azimuth * (Math.PI / 180)
  const endLat = lat + distance * Math.cos(azimuthRad)
  const endLon = lon + distance * Math.sin(azimuthRad)

  const result = [[lat, lon], [endLat, endLon]]

  azimuthLineCache.set(cacheKey, result)

  if (azimuthLineCache.size > 1000) {
    const keys = Array.from(azimuthLineCache.keys()).slice(0, 200)
    keys.forEach(key => azimuthLineCache.delete(key))
  }

  return result
}

// Optimalizált segédfüggvények
function getColorById (id) {
  return lineColors[id % lineColors.length]
}

function getDotIconById (id: number) {
  return dotIcons[id % dotIcons.length]
}

// Frissítés throttling
function throttledUpdate () {
  if (updateTimer) clearTimeout(updateTimer)

  updateTimer = setTimeout(() => {
    updateMapView()
  }, updateThrottle.value)
}


// Figyelés a kiválasztott szenzorok változására
watch(sensorsList, () => {
  throttledUpdate()
}, { deep: false }) // Shallow figyelés a teljesítmény érdekében

// Térképre nagyítás új pont érkezésekor
watch(() => visibleDetections.value, (newVal) => {
  if (autoZoom.value && newVal && newVal.length > 0 && leafletMap.value) {
    const lastPoint = newVal[newVal.length - 1]
    if (lastPoint && lastPoint.coordinate) {
      leafletMap.value.setView(lastPoint.coordinate, zoom.value)
    }
  }
}, { deep: false })

// Beállítások frissítése
function updateSettings () {
  const size = newDetectionSize.value
  if (!isNaN(size) && size > 0) {
    sensorStore.$patch({
      detectionSize: size
    })
  }

  // Frissítsük a térkép nézetet
  throttledUpdate()
}

// Adatok törlése
function clearMapData () {
  sensorStore.clearDetections()
  azimuthLineCache.clear()
  console.log('Térkép adatok törölve')
}

// Inicializálás
onMounted(async () => {
  // Várunk egy kis időt, hogy a térkép komponens betöltődjön
  await nextTick()

  try {
    // Inicalizáljuk a térképet
    if (mapRef.value && mapRef.value.leafletObject) {
      leafletMap.value = mapRef.value.leafletObject
      mapBounds.value = leafletMap.value.getBounds()

      // Event listener a térkép mozgatáshoz
      leafletMap.value.on('moveend', throttledUpdate)
      leafletMap.value.on('zoomend', throttledUpdate)
    }
  } catch (error) {
    console.error('Hiba a térkép inicializálása során:', error)

    // Próbáljuk újra egy kis késleltetéssel
    setTimeout(() => {
      try {
        if (mapRef.value && mapRef.value.leafletObject) {
          leafletMap.value = mapRef.value.leafletObject
          mapBounds.value = leafletMap.value.getBounds()

          // Event listener a térkép mozgatáshoz
          leafletMap.value.on('moveend', throttledUpdate)
          leafletMap.value.on('zoomend', throttledUpdate)
        }
      } catch (innerError) {
        console.error('Nem sikerült inicializálni a térképet:', innerError)
      }
    }, 500)
  }
})

// Erőforrások felszabadítása
onBeforeUnmount(() => {
  if (updateTimer) {
    clearTimeout(updateTimer)
  }

  if (leafletMap.value) {
    leafletMap.value.off('moveend', throttledUpdate)
    leafletMap.value.off('zoomend', throttledUpdate)
  }

  // Cache ürítése
  azimuthLineCache.clear()
})
</script>

<template>
  <div v-bind="$attrs" class="h-[500px] w-full z-1">
    <l-map ref="mapRef" :zoom="zoom" :center="center">
      <l-tile-layer :url="url" :attribution="attribution" class="z-1" />

      <!-- Csak a látható pontokat jelenítjük meg -->
      <template v-for="(detection, index) in visibleDetections" :key="`det-${detection.uavId}-${index}`">
        <!-- Repülő marker -->
        <l-marker
          v-if="detection && detection.coordinate &&
                detection.coordinate.length === 2 &&
                typeof detection.coordinate[0] === 'number' &&
                typeof detection.coordinate[1] === 'number'"
          :lat-lng="detection.coordinate"
          :icon="planeIcon"
        />

        <!-- Azimuth vonal -->
        <l-polyline
          v-if="detection && detection.coordinate &&
                detection.azimuth !== undefined &&
                computeAzimuthLine(detection.coordinate, detection.azimuth, detection.uavId).length > 0"
          :lat-lngs="computeAzimuthLine(detection.coordinate, detection.azimuth, detection.uavId)"
          :color="getColorById(detection.uavId)"
          :weight="2"
        />

        <!-- Pont ikon -->
        <l-marker
          v-if="detection && detection.coordinate &&
                detection.coordinate.length === 2 &&
                typeof detection.coordinate[0] === 'number' &&
                typeof detection.coordinate[1] === 'number'"
          :lat-lng="detection.coordinate"
          :icon="getDotIconById(detection.uavId)"
        />
      </template>
    </l-map>
  </div>

  <div class="controls mt-2 flex gap-2 items-center flex-wrap">
    <button @click="clearMapData" class="bg-red-500 text-white p-2 rounded">
      Clear Map
    </button>

    <div class="flex items-center">
      <label for="detectionSize" class="mr-2">Detection Size:</label>
      <input
        id="detectionSize"
        type="number"
        v-model="newDetectionSize"
        min="1"
        class="border border-gray-300 rounded p-2 w-20"
      />
    </div>

    <div class="flex items-center ml-4">
      <label for="maxVisible" class="mr-2">Max visible:</label>
      <input
        id="maxVisible"
        type="number"
        v-model="maxVisiblePoints"
        min="10"
        max="500"
        class="border border-gray-300 rounded p-2 w-20"
      />
      <button
        @click="updateSettings"
        class="ml-2 bg-blue-500 text-white p-2 rounded"
      >
        Update
      </button>
    </div>

    <div class="flex items-center ml-4">
      <input
        id="autoZoom"
        type="checkbox"
        v-model="autoZoom"
        class="mr-2"
      />
      <label for="autoZoom">Auto-zoom</label>
    </div>

    <div class="ml-4">
      <label for="updateThrottle" class="mr-2">Update Speed (ms):</label>
      <input
        id="updateThrottle"
        type="number"
        v-model="updateThrottle"
        min="100"
        max="2000"
        step="100"
        class="border border-gray-300 rounded p-2 w-20"
      />
    </div>

<!--    <div class="ml-4">-->
<!--      <label for="updateSampleRate" class="mr-2">Sampling Rate:</label>-->
<!--      <input-->
<!--        id="updateSampleRate"-->
<!--        type="number"-->
<!--        v-model="updateSampleRate"-->
<!--        min="1"-->
<!--        max="100"-->
<!--        step="1"-->
<!--        class="border border-gray-300 rounded p-2 w-20"-->
<!--      />-->
<!--    </div>-->

    <div class="text-sm text-gray-500 ml-4">
      Visible points: {{ visibleDetections.length }} | Sensors: {{ sensorsList.length }}
    </div>
  </div>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
