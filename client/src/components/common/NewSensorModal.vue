<script setup>
import { ref } from 'vue'

const isModalOpen = ref(false)
const addSensor = () => {
  console.log('add sensor')
  // sensorStore.addSensor()
  isModalOpen.value = true
}

</script>

<template>
  <div>
    <div class="mt-4">
      <button @click="addSensor()" class="mt-2 w-full bg-green-500 text-white p-2 rounded hover:bg-green-700">
        + Szenzor hozzáadása
      </button>
    </div>
    <div v-if="isModalOpen" class="fixed inset-0 z-[999] grid h-screen w-screen place-items-center bg-black bg-opacity-60 backdrop-blur-sm transition-opacity duration-300">
      <div class="bg-slate-500 min-w-72 rounded-lg">
        <div class="m-2">
          <p class="m-2">Add Sensor</p>
          <p>Sensor Label:</p>
          <input>
          <p>Sensor Address:</p>
          <input>
          <p>Last position latitude:</p>
          <input>
          <p>Last position longitude:</p>
          <input>
          <p>Last position altitude:</p>
          <input>
          <p>Last position q0:</p>
          <input>
          <p>Last position q1:</p>
          <input>
          <p>Last position q2:</p>
          <input>
          <p>Last position q3:</p>
          <input>
          <p>Active:</p>
          <input type="checkbox">
        </div>
        <div class="py-10 flex flex-row">
          <button class="basis-1/2 bg-green-700 m-2 h-10">Submit</button>
          <button class="basis-1/2 bg-red-700 m-2 h-10" @click="isModalOpen = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>