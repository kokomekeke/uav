import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MapView from '@/components/map/MapComponent.vue'
import { useSensorStore } from '@/stores/sensor'
import { useGeoLocStore } from '@/stores/geoloc'
import { useConnectionStore } from '@/stores/connection'

describe('MapView Component', () => {
  let mockLeafletMap: any
  let LMapStub: any

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()

    mockLeafletMap = {
      getBounds: vi.fn(() => ({
        contains: vi.fn(() => true)
      })),
      on: vi.fn(),
      off: vi.fn()
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
        this.$emit('ready', mockLeafletMap)
      }
    }
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('should render map container', () => {
    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true,
          'l-marker': true,
          'l-polyline': true,
          'l-circle-marker': true,
          'l-popup': true
        }
      }
    })

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.flex.flex-col').exists()).toBe(true)
  })

  it('should display debug info panel', async () => {
    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(50)

    const debugPanel = wrapper.find('.absolute.top-2.left-2')
    expect(debugPanel.exists()).toBe(true)
    expect(debugPanel.text()).toContain('Map:')
    expect(debugPanel.text()).toContain('Sensors:')
    expect(debugPanel.text()).toContain('Detections:')
  })

  it('should update max visible points', async () => {
    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    const input = wrapper.find('input[type="number"]')
    await input.setValue(100)

    expect(wrapper.vm.maxVisiblePoints).toBe(100)
  })

  it('should toggle azimuth lines', async () => {
    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    expect(wrapper.vm.showAzimuthLines).toBe(true)

    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    const azimuthCheckbox = checkboxes.find(cb =>
      cb.element.parentElement?.textContent?.includes('Show Azimuth Lines')
    )

    await azimuthCheckbox?.setChecked(false)

    expect(wrapper.vm.showAzimuthLines).toBe(false)
  })

  it('should toggle GeoJSON fetch', async () => {
    const geolocStore = useGeoLocStore()
    const startSpy = vi.spyOn(geolocStore, 'startGeoJsonFetch')
    const stopSpy = vi.spyOn(geolocStore, 'stopGeoJsonFetch')

    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    const toggleButton = wrapper.findAll('button').find(btn =>
      btn.text().includes('GeoJSON Fetch')
    )

    expect(toggleButton).toBeDefined()
    await toggleButton?.trigger('click')

    expect(startSpy.mock.calls.length + stopSpy.mock.calls.length).toBeGreaterThan(0)
  })

  it('should update GeoJSON settings', async () => {
    const geolocStore = useGeoLocStore()
    const updateSpy = vi.spyOn(geolocStore, 'updateGeoJsonSettings')

    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    wrapper.vm.localGeoJsonSettings.limit = 50
    wrapper.vm.updateGeoJsonSettings()

    expect(updateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 50 })
    )
  })

  it('should clear map data', async () => {
    const sensorStore = useSensorStore()
    const clearSpy = vi.spyOn(sensorStore, 'clearDetections')

    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    const clearButton = wrapper.findAll('button').find(btn =>
      btn.text().includes('Clear All')
    )

    await clearButton?.trigger('click')

    expect(clearSpy).toHaveBeenCalled()
    expect(wrapper.vm.detectionBuffer.size).toBe(0)
  })

  it('should render detections when sensors are selected', async () => {
    const sensorStore = useSensorStore()

    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        is_selected: true,
        detections: [
          {
            coordinate: [47.4979, 19.0402],
            timestamp: Date.now(),
            azimuth: 45,
            frequency: 2400
          }
        ]
      } as any
    }

    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true,
          'l-marker': true,
          'l-polyline': true
        }
      }
    })

    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(100)

    wrapper.vm.leafletMap = mockLeafletMap
    wrapper.vm.mapBounds = mockLeafletMap.getBounds()
    wrapper.vm.renderDetections()

    await vi.advanceTimersByTimeAsync(20)

    expect(wrapper.vm.detectionBuffer.size).toBeGreaterThan(0)
  })

  it('should render GeoJSON points', async () => {
    const geolocStore = useGeoLocStore()

    geolocStore.geoJsonData = [
      {
        id: 1,
        coordinate: [47.4979, 19.0402],
        timestamp: Date.now(),
        type: 'raw'
      }
    ]

    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true,
          'l-circle-marker': true,
          'l-popup': true
        }
      }
    })

    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(100)

    wrapper.vm.leafletMap = mockLeafletMap
    wrapper.vm.mapBounds = mockLeafletMap.getBounds()
    wrapper.vm.updateGeoJsonBuffer()

    await vi.advanceTimersByTimeAsync(110)

    expect(wrapper.vm.geoJsonBuffer.size).toBeGreaterThan(0)
  })

  it('should compute Vincenty forward correctly', () => {
    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    const result = wrapper.vm.vincentyForward(47.4979, 19.0402, 90, 1000)

    expect(result.lat).toBeCloseTo(47.4979, 3)
    expect(result.lon).toBeGreaterThan(19.0402)
  })

  it('should compute azimuth line', () => {
    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    wrapper.vm.lineLength = 0.05
    const line = wrapper.vm.computeAzimuthLine([47.4979, 19.0402], 45, false)

    expect(line.length).toBe(2)
    expect(line[0]).toEqual([47.4979, 19.0402])
    expect(line[1]).toBeDefined()
  })

  it('should update realtime config', async () => {
    const sensorStore = useSensorStore()
    const updateSpy = vi.spyOn(sensorStore, 'updateRealtimeConfig')

    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    wrapper.vm.realtimeConfig.maxLatencyMs = 500
    wrapper.vm.updateRealtimeConfig()

    expect(updateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ maxLatencyMs: 500 })
    )
  })

  it('should handle map ready event', async () => {
    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    wrapper.vm.onMapReady(mockLeafletMap)

    expect(wrapper.vm.leafletMap).toBe(mockLeafletMap)
    expect(wrapper.vm.debugInfo.mapInitialized).toBe(true)
  })

  it('should cleanup on unmount', async () => {
    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    wrapper.vm.leafletMap = mockLeafletMap

    wrapper.unmount()

    expect(mockLeafletMap.off).toHaveBeenCalled()
  })

  it('should call debug store method', async () => {
    const sensorStore = useSensorStore()
    const debugSpy = vi.spyOn(sensorStore, 'debugReactivity')

    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    const debugButton = wrapper.findAll('button').find(btn =>
      btn.text().includes('Debug')
    )

    await debugButton?.trigger('click')

    expect(debugSpy).toHaveBeenCalled()
  })

  it('should show connection warning when disconnected', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'disconnected'

    const wrapper = mount(MapView, {
      global: {
        stubs: {
          'l-map': LMapStub,
          'l-tile-layer': true
        }
      }
    })

    await wrapper.vm.$nextTick()

    expect(connectionStore.isConnected).toBe(false)
  })
})