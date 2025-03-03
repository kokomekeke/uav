<script setup>
import { ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()

const props = defineProps({
  ipPort: String,
  isConnected: Boolean,
  isMenuOpen: Boolean
})
const isOpen = ref(props.isMenuOpen)
const newSensor = ref('')
const sensors = ref([])
const selectedSensor = ref(null)

const emit = defineEmits(['update:isMenuOpen'])

watch(() => props.isMenuOpen, (newValue) => {
  console.log('newvalue:', isOpen.value)
  isOpen.value = newValue
})

const toggleMenu = () => {
  isOpen.value = !isOpen.value
  emit('update:isMenuOpen', isOpen.value)
}

const addSensor = () => {
  sensors.value.push(newSensor.value)
  newSensor.value = ''
}

const selectSensor = (sensor, event) => {
  selectedSensor.value = sensor
  console.log('sensor: ', sensor)
  if (event) event.stopPropagation()
}

watchEffect(() => {
  console.log('BurgerMenu ipPort:', props.ipPort)
  console.log('BurgerMenu:', props.isConnected)
  if (props.isConnected && props.ipPort) {
    console.log('Fetching sensors...')
    fetchSensors()
  }
})

watch(() => route.params.sensor, (newSensor) => {
  selectedSensor.value = newSensor
  console.log('Új szenzor kiválasztva:', newSensor)
  fetchSensors()
})

const fetchSensors = async () => {
  try {
    const url = `${props.ipPort}/v1/uav/`
    console.log('Fetching from:', url)
    const response = await axios.get(url)

    if (!response || !response.data) {
      console.error('API válasz üres vagy undefined!')
      sensors.value = [1, 2]
      return
    }

    if (response.status !== 200) {
      console.error(`API hiba: ${response.status} - ${response.statusText}`)
      sensors.value = [2, 3]
      return
    }

    if (Array.isArray(response.data)) {
      sensors.value = response.data
    } else {
      console.error('API response is not an array:', response.data)
      sensors.value = response.data.sensors || []
    }

    console.log('Updated sensors list:', sensors.value)
  } catch (error) {
    console.error('Hiba az API hívás során:', error)
    sensors.value = ['10.1.1.113', '10.1.1.119']
  }
}
</script>

<template>
  <div class="flex min-h-screen transition-all duration-300">
    <div v-if="isOpen" class="w-64"></div> <!-- Sidebar helykitöltő -->

    <div class="flex-1">
      <!-- Hamburger Button -->
      <button
        @click="toggleMenu"
        class="fixed top-4 left-4 z-50 h-10 w-10 p-2 bg-blue-600 flex flex-col items-center justify-center gap-1 rounded"
        v-if="!isOpen"
      >
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
      </button>

      <!-- Sidebar -->
      <div
        class="fixed top-0 left-0 h-full w-64 bg-gray-800 p-5 z-40 transition-transform duration-300"
        :class="{ '-translate-x-full': !isOpen, 'translate-x-0': isOpen }"
      >
        <button @click="toggleMenu" class="text-white text-2xl mb-4">✖</button>
        <div class="bg-blue-500 flex-grow my-4 text-white p-4 text-center overflow-y-auto rounded-lg">
          <ul v-if="props.isConnected" class="max-h-90">
            <li
              v-for="sensor in sensors" :key="sensor"
              @click="selectSensor(sensor, $event)"
              :class="{'bg-gray-500': selectedSensor === sensor, 'bg-gray-700 hover:bg-gray-500': selectedSensor !== sensor}"
            >
              <router-link :to="`/sensor/${sensor}`" class="text-white hover:underline">
                {{ sensor }}
              </router-link>
              <button>❌</button>
            </li>
          </ul>
          <input v-model="newSensor" placeholder="Add new sensor">
          <button @click="addSensor">add sensor</button>
          <button>rms</button>
        </div>
      </div>

      <!-- Fő tartalom -->
<!--      <router-view :key="route.fullPath"/>-->
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
