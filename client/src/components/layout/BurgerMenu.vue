<script setup>
import { ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useConnectionStore } from '@/stores/connection'
import { useSensorStore } from '@/stores/sensor'

const route = useRoute()
const connectionStore = useConnectionStore()
const { ipPort, isConnected } = storeToRefs(connectionStore)

const sensorStore = useSensorStore()
const { sensors } = storeToRefs(sensorStore)

const props = defineProps({
  isMenuOpen: Boolean
})
const isOpen = ref(props.isMenuOpen)

const emit = defineEmits(['update:isMenuOpen'])

watch(() => props.isMenuOpen, (newValue) => {
  isOpen.value = newValue
})

watch(() => sensorStore.sensors, (newSensors) => {
  console.log('🔄 Szenzor lista változott:', newSensors)
}, { deep: true })

const toggleMenu = () => {
  isOpen.value = !isOpen.value
  emit('update:isMenuOpen', isOpen.value)
}

</script>

<template>
  <div class="flex min-h-screen transition-all duration-300">
    <div v-if="isOpen" class="w-64"></div>

    <div class="flex-1">
      <button
        @click="toggleMenu"
        class="fixed top-4 left-4 z-50 h-10 w-10 p-2 bg-blue-600 flex flex-col items-center justify-center gap-1 rounded"
        v-if="!isOpen"
      >
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
      </button>

      <div
        class="fixed top-0 left-0 h-full w-64 bg-gray-800 p-5 z-40 transition-transform duration-300"
        :class="{ '-translate-x-full': !isOpen, 'translate-x-0': isOpen }"
      >
        <button @click="toggleMenu" class="text-white text-2xl mb-4">✖</button>

        <div class="bg-blue-500 flex-grow my-4 text-white p-4 text-center overflow-y-auto rounded-lg">
          <p v-if="sensorStore.isLoading" class="text-yellow-300">Betöltés...</p>
          <p v-if="sensorStore.errorMessage" class="text-red-500">{{ sensorStore.errorMessage }}</p>
          <ul class="max-h-90">
            <li
              v-for="sensor in sensors"
              :key="sensor"
              @click="sensorStore.selectSensor(sensor)"
              :class="{'bg-gray-500': sensorStore.selectedSensor === sensor, 'bg-gray-700 hover:bg-gray-500': sensorStore.selectedSensor !== sensor}"
              class="p-2 flex justify-between items-center rounded cursor-pointer"
            >
              <router-link :to="`/sensor/${sensor}`" class="text-white hover:underline flex-grow text-left">
                {{ sensor }}
              </router-link>
              <button @click="sensorStore.removeSensor(sensor)" class="text-red-400 hover:text-red-600 ml-2">❌</button>
            </li>
          </ul>

          <div class="mt-4">
            <input
              v-model="sensorStore.newSensor"
              placeholder="Új szenzor hozzáadása"
              class="text-black p-2 w-full rounded"
            />
            <button @click="sensorStore.addSensor" class="mt-2 w-full bg-green-500 text-white p-2 rounded hover:bg-green-700">
              + Szenzor hozzáadása
            </button>
          </div>

          <button class="mt-4 w-full bg-gray-700 text-white p-2 rounded hover:bg-gray-900">
            RMS
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Alapértelmezett rejtett állapot */
.-translate-x-full {
  transform: translateX(-100%);
}

.translate-x-0 {
  transform: translateX(0);
}
</style>
