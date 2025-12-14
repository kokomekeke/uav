import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SensorSidebar from '@/components/layout/BurgerMenu.vue'
import { useSensorStore } from '@/stores/sensor'
import { useConnectionStore } from '@/stores/connection'
import { mockFetch } from '../../setup.ts'
import axios from 'axios'

vi.mock('axios')

describe('SensorSidebar Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should render closed by default', () => {
    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: false
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    const sidebar = wrapper.find('.fixed.top-0.left-0')
    expect(sidebar.classes()).toContain('-translate-x-full')
  })

  it('should render open when prop is true', () => {
    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    const sidebar = wrapper.find('.fixed.top-0.left-0')
    expect(sidebar.classes()).toContain('translate-x-0')
  })

  it('should toggle menu on button click', async () => {
    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: false
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    const toggleButton = wrapper.findAll('button').find(btn =>
      btn.classes().includes('fixed')
    )

    await toggleButton?.trigger('click')

    expect(wrapper.emitted('update:isMenuOpen')).toBeTruthy()
    expect(wrapper.emitted('update:isMenuOpen')?.[0]).toEqual([true])
  })

  it('should display sensors when connected', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    const sensorStore = useSensorStore()

    vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        uav_address: '192.168.1.100',
        active: true,
        is_selected: false,
        detections: []
      } as any,
      2: {
        uav_id: 2,
        uav_label: 'UAV-2',
        uav_address: '192.168.1.101',
        active: true,
        is_selected: false,
        detections: []
      } as any
    }

    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': {
            template: '<a><slot /></a>'
          },
          'new-sensor-modal': true
        }
      }
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('UAV-1')
    expect(wrapper.text()).toContain('UAV-2')
  })

  it('should show warning when disconnected', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'disconnected'

    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Not connected to server')
  })

  it('should toggle sensor selection', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    const sensorStore = useSensorStore()

    vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        is_selected: false,
        detections: []
      } as any
    }

    const selectSpy = vi.spyOn(sensorStore, 'selectSensor')

    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': {
            template: '<a><slot /></a>'
          },
          'new-sensor-modal': true
        }
      }
    })

    await wrapper.vm.$nextTick()

    const checkbox = wrapper.find('input[type="checkbox"]')
    await checkbox.trigger('change')

    expect(selectSpy).toHaveBeenCalledWith(1)
  })

  it('should open modify panel', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    const sensorStore = useSensorStore()

    vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        uav_address: '192.168.1.100',
        active: true,
        is_selected: false,
        detections: []
      } as any
    }

    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    await wrapper.vm.$nextTick()

    const settingsButton = wrapper.findAll('button').find(btn =>
      btn.text().includes('⚙️')
    )

    await settingsButton?.trigger('click')

    expect(wrapper.vm.isModifyPanelOpen).toBe(true)
    expect(wrapper.vm.selectedSensorForModify?.uav_id).toBe(1)
  })

  it('should update sensor on confirm', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'
    connectionStore.ipPort = 'http://localhost:5000'

    const sensorStore = useSensorStore()

    vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        uav_address: '192.168.1.100',
        active: true,
        is_selected: false,
        detections: []
      } as any
    }

    const mockAxiosPatch = vi.fn().mockResolvedValue({ data: { success: true } })
    ;(axios.patch as any) = mockAxiosPatch

    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    await wrapper.vm.$nextTick()

    wrapper.vm.openModifyPanel(sensorStore.sensors[1] as any)
    await wrapper.vm.$nextTick()

    wrapper.vm.label = 'UAV-1-Modified'
    wrapper.vm.address = '192.168.1.200'

    await wrapper.vm.confirm()
    await wrapper.vm.$nextTick()

    expect(mockAxiosPatch).toHaveBeenCalledWith(
      'http://localhost:5000/v1/uav/1',
      {
        uav_label: 'UAV-1-Modified',
        uav_address: '192.168.1.200',
        active: true
      },
      { headers: { 'Content-Type': 'application/json' } }
    )
  })

  it('should open delete dialog', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    const sensorStore = useSensorStore()

    vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        is_selected: false,
        detections: []
      } as any
    }

    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true,
          teleport: true
        }
      }
    })

    await wrapper.vm.$nextTick()

    const deleteButton = wrapper.findAll('button').find(btn =>
      btn.text().includes('✕')
    )

    await deleteButton?.trigger('click')

    expect(wrapper.vm.isRemoveDialogOpen).toBe(true)
    expect(wrapper.vm.selectedSensorForModify?.uav_id).toBe(1)
  })

  it('should delete sensor', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    const sensorStore = useSensorStore()

    vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        is_selected: false,
        detections: []
      } as any
    }

    const removeSpy = vi.spyOn(sensorStore, 'removeSensor')

    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true,
          teleport: true
        }
      }
    })

    wrapper.vm.selectedSensorForModify = sensorStore.sensors[1] as any
    wrapper.vm.isRemoveDialogOpen = true

    await wrapper.vm.$nextTick()

    await wrapper.vm.removeSensor()

    expect(removeSpy).toHaveBeenCalledWith(1)
  })

  it('should display loading state', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    const sensorStore = useSensorStore()

    vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    sensorStore.isLoading = true

    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Loading')
  })

  it('should display error message', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    const sensorStore = useSensorStore()

    vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    sensorStore.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'Dummy',
        is_selected: false,
        detections: []
      } as any
    }
    sensorStore.isLoading = false
    sensorStore.errorMessage = 'Failed to load sensors'

    const wrapper = mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Failed to load sensors')
  })

  it('should fetch sensors on mount when connected', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    const sensorStore = useSensorStore()
    const fetchSpy = vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    mockFetch([])

    mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    await vi.runAllTimersAsync()

    expect(fetchSpy).toHaveBeenCalled()
  })

  it('should not fetch sensors when disconnected', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'disconnected'

    const sensorStore = useSensorStore()
    const fetchSpy = vi.spyOn(sensorStore, 'fetchSensors').mockResolvedValue()
    vi.spyOn(sensorStore, 'isWorkerReady').mockReturnValue(true)

    mount(SensorSidebar, {
      props: {
        isMenuOpen: true
      },
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          'new-sensor-modal': true
        }
      }
    })

    await vi.runAllTimersAsync()

    expect(fetchSpy).not.toHaveBeenCalled()
  })
})