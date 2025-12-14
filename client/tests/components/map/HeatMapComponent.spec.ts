import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import HeatMapView from '@/components/map/HeatMapComponent.vue'
import { useGeoLocStore } from '@/stores/geoloc'

describe('HeatMapView Component', () => {
  let mockLeafletMap: any
  let mockHeatLayer: any
  let LMapStub: any
  let LTileLayerStub: any

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()

    mockHeatLayer = {
      addTo: vi.fn().mockReturnThis(),
      setLatLngs: vi.fn(),
      redraw: vi.fn(),
      remove: vi.fn()
    }

    mockLeafletMap = {
      getBounds: vi.fn(() => ({
        contains: vi.fn(() => true)
      })),
      on: vi.fn(),
      off: vi.fn(),
      remove: vi.fn()
    }

    LMapStub = {
      name: 'LMap',
      template: '<div class="l-map-stub"><slot /></div>',
      props: ['zoom', 'center'],
      emits: ['ready'],
      data() {
        return {
          leafletObject: mockLeafletMap
        }
      },
      async mounted() {
        await this.$nextTick()
        this.$emit('ready')
      }
    }

    LTileLayerStub = {
      name: 'LTileLayer',
      template: '<div class="l-tile-layer-stub"></div>',
      props: ['url', 'attribution']
    }

    global.L = {
      heatLayer: vi.fn(() => mockHeatLayer)
    } as any
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  it('should render with default props', () => {
    const wrapper = mount(HeatMapView, {
      props: {
        showControls: true,
        compactMode: false
      },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.flex').exists()).toBe(true)
  })

  it('should render without controls in compact mode', () => {
    const wrapper = mount(HeatMapView, {
      props: {
        showControls: false,
        compactMode: true
      },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('should toggle settings panel', async () => {
    const wrapper = mount(HeatMapView, {
      props: {
        showControls: true
      },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    const settingsButton = wrapper.find('button')
    expect(settingsButton.exists()).toBe(true)

    await settingsButton.trigger('click')
    await wrapper.vm.$nextTick()

    const settingsPanel = wrapper.find('.absolute.top-14')
    expect(settingsPanel.exists()).toBe(true)

    await settingsButton.trigger('click')
    await wrapper.vm.$nextTick()
  })

  it('should display correct statistics', async () => {
    const geolocStore = useGeoLocStore()

    geolocStore.heatMapPoints = [
      { coordinate: [47.4979, 19.0402], lastUpdate: Date.now() },
      { coordinate: [47.4980, 19.0403], lastUpdate: Date.now() },
      { coordinate: [47.4981, 19.0404], lastUpdate: Date.now() }
    ]

    const wrapper = mount(HeatMapView, {
      props: { showControls: true },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(200)

    const statsPanel = wrapper.find('.absolute.top-2.left-2')
    expect(statsPanel.exists()).toBe(true)
    expect(statsPanel.text()).toContain('Heatmap Statistics')
  })

  it('should update heatmap settings', async () => {
    const wrapper = mount(HeatMapView, {
      props: { showControls: true },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    const radiusSlider = wrapper.findAll('input[type="range"]').find(input =>
      input.element.parentElement?.textContent?.includes('Radius')
    )

    await radiusSlider?.setValue(30)

    expect(wrapper.vm.heatmapSettings.radius).toBe(30)
  })

  it('should handle max points limit', async () => {
    const wrapper = mount(HeatMapView, {
      props: { showControls: true },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    wrapper.vm.dataSettings.maxPoints = 3

    const points = Array.from({ length: 5 }, (_, i) => ({
      coordinate: [47.4979 + i * 0.001, 19.0402] as [number, number],
      lastUpdate: Date.now() - i * 1000
    }))

    points.forEach(p => {
      wrapper.vm.persistedPoints.push(p)
    })

    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(200)

    expect(wrapper.vm.persistedPoints.length).toBeLessThanOrEqual(3)
  })

  it('should clear heatmap', async () => {
    const wrapper = mount(HeatMapView, {
      props: { showControls: true },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    wrapper.vm.persistedPoints = [
      { coordinate: [47.4979, 19.0402], lastUpdate: Date.now() },
      { coordinate: [47.4980, 19.0403], lastUpdate: Date.now() }
    ]

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    const clearButton = wrapper.findAll('button').find(btn =>
      btn.text().includes('Clear Heatmap')
    )

    expect(clearButton).toBeDefined()
    await clearButton?.trigger('click')

    expect(wrapper.vm.persistedPoints.length).toBe(0)
  })

  it('should export data', async () => {
    const wrapper = mount(HeatMapView, {
      props: { showControls: true },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    const exportDataSpy = vi.spyOn(wrapper.vm, 'exportData')

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    const exportButton = wrapper.findAll('button').find(btn =>
      btn.text().includes('Export Data')
    )

    await exportButton?.trigger('click')

    expect(exportDataSpy).toHaveBeenCalled()
  })

  it('should toggle realtime updates', async () => {
    const wrapper = mount(HeatMapView, {
      props: { showControls: true },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    const realtimeCheckbox = wrapper.find('input[type="checkbox"]#realtime-compact')

    expect(wrapper.vm.dataSettings.showRealtime).toBe(true)

    await realtimeCheckbox.setChecked(false)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.dataSettings.showRealtime).toBe(false)
  })

  it('should initialize map on mount', async () => {
    const wrapper = mount(HeatMapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(600)

    expect(wrapper.vm.leafletMap).toBeDefined()
  })

  it('should set center from first point', async () => {
    const wrapper = mount(HeatMapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    wrapper.vm.persistedPoints = [
      { coordinate: [47.4979, 19.0402], lastUpdate: Date.now() }
    ]

    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(200)

    expect(wrapper.vm.center).toBeTruthy()
  })

  it('should handle grid resolution change', async () => {
    const wrapper = mount(HeatMapView, {
      props: { showControls: true },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    const initialResolution = wrapper.vm.dataSettings.gridResolution

    wrapper.vm.dataSettings.gridResolution = 5

    await wrapper.vm.$nextTick()

    expect(wrapper.vm.dataSettings.gridResolution).toBe(5)
    expect(wrapper.vm.dataSettings.gridResolution).not.toBe(initialResolution)
  })

  it('should cleanup on unmount', async () => {
    const wrapper = mount(HeatMapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(600)

    wrapper.vm.leafletMap = mockLeafletMap
    wrapper.vm.heatLayer = mockHeatLayer

    wrapper.unmount()

    expect(wrapper.vm.leafletMap).toBeNull()
    expect(wrapper.vm.heatLayer).toBeNull()
  })

  it('should compute heatmap points correctly', async () => {
    const wrapper = mount(HeatMapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    wrapper.vm.persistedPoints = [
      { coordinate: [47.4979, 19.0402], lastUpdate: Date.now() },
      { coordinate: [47.4979, 19.0402], lastUpdate: Date.now() - 1000 },
      { coordinate: [47.4980, 19.0403], lastUpdate: Date.now() }
    ]

    await wrapper.vm.$nextTick()

    const heatmapPoints = wrapper.vm.heatmapPoints

    expect(heatmapPoints.length).toBeLessThanOrEqual(wrapper.vm.persistedPoints.length)
  })

  it('should display legend', () => {
    const wrapper = mount(HeatMapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    const legend = wrapper.find('.absolute.bottom-2.right-2')
    expect(legend.exists()).toBe(true)
    expect(legend.text()).toContain('Old → New')
  })

  it('should handle update interval change', async () => {
    const wrapper = mount(HeatMapView, {
      props: { showControls: true },
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': LTileLayerStub
        }
      }
    })

    wrapper.vm.dataSettings.updateInterval = 2000

    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(200)

    expect(wrapper.vm.dataSettings.updateInterval).toBe(2000)
  })
})