import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref, nextTick } from 'vue'
import BurgerMenu from '@/components/layout/BurgerMenu.vue'
import axios from 'axios'

// =======================
// MOCKS
// =======================

vi.mock('axios')
const mockedAxios = vi.mocked(axios)

vi.mock('@/stores/connection', () => ({
  useConnectionStore: () => ({
    ipPort: 'http://localhost:5000/'
  })
}))

vi.mock('@/components/common/NewSensorModal.vue', () => ({
  default: { template: '<div />' }
}))

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
    props: ['to']
  }
}))

// =======================
// STORE MOCK
// =======================

vi.mock('@/stores/sensor', () => {
  const sensors = ref({
    1: {
      uav_id: 1,
      uav_label: 'UAV-1',
      uav_address: '192.168.1.1',
      active: true,
      is_selected: false,
      detections: []
    }
  })

  return {
    useSensorStore: () => ({
      sensors,
      isConnected: ref(true),
      isLoading: ref(false),
      errorMessage: ref(''),
      selectedSensor: ref(null),

      fetchSensors: vi.fn(),
      initializeWorker: vi.fn(),
      isWorkerReady: vi.fn(() => false),
      selectSensor: vi.fn(),
      removeSensor: vi.fn(),
      setCurrentSensor: vi.fn()
    })
  }
})

// =======================
// TESTS
// =======================

describe('BurgerMenu.vue', () => {
  const mountMenu = (props = {}) =>
    mount(BurgerMenu, {
      props: { isMenuOpen: true, ...props },
      global: {
        plugins: [createPinia()],
        stubs: { Teleport: true }
      }
    })

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders sensor list when connected', () => {
    const wrapper = mountMenu()
    expect(wrapper.text()).toContain('UAV-1')
  })

  it('opens modify panel when settings clicked', async () => {
    const wrapper = mountMenu()
    await wrapper.find('button[title="Settings"]').trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('Host IP:')
  })

  it('pre-fills modify form with sensor data', async () => {
    const wrapper = mountMenu()
    await wrapper.find('button[title="Settings"]').trigger('click')
    await nextTick()

    const inputs = wrapper.findAll('input[type="text"]')
    expect(inputs[0].element.value).toBe('192.168.1.1')
    expect(inputs[1].element.value).toBe('UAV-1')
  })

  it('sends PATCH request on confirm', async () => {
    mockedAxios.patch.mockResolvedValue({})

    const wrapper = mountMenu()
    await wrapper.find('button[title="Settings"]').trigger('click')
    await nextTick()

    await wrapper.find('button.bg-green-700').trigger('click')

    expect(mockedAxios.patch).toHaveBeenCalledWith(
      'http://localhost:5000/v1/uav/1',
      {
        uav_label: 'UAV-1',
        uav_address: '192.168.1.1',
        active: true
      },
      expect.any(Object)
    )
  })

  it('emits update:isMenuOpen when close clicked', async () => {
    const wrapper = mountMenu({ isMenuOpen: true })
    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('update:isMenuOpen')).toBeTruthy()
  })
})
