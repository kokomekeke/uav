<script setup lang="ts">
import { ref, watch, onMounted, onBeforeMount, computed } from 'vue'
import { LMap, LTileLayer, LMarker, LPolyline } from '@vue-leaflet/vue-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import pW from '@/assets/p3.png'
import { useSensorStore } from '@/stores/sensor'
import { Sensor } from '@/types/sensor'
import { Detection } from '@/types/detection'

const zoom = ref(10)
const center = ref([47.4979, 19.0402])
const sensorStore = useSensorStore()
const sensors: { [id: number] : Sensor} = sensorStore.sensors
// Ha online vagy
// const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')

// Ha offline
const url = ref('/tiles/{z}/{x}/{y}.png')
const attribution = ref('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

// Repülő ikon
const planeIcon = L.icon({
  iconUrl: pW,
  iconSize: [64, 64],
  iconAnchor: [32, 32]
})

const detections = computed(() => sensorStore.detections)
const newDetectionSize = ref(Math.abs(sensorStore.detectionSize))

onBeforeMount(() => {
  console.log('beforeMount')
})

onMounted(() => {
  console.log('onmounted')
})

watch(detections, (n) => { console.log('detection debug:', n) }, { deep: true })
watch(() => detections.value.length, (n) => { console.log('detection debug11:', n) })

function updateDetectionSize() {
  console.log("updateee")
  // Ensure the input is a positive number
  const size = parseInt(newDetectionSize.value)
  if (!isNaN(size) && size > 0) {
    // Access the actual ref value property
    sensorStore.$patch({
      detectionSize: -size
    })
    // Or try this alternative approach
    // sensorStore.$state.detectionSize = size

    console.log('Detection size updated to:', -size)
    // Optionally refresh detections after changing the size
    sensorStore.fetchAllSelectedDetections()
  }
}

function computeAzimuthLine (coord: [number, number], azimuth: number): [number, number][] {
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

  const lat = coord[0]
  const lon = coord[1]

  const distance = 0.1

  const azimuthRad = azimuth * (Math.PI / 180)

  const endLat = lat + distance * Math.cos(azimuthRad)
  const endLon = lon + distance * Math.sin(azimuthRad)

  return [[lat, lon], [endLat, endLon]]
}

function getColorById (id) {
  const colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'cyan']
  return colors[id % colors.length] // egyszerű színkiosztás ID alapján
}
</script>

<template>
  <l-map class="h-[500px] w-full z-1" :zoom="zoom" :center="center">
    <l-tile-layer :url="url" :attribution="attribution" class="z-1" />
    <template v-if="detections && detections.length > 0">
      <template v-for="(detection, index) in detections" :key="index">
        <l-marker
          v-if="detection && detection.coordinate &&
                detection.coordinate.length === 2 &&
                typeof detection.coordinate[0] === 'number' &&
                typeof detection.coordinate[1] === 'number'"
          :lat-lng="detection.coordinate"
          :icon="planeIcon"
        />

        <!-- Only render polyline if detection and azimuth exist and function returns valid points -->
        <l-polyline
          v-if="detection && detection.coordinate &&
                detection.azimuth !== undefined &&
                computeAzimuthLine(detection.coordinate, detection.azimuth).length > 0"
          :lat-lngs="computeAzimuthLine(detection.coordinate, detection.azimuth)"
          :color="getColorById(detection.uavId)"
        />
      </template>
    </template>
  </l-map>

  <!-- Controls section with new input and button -->
  <div class="controls mt-2 flex gap-2 items-center">
    <button @click="sensorStore.clearDetections()" class="bg-red-500 text-white p-2 rounded">
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
      <button
        @click="updateDetectionSize()"
        class="ml-2 bg-blue-500 text-white p-2 rounded"
      >
        Update
      </button>
    </div>

    <div class="text-sm text-gray-500">
      Current size: {{ Math.abs(sensorStore.detectionSize) }}
    </div>
  </div>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>