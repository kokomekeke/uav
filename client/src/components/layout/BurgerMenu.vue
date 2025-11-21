<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useSensorStore } from '@/stores/sensor'
import NewSensorModal from '@/components/common/NewSensorModal.vue'
import axios from 'axios'
import type { Sensor } from '@/types/sensor'

const sensorStore = useSensorStore()
const { sensors } = storeToRefs(sensorStore)

interface Props {
  isMenuOpen: boolean
}

const props = defineProps<Props>()

const isMenuOpen = ref(props.isMenuOpen)
const isRemoveDialogOpen = ref(false)
const isModalOpen = ref(false)
const isModifyPanelOpen = ref(false)
const selectedSensorForModify = ref<Sensor | null>(null)
const address = ref('')
const label = ref('')
const active = ref(false)

const emit = defineEmits<{
  'update:isMenuOpen': [value: boolean]
}>()

const sensorList = computed(() => Object.values(sensors.value))

// ============================================================================
// LIFECYCLE - Worker inicializálás
// ============================================================================

onMounted(async () => {
  console.log('[SensorSidebar] 🚀 Component mounted')

  // 1. Worker inicializálás
  if (!sensorStore.isWorkerReady()) {
    console.log('[SensorSidebar] Initializing worker...')
    sensorStore.initializeWorker()
  } else {
    console.log('[SensorSidebar] Worker already initialized')
  }

  // 2. Szenzorok betöltése (ha még nincsenek)
  if (Object.keys(sensors.value).length === 0) {
    console.log('[SensorSidebar] Fetching sensors...')
    await sensorStore.fetchSensors()
  }

  console.log('[SensorSidebar] ✅ Ready')
})

// ============================================================================
// WATCHERS
// ============================================================================

watch(() => props.isMenuOpen, (newValue) => {
  isMenuOpen.value = newValue
})

// ============================================================================
// METHODS
// ============================================================================

const removeSensor = (): void => {
  sensorStore.removeSensor()
  isRemoveDialogOpen.value = false
}

const openModifyPanel = (sensor: Sensor): void => {
  isModifyPanelOpen.value = !isModifyPanelOpen.value
  selectedSensorForModify.value = sensor

  // Pre-fill form values
  if (sensor) {
    address.value = sensor.uav_address
    label.value = sensor.uav_label
    active.value = sensor.active
  }
}

const handleMouseOver = (sensor: Sensor): void => {
  sensorStore.handleMouseOver(sensor)
}

const showMap = (): void => {
  console.log('[SensorSidebar] Routing to Map')
}

// const addSensor = (): void => {
//   isModalOpen.value = true
// }

const confirm = async (): Promise<void> => {
  if (!selectedSensorForModify.value) {
    console.warn('[SensorSidebar] No sensor selected for modification')
    return
  }

  if (address.value && label.value) {
    try {
      await axios.patch(
        `http://localhost:5000/v1/uav/${selectedSensorForModify.value.uav_id}`,
        {
          uav_label: label.value,
          uav_address: address.value,
          active: active.value
        },
        { headers: { 'Content-Type': 'application/json' } }
      )

      console.log('[SensorSidebar] ✅ Sensor updated')
      await sensorStore.fetchSensors()

      // Close modify panel
      isModifyPanelOpen.value = false
      selectedSensorForModify.value = null
    } catch (error) {
      console.error('[SensorSidebar] API error:', error)
      if (axios.isAxiosError(error)) {
        console.error('Response:', error.response?.data)
      }
    }
  } else {
    console.warn('[SensorSidebar] Address or label is empty')
  }
}

const toggleMenu = (): void => {
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
          class="text-cyan-800 dark:text-cyan-400 text-2xl mb-6 font-bold z-[9999] relative hover:text-cyan-300 transition"
        >
          ×
        </button>

        <div class="flex-grow text-gray-200 text-sm overflow-y-auto">
          <!-- Loading state -->
          <p v-if="sensorStore.isLoading" class="text-yellow-400">Loading...</p>

          <!-- Error state -->
          <p v-if="sensorStore.errorMessage" class="text-red-500">
            {{ sensorStore.errorMessage }}
          </p>

          <!-- Sensor list -->
          <ul>
            <li
              v-for="sensor in sensorList"
              :key="sensor.uav_id"
              @click="showMap"
              @mouseover="handleMouseOver(sensor)"
              :class="{
                'bg-slate-800': sensorStore.selectedSensor === sensor,
                'hover:bg-slate-700': sensorStore.selectedSensor !== sensor
              }"
              class="p-2 rounded cursor-pointer mb-2 transition text-slate-800 dark:text-white bg-slate-100/30 dark:bg-slate-100/20"
            >
              <div class="flex justify-between items-center">
                <!-- Checkbox -->
                <input
                  type="checkbox"
                  :id="`sensor-${sensor.uav_id}`"
                  :checked="sensor.is_selected"
                  @change="sensorStore.selectSensor(sensor.uav_id)"
                  @click.stop
                  class="cursor-pointer"
                >

                <!-- Label with router link -->
                <router-link
                  :to="`/sensor/${sensor.uav_label}`"
                  class="pl-2 flex-grow text-left hover:underline"
                  @click.stop
                >
                  {{ sensor.uav_label }}
                </router-link>

                <!-- Settings button -->
                <button
                  @click.stop="openModifyPanel(sensor)"
                  class="text-cyan-400 hover:text-cyan-300 px-2 transition"
                  title="Settings"
                >
                  ⚙️
                </button>

                <!-- Delete button -->
                <button
                  @click.stop="() => {
                    selectedSensorForModify = sensor
                    isRemoveDialogOpen = true
                  }"
                  class="text-red-400 hover:text-red-600 ml-2 transition"
                  title="Delete"
                >
                  ✕
                </button>
              </div>

              <!-- Modify panel -->
              <div
                v-if="selectedSensorForModify === sensor && isModifyPanelOpen"
                class="mt-2 p-3 rounded border border-cyan-700 bg-slate-700/10
                       dark:border-cyan-600 dark:bg-slate-800"
              >
                <div>
                  <label class="block mb-1 text-xs font-semibold">Host IP:</label>
                  <input
                    v-model="address"
                    type="text"
                    class="w-full max-w-40 text-black px-2 py-1 rounded text-sm"
                    placeholder="192.168.1.100"
                  >

                  <label class="block mt-2 mb-1 text-xs font-semibold">Label:</label>
                  <input
                    v-model="label"
                    type="text"
                    class="w-full max-w-40 text-black px-2 py-1 rounded text-sm"
                    placeholder="UAV-1"
                  >

                  <div class="flex items-center gap-2 mt-2">
                    <label class="text-xs font-semibold">Active:</label>
                    <input
                      v-model="active"
                      type="checkbox"
                      class="cursor-pointer"
                    >
                  </div>

                  <button
                    @click="confirm"
                    class="bg-green-700 mt-3 px-3 py-1 rounded hover:bg-green-600 transition text-sm w-full"
                  >
                    Confirm
                  </button>
                </div>
              </div>
            </li>
          </ul>

          <!-- New sensor modal -->
          <new-sensor-modal />

          <!-- Delete confirmation modal -->
          <teleport to="body">
            <div
              v-if="isRemoveDialogOpen"
              class="fixed inset-0 z-[999] grid place-items-center bg-black bg-opacity-70 backdrop-blur-sm"
              @click="isRemoveDialogOpen = false"
            >
              <div
                class="relative m-4 p-6 w-2/5 min-w-[40%] max-w-[40%] rounded-lg bg-slate-900 border border-red-600 shadow-lg text-gray-200"
                @click.stop
              >
                <div class="font-bold mb-4 text-lg text-red-400">
                  Delete sensor "{{ selectedSensorForModify?.uav_label }}"?
                </div>
                <p class="text-sm text-gray-400 mb-6">
                  This action cannot be undone.
                </p>
                <div class="flex justify-end gap-3">
                  <button
                    @click="isRemoveDialogOpen = false"
                    class="px-4 py-2 rounded-md bg-slate-700 hover:bg-slate-600 transition"
                  >
                    Cancel
                  </button>
                  <button
                    @click="removeSensor"
                    class="px-4 py-2 rounded-md bg-red-600 hover:bg-red-500 transition"
                  >
                    Delete
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
