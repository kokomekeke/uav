<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
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

onMounted(() => {
  updateDetections()
})

watch(() => sensorStore.sensors, updateDetections, { deep: true })

function updateDetections() {
  detections.value = []
  for (const key in sensorStore.sensors) {
    const s = sensorStore.sensors[key]
    if (s.detections && s.detections.length > 0) {
      s.detections.forEach((d) => {
        detections.value.push({
          azimuth: d.lob_azim_deg,
          coordinate: [d.uav_pos_lat, d.uav_pos_lon]
        })
      })
    }
  }
}

function computeAzimuthLine( coord: [number, number], azimuth: number): [number, number][] {
  const lat = coord[0]
  const lon = coord[1]

  const distance = 0.01 // ~1 km, állítható

  const azimuthRad = azimuth * (Math.PI / 180)

  const endLat = lat + distance * Math.cos(azimuthRad)
  const endLon = lon + distance * Math.sin(azimuthRad)

  return [[lat, lon], [endLat, endLon]]
}
</script>

<template>
  <l-map class="h-[500px] w-full z-1" :zoom="zoom" :center="center">
    <l-tile-layer :url="url" :attribution="attribution" class="z-1"></l-tile-layer>

    <!-- Marker minden szenzorhoz -->
    <template v-for="(sensor, index) in detections" :key="index">
      <l-marker :lat-lng="sensor.coordinate" :icon="planeIcon"></l-marker>
      <l-polyline :lat-lngs="computeAzimuthLine(sensor.coordinate, sensor.azimuth)" color="red"></l-polyline>
    </template>
  </l-map>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
