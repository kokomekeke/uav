<script setup>
import { ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useSensorStore } from '@/stores/sensor'
import NewSensorModal from "@/components/common/NewSensorModal.vue";

const sensorStore = useSensorStore()
const { sensors } = storeToRefs(sensorStore)

const props = defineProps({
  isMenuOpen: Boolean
})
const isMenuOpen = ref(props.isMenuOpen)
const isRemoveDialogOpen = ref(false)
const isModalOpen = ref(false)
// const isModifyPanelOpen = ref(false)
const selectedSensorForModify = ref(null)
const emit = defineEmits(['update:isMenuOpen'])

watch(() => props.isMenuOpen, (newValue) => {
  isMenuOpen.value = newValue
})

const removeSensor = () => {
  console.log('remove sensor')
  sensorStore.removeSensor()
  isRemoveDialogOpen.value = false
}

const openModifyPanel = (sensor) => {
  console.log('open modify panel for sensor:', sensor)
  selectedSensorForModify.value = sensor
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
        class="fixed top-4 left-4 z-50 h-10 w-10 p-2 bg-blue-600 flex flex-col items-center justify-center gap-1 rounded"
        v-if="!isMenuOpen"
      >
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
        <span class="h-0.5 rounded bg-gray-400 w-6"></span>
      </button>

      <div
        class="fixed top-0 left-0 h-full w-64 bg-gray-800 p-5 z-40 transition-transform duration-300"
        :class="{ '-translate-x-full': !isMenuOpen, 'translate-x-0': isMenuOpen }"
      >
        <button @click="toggleMenu" class="text-white text-2xl mb-4">✖</button>

        <div class="bg-blue-500 flex-grow my-4 text-white p-4 text-center overflow-y-auto rounded-lg">
          <p v-if="sensorStore.isLoading" class="text-yellow-300">Betöltés...</p>
          <p v-if="sensorStore.errorMessage" class="text-red-500">{{ sensorStore.errorMessage }}</p>

          <ul class="max-h-90">
            <li
              v-for="sensor in sensors"
              :key="sensor.uav_label"
              @click="selectSensor(sensor)"
              @mouseover="handleMouseOver(sensor)"
              :class="{
                'bg-gray-700': sensorStore.selectedSensor === sensor,
                'bg-gray-700 hover:bg-gray-600': sensorStore.selectedSensor !== sensor
              }"
              class="p-2 rounded cursor-pointer"
            >
              <div class="flex justify-between items-center">
                <input type="checkbox" id="checkbox">
                <router-link :to="`/sensor/${sensor['uav_label']}`" class="pl-2 text-white hover:underline flex-grow text-left">
                  {{ sensor['uav_label'] }}
                </router-link>
                <button @click.stop="openModifyPanel(sensor)" class="text-white p-2 rounded">⚙️</button>
                <button @click.stop="isRemoveDialogOpen = true" class="text-red-400 hover:text-red-600 ml-2">❌</button>
              </div>
              <div v-if="selectedSensorForModify === sensor" class="mt-2 h-20 bg-amber-500 rounded">
                <div>
                  <p>Host ip:</p>
                  <input class="max-w-40 text-black">
                  <button class="bg-green-700 m-1 rounded">Confirm</button>
                </div>
              </div>
            </li>
          </ul>
          <new-sensor-modal></new-sensor-modal>

<!--          <button-->
<!--            @click="isRemoveDialogOpen = true"-->
<!--            class="rounded-md bg-slate-800 py-2 px-4 border border-transparent text-center text-sm text-white transition-all shadow-md hover:shadow-lg focus:bg-slate-700 focus:shadow-none active:bg-slate-700 hover:bg-slate-700 active:shadow-none disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none ml-2"-->
<!--          >-->
<!--            Open Modal-->
<!--          </button>-->
          <div
            v-if="isRemoveDialogOpen"
            class="fixed inset-0 z-[999] grid h-screen w-screen place-items-center bg-black bg-opacity-60 backdrop-blur-sm transition-opacity duration-300"
          >
            <div class="relative m-4 p-4 w-2/5 min-w-[40%] max-w-[40%] rounded-lg bg-red-100 shadow-sm">
              <div class="flex shrink-0 items-center pb-4 text-xl font-medium text-slate-800">
              </div>
              <div class="relative border-t border-slate-200 py-4 leading-normal text-slate-600 font-bold">
                Are you sure you want to delete the sensor?
              </div>
              <div class="flex shrink-0 flex-wrap items-center pt-4 justify-end">
                <button
                  @click="isRemoveDialogOpen = false"
                  class="rounded-md border border-transparent py-2 px-4 text-center text-sm transition-all text-slate-600 hover:bg-slate-100 focus:bg-slate-100 active:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  @click="removeSensor()"
                  class="rounded-md bg-red-600 py-2 px-4 border border-transparent text-center text-sm text-white transition-all shadow-md hover:shadow-lg focus:bg-red-700 hover:bg-red-700 ml-2"
                >
                  Confirm
                </button>
              </div>
            </div>
          </div>
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
