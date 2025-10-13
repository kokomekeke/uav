<template>
  <div>
    <button
      @click="addSensor"
      class="w-full bg-green-500 hover:bg-green-600 text-white font-medium px-4 py-2 rounded-xl shadow transition-all"
    >
      + Add Sensor
    </button>

    <CenteredModal :show="isModalOpen" @close="isModalOpen = false">
      <!-- HEADER -->
      <template #header>
        <h3 class="text-lg font-semibold text-cyan-400">Add Sensor</h3>
      </template>

      <!-- BODY -->
      <template #body>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-200">Sensor Label *</label>
            <input
              v-model="label"
              class="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-200">Sensor Address *</label>
            <input
              v-model="address"
              class="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
            />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm font-medium text-gray-200">Latitude</label>
              <input v-model="lastPosLat" class="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-gray-100"/>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-200">Longitude</label>
              <input v-model="lastPosLon" class="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-gray-100"/>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-200">Altitude</label>
              <input v-model="lastPosAlt" class="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-gray-100"/>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-200">Q0</label>
              <input v-model="lastPosQ0" class="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-gray-100"/>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-200">Q1</label>
              <input v-model="lastPosQ1" class="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-gray-100"/>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-200">Q2</label>
              <input v-model="lastPosQ2" class="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-gray-100"/>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-200">Q3</label>
              <input v-model="lastPosQ3" class="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-gray-100"/>
            </div>
          </div>

          <div class="flex items-center space-x-2">
            <input
              v-model="isActive"
              type="checkbox"
              class="h-4 w-4 text-green-500 focus:ring-green-400 border-slate-600 rounded"
            />
            <label class="text-sm text-gray-200">Active</label>
          </div>
        </div>
      </template>

      <!-- FOOTER -->
      <template #submit>
        <button
          class="bg-gray-600 hover:bg-gray-500 px-4 py-2 rounded-xl text-white font-medium"
          @click="isModalOpen = false"
        >
          Cancel
        </button>
        <button
          class="bg-green-600 hover:bg-green-500 px-4 py-2 rounded-xl text-white font-medium"
          @click="submit"
        >
          Submit
        </button>
      </template>
    </CenteredModal>
  </div>
</template>

<script setup>
import CenteredModal from '@/components/common/CenteredModal.vue'
import { ref } from 'vue'

const isModalOpen = ref(false)
const label = ref('')
const address = ref('')
const lastPosLat = ref('')
const lastPosLon = ref('')
const lastPosAlt = ref('')
const lastPosQ0 = ref('')
const lastPosQ1 = ref('')
const lastPosQ2 = ref('')
const lastPosQ3 = ref('')
const isActive = ref(false)

const addSensor = () => {
  isModalOpen.value = true
}

const submit = () => {
  console.log('Submitting sensor:', {
    label: label.value,
    address: address.value,
    lat: lastPosLat.value,
    lon: lastPosLon.value,
    alt: lastPosAlt.value,
    q0: lastPosQ0.value,
    q1: lastPosQ1.value,
    q2: lastPosQ2.value,
    q3: lastPosQ3.value,
    active: isActive.value
  })
  isModalOpen.value = false
}
</script>

