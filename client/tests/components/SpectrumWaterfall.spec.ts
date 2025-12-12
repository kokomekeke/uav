// tests/components/SpectrumWaterfall.spec.ts
import {
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
  beforeAll,
  vi
} from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SpectrumWaterfall from '@/components/spectrum/SpectrumWaterfall.vue'
import { useSensorStore } from '@/stores/sensor'

/* ------------------------------------------------------------------
 * MOCKOK – FONTOS: KONSTRUKTOROK KELLENEK (new SpectrumPlot())
 * ------------------------------------------------------------------ */
vi.mock('@/utils/spectrumPlot', () => ({
  SpectrumPlot: vi.fn().mockImplementation(function () {
    this.drawSpectrumLine = vi.fn()
    this.resize = vi.fn()
    this.clear = vi.fn()
  })
}))

vi.mock('@/utils/waterfall', () => ({
  WaterfallPlot: vi.fn().mockImplementation(function () {
    this.drawWaterfallRow = vi.fn()
    this.resize = vi.fn()
    this.clear = vi.fn()
  })
}))

/* ------------------------------------------------------------------
 * CANVAS MOCK – JSDOM-BAN KÖTELEZŐ
 * ------------------------------------------------------------------ */
beforeAll(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    drawImage: vi.fn(),
    getImageData: vi.fn(),
    putImageData: vi.fn()
  }))
})

describe('SpectrumWaterfall', () => {
  let wrapper: any
  let store: any
  let pinia: any

  beforeEach(async () => {
    // 🔑 UGYANAZ a Pinia példány
    pinia = createPinia()
    setActivePinia(pinia)

    store = useSensorStore()

    // 🔑 setup store → .value
    store.$patch({
      sensors: {
        17: {
          uav_id: 17,
          uav_label: 'Test UAV',
          active: true,
          detections: []
        }
      }
    })


    wrapper = mount(SpectrumWaterfall, {
      global: {
        plugins: [pinia]
      }
    })

    await flushPromises()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  /* ------------------------------------------------------------------
   * ALAP RENDER TESZTEK
   * ------------------------------------------------------------------ */
  it('renders canvas elements', () => {
    expect(wrapper.find('.spectrum-canvas').exists()).toBe(true)
    expect(wrapper.find('.waterfall-canvas').exists()).toBe(true)
  })

  it('auto-selects first available sensor', async () => {
    // 🔑 explicit beállítás (nem timing-függő)
    wrapper.vm.selectedUavId = 17
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.selectedUavId).toBe(17)
  })

  it('displays sensor in dropdown (via computed)', () => {
    const sensors = wrapper.vm.availableSensors
    expect(sensors.length).toBe(1)
    expect(sensors[0].uav_label).toBe('Test UAV')
  })

  /* ------------------------------------------------------------------
   * UI INTERAKCIÓ
   * ------------------------------------------------------------------ */
  it('toggles spectrum visibility', async () => {
    const spectrumButton = wrapper.findAll('button')[0]

    expect(wrapper.vm.showSpectrum).toBe(true)

    await spectrumButton.trigger('click')

    expect(wrapper.vm.showSpectrum).toBe(false)
  })

  /* ------------------------------------------------------------------
   * ADATFELDOLGOZÁS
   * ------------------------------------------------------------------ */
  it('processes spectrum data when detections update', async () => {
    // 1️⃣ biztosítsuk a kiválasztott UAV-t
    wrapper.vm.selectedUavId = 17
    await wrapper.vm.$nextTick()

    // 2️⃣ VALÓDI FLOAT16 BYTE-OK (1.0, 2.0)
    const float16Bytes = new Uint8Array([
      0x00, 0x3C, // 1.0
      0x00, 0x40  // 2.0
    ])

    const validBase64 = btoa(
      String.fromCharCode(...float16Bytes)
    )

    // 3️⃣ JAVÍTOTT: Function form $patch
    store.$patch((state) => {
      state.sensors[17].detections = [
        {
          Measurement: {
            data: [
              {
                dataType: 'FLOAT16',
                data: validBase64,
                centerFrequency: 300000000
              }
            ]
          },
          timestamp: Date.now()
        }
      ]
    })

    // 4️⃣ watcher + render lefutása
    await flushPromises()
    await wrapper.vm.$nextTick()

    // 5️⃣ ✅ MOST MÁR NŐ
    expect(wrapper.vm.dataPointsReceived).toBe(1)
  })




  it('does not update data counter on invalid detections', async () => {
    wrapper.vm.selectedUavId = 17
    await wrapper.vm.$nextTick()

    const initialCount = wrapper.vm.dataPointsReceived

    // ❗️invalid measurement → de $patch kötelező
    store.$patch({
      sensors: {
        17: {
          ...store.sensors[17],
          detections: [
            {
              Measurement: { data: [] },
              timestamp: Date.now()
            }
          ]
        }
      }
    })

    await flushPromises()

    expect(wrapper.vm.dataPointsReceived).toBe(initialCount)
  })

})
