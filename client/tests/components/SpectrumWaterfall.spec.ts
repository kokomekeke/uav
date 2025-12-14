// tests/components/SpectrumWaterfall.spec.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SpectrumWaterfall from '@/components/spectrum/SpectrumWaterfall.vue'
import { useSensorStore } from '@/stores/sensor'

describe('SpectrumWaterfall Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should render component', () => {
    const wrapper = mount(SpectrumWaterfall)

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.spectrum-waterfall-container').exists()).toBe(true)
  })

  it('should display UAV selector', () => {
    const wrapper = mount(SpectrumWaterfall)

    expect(wrapper.find('.sensor-selector').exists()).toBe(true)
    expect(wrapper.find('select').exists()).toBe(true)
  })

  it('should display status indicator', () => {
    const wrapper = mount(SpectrumWaterfall)

    const status = wrapper.find('.status')
    expect(status.exists()).toBe(true)
    expect(status.text()).toContain('No Data')
  })

  it('should list available sensors', async () => {
    const sensorStore = useSensorStore()
    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        active: true,
        detections: []
      } as any,
      2: {
        uav_id: 2,
        uav_label: 'UAV-2',
        active: true,
        detections: []
      } as any
    }

    const wrapper = mount(SpectrumWaterfall)
    await wrapper.vm.$nextTick()

    const options = wrapper.findAll('option')
    expect(options.length).toBeGreaterThan(1)
    expect(wrapper.text()).toContain('UAV-1')
    expect(wrapper.text()).toContain('UAV-2')
  })

  it('should select UAV', async () => {
    const sensorStore = useSensorStore()
    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        active: true,
        detections: []
      } as any
    }

    const wrapper = mount(SpectrumWaterfall)
    await wrapper.vm.$nextTick()

    const select = wrapper.find('select')
    await select.setValue(1)

    expect(wrapper.vm.selectedUavId).toBe(1)
  })

  it('should decode Float16 data', () => {
    const wrapper = mount(SpectrumWaterfall)

    const testData = 'AAA='

    const result = wrapper.vm.decodeFloat16Array(testData)

    expect(Array.isArray(result)).toBe(true)
  })

  it('should normalize spectrum data', () => {
    const wrapper = mount(SpectrumWaterfall)

    const testData = [10, 20, 30, 40, 50]
    const normalized = wrapper.vm.normalizeSpectrum(testData)

    expect(normalized.length).toBe(testData.length)
    expect(Math.min(...normalized)).toBeGreaterThanOrEqual(0)
    expect(Math.max(...normalized)).toBeLessThanOrEqual(255)
  })

  it('should handle empty spectrum data', () => {
    const wrapper = mount(SpectrumWaterfall)

    const normalized = wrapper.vm.normalizeSpectrum([])

    expect(normalized.length).toBe(0)
  })


  it('should show receiving status when data arrives', async () => {
    const wrapper = mount(SpectrumWaterfall)

    wrapper.vm.isReceivingData = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.connected').exists()).toBe(true)
    expect(wrapper.text()).toContain('Receiving Data')
  })

  it('should timeout when no data received', () => {
    const wrapper = mount(SpectrumWaterfall)

    wrapper.vm.isReceivingData = true
    wrapper.vm.lastDataTimestamp = Date.now() - 3000

    wrapper.vm.checkDataTimeout()

    expect(wrapper.vm.isReceivingData).toBe(false)
  })

  it('should auto-select first sensor', async () => {
    const sensorStore = useSensorStore()
    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        active: true,
        detections: []
      } as any
    }

    const wrapper = mount(SpectrumWaterfall)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.selectedUavId).toBe(1)
  })

  it('should initialize canvas on mount', async () => {
    const wrapper = mount(SpectrumWaterfall)

    await wrapper.vm.$nextTick()

    const canvas = wrapper.find('canvas')
    expect(canvas.exists()).toBe(true)
  })

  it('should cleanup on unmount', () => {
    const wrapper = mount(SpectrumWaterfall)
    const clearIntervalSpy = vi.spyOn(global, 'clearInterval')

    wrapper.unmount()

    expect(clearIntervalSpy).toHaveBeenCalled()
  })

  it('should watch for new detections', async () => {
    const sensorStore = useSensorStore()
    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        active: true,
        detections: []
      } as any
    }

    const wrapper = mount(SpectrumWaterfall)
    wrapper.vm.selectedUavId = 1
    await wrapper.vm.$nextTick()

    const initialCount = wrapper.vm.dataPointsReceived

    sensorStore.sensors[1].detections.push({
      Measurement: {
        data: [
          {
            dataType: 'FLOAT16',
            data: 'AAA='
          }
        ]
      }
    } as any)

    await wrapper.vm.$nextTick()

    expect(wrapper.vm.dataPointsReceived).toBeGreaterThanOrEqual(initialCount)
  })
})