<script setup>
import { ref, watch } from 'vue'
import { LMap, LTileLayer, LMarker } from '@vue-leaflet/vue-leaflet'
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

const url = ref('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
const attribution = ref(
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
)

const markerLatLng = ref([47.4979, 19.0402]) // Marker pozíciója

const test = ref(0.001)

const planeIcon = L.icon({
  iconUrl: pW,
  iconSize: [64, 64], // Méret beállítása
  iconAnchor: [32, 32] // Középpont igazítása
})

watch(
  () => sensorStore.selectedSensor?.detections,
  (newDetections) => {
    console.log("---3-23-32323----new detections:", newDetections)

    if (newDetections && newDetections.features?.length > 0) {
      // Az első találat kinyerése
      const latestDetection = newDetections.features[0] // Az első objektum
      console.log("latest detection::::", latestDetection)

      // Koordináták kinyerése
      const coordinates = latestDetection.geometry?.coordinates
      if (coordinates && coordinates.length === 2) {
        const [lng, lat] = coordinates // GeoJSON formátumban [lng, lat] van!

        markerLatLng.value = [lat + test.value, lng + test.value + test.value] // Leafletnek [lat, lng] kell!
        center.value = [lat + test.value, lng + test.value + test.value] // Középre állítjuk a térképet
      }
      test.value = test.value + 0.001
    }
  },
  { deep: true } // Mély figyelés, hogy az adatváltozásokra is reagáljon
)

</script>

<template>
  <l-map class="h-[500px] w-full z-1" :zoom="zoom" :center="center">
    <l-tile-layer :url="url" :attribution="attribution" class="z-1"></l-tile-layer>
    <l-marker :lat-lng="markerLatLng" :icon="planeIcon"></l-marker>
  </l-map>
</template>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>

<style scoped>
@import "leaflet/dist/leaflet.css";
</style>
