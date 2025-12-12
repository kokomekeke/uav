import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import ConnectionView from '@/views/ConnectionView.vue'
import { createPinia, setActivePinia } from 'pinia'
import { useConnectionStore } from "@/stores/connection.ts"
import { useSensorStore } from "@/stores/sensor.ts"

let pinia

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
})

afterEach(() => {
  // ✅ Cleanup
  vi.clearAllMocks()
})

/* ------------------------------------------------------------------
   STUB MODAL
------------------------------------------------------------------- */

const CenteredModalStub = {
  template: `
    <div v-if="show" data-test="modal">
      <slot name="header" />
      <slot name="body" />
      <slot name="submit" />
      <slot name="alert" />
      <button data-test="close" @click="$emit('close')">close</button>
    </div>
  `,
  props: ['show'],
  emits: ['close']
}

/* ------------------------------------------------------------------
   HELPERS
------------------------------------------------------------------- */

const mountComponent = (props = {}) => {
  const wrapper = mount(ConnectionView, {
    props: {
      isModalVisible: false,
      ...props
    },
    global: {
      plugins: [pinia],
      stubs: {
        CenteredModal: CenteredModalStub
      }
    }
  })
  return wrapper
}

/* ------------------------------------------------------------------
   TESTS
------------------------------------------------------------------- */

describe('ConnectionView.vue', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })

  it('does not show modal by default', () => {
    const wrapper = mountComponent()
    expect(wrapper.find('[data-test="modal"]').exists()).toBe(false)
  })

  it('shows modal when isModalVisible=true', async () => {
    const wrapper = mountComponent({ isModalVisible: true })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="modal"]').exists()).toBe(true)
  })

  it('emits update:isModalVisible when closed', async () => {
    const wrapper = mountComponent({ isModalVisible: true })
    await wrapper.vm.$nextTick()

    await wrapper.find('[data-test="close"]').trigger('click')

    expect(wrapper.emitted('update:isModalVisible')).toBeTruthy()
    expect(wrapper.emitted('update:isModalVisible')![0]).toEqual([false])
  })

  it('disables connect button when ipPort is empty', async () => {
    const connectionStore = useConnectionStore()

    // ✅ Explicit setup
    connectionStore.ipPort = ''
    connectionStore.connectionState = 'disconnected'

    const wrapper = mountComponent({ isModalVisible: true })
    await wrapper.vm.$nextTick()

    const connectButton = wrapper.find('button.bg-green-600')
    expect(connectButton.exists()).toBe(true)

    // ✅ Check disabled state
    expect(connectButton.element.disabled).toBe(true)
  })

  it('calls connectToServer when Connect clicked', async () => {
    const connectionStore = useConnectionStore()
    const sensorStore = useSensorStore()

    connectionStore.connectionState = 'disconnected'
    connectionStore.ipPort = 'http://localhost:5000'

    const connectSpy = vi.fn().mockResolvedValue(true)
    const fetchSensorsSpy = vi.fn().mockResolvedValue(undefined)

    connectionStore.connectToServer = connectSpy
    sensorStore.fetchSensors = fetchSensorsSpy

    const wrapper = mount(ConnectionView, {
      props: {
        isModalVisible: true
      },
      global: {
        plugins: [pinia],
        stubs: {
          CenteredModal: CenteredModalStub
        }
      }
    })

    await wrapper.vm.$nextTick()

    const connectButton = wrapper.find('button.bg-green-600')
    expect(connectButton.exists()).toBe(true)
    expect(connectButton.element.disabled).toBe(false)

    await connectButton.trigger('click')
    await wrapper.vm.$nextTick()

    expect(connectSpy).toHaveBeenCalledTimes(1)
    expect(fetchSensorsSpy).toHaveBeenCalledTimes(1)
  })

  it('closes modal after successful connect', async () => {
    const connectionStore = useConnectionStore()
    const sensorStore = useSensorStore()

    connectionStore.ipPort = 'http://localhost:5000'
    connectionStore.connectionState = 'disconnected'
    connectionStore.connectToServer = vi.fn().mockResolvedValue(true)
    sensorStore.fetchSensors = vi.fn().mockResolvedValue(undefined)

    const wrapper = mountComponent({ isModalVisible: true })
    await wrapper.vm.$nextTick()

    const connectButton = wrapper.find('button.bg-green-600')
    await connectButton.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:isModalVisible')!.at(-1)).toEqual([false])
  })

  it('closes modal on Escape key', async () => {
    const wrapper = mountComponent({ isModalVisible: true })
    await wrapper.vm.$nextTick()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))

    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:isModalVisible')).toBeTruthy()
  })

  it('shows retry button when failed', async () => {
    const connectionStore = useConnectionStore()

    const wrapper = mountComponent({ isModalVisible: true })

    connectionStore.connectionState = 'failed'

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Retry')
  })
})