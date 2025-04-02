import { defineStore } from 'pinia'
import {ref, watch} from 'vue'

interface ROIConfig {
    roi_center: string
    roi_span: string
    roi_threshold: string
}

interface Config {
    center_freq: string
    bandwidth: string
    gain: string
    bin_count: string
    burst_stride: string
    roi_config: ROIConfig[]
}

export const useConfigStore = defineStore('config', () => {
  const configs = ref<Config | undefined>(undefined)
  const ROIConfig = ref<ROIConfig[]>([])
  const center_freq = ref<string>('446M')
  const bandwidth = ref<string>('1M')
  const gain = ref<string>('50')
  const bin_count = ref<string>('1024')
  const burst_stride = ref<string>('65536')

  const selectedROI = ref<ROIConfig>(null)
  const handleMouseOver = (roi: ROIConfig) => {
    selectedROI.value = roi
  }

  const selectROI = (roi: ROIConfig) => {
    selectedROI.value = roi
  }

  watch(() => selectedROI.value, (newValue) => {
    console.log('newConfig:::', newValue)
  })

  return { handleMouseOver, selectROI, selectedROI }
})
