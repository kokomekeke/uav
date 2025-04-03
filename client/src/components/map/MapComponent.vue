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
const markerLatLng = ref([47.4979, 19.0402]) // Marker pozíciója
const azimuth = ref(0) // Azimut tárolása
const polyline = ref({ coords: [], color: 'red' }) // Vonal adatai

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

// **Watch a detections változásra**
watch(
  () => sensorStore.selectedSensor?.detections,
  (newDetections) => {
    console.log("🔄 Új detections:", newDetections)

    if (newDetections && newDetections.features?.length > 0) {
      const latestDetection = newDetections.features[0] // Az első detektált objektum
      console.log("📍 Legutóbbi detection:", latestDetection)

      const coordinates = latestDetection.geometry?.coordinates
      const azimuthValue = latestDetection.properties?.lob_azim_deg

      if (coordinates && coordinates.length === 2 && azimuthValue !== undefined) {
        const [lng, lat] = coordinates // GeoJSON formátum [lng, lat] !

        // Frissítjük a marker pozícióját
        markerLatLng.value = [lat, lng]
        center.value = [lat, lng]

        // Kiszámítjuk a vonal végpontját az azimut alapján
        const destination = calculateDestination(lat, lng, azimuthValue)

        // Frissítjük a vonalat
        polyline.value.coords = [[lat, lng], destination]
        console.log("➡️ Vonal:", polyline.value.coords)
      }
    }
  },
  { deep: true }
)
</script>

<template>
  <l-map class="h-[500px] w-full z-1" :zoom="zoom" :center="center">
    <l-tile-layer :url="url" :attribution="attribution" class="z-1"></l-tile-layer>

    <!-- Marker -->
    <l-marker :lat-lng="markerLatLng" :icon="planeIcon"></l-marker>

    <!-- Azimut vonal -->
    <l-polyline v-if="polyline.coords.length > 0" :lat-lngs="polyline.coords" :color="polyline.color"></l-polyline>
  </l-map>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
