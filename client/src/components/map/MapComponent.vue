<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { LMap, LTileLayer, LMarker, LPolyline } from '@vue-leaflet/vue-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import pW from '@/assets/p3.png'
import { useSensorStore } from '@/stores/sensor'

const zoom = ref(10)
const center = ref([47.4979, 19.0402])
const sensorStore = useSensorStore()
const sensors: { [id: number] : Sensor} = ref(sensorStore.sensors)

const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
const attribution = ref('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

// Repülő ikon
const planeIcon = L.icon({
  iconUrl: pW,
  iconSize: [64, 64],
  iconAnchor: [32, 32]
})

const detections = ref([])


for (const key in sensors.value) {
  if (sensors.value[key].detections.length !== 0) {
    // Az észlelések geometriáját hozzáadjuk
    detections.value.push(...sensors.value[key].detections.map(detection => detection.geometry))
  }
}

</script>


<template>
  <l-map class="h-[500px] w-full z-1" :zoom="zoom" :center="center">
    <l-tile-layer :url="url" :attribution="attribution" class="z-1"></l-tile-layer>

    <!-- Marker minden szenzorhoz -->
    <template v-for="sensor in detections" :key="sensor.id">
      <l-marker :lat-lng="sensor.position" :icon="planeIcon"></l-marker>
      <l-polyline v-if="sensor.azimuthLine.length > 0" :lat-lngs="sensor.azimuthLine" color="red"></l-polyline>
    </template>
  </l-map>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
