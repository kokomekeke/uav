<script setup lang="ts">
import { ref, watch, onMounted, onBeforeMount } from 'vue'
import { LMap, LTileLayer, LMarker, LPolyline } from '@vue-leaflet/vue-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import pW from '@/assets/p3.png'
import { useSensorStore } from '@/stores/sensor'
import { Sensor } from '@/types/sensor'

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

interface Detection {
  azimuth: number;
  coordinate: [number, number];
}

const detections = ref<Detection[]>([])

onBeforeMount(() => {
  updateDetections()
  console.log("beforeMount")
})

onMounted(() => {
  console.log("onmounted")
})

watch(() => sensorStore.sensors, updateDetections, { deep: true })

watch(detections, (n) => { console.log("detection debug:", n)})

async function updateDetections() {

  const newDetections: Detection[] = []

  for (const key in sensorStore.sensors) {
    const s = sensorStore.sensors[key]
    if (s.detections && s.detections.length > 0 && s.is_selected) {
      s.detections.forEach((d: any) => {
          const azimuth = d.properties?.lob_azim_deg
          const lat = d.geometry?.coordinates?.[1]
          const lon = d.geometry?.coordinates?.[0]

          if (
            typeof azimuth === 'number' &&
            typeof lat === 'number' &&
            typeof lon === 'number'
          ) {
            newDetections.push({
              azimuth,
              coordinate: [lat, lon]
            })
          }
        })
    }
  }

  // Csak a legfeljebb 10 elem
  detections.value = newDetections.slice(0, 10)
}

function computeAzimuthLine(coord: [number, number], azimuth: number): [number, number][] {
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

function haha() {
  console.log("hahaha")
}
</script>

<template>
  <l-map class="h-[500px] w-full z-1" :zoom="zoom" :center="center">
    <l-tile-layer :url="url" :attribution="attribution" class="z-1" />
    <div
      v-if="detections.length > 0"
    >
      <l-marker
        v-for="(detection, index) in detections"
        v-if="detection.coordinate && detection.coordinate.length === 2"
        :key="index"
        :lat-lng="detection.coordinate"
        :icon="planeIcon"
      />
      <l-polyline
        v-for="(detection, index) in detections"
        :key="'line-' + index"
        v-if="detections.length > 0 && computeAzimuthLine(detection.coordinate, detection.azimuth).length > 0"
        :lat-lngs="computeAzimuthLine(detection.coordinate, detection.azimuth)"
        color="red"
      />
    </div>


  </l-map>

</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
