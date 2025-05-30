<script setup>
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useSensorStore } from '@/stores/sensor'
import NewSensorModal from '@/components/common/NewSensorModal.vue'
import axios from 'axios'

const sensorStore = useSensorStore()
const { sensors } = storeToRefs(sensorStore)

const props = defineProps({
  isMenuOpen: Boolean
})
const isMenuOpen = ref(props.isMenuOpen)
const isRemoveDialogOpen = ref(false)
const isModalOpen = ref(false)
const isModifyPanelOpen = ref(false)
const selectedSensorForModify = ref(null)
const emit = defineEmits(['update:isMenuOpen'])
const address = ref('')
const label = ref('')
const active = ref(false)
const sensorList = computed(() => Object.values(sensors.value))

watch(() => props.isMenuOpen, (newValue) => {
  isMenuOpen.value = newValue
})

const removeSensor = () => {
  console.log('remove sensor')
  sensorStore.removeSensor()
  isRemoveDialogOpen.value = false
}

const openModifyPanel = (sensor) => {
  isModifyPanelOpen.value = !isModifyPanelOpen.value
  selectedSensorForModify.value = sensor
  console.log('open modify panel for sensor:', selectedSensorForModify.value)
}

const selectSensor = (sensor) => {
  sensorStore.selectSensor(sensor)
}

const handleMouseOver = (sensor) => {
  sensorStore.handleMouseOver(sensor)
}

const addSensor = () => {
  console.log('add sensor')
  // sensorStore.addSensor()
  isModalOpen.value = true
}

const confirm = async () => { // 🛠️ async kell, hogy használhassuk az await-et
  console.log('confirm changes')

  if (address.value && label.value) {
    try {
      await axios.patch(`http://localhost:5000/v1/uav/${selectedSensorForModify.value.uav_id}`, {
        uav_label: label.value,
        uav_address: address.value,
        active: active.value
      },
      { headers: { 'Content-Type': 'application/json' } })

      console.log('✅ Sikeres módosítás!')

      // Most már biztos, hogy a PATCH lefutott, frissíthetjük az adatokat
      await sensorStore.fetchSensors()
    } catch (error) {
      console.error('❌ Hiba az API hívás során:', error.response ? error.response.data : error.message)
    }
  } else {
    console.log('❌ Hiányzó adatok, nem lehet menteni!')
  }
}

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
  emit('update:isMenuOpen', isMenuOpen.value)
}
</script>

<template>
  <div class="flex min-h-screen transition-all duration-300">
    <div v-if="isMenuOpen" class="w-64"></div>
    <div class="flex-1">
      <button
        @click="toggleMenu"
        class="fixed top-4 left-4 z-50 h-10 w-10 p-2 bg-cyan-950 flex flex-col items-center justify-center gap-1 rounded"
        v-if="!isMenuOpen"
      >
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
      </button>

      <div
        class="fixed top-0 left-0 min-h-screen w-64 bg-gray-800 p-5 z-40 transition-transform duration-300"
        :class="{ '-translate-x-full': !isMenuOpen, 'translate-x-0': isMenuOpen }"
      >
        <button
          @click="toggleMenu"
          class="text-white text-2xl mb-4 scale-x-150 font-bold z-[9999] relative"
        >
          X
        </button>

        <div class="bg-blue-500 flex-grow my-4 text-white p-4 text-center overflow-y-auto rounded-lg">
          <p v-if="sensorStore.isLoading" class="text-yellow-300">Betöltés...</p>
          <p v-if="sensorStore.errorMessage" class="text-red-500">{{ sensorStore.errorMessage }}</p>

          <ul class="max-h-90">
            <li
              v-for="sensor in sensorList"
              :key="sensor.uav_label"
              @click="selectSensor(sensor)"
              @mouseover="handleMouseOver(sensor)"
              :class="{
                'bg-gray-700': sensorStore.selectedSensor === sensor,
                'bg-gray-700 hover:bg-gray-600': sensorStore.selectedSensor !== sensor
              }"
              class="p-2 rounded cursor-pointer mb-1"
            >
              <div class="flex justify-between items-center">
                <input
                  type="checkbox"
                  id="checkbox"
                  :checked="sensors[sensor.uav_id].is_selected"
                  @change="sensorStore.toggleSensorSelection(sensor.uav_id)"
                  @click.stop
                >
                <router-link :to="`/sensor/${sensor['uav_label']}`" class="pl-2 text-white hover:underline flex-grow text-left">
                  {{ sensor['uav_label'] }}
                </router-link>
                <button @click.stop="openModifyPanel(sensor)" class="text-white p-2 rounded">⚙️</button>
                <button @click.stop="isRemoveDialogOpen = true" class="text-red-400 hover:text-red-600 ml-2">❌</button>
              </div>
              <div v-if="selectedSensorForModify === sensor && isModifyPanelOpen" class="mt-2 h-40 bg-gray-800 rounded">
                <div>
                  <p>Host ip:</p>
                  <input v-model="address" class="max-w-40 text-black">
                  <p>Host label:</p>
                  <input v-model="label" class="max-w-40 text-black">
                  <div class="flex ml-12">
                      <p>Active:</p>
                      <input v-model="active" type="checkbox">
                  </div>
                  <button @click="confirm" class="bg-green-700 m-1 rounded">Confirm</button>
                </div>
              </div>
            </li>
          </ul>
          <new-sensor-modal></new-sensor-modal>
          <teleport to="body">
            <div
              v-if="isRemoveDialogOpen"
              class="fixed inset-0 z-[999] grid place-items-center bg-black bg-opacity-60 backdrop-blur-sm transition-opacity duration-300"
            >
              <div class="relative m-4 p-4 w-2/5 min-w-[40%] max-w-[40%] rounded-lg bg-red-100 shadow-sm">
                <div class="relative border-t border-slate-200 py-4 leading-normal text-slate-600 font-bold">
                  Are you sure you want to delete the sensor?
                </div>
                <div class="flex shrink-0 flex-wrap items-center pt-4 justify-end">
                  <button
                    @click="isRemoveDialogOpen = false"
                    class="rounded-md border border-transparent py-2 px-4 text-center text-sm transition-all text-slate-600 hover:bg-slate-100"
                  >
                    Cancel
                  </button>
                  <button
                    @click="removeSensor()"
                    class="rounded-md bg-red-600 py-2 px-4 border border-transparent text-center text-sm text-white transition-all shadow-md hover:shadow-lg ml-2"
                  >
                    Confirm
                  </button>
                </div>
              </div>
            </div>
          </teleport>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.-translate-x-full {
  transform: translateX(-100%);
}

.translate-x-0 {
  transform: translateX(0);
}
</style>
