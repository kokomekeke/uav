// tests/components/SpectrumWaterfall.spec.ts
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SpectrumWaterfall from '@/components/spectrum/SpectrumWaterfall.vue'
import { useSensorStore } from '@/stores/sensor'

// ✅ Mock canvas utilities
vi.mock('@/utils/spectrumPlot', () => ({
  SpectrumPlot: vi.fn().mockImplementation(() => ({
    drawSpectrumLine: vi.fn(),
    resize: vi.fn(),
    clear: vi.fn()
  }))
}))

vi.mock('@/utils/waterfall', () => ({
  WaterfallPlot: vi.fn().mockImplementation(() => ({
    drawWaterfallRow: vi.fn(),
    resize: vi.fn(),
    clear: vi.fn()
  }))
}))

describe('SpectrumWaterfall', () => {
  let wrapper: any
  let store: any

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useSensorStore()

    // ✅ Mock sensors
    store.sensors = {
      17: {
        uav_id: 17,
        uav_label: 'Test UAV',
        active: true,
        detections: []
      }
    }

    wrapper = mount(SpectrumWaterfall, {
      global: {
        plugins: [createPinia()]
      }
    })
  })

  afterEach(() => {
    wrapper.unmount()
  })

  it('renders canvas elements', () => {
    expect(wrapper.find('.spectrum-canvas').exists()).toBe(true)
    expect(wrapper.find('.waterfall-canvas').exists()).toBe(true)
  })

  it('auto-selects first available sensor', async () => {
    await flushPromises()

    expect(wrapper.vm.selectedUavId).toBe(17)
  })

  it('displays sensor in dropdown', () => {
    const options = wrapper.findAll('option')
    expect(options.length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('Test UAV')
  })

  it('toggles spectrum visibility', async () => {
    const spectrumButton = wrapper.findAll('button')[0]

    expect(wrapper.vm.showSpectrum).toBe(true)

    await spectrumButton.trigger('click')

    expect(wrapper.vm.showSpectrum).toBe(false)
  })

  it('processes spectrum data when detections update', async () => {
    // ✅ Mock FLOAT16 data
    const mockMeasurement = {
      Measurement: {
        time: '2025-12-12T10:00:00Z',
        data: [{
          dataType: 'FLOAT16',
          data: btoa('test_data'), // Base64 mock
          centerFrequency: 300000000
        }]
      },
      timestamp: Date.now()
    }

    // ✅ Triggerelés
    store.sensors[17].detections = [mockMeasurement]

    await flushPromises()

    expect(wrapper.vm.dataPointsReceived).toBeGreaterThan(0)
  })

  it('updates data counter on new detections', async () => {
    const initialCount = wrapper.vm.dataPointsReceived

    // Add detection
    store.sensors[17].detections.push({
      Measurement: { data: [] },
      timestamp: Date.now()
    })

    await flushPromises()

    // Counter should not change if data is invalid
    expect(wrapper.vm.dataPointsReceived).toBe(initialCount)
  })
})