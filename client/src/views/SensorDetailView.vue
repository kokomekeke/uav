<script setup lang="ts">
import { ref } from 'vue'
import ConfigurationView from '@/views/config/ConfigurationView.vue'
import MapComponent from '@/components/map/MapComponent.vue'
import HeatmapComponent from '@/components/map/HeatMapComponent.vue'

// View mode: 'map' | 'heatmap' | 'split'
const viewMode = ref<'map' | 'heatmap' | 'split'>('map')

// Tab selection helper
const isActiveTab = (mode: string) => viewMode.value === mode
</script>

<template>
  <div class="relative flex flex-row gap-6 w-full min-h-screen pt-20 px-6 pb-6 bg-transparent dark:bg-slate-900 text-gray-100">

    <!-- JOBB FELSŐ SAROKRA FIXÁLT GOMB -->
    <router-link
      to="/log"
      class="absolute top-4 right-6 z-50"
    >
      <button class="p-0 bg-transparent border-0">
        <div class="log-lines">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>
      </button>
    </router-link>
    <!-- Left panel: Configuration -->
    <div class="flex-1 bg-sgx-accent-light-blue/30 dark:bg-slate-800 rounded-2xl shadow-lg p-4 border border-slate-100 dark:border-slate-700 overflow-auto">
      <configuration-view class="w-full"></configuration-view>
    </div>

    <!-- Right panel: Map/Heatmap with tabs -->
    <div class="flex-[2] bg-slate-400/20 dark:bg-slate-800 rounded-2xl shadow-lg border border-slate-700 overflow-hidden flex flex-col">

      <!-- Tab Header -->
      <div class="flex items-center gap-2 px-4 py-3 border-b border-slate-700 bg-slate-400/20 dark:bg-slate-800/50">
        <!-- Map Tab -->
        <button
          @click="viewMode = 'map'"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200',
            isActiveTab('map')
              ? 'bg-cyan-600 text-white shadow-lg'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          ]"
        >
          🗺️ Map View
        </button>

        <!-- Heatmap Tab -->
        <button
          @click="viewMode = 'heatmap'"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200',
            isActiveTab('heatmap')
              ? 'bg-cyan-600 text-white shadow-lg'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          ]"
        >
          🔥 Heatmap View
        </button>

        <!-- Split View Tab -->
        <button
          @click="viewMode = 'split'"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200',
            isActiveTab('split')
              ? 'bg-cyan-600 text-white shadow-lg'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          ]"
        >
          ⚡ Split View
        </button>

        <!-- Spacer -->
        <div class="flex-1"></div>

        <!-- Info Badge -->
        <div class="text-sm text-gray-400">
          {{ viewMode === 'map' ? 'Real-time Tracking' : viewMode === 'heatmap' ? 'Density Analysis' : 'Dual View' }}
        </div>
      </div>

      <!-- Content Area -->
      <div class="flex-1 overflow-hidden">

        <!-- Map View (Single) -->
        <div v-if="viewMode === 'map'" class="w-full h-full p-4">
          <div class="w-full h-full rounded-xl overflow-hidden">
            <map-component class="w-full h-full"></map-component>
          </div>
        </div>

        <!-- Heatmap View (Single) -->
        <div v-else-if="viewMode === 'heatmap'" class="w-full h-full">
          <heatmap-component class="w-full h-full"></heatmap-component>
        </div>

        <!-- Split View (Both) -->
        <div v-else-if="viewMode === 'split'" class="w-full h-full flex flex-col gap-4 p-4">
          <!-- Top: Map -->
          <div class="flex-1 rounded-xl overflow-hidden border border-slate-700">
            <map-component class="w-full h-full"></map-component>
          </div>

          <!-- Bottom: Heatmap -->
          <div class="flex-1 rounded-xl overflow-hidden border border-slate-700">
            <heatmap-component class="w-full h-full"></heatmap-component>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
/* Smooth transitions for tab changes */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.log-lines {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 24px;
}

.log-lines span {
  height: 3px;
  width: 100%;
  background-color: #a6ecfa;
  border-radius: 3px;
}

</style>
