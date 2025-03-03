<script setup>
import { ref } from 'vue';

// Alapértelmezett konfiguráció beállítása ref-ként
const config = ref({
  host: 'localhost',
  center_freq: '446M',
  bandwidth: '1M',
  gain: '50',
  bin_count: '1024',
  burst_stride: '65536',
  roi_center: '446.065M',
  roi_span: '100k',
  roi_threshold: '-40'
});

// Változások kezelése
const updateConfig = () => {
  console.log('Updates settings:', config.value);
};
</script>

<template>
  <div class="p-6 bg-gray-100 rounded shadow-md w-96 mx-auto mt-10">
    <h2 class="text-lg font-bold mb-4">Configuration Settings</h2>

    <div v-for="(value, key) in config" :key="key" class="mb-2">
      <label :for="key" class="block text-sm font-medium text-gray-700">
        {{ key.replace('_', ' ').toUpperCase() }}
      </label>
      <input
        :id="key"
        v-model="config[key]"
        type="text"
        class="mt-1 p-2 w-full border rounded"
      />
    </div>

    <button @click="updateConfig" class="mt-4 w-full bg-blue-500 text-white py-2 rounded">
      Save
    </button>
  </div>
</template>

<style scoped>
</style>
