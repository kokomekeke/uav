import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConnectionView from '@/views/ConnectionView.vue'
import { useConnectionStore } from '@/stores/connection'
import { useSensorStore } from '@/stores/sensor'

vi.mock('@/stores/sensor', () => ({
  useSensorStore: vi.fn(() => ({
    fetchSensors: vi.fn().mockResolvedValue(undefined)
  }))
}))

describe('ConnectionView', () => {
  let wrapper: VueWrapper
  let connectionStore: ReturnType<typeof useConnectionStore>
  let sensorStore: ReturnType<typeof useSensorStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    connectionStore = useConnectionStore()
    sensorStore = useSensorStore()

    wrapper = mount(ConnectionView, {
      props: {
        isModalVisible: true
      },
      global: {
        stubs: {
          CenteredModal: {
            template: `
              <div class="modal">
                <slot name="header" />
                <slot name="body" />
                <slot name="submit" />
                <slot name="alert" />
              </div>
            `
          }
        }
      }
    })
  })

  afterEach(() => {
    wrapper.unmount()
    vi.clearAllMocks()
  })

  describe('Component Rendering', () => {
    it('should render modal when isModalVisible is true', () => {
      expect(wrapper.find('.modal').exists()).toBe(true)
    })

    it('should display IP input field', () => {
      const input = wrapper.find('input')
      expect(input.exists()).toBe(true)
      expect(input.attributes('placeholder')).toBe('http://192.168.0.82:5000')
    })

    it('should display connection status', () => {
      expect(wrapper.text()).toContain('Connection status:')
    })

    it('should show Connect button by default', () => {
      const buttons = wrapper.findAll('button')
      const connectBtn = buttons.find(btn => btn.text().includes('Connect') && !btn.text().includes('Test'))
      expect(connectBtn).toBeTruthy()
    })
  })

  describe('Connection States', () => {
    it('should display "Disconnected" state by default', () => {
      expect(wrapper.text()).toContain('Disconnected')
    })

    it('should display "Connecting..." state', async () => {
      connectionStore.connectionState = 'connecting'
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Connect...')
    })

    it('should display "Connected" state', async () => {
      connectionStore.connectionState = 'connected'
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Connected')
    })

    it('should display "Connection failed" state', async () => {
      connectionStore.connectionState = 'failed'
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Connection failed')
    })
  })

  describe('IP Input', () => {
    it('should bind to ipPortModel', async () => {
      const input = wrapper.find('input')
      await input.setValue('http://192.168.1.100:5000')

      expect(connectionStore.ipPortModel).toBe('http://192.168.1.100:5000')
    })

    it('should be disabled when connecting', async () => {
      connectionStore.connectionState = 'connecting'
      await wrapper.vm.$nextTick()

      const input = wrapper.find('input')
      expect(input.attributes('disabled')).toBeDefined()
    })

    it('should be disabled when connected', async () => {
      connectionStore.connectionState = 'connected'
      await wrapper.vm.$nextTick()

      const input = wrapper.find('input')
      expect(input.attributes('disabled')).toBeDefined()
    })
  })

  describe('Connect Button', () => {
    it('should call connectToServer when clicked', async () => {
      const connectSpy = vi.spyOn(connectionStore, 'connectToServer').mockResolvedValue(true)

      const buttons = wrapper.findAll('button')
      const connectBtn = buttons.find(btn => btn.classes().includes('bg-green-600'))

      await connectBtn?.trigger('click')

      expect(connectSpy).toHaveBeenCalled()
    })

    it('should be disabled when connecting', async () => {
      connectionStore.connectionState = 'connecting'
      await wrapper.vm.$nextTick()

      const buttons = wrapper.findAll('button')
      const connectBtn = buttons.find(btn => btn.classes().includes('bg-green-600'))

      expect(connectBtn?.attributes('disabled')).toBeDefined()
    })
  })

  describe('Manual Actions', () => {
    it('should show Retry button when connection failed', async () => {
      connectionStore.connectionState = 'failed'
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Retry')
    })

    it('should show Disconnect button when connected', async () => {
      connectionStore.connectionState = 'connected'
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Disconnect')
    })

    it('should always show Emergency button', () => {
      expect(wrapper.text()).toContain('Emergency')
    })
  })
})