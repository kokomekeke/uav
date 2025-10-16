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
  sensorStore.removeSensor()
  isRemoveDialogOpen.value = false
}

const openModifyPanel = (sensor) => {
  isModifyPanelOpen.value = !isModifyPanelOpen.value
  selectedSensorForModify.value = sensor
}

const selectSensor = (sensor) => {
  sensorStore.selectSensor(sensor)
}

const handleMouseOver = (sensor) => {
  sensorStore.handleMouseOver(sensor)
}

const addSensor = () => {
  isModalOpen.value = true
}

const confirm = async () => {
  if (address.value && label.value) {
    try {
      await axios.patch(`http://localhost:5000/v1/uav/${selectedSensorForModify.value.uav_id}`, {
        uav_label: label.value,
        uav_address: address.value,
        active: active.value
      },
      { headers: { 'Content-Type': 'application/json' } })

      await sensorStore.fetchSensors()
    } catch (error) {
      console.error('API error:', error.response ? error.response.data : error.message)
    }
  }
}

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
  emit('update:isMenuOpen', isMenuOpen.value)
}
</script>

<template>
  <div class="flex min-h-screen transition-all duration-300">
    <div class="flex-1">
      <button
        @click="toggleMenu"
        v-if="!isMenuOpen"
        class="fixed top-1/2 left-0 -translate-y-1/2 -translate-x-10 h-full w-32 z-50 flex items-center justify-center
               hover:bg-blue-600/40
               dark:hover:bg-red-800/40
               rounded-r-[800px]
               transform transition-all duration-300 ease-in-out
               hover:-translate-x-2 hover:scale-105 hover:shadow-2xl"
      >
        <div class="arrow right transition-transform duration-300 ease-in-out hover:translate-x-2"></div>
      </button>

      <!-- Sidebar -->
      <!-- Módosított Sidebar rész enyhe világosító filterrel -->
      <div
        class="fixed top-0 left-0 min-h-screen w-72 p-5 z-40 transition-transform duration-300 border-r
               bg-white/10 backdrop-blur-md
               border-emerald-400/60 shadow-2xl shadow-emerald-500/30
               rounded-r-[2.5rem]
               dark:bg-gradient-to-b dark:from-[#0b1a27]/40 dark:via-[#102b3f]/40 dark:to-red-800/40
               dark:border-red-900/60 dark:shadow-[0_0_40px_-10px_rgba(255,0,0,0.25)]"
        :class="{ '-translate-x-full': !isMenuOpen, 'translate-x-0': isMenuOpen }"
      >

        <button
          @click="toggleMenu"
          class=" text-cyan-800 dark:text-cyan-400 text-2xl mb-6 font-bold z-[9999] relative hover:text-cyan-300 transition"
        >
          x
        </button>

        <div class="flex-grow text-gray-200 text-sm overflow-y-auto">
          <p v-if="sensorStore.isLoading" class="text-yellow-400">Loading...</p>
          <p v-if="sensorStore.errorMessage" class="text-red-500">{{ sensorStore.errorMessage }}</p>

          <ul>
            <li
              v-for="sensor in sensorList"
              :key="sensor.uav_label"
              @click="selectSensor(sensor)"
              @mouseover="handleMouseOver(sensor)"
              :class="{
                'bg-slate-800': sensorStore.selectedSensor === sensor,
                'hover:bg-slate-700': sensorStore.selectedSensor !== sensor
              }"
              class="p-2 rounded cursor-pointer mb-2 transition text-slate-800 dark:text-white bg-slate-100/30 dark:bg-slate-100/20"
            >
              <div class="flex justify-between items-center">
                <input
                  type="checkbox"
                  id="checkbox"
                  :checked="sensors[sensor.uav_id].is_selected"
                  @change="sensorStore.toggleSensorSelection(sensor.uav_id)"
                  @click.stop
                >
                <router-link :to="`/sensor/${sensor['uav_label']}`" class="pl-2 flex-grow text-left hover:underline">
                  {{ sensor['uav_label'] }}
                </router-link>
                <button @click.stop="openModifyPanel(sensor)" class="text-cyan-400 hover:text-cyan-300 px-2">⚙️</button>
                <button @click.stop="isRemoveDialogOpen = true" class="text-red-400 hover:text-red-600 ml-2">✕</button>
              </div>

              <!-- Modify panel -->
              <div v-if="selectedSensorForModify === sensor && isModifyPanelOpen" class="mt-2 p-3 rounded border-cyan-700 bg-slate-700/10
                dark:border-cyan-600 dark:bg-slate-800 ">
                <div>
                  <p>Host IP:</p>
                  <input v-model="address" class="max-w-40 text-black px-1 rounded">
                  <p class="mt-2">Label:</p>
                  <input v-model="label" class="max-w-40 text-black px-1 rounded">
                  <div class="flex items-center gap-2 mt-2">
                      <p>Active:</p>
                      <input v-model="active" type="checkbox">
                  </div>
                  <button @click="confirm" class="bg-green-700 mt-2 px-3 py-1 rounded hover:bg-green-600">Confirm</button>
                </div>
              </div>
            </li>
          </ul>
          <new-sensor-modal></new-sensor-modal>

          <!-- Delete confirmation modal -->
          <teleport to="body">
            <div
              v-if="isRemoveDialogOpen"
              class="fixed inset-0 z-[999] grid place-items-center bg-black bg-opacity-70 backdrop-blur-sm"
            >
              <div class="relative m-4 p-6 w-2/5 min-w-[40%] max-w-[40%] rounded-lg bg-slate-900 border border-red-600 shadow-lg text-gray-200">
                <div class="font-bold mb-4 text-lg text-red-400">Delete sensor?</div>
                <div class="flex justify-end gap-3">
                  <button
                    @click="isRemoveDialogOpen = false"
                    class="px-4 py-2 rounded-md bg-slate-700 hover:bg-slate-600"
                  >
                    Cancel
                  </button>
                  <button
                    @click="removeSensor()"
                    class="px-4 py-2 rounded-md bg-red-600 hover:bg-red-500"
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

.arrow {
  border: solid #a6ecfa;
  border-width: 0 3px 3px 0;
  border-radius: 3px;
  display: inline-block;
  padding: 15px;
}

.right {
  margin-top: 100px;
  transform: rotate(-45deg);
  -webkit-transform: rotate(-45deg);
}

</style>
