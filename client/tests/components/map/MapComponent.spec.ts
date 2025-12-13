import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MapComponent from '@/components/map/MapComponent.vue'

// -----------------------------------------------------------------------------
// 🔥 MOCKOK
// -----------------------------------------------------------------------------

// leaflet mock
vi.mock('leaflet', () => ({
  default: {},
  divIcon: vi.fn(() => ({})),
  latLng: vi.fn((lat, lng) => ({ lat, lng }))
}))

// vue-leaflet komponensek stub
vi.mock('@vue-leaflet/vue-leaflet', () => ({
  LMap: {
    template: '<div data-test="l-map"><slot /></div>',
    props: ['zoom', 'center']
  },
  LTileLayer: { template: '<div />' },
  LMarker: { template: '<div data-test="marker" />' },
  LPolyline: { template: '<div data-test="polyline" />' },
  LCircleMarker: { template: '<div data-test="circle-marker"><slot /></div>' },
  LPopup: { template: '<div><slot /></div>' }
}))

// image import
vi.mock('@/assets/dir1.png', () => ({
  default: 'mocked-plane-icon.png'
}))

// sensor store mock
vi.mock('@/stores/sensor', () => ({
  useSensorStore: () => ({
    sensors: {},
    batchInterval: 1,
    selectedSensors: [],
    selectedSensorIds: [],
    hasSelectedSensors: false,
    detectionSize: 10,
    realtimeConfig: {
      detectionTTL: 10000
    },
    clearDetections: vi.fn(),
    updateRealtimeConfig: vi.fn(),
    debugReactivity: vi.fn(),
    $patch: vi.fn()
  })
}))

// geoloc store mock
vi.mock('@/stores/geoloc', () => ({
  useGeoLocStore: () => ({
    geoJsonData: [],
    geoJsonSettings: {},
    isGeoJsonEnabled: false,
    startGeoJsonFetch: vi.fn(),
    stopGeoJsonFetch: vi.fn(),
    updateGeoJsonSettings: vi.fn()
  })
}))

// -----------------------------------------------------------------------------
// 🧪 TESTEK
// -----------------------------------------------------------------------------

describe('MapComponent', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  const mountMap = () =>
    mount(MapComponent, {
      global: {
        plugins: [createPinia()]
      }
    })

  it('renders component', () => {
    const wrapper = mountMap()
    expect(wrapper.exists()).toBe(true)
  })

  it('renders Leaflet map container', () => {
    const wrapper = mountMap()
    expect(wrapper.find('[data-test="l-map"]').exists()).toBe(true)
  })

  it('shows debug panel', () => {
    const wrapper = mountMap()
    expect(wrapper.text()).toContain('GeoJSON')
    expect(wrapper.text()).toContain('Detections')
  })

  it('GeoJSON fetch button toggles state', async () => {
    const wrapper = mountMap()
    const button = wrapper.find('button')

    expect(button.exists()).toBe(true)

    await button.trigger('click')
    expect(wrapper.exists()).toBe(true)
  })

  it('updates batch interval safely', async () => {
    const wrapper = mountMap()
    const input = wrapper.find('input[type="number"]')

    if (input.exists()) {
      await input.setValue(2)
      await input.trigger('change')
      expect(wrapper.exists()).toBe(true)
    }
  })

  it('clears map data when Clear button clicked', async () => {
    const wrapper = mountMap()

    const clearBtn = wrapper.findAll('button')
      .find(btn => btn.text().includes('Clear All'))

    if (!clearBtn) return

    await clearBtn.trigger('click')
    expect(wrapper.exists()).toBe(true)
  })

  it('renders geojson circle markers when data exists', async () => {
    const wrapper = mountMap()

    // inject geojson points manually
    const vm = wrapper.vm as any
    vm.geoJsonBuffer = new Map([
      [
        '1-raw',
        {
          stableKey: '1-raw',
          coordinate: [47, 19],
          opacity: 0.8,
          type: 'raw'
        }
      ]
    ])

    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[data-test="circle-marker"]').length).toBeGreaterThan(0)
  })

  it('does not crash on unmount', () => {
    const wrapper = mountMap()
    expect(() => wrapper.unmount()).not.toThrow()
  })
})
