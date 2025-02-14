<script setup>
import { ref } from 'vue'
// import { axios } from 'axios'

const isMenuOpen = ref(false)
const newSensor = ref('')
const sensors = ref([1, 2, 3])
const selectedSensor = ref(null)
const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}

const addSensor = () => {
  sensors.value.push(newSensor.value)
  newSensor.value = ''
}

const selectSensor = (sensor) => {
  selectedSensor.value = sensor
}
</script>

<template>
  <div class="h-full">
    <!-- Hamburger Button -->
    <button
      @click="toggleMenu"
      class="fixed top-4 left-4 z-50 h-10 w-10 p-2 bg-amber-950 flex flex-col items-center justify-center gap-1 rounded"
      v-if="!isMenuOpen"
    >
      <span class="h-0.5 rounded bg-gray-600 w-6"></span>
      <span class="h-0.5 rounded bg-gray-600 w-6"></span>
      <span class="h-0.5 rounded bg-gray-600 w-6"></span>
    </button>

    <!-- Sidebar -->
    <div
      class="fixed top-0 left-0 h-full w-64 bg-gray-800 p-5 transform transition-transform duration-300"
      :class="{ '-translate-x-full': !isMenuOpen, 'translate-x-0': isMenuOpen }"
    >
      <button @click="toggleMenu" class="text-white text-2xl mb-4">✖</button>
      <div class="bg-blue-500 flex-grow my-4 text-white p-4 text-center overflow-y-auto rounded-lg">
        <ul class="max-h-90">
          <li
              v-for="sensor in sensors" :key="sensor"
              @click="selectSensor"
              :class="{'bg-gray-500': selectedSensor === sensor, 'bg-gray-700 hover:bg-gray-500': selectedSensor !== sensor}"
          >
            <span @click="selectSensor(sensor)">{{ sensor }}</span>
            <button>❌</button>
          </li>
        </ul>
        <input v-model="newSensor" placeholder="Add new sensor">
        <button @click="addSensor">add sensor</button>
        <button>rms</button>
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
