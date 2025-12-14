<template>
  <div class="bg-gray-200 rounded p-4 relative">
    <hr />
    <h4 class="text-base font-bold mb-4 mt-4 pl-2">ROI Settings</h4>
    <ul>
      <li
        v-for="(roi, index) in configs"
        :key="index"
        class="relative mb-1 pl-2 pr-2"
      >
        <div class="w-full bg-rose-800 rounded flex items-center">
          <button
            class="w-11/12 h-6 justify-items-center bg-rose-700 text-white rounded m-2 relative"
            @click="selectROI(roi, $event)"
          >
            {{ index }}
          </button>
        </div>
      </li>
    </ul>
    <hr />
    <div class="grid grid-cols-2">
        <button onclick="addItem()" class="bg-green-300 ml-2 mr-0.5 rounded">➕</button>
        <button onclick="deleteItem()" class="bg-red-300 mr-2 ml-0.5 rounded">➖</button>
    </div>
    <teleport to="body">
      <div
        v-if="selectedROIConfig"
        class="fixed z-[9999] px-5 py-2 bg-gray-200 text-black rounded shadow-lg border border-gray-300 grid grid-row-3"
        :style="tooltipStyle"
      >
        <label>roi_center</label>
        <input>
        <label>roi_span</label>
        <input>
        <label>roi_threshold</label>
        <input>
        <div class="grid grid-cols-2">
          <button>✅</button>
          <button>❌</button>
        </div>

      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

interface ROIConfig {
  roi_center: string
  roi_span: string
  roi_threshold: string
}

const configs = ref<ROIConfig[]>([
  { roi_center: '446.065M', roi_span: '100k', roi_threshold: '-40' },
  { roi_center: '30,30', roi_span: '15', roi_threshold: '0.7' }
])

const selectedROIConfig = ref<ROIConfig | null>(null)
const tooltipPosition = ref({ x: 0, y: 0 })

const selectROI = (roi: ROIConfig, event: MouseEvent) => {
  selectedROIConfig.value = roi

  const target = event.target as HTMLElement
  if (!target) return

  const rect = target.getBoundingClientRect()

  tooltipPosition.value = {
    x: rect.left + window.scrollX + rect.width + 10, // Középre igazítás
    y: rect.top + window.scrollY + rect.height - 175 // A gomb alá helyezés
  }
}

const tooltipStyle = computed(() => ({
  left: `${tooltipPosition.value.x}px`,
  top: `${tooltipPosition.value.y}px`
}))

const hideTooltipOnScroll = () => {
  selectedROIConfig.value = null
}

onMounted(() => {
  window.addEventListener('scroll', hideTooltipOnScroll)
})
onUnmounted(() => {
  window.removeEventListener('scroll', hideTooltipOnScroll)
})
</script>

<style scoped>
div[role="tooltip"] {
  position: absolute;
  background: white;
  padding: 8px;
  border-radius: 4px;
  border: 1px solid #ccc;
  box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
  z-index: 1000;
}
</style>
