<script setup>
import { ref, watch } from 'vue'
import { LMap, LTileLayer, LMarker, LPolyline } from '@vue-leaflet/vue-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import pW from '@/assets/p3.png'
import { useSensorStore } from '@/stores/sensor'

// **Fix Leaflet ikon betöltési hiba**
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).href,
  iconUrl: new URL('leaflet/dist/images/marker-icon.png', import.meta.url).href,
  shadowUrl: new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).href
})

const sensorStore = useSensorStore()

const zoom = ref(13)
const center = ref([47.4979, 19.0402]) // Budapest példaként
const sensors = ref([]) // Szenzorok listája

const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
const attribution = ref('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')

// Repülő ikon beállítása
const planeIcon = L.icon({
  iconUrl: pW,
  iconSize: [64, 64],
  iconAnchor: [32, 32]
})

// **Függvény az új pont kiszámításához az azimut irányában**
function calculateDestination(lat, lng, azimuth, distanceKm = 5) {
  const R = 6371 // Föld sugara km-ben
  const azimuthRad = (azimuth * Math.PI) / 180 // Fok -> radián

  const latRad = (lat * Math.PI) / 180
  const lngRad = (lng * Math.PI) / 180

  const newLatRad = Math.asin(
    Math.sin(latRad) * Math.cos(distanceKm / R) +
    Math.cos(latRad) * Math.sin(distanceKm / R) * Math.cos(azimuthRad)
  )

  const newLngRad = lngRad + Math.atan2(
    Math.sin(azimuthRad) * Math.sin(distanceKm / R) * Math.cos(latRad),
    Math.cos(distanceKm / R) - Math.sin(latRad) * Math.sin(newLatRad)
  )

  return [(newLatRad * 180) / Math.PI, (newLngRad * 180) / Math.PI] // Visszaalakítjuk fokba
}

// **Watch a sensors változásra**
watch(
  () => sensorStore.selectedSensors, // Több szenzort figyelünk
  (newSensors) => {
    console.log("🔄 Új sensors lista:", newSensors)

    sensors.value = newSensors.map(sensor => {
      const latestDetection = sensor.detections?.features?.[0]
      if (!latestDetection) return null

      const coordinates = latestDetection.geometry?.coordinates
      const azimuthValue = latestDetection.properties?.lob_azim_deg

      if (coordinates && coordinates.length === 2 && azimuthValue !== undefined) {
        const [lng, lat] = coordinates // GeoJSON formátum [lng, lat]
        const destination = calculateDestination(lat, lng, azimuthValue)

        return {
          id: sensor.id,
          position: [lat, lng],
          azimuthLine: [[lat, lng], destination]
        }
      }
      return null
    }).filter(Boolean)
  },
  { deep: true }
)
</script>

<template>
  <l-map class="h-[500px] w-full z-1" :zoom="zoom" :center="center">
    <l-tile-layer :url="url" :attribution="attribution" class="z-1"></l-tile-layer>

    <!-- Marker minden szenzorhoz -->
    <template v-for="sensor in sensors" :key="sensor.id">
      <l-marker :lat-lng="sensor.position" :icon="planeIcon"></l-marker>
      <l-polyline v-if="sensor.azimuthLine.length > 0" :lat-lngs="sensor.azimuthLine" color="red"></l-polyline>
    </template>
  </l-map>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
