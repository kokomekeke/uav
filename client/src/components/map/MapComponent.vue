<script setup lang="ts">
import { ref, watch, onMounted, onBeforeMount } from 'vue'
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

const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
const attribution = ref('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

// Repülő ikon
const planeIcon = L.icon({
  iconUrl: pW,
  iconSize: [64, 64],
  iconAnchor: [32, 32]
})

const detections = sensorStore.detections

onBeforeMount(() => {
  console.log('beforeMount')
})

onMounted(() => {
  console.log('onmounted')
})

watch(detections, (n) => { console.log('detection debug:', n) })

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

  const distance = 0.01 // kb. 1km

  const azimuthRad = azimuth * (Math.PI / 180)

  const endLat = lat + distance * Math.cos(azimuthRad)
  const endLon = lon + distance * Math.sin(azimuthRad)

  return [[lat, lon], [endLat, endLon]]
}
</script>

<template>
  <l-map class="h-[500px] w-full z-1" :zoom="zoom" :center="center">
    <l-tile-layer :url="url" :attribution="attribution" class="z-1" />
    <template v-if="detections && detections.length > 0">
      <template v-for="(detection, index) in detections" :key="index">
        <!-- Only render marker if detection and coordinates exist -->
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
          color="red"
        />
      </template>
    </template>
  </l-map>

  <!-- Optional: Add a clear button as suggested -->
  <div class="controls mt-2">
    <button @click="sensorStore.clearDetections()" class="bg-red-500 text-white p-2 rounded">
      Clear Map
    </button>
  </div>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
