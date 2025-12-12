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

const selectedCommand = ref(null)

const params = ref({})

const selectCommand = async (v, k) => {
  selectedCommand.value = {
    instruction: k,
    params: v
  }

  const resp = await fetch(`${ipPort.value}/v1/command/descriptor/${k}`)
  const data = await resp.json()

  // Ha nincs fields mező, ez a command nem vár paramétert
  if (!data.fields) {
    params.value = {}
    return
  }

  // Paramétermezők generálása default értékekkel
  params.value = Object.fromEntries(
    data.fields.map(f => {
      let def = f.default
      if (def === undefined) def = null
      return [f.name, def]
    })
  )
}

const sendCommand = async () => {
  const instruction = selectedCommand.value.instruction
  const uavId = selectedSensor.value.uav_id

  const url = `${ipPort.value}/v1/uav/${uavId}/command/${instruction}/`

  // ha nincs paraméter, küldjünk üres objectet
  const body = params.value || {}

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
  <div class="flex flex-col pt-20 h-screen bg-transparent max-w-screen max-h-full text-black dark:text-white">
    <div class="flex flex-col bg-transparent">
      <div>Send command to sensor</div>
      <div class="flex flex-row gap-6 items-start mt-4">

        <!-- COMMAND DROPDOWN -->
        <div class="w-64">
          <dropdown title="Commands" class="w-full bg-sgx-dark-blue dark:bg-sgx-darkblue shadow rounded">
            <div class="h-64 overflow-auto">
              <dropdown-item
                v-for="(value, key) in commands"
                :key="key"
                class="text-slate-900 dark:text-white hover:bg-slate-600 dark:hover:bg-slate-600 px-2 py-1"
                @click="selectCommand(value, key)"
              >
                {{ key }}
              </dropdown-item>
            </div>
          </dropdown>
        </div>

        <!-- PARAMETER GRID + SEND BUTTON -->
        <div
          v-if="selectedCommand && selectedCommand.params"
          class="bg-slate-500 dark:bg-sgx-darkblue border border-slate-900 dark:border-slate-600 rounded-md p-4 w-[600px] flex flex-col gap-4"
        >

          <!-- TITLE -->
          <div class="text-lg font-semibold text-slate-700 dark:text-white mb-1">
            {{ selectedCommand.instruction }}
          </div>

          <!-- GRID OF INPUTS (AUTO-FLOW) -->
          <div class="grid grid-cols-2 gap-4">
            <div
              v-for="(value, key) in params"
              :key="key"
              class="flex flex-col"
            >
              <label class="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
                {{ key }}
              </label>

              <input
                v-model="params[key]"
                class="bg-white dark:bg-slate-700 text-black dark:text-white
                       border border-slate-300 dark:border-slate-600
                       rounded px-2 py-1 focus:ring focus:ring-blue-400 dark:focus:ring-blue-600"
              >
            </div>
          </div>

          <!-- SEND BUTTON RIGHT-ALIGNED -->
          <div class="flex justify-end mt-2">
            <button
              @click="sendCommand"
              class="px-6 py-2 rounded-md
                    bg-blue-600 hover:bg-blue-700
                    text-white font-semibold shadow"
            >
              Send
            </button>
          </div>
        </div>

      </div>

    </div>
    <div
      ref="logScrollContainer"
      class="rounded-md mt-4 bg-slate-400 dark:bg-slate-700 h-128 overflow-auto"
    >
      <ol>
        <li v-for="(logEntry, index) in logs" :key="index" class="border-2 border-y-white pt-4">
          {{ logEntry }}
        </li>
      </ol>
    </div>
  </div>
</template>

<style scoped>

</style>
