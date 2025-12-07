<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import { useLogStore } from '@/stores/log'
import { storeToRefs } from 'pinia'
import DropdownItem from '@/components/common/DropdownItem.vue'
import { useConnectionStore } from '@/stores/connection'
import Dropdown from '@/components/common/Dropdown.vue'
import { useSensorStore } from '@/stores/sensor'

const logStore = useLogStore()
const { logs } = storeToRefs(logStore)

const connectionStore = useConnectionStore()
const { ipPort } = storeToRefs(connectionStore)

const sensorStore = useSensorStore()
const { selectedSensor } = storeToRefs(sensorStore)

// ✅ Teljesen egyedi név
const logScrollContainer = ref(null)

const commands = ref({})
const selectCommand = async (key) => {
  console.log(selectedSensor.value.uav_id)
  const url = `${ipPort.value}/v1/uav/${selectedSensor.value.uav_id}/command/${key}/`

  const body = {
    level: 'SPECTRUM',
    id: 1  // Ez elég, a többi mezőt a backend kiegészíti!
  }

  const requestOptions = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }

  try {
    const resp = await fetch(url, requestOptions)
    const data = await resp.json()
    console.log('resp', data)
  } catch (error) {
    console.error('Command failed:', error)
  }
}
watch(logs, async () => {
  if (!logScrollContainer.value) return

  const c = logScrollContainer.value
  const isAtBottom = c.scrollTop + c.clientHeight >= c.scrollHeight - 10

  if (isAtBottom) {
    await nextTick()
    c.scrollTop = c.scrollHeight
  }
}, { deep: true })

onMounted(async () => {
  const url = ipPort.value + '/v1/command/list'
  const res = await fetch(url)
  commands.value = await res.json()
  console.log('commands:::', commands.value)
})
</script>

<template>
  <div class="flex flex-col pt-20 h-screen bg-slate-200 dark:bg-slate-700 w-screen max-h-full text-black dark:text-white">
    <div class="flex flex-col bg-blue-200 dark:bg-sgx-dark-blue">
      <div>Send command to sensor</div>
      <div class="flex flex-row">
        <div class="mx-auto py-2 ml-0">
          <dropdown title="Commands" class="w-64">
            <div class="h-64 overflow-auto">
              <dropdown-item
                v-for="(value, key) in commands"
                :key="key"
                class="text-slate-900 hover:bg-slate-300"
                @click="selectCommand(key)"
              >
                {{ key }}
              </dropdown-item>
            </div>
          </dropdown>
        </div>
        <button>send</button>
      </div>
    </div>
    <div
      ref="logScrollContainer"
      class="bg-slate-400 dark:bg-slate-700 h-96 overflow-auto"
    >
      <ol>
        <li v-for="(logEntry, index) in logs" :key="index" class="border-2 border-y-white">
          {{ logEntry }}
        </li>
      </ol>
    </div>
  </div>
</template>

<style scoped>

</style>
