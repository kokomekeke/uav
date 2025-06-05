<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick, shallowRef, onBeforeUnmount } from 'vue'
import { LMap, LTileLayer, LMarker, LPolyline } from '@vue-leaflet/vue-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import pW from '@/assets/dir1.png'
import { useSensorStore } from '@/stores/sensor'
import { storeToRefs } from 'pinia'
// Make sure to properly import the fullscreen plugin
import 'leaflet.fullscreen'
import 'leaflet.fullscreen/Control.FullScreen.css'
import { Sensor } from '@/types/sensor'

const zoom = ref(10)
const center = ref([47.4979, 19.0402])
const sensorStore = useSensorStore()
const { sensors, batchInterval } = storeToRefs(sensorStore)
const batchIntervalLocal = ref(sensorStore.batchInterval)

watch(batchInterval, (newVal) => {
  batchIntervalLocal.value = newVal
}, { immediate: true })

function updateBatchInterval () {
  // Konvertáljuk számmá, ha string lenne (input mezőből)
  const newInterval = typeof batchIntervalLocal.value === 'string'
    ? parseFloat(batchIntervalLocal.value)
    : Number(batchIntervalLocal.value)

  // Validáció
  if (isNaN(newInterval) || newInterval < 0.1 || newInterval > 10) {
    console.warn('Invalid batch interval value:', batchIntervalLocal.value, 'converted to:', newInterval)
    // Visszaállítjuk az előző érvényes értékre
    batchIntervalLocal.value = sensorStore.batchInterval
    return
  }

  // Store frissítése
  sensorStore.$patch({
    batchInterval: newInterval
  })

  console.log('Batch interval updated to:', newInterval)
}

// Debug információk
const debugInfo = ref({
  sensorsCount: 0,
  selectedSensorsCount: 0,
  visibleDetectionsCount: 0,
  mapInitialized: false
})

// Csak az alapvető tulajdonságokat figyeljük, ne az egész objektumot
const sensorsList = computed(() => {
  const result: { [id: number]: Sensor } = {}
  let count = 0

  // console.log('🔍 Sensors raw data:', sensors.value)

  for (const key in sensors.value) {
    const sensor = sensors.value[key]
    // console.log(`Sensor ${key}:`, {
    //   exists: !!sensor,
    //   is_selected: sensor?.is_selected,
    //   detections_count: sensor?.detections?.length || 0,
    //   detections: sensor?.detections
    // })

    if (sensor?.is_selected) {
      result[Number(key)] = sensor
      count++
    }
  }

  debugInfo.value.selectedSensorsCount = count
  // console.log('✅ Selected sensors:', result)

  return result
})

// Map referencia
const mapRef = ref(null)
const leafletMap = shallowRef(null)
// Ref to store the map container element
const mapContainer = ref(null)

// Alapvető térkép beállítások
const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
const attribution = ref('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

function getHeading (sensor) {
  const q0 = sensor.last_pos_q0 // w komponens
  const q1 = sensor.last_pos_q1 // x komponens
  const q2 = sensor.last_pos_q2 // y komponens
  const q3 = sensor.last_pos_q3 // z komponens
  // console.log('q0', q0, 'q1', q1, 'q2', q2, 'q3', q3)

  // Ellenőrizzük, hogy vannak-e érvényes értékek
  if (q0 === undefined || q1 === undefined || q2 === undefined || q3 === undefined) {
    console.warn('Missing quaternion values, using default heading 0')
    return 0
  }

  // Yaw (heading) kiszámítása quaternion-ból
  const headingRad = Math.atan2(
    2.0 * (q0 * q3 + q1 * q2),
    q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3
  )

  // Átváltjuk fokra (0-360 között)
  let headingDeg = headingRad * (180 / Math.PI)
  if (headingDeg < 0) {
    headingDeg += 360
  }
  // console.log('HEADING: ', headingDeg)
  return headingDeg
}

function getPlaneIconById (Id: number) {
  const heading = sensors.value[Id] ? getHeading(sensors.value[Id]) : 0

  return L.divIcon({
    className: '',
    html: `<div style="
      width: 64px;
      height: 64px;
      background: url('${pW}') no-repeat center center;
      background-size: contain;
      transform: rotate(${heading + 90}deg);
    "></div>`,
    iconSize: [64, 64],
    iconAnchor: [32, 32]
  })
}

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
// New settings for line length and plane display period
const lineLength = ref(0.1) // Default line length in degrees (approximately 11km)
const planeDisplayPeriod = ref(1) // Show plane every N points

// Nagyobb méretű adatok esetén csökkentsük a frissítési gyakoriságot
const updateThrottle = ref(500) // ms

let updateTimer = null

// Optimalizált számításokhoz cache
const azimuthLineCache = new Map()

// Láthatatlan pontok nem kerülnek feldolgozásra - JAVÍTVA: alapértelmezetten true-t adunk vissza ha nincs mapBounds
const isInViewport = (coords) => {
  if (!coords || coords.length !== 2) return false
  if (!mapBounds.value) {
    // console.log('No map bounds available, showing all points')
    return true // Ha nincs mapBounds, akkor mutassunk mindent
  }

  const result = mapBounds.value.contains(L.latLng(coords[0], coords[1]))
  // console.log(`Point [${coords[0]}, ${coords[1]}] in viewport:`, result)
  return result
}

const flatDetections = computed(() => {
  const result = []

  Object.entries(visibleDetections.value).forEach(([sensorId, detections]) => {
    const sensorIdNum = Number(sensorId)

    detections.forEach((detection, index) => {
      const isValid = detection &&
                     detection.coordinate &&
                     detection.coordinate.length === 2 &&
                     typeof detection.coordinate[0] === 'number' &&
                     typeof detection.coordinate[1] === 'number'

      if (isValid) {
        result.push({
          ...detection,
          uniqueKey: `${sensorId}-${index}`,
          sensorId: sensorIdNum,
          showPlane: index % planeDisplayPeriod.value === 0,
          hasAzimuth: detection.azimuth !== undefined,
          azimuthLine: detection.azimuth !== undefined
            ? computeAzimuthLine(detection.coordinate, detection.azimuth, sensorIdNum)
            : [],
          color: getColorsByRoiId(detection, sensorIdNum),
          dotIcon: getDotIconById(sensorIdNum),
          planeIcon: getPlaneIconById(sensorIdNum)
        })
      }
    })
  })

  return result
})

const visibleDetections = computed(() => {
  const selectedSensors = sensorsList.value
  // console.log('🎯 Computing visible detections from sensors:', selectedSensors)

  if (!selectedSensors || Object.keys(selectedSensors).length === 0) {
    // console.log('❌ No selected sensors')
    return {}
  }

  const result: { [id: number]: any[] } = {}
  let totalVisibleCount = 0

  Object.entries(selectedSensors).forEach(([key, sensor]) => {
    // console.log(`Processing sensor ${key}:`, {
    //   has_detections: !!sensor.detections,
    //   detections_type: typeof sensor.detections,
    //   detections_length: sensor.detections?.length || 0,
    //   first_detection: sensor.detections?.[0]
    // })

    if (!sensor.detections || !Array.isArray(sensor.detections)) {
      console.log(`❌ Sensor ${key}: no valid detections array`)
      return
    }

    const sensorDetections = sensor.detections
      .slice(-maxVisiblePoints.value)
      .filter(d => {
        const hasCoord = d && d.coordinate && Array.isArray(d.coordinate) && d.coordinate.length === 2
        const isValid = hasCoord && typeof d.coordinate[0] === 'number' && typeof d.coordinate[1] === 'number'
        const inView = isValid ? isInViewport(d.coordinate) : false

        return isValid && inView
      })
      .sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))

    console.log(`Sensor ${key} filtered detections:`, sensorDetections.length)

    if (sensorDetections.length > 0) {
      result[Number(key)] = sensorDetections
      totalVisibleCount += sensorDetections.length
    }
  })

  debugInfo.value.visibleDetectionsCount = totalVisibleCount
  // console.log('✅ Final visible detections:', result, 'Total count:', totalVisibleCount)

  return result
})

// Metódus a térkép nézet frissítésére
function updateMapView () {
  if (!mapRef.value || !mapRef.value.leafletObject) {
    // console.log('❌ Map not ready for view update')
    return
  }

  leafletMap.value = mapRef.value.leafletObject
  mapBounds.value = leafletMap.value.getBounds()
  debugInfo.value.mapInitialized = true

  // console.log('🗺️ Map view updated, bounds:', mapBounds.value?.toBBoxString())
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
  const cacheKey = `${roundedLat}_${roundedLon}_${roundedAzimuth}_${id}_${lineLength.value}`

  if (azimuthLineCache.has(cacheKey)) {
    return azimuthLineCache.get(cacheKey)
  }

  const lat = coord[0]
  const lon = coord[1]
  const distance = lineLength.value // Use the configured line length
  const azimuthRad = azimuth * (Math.PI / 180)
  const endLat = lat + distance * Math.cos(azimuthRad)
  const endLon = lon + distance * Math.sin(azimuthRad)

  const result = [[lat, lon], [endLat, endLon]]

  azimuthLineCache.set(cacheKey, result)

  if (azimuthLineCache.size > 1000) {
  // Töröljük a legrégebbi 800 elemet, csak 200-at hagyunk
    const keys = Array.from(azimuthLineCache.keys())
    const keysToDelete = keys.slice(0, keys.length - 200)
    keysToDelete.forEach(key => azimuthLineCache.delete(key))
  }
  return result
}

function hasDifferentRoiFromDetectionList (detections, uav_id) {
  if (!Array.isArray(detections)) return false

  for (const det of detections) {
    if (det?.roi_id !== null && det.roi_id !== uav_id) {
      return true
    }
  }
  return false
}

function getColorsByRoiId (detection, sensorId) {
  const sensor = sensorsList.value[sensorId]
  if (!sensor) {
    return lineColors[sensorId % lineColors.length]
  }

  if (hasDifferentRoiFromDetectionList(sensor.detections, sensor.uav_id)) {
    if (detection.roi_id !== null && detection.roi_id !== undefined) {
      return lineColors[detection.roi_id % lineColors.length]
    }
  }

  if (detection.roi_id !== null && detection.roi_id !== undefined) {
    return lineColors[detection.roi_id % lineColors.length]
  }

  return lineColors[sensor.uav_id % lineColors.length]
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
watch(sensorsList, (newVal) => {
  // console.log('👀 Sensors list changed:', newVal)
  throttledUpdate()
}, { deep: false })

// Térképre nagyítás új pont érkezésekor
watch(() => visibleDetections.value, (newVal) => {
  // console.log('👀 Visible detections changed:', newVal)

  if (autoZoom.value && newVal && Object.keys(newVal).length > 0 && leafletMap.value) {
    // Kiválasztjuk az összes detekciót, majd összefűzzük egy tömbbé
    const allDetections = Object.values(newVal).flat()

    // Ha van legalább egy detekció, akkor az utolsó koordinátájára zoomolunk
    const lastPoint = allDetections[allDetections.length - 1]

    if (lastPoint && lastPoint.coordinate) {
      // console.log('🎯 Auto-zooming to:', lastPoint.coordinate)
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
  updateBatchInterval()
  // Frissítsük a térkép nézetet
  throttledUpdate()
}

// Adatok törlése
function clearMapData () {
  sensorStore.clearDetections()
  azimuthLineCache.clear()
  // console.log('Térkép adatok törölve')
}

// Debug funkció a store állapotának ellenőrzésére
function debugStore () {
  console.log('=== STORE DEBUG ===')
  console.log('Raw sensors:', sensors.value)
  console.log('Selected sensors:', sensorsList.value)
  console.log('Visible detections:', visibleDetections.value)
  console.log('Map initialized:', debugInfo.value.mapInitialized)
  console.log('Map bounds:', mapBounds.value?.toBBoxString())
  console.log('Batch interval:', sensorStore.batchInterval)
  console.log('Selected sensor:', sensorStore.selectedSensor)
  console.log('Active workers:', Object.keys(sensorStore.detectionWorkers || {}).length)
  console.log('==================')
}

// Inicializálás
onMounted(async () => {
  // console.log('🚀 Component mounting...')

  // Várunk egy kis időt, hogy a térkép komponens betöltődjön
  await nextTick()

  try {
    // Inicalizáljuk a térképet
    if (mapRef.value && mapRef.value.leafletObject) {
      leafletMap.value = mapRef.value.leafletObject
      mapBounds.value = leafletMap.value.getBounds()
      debugInfo.value.mapInitialized = true

      // console.log('✅ Map initialized successfully')

      // Event listener a térkép mozgatáshoz
      leafletMap.value.on('moveend', throttledUpdate)
      leafletMap.value.on('zoomend', throttledUpdate)
    } else {
      // console.log('❌ Map not ready yet')
    }
  } catch (error) {
    console.error('Hiba a térkép inicializálása során:', error)

    // Próbáljuk újra egy kis késleltetéssel
    setTimeout(() => {
      try {
        if (mapRef.value && mapRef.value.leafletObject) {
          leafletMap.value = mapRef.value.leafletObject
          mapBounds.value = leafletMap.value.getBounds()
          debugInfo.value.mapInitialized = true

          // console.log('✅ Map initialized successfully (retry)')

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

// Fixed fullscreen function
function goFullscreen () {
  if (!mapContainer.value) {
    console.warn('Fullscreen nem elérhető: nem található a térkép elem referencia.')
    return
  }

  try {
    // Use the native browser fullscreen API
    if (!document.fullscreenElement &&
        !document.mozFullScreenElement &&
        !document.webkitFullscreenElement &&
        !document.msFullscreenElement) {
      // Request fullscreen
      if (mapContainer.value.requestFullscreen) {
        mapContainer.value.requestFullscreen()
      } else if (mapContainer.value.mozRequestFullScreen) {
        mapContainer.value.mozRequestFullScreen()
      } else if (mapContainer.value.webkitRequestFullscreen) {
        mapContainer.value.webkitRequestFullscreen()
      } else if (mapContainer.value.msRequestFullscreen) {
        mapContainer.value.msRequestFullscreen()
      } else {
        console.warn('Fullscreen API nem támogatott ebben a böngészőben')
      }
    } else {
      // Exit fullscreen
      if (document.exitFullscreen) {
        document.exitFullscreen()
      } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen()
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen()
      } else if (document.msExitFullscreen) {
        document.msExitFullscreen()
      }
    }
  } catch (e) {
    console.error('Hiba történt a fullscreen átváltása során:', e)
  }
}
</script>

<template>
  <div v-bind="$attrs" class="h-[60vh] w-full z-1" ref="mapContainer">
    <l-map ref="mapRef" :zoom="zoom" :center="center">
      <l-tile-layer :url="url" :attribution="attribution" class="z-1" />

      <!-- Debug info -->
      <div class="absolute top-2 left-2 bg-white p-2 rounded shadow z-10 text-xs">
        <div>Map: {{ debugInfo.mapInitialized ? '✅' : '❌' }}</div>
        <div>Sensors: {{ debugInfo.selectedSensorsCount }}</div>
        <div>Detections: {{ debugInfo.visibleDetectionsCount }}</div>
      </div>

      <!-- Iterate through each sensor's detections -->
      <template v-for="detection in flatDetections" :key="detection.uniqueKey">
        <!-- Plane marker -->
        <l-marker
          v-if="detection.showPlane"
          :lat-lng="detection.coordinate"
          :icon="detection.planeIcon"
        />

        <!-- Azimuth line -->
        <l-polyline
          v-if="detection.hasAzimuth && detection.azimuthLine.length > 0"
          :lat-lngs="detection.azimuthLine"
          :color="detection.color"
          :weight="2"
        />

        <!-- Detection dot marker -->
        <l-marker
          :lat-lng="detection.coordinate"
          :icon="detection.dotIcon"
        />
      </template>
    </l-map>
  </div>

  <div class="w-full h-40 mt-4 px-4">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 bg-white p-4 rounded shadow">
      <div>
        <label class="font-semibold">Detection size</label>
        <input type="number" v-model="newDetectionSize" @change="updateSettings" class="w-full border rounded px-2 py-1 mt-1" />
      </div>

      <div>
        <label class="font-semibold">Max visible points</label>
        <input type="number" v-model="maxVisiblePoints" @change="updateSettings" class="w-full border rounded px-2 py-1 mt-1" />
      </div>

      <div>
        <label class="font-semibold">Line length (km)</label>
        <input type="number" v-model="lineLength" @change="updateSettings" class="w-full border rounded px-2 py-1 mt-1" />
      </div>

      <div>
        <label class="font-semibold">Plane display period (points)</label>
        <input type="number" v-model="planeDisplayPeriod" @change="updateSettings" class="w-full border rounded px-2 py-1 mt-1" />
      </div>

      <!-- ÚJ: Batch interval beállítás -->
      <div>
        <label class="font-semibold">Batch interval (s)</label>
        <input
          type="number"
          step="0.01"
          min="0.05"
          max="10"
          v-model="batchIntervalLocal"
          @change="updateBatchInterval"
          class="w-full border rounded px-2 py-1 mt-1"
        />
      </div>

      <div class="flex items-center gap-2">
        <input type="checkbox" id="autoz" v-model="autoZoom" @change="updateSettings" />
        <label for="autoz" class="font-semibold">Auto zoom</label>
      </div>

      <div>
        <button @click="clearMapData" class="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600 w-full">
          Clear Map
        </button>
      </div>

      <div>
        <button @click="debugStore" class="bg-gray-500 text-white px-4 py-2 rounded hover:bg-gray-600 w-full">
          Debug info
        </button>
      </div>

      <div>
        <button @click="goFullscreen" class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 w-full">
          Fullscreen
        </button>
      </div>

      <!-- ÚJ: Stream állapot információ -->
      <div class="col-span-1 md:col-span-2 lg:col-span-1">
        <div class="text-sm bg-gray-100 p-2 rounded">
          <div>Stream: {{ sensorStore.selectedSensor ? '🟢 Aktív' : '🔴 Inaktív' }}</div>
          <div>Interval: {{ sensorStore.batchInterval }}s</div>
        </div>
      </div>
    </div>
  </div>

</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
