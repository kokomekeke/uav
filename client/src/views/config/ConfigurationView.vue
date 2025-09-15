<script setup>
import { ref } from 'vue'
import ConfigComponent from "@/components/configuration/ConfigComponent.vue";

const config = ref({
  center_freq: '446M',
  bandwidth: '1M',
  gain: '50',
  bin_count: '1024',
  burst_stride: '65536'
})

const updateConfig = () => {
  console.log('Updates settings:', config.value);
}
</script>

<template>
  <div class="p-6 bg-slate-900 rounded-xl shadow-lg w-full h-full overflow-y-auto border border-slate-700">
    <h1 class="text-lg font-semibold text-cyan-400 mb-6">Configuration Settings</h1>

    <div v-for="(value, key) in config" :key="key" class="mb-4">
      <label :for="key" class="block text-sm font-medium text-gray-300 mb-1">
        {{ key.replace('_', ' ').toUpperCase() }}
      </label>
      <input
        :id="key"
        v-model="config[key]"
        type="text"
        class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
      />
    </div>

    <config-component class="mb-4"></config-component>

    <button
      @click="updateConfig"
      class="w-full bg-cyan-600 hover:bg-cyan-500 text-white py-2 rounded-xl font-medium shadow transition"
    >
      Save
    </button>
  </div>
</template>
