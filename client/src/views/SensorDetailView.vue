<script setup lang="ts">
import { ref, nextTick } from 'vue'
import ConfigurationView from '@/views/config/ConfigurationView.vue'
import MapComponent from '@/components/map/MapComponent.vue'
import HeatmapComponent from '@/components/map/HeatMapComponent.vue'
import SpectrumWaterfall from '@/components/spectrum/SpectrumWaterfall.vue'

const viewMode = ref<'map' | 'heatmap' | 'split' | 'spectrum'>('map')
const showConfig = ref(true)

const mapKey = ref(0)
const heatmapKey = ref(0)

const isActiveTab = (mode: string) => viewMode.value === mode

const switchView = async (newMode: 'map' | 'heatmap' | 'split' | 'spectrum') => {
  if (viewMode.value === newMode) return

  console.log(`[SensorDetail] Switching from ${viewMode.value} to ${newMode}`)

  const oldMode = viewMode.value

  viewMode.value = null as any
  await nextTick()

  if (oldMode === 'map' || newMode === 'map' || oldMode === 'split' || newMode === 'split') {
    mapKey.value++
  }
  if (oldMode === 'heatmap' || newMode === 'heatmap' || oldMode === 'split' || newMode === 'split') {
    heatmapKey.value++
  }

  await nextTick()

  viewMode.value = newMode

  console.log(`[SensorDetail] Switched to ${newMode} (map key: ${mapKey.value}, heatmap key: ${heatmapKey.value})`)
}
</script>

<template>
  <div class="relative flex flex-row rounded-xl gap-6 w-full min-h-screen pt-20 px-6 pb-6 bg-transparent dark:bg-slate-900 text-gray-100">
    <router-link to="/log" class="absolute top-4 right-6 z-50">
      <button class="p-0 bg-transparent border-0">
        <div class="log-lines">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>
      </button>
    </router-link>

    <div
      class="relative bg-sgx-accent-light-blue/30 dark:bg-slate-800 rounded-2xl shadow-lg p-4 border border-slate-100 dark:border-slate-700 overflow-hidden transition-all duration-300"
      :class="showConfig ? 'flex-1' : 'w-20'"
    >
      <button
        class="absolute top-2 left-2 z-50 border border-gray-700 rounded-xl bg-white dark:bg-slate-900 px-2"
        @click="showConfig = !showConfig"
      >
        ⚙️
      </button>

      <configuration-view v-if="showConfig" class="w-full" />
    </div>

    <div class="flex-[2] bg-slate-400/20 dark:bg-slate-800 rounded-2xl shadow-lg border border-slate-700 overflow-hidden flex flex-col">
      <div class="flex items-center gap-2 px-4 py-3 border-b border-slate-700 bg-slate-400/20 dark:bg-slate-800/50">
        <button
          @click="switchView('map')"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200',
            isActiveTab('map')
              ? 'bg-cyan-600 text-white shadow-lg'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          ]"
        >
          🗺️ Map View
        </button>

        <button
          @click="switchView('heatmap')"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200',
            isActiveTab('heatmap')
              ? 'bg-cyan-600 text-white shadow-lg'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          ]"
        >
          🔥 Heatmap View
        </button>

        <button
          @click="switchView('spectrum')"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200',
            isActiveTab('spectrum')
              ? 'bg-cyan-600 text-white shadow-lg'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          ]"
        >
          📊 Spectrum View
        </button>

        <button
          @click="switchView('split')"
          :class="[
            'px-4 py-2 rounded-lg font-medium transition-all duration-200',
            isActiveTab('split')
              ? 'bg-cyan-600 text-white shadow-lg'
              : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
          ]"
        >
          ⚡ Split View
        </button>

        <div class="flex-1"></div>

        <div class="text-sm text-gray-400">
          {{
            viewMode === 'map' ? 'Real-time Tracking' :
            viewMode === 'heatmap' ? 'Density Analysis' :
            viewMode === 'spectrum' ? 'Spectrum Analysis' :
            'Dual View'
          }}
        </div>
      </div>

      <div class="flex-1 overflow-hidden">
        <div v-if="viewMode === 'map'" class="w-full h-full p-4">
          <div class="w-full h-full rounded-xl overflow-hidden">
            <map-component :key="`map-${mapKey}`" class="w-full h-full" />
          </div>
        </div>

        <div v-else-if="viewMode === 'heatmap'" class="w-full h-full p-4">
          <div class="w-full h-full rounded-xl overflow-hidden">
            <heatmap-component :key="`heatmap-${heatmapKey}`" class="w-full h-full" />
          </div>
        </div>

        <div v-else-if="viewMode === 'spectrum'" class="w-full h-full p-4">
          <div class="w-full h-full rounded-xl overflow-hidden">
            <spectrum-waterfall class="w-full h-full" />
          </div>
        </div>

        <div v-else-if="viewMode === 'split'" class="w-full h-full flex flex-col gap-4 p-4">
          <div class="flex-1 rounded-xl overflow-hidden border border-slate-700">
            <map-component :key="`split-map-${mapKey}`" class="w-full h-full" />
          </div>

          <div class="flex-1 rounded-xl overflow-hidden border border-slate-700">
            <heatmap-component :key="`split-heatmap-${heatmapKey}`" class="w-full h-full" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
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