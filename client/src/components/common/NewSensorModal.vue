<script setup>
import { ref } from 'vue'
import { useSensorStore } from '@/stores/sensor'

const sensorStore = useSensorStore()

const isModalOpen = ref(false)

const label = ref('')
const address = ref('')
const isActive = ref(false)
const lastPosLat = ref(null)
const lastPosLon = ref(null)
const lastPosAlt = ref(null)
const lastPosQ0 = ref(null)
const lastPosQ1 = ref(null)
const lastPosQ2 = ref(null)
const lastPosQ3 = ref(null)

const addSensor = () => {
  console.log('add sensor')
  isModalOpen.value = true
}

const submit = () => {
    if (label.value && address.value) {
        console.log('submit data')
        const data = JSON.stringify({
            uav_label: label.value,
            uav_address: address.value,
            active: isActive.value
        })
        console.log(data)
        sensorStore.addSensor(data)

    } else {
        console.log('fill the form!!!')
    }
}

</script>

<template>
  <div>
    <div class="mt-4">
      <button
        @click="addSensor"
        class="mt-2 w-full bg-green-500 text-white p-2 rounded hover:bg-green-700"
      >
        + Szenzor hozzáadása
      </button>
    </div>

    <div
      v-if="isModalOpen"
      class="fixed inset-0 z-[999] grid h-screen w-screen place-items-center bg-black bg-opacity-60 backdrop-blur-sm transition-opacity duration-300"
    >
      <div class="bg-slate-500 min-w-72 rounded-lg p-4">
        <div class="m-2 text-black">
          <p class="m-2 font-bold">Add Sensor</p>

          <label class="block">Sensor Label:*</label>
          <input v-model="label" class="w-full p-1 border rounded" />

          <label class="block mt-2">Sensor Address:*</label>
          <input v-model="address" class="w-full p-1 border rounded" />

          <label class="block mt-2">Last position latitude:</label>
          <input v-model="lastPosLat" class="w-full p-1 border rounded" />

          <label class="block mt-2">Last position longitude:</label>
          <input v-model="lastPosLon" class="w-full p-1 border rounded" />

          <label class="block mt-2">Last position altitude:</label>
          <input v-model="lastPosAlt" class="w-full p-1 border rounded" />

          <label class="block mt-2">Last position q0:</label>
          <input v-model="lastPosQ0" class="w-full p-1 border rounded" />

          <label class="block mt-2">Last position q1:</label>
          <input v-model="lastPosQ1" class="w-full p-1 border rounded" />

          <label class="block mt-2">Last position q2:</label>
          <input v-model="lastPosQ2" class="w-full p-1 border rounded" />

          <label class="block mt-2">Last position q3:</label>
          <input v-model="lastPosQ3" class="w-full p-1 border rounded" />

          <label class="block mt-2">Active:*</label>
          <input v-model="isActive" type="checkbox" class="ml-2" />
        </div>

        <div class="py-4 flex flex-row">
          <button
            class="basis-1/2 bg-green-700 text-white m-2 h-10 rounded"
            @click="submit"
          >
            Submit
          </button>
          <button
            class="basis-1/2 bg-red-700 text-white m-2 h-10 rounded"
            @click="isModalOpen = false"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
</template>


<style scoped>

</style>