import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import HeatmapComponent from '@/components/map/HeatmapComponent.vue'

// -----------------------------------------------------------------------------
// 🔥 MOCKOK
// -----------------------------------------------------------------------------

// leaflet + heat mock
vi.mock('leaflet', () => ({
  default: {},
  heatLayer: vi.fn(() => ({
    addTo: vi.fn(),
    setLatLngs: vi.fn(),
    redraw: vi.fn(),
    remove: vi.fn()
  }))
}))

// vue-leaflet stubok
vi.mock('@vue-leaflet/vue-leaflet', () => ({
  LMap: {
    template: '<div data-test="l-map"><slot /></div>',
    props: ['zoom', 'center']
  },
  LTileLayer: {
    template: '<div data-test="tile-layer" />'
  }
}))

// vueuse throttle
vi.mock('@vueuse/core', () => ({
  useThrottleFn: (fn: any) => fn
}))

// geoloc store mock
vi.mock('@/stores/geoloc', () => ({
  useGeoLocStore: () => ({
    heatMapPoints: [
      {
        coordinate: [47, 19],
        lastUpdate: Date.now()
      }
    ]
  })
}))

// -----------------------------------------------------------------------------
// 🧪 TESTEK
// -----------------------------------------------------------------------------

describe('HeatmapComponent', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  const mountHeatmap = (props: any = {}) =>
    mount(HeatmapComponent, {
      props,
      global: {
        plugins: [createPinia()]
      }
    })

  it('renders component', () => {
    const wrapper = mountHeatmap()
    expect(wrapper.exists()).toBe(true)
  })

  it('renders Leaflet map', () => {
    const wrapper = mountHeatmap()
    expect(wrapper.find('[data-test="l-map"]').exists()).toBe(true)
  })

  it('shows statistics panel', () => {
    const wrapper = mountHeatmap()
    expect(wrapper.text()).toContain('Heatmap Statistics')
    expect(wrapper.text()).toContain('Source Points')
  })

  it('toggles control panel when settings button clicked', async () => {
    const wrapper = mountHeatmap({ showControls: true })

    const settingsBtn = wrapper.find('button')
    expect(settingsBtn.exists()).toBe(true)

    await settingsBtn.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Heatmap Settings')
  })

  it('processes incoming heatMapPoints into persistedPoints', async () => {
    const wrapper = mountHeatmap()
    const vm = wrapper.vm as any

    // throttle miatt
    vi.runAllTimers()
    await wrapper.vm.$nextTick()

    expect(vm.persistedPoints.length).toBeGreaterThan(0)
  })

  it('limits persisted points by maxPoints', async () => {
    const wrapper = mountHeatmap()
    const vm = wrapper.vm as any

    vm.dataSettings.maxPoints = 1
    await wrapper.vm.$nextTick()

    vm.persistedPoints.push(
      { coordinate: [1, 1], lastUpdate: Date.now() },
      { coordinate: [2, 2], lastUpdate: Date.now() }
    )

    await wrapper.vm.$nextTick()
    vi.runAllTimers()

    expect(vm.persistedPoints.length).toBeLessThanOrEqual(1)
  })

  it('clears heatmap when Clear Heatmap clicked', async () => {
    const wrapper = mountHeatmap({ showControls: true })
    const vm = wrapper.vm as any

    vm.showControlPanel = true
    await wrapper.vm.$nextTick()

    const clearBtn = wrapper
      .findAll('button')
      .find(b => b.text().includes('Clear Heatmap'))

    expect(clearBtn).toBeDefined()

    await clearBtn!.trigger('click')
    expect(vm.persistedPoints.length).toBe(0)
  })

  it('forces heatmap refresh manually', async () => {
    const wrapper = mountHeatmap({ showControls: true })
    const vm = wrapper.vm as any

    vm.showControlPanel = true
    await wrapper.vm.$nextTick()

    const refreshBtn = wrapper
      .findAll('button')
      .find(b => b.text().includes('Force Refresh'))

    expect(refreshBtn).toBeDefined()

    await refreshBtn!.trigger('click')
    expect(wrapper.exists()).toBe(true)
  })

  it('exports data without crashing', async () => {
    const wrapper = mountHeatmap({ showControls: true })
    const vm = wrapper.vm as any

    vm.showControlPanel = true
    await wrapper.vm.$nextTick()

    const exportBtn = wrapper
      .findAll('button')
      .find(b => b.text().includes('Export Data'))

    expect(exportBtn).toBeDefined()

    // mock URL methods
    const createSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:url')
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})

    await exportBtn!.trigger('click')

    expect(createSpy).toHaveBeenCalled()
    expect(revokeSpy).toHaveBeenCalled()

    createSpy.mockRestore()
    revokeSpy.mockRestore()
  })

  it('cleans up on unmount', () => {
    const wrapper = mountHeatmap()
    expect(() => wrapper.unmount()).not.toThrow()
  })
})
