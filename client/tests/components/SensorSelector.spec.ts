// tests/components/SensorSelector.spec.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SensorSelector from '@/components/SensorSelector.vue'
import { useSensorStore } from '@/stores/sensor'

describe('SensorSelector', () => {
  beforeEach(() => {
    // ✅ Új Pinia instance minden teszthez
    setActivePinia(createPinia())
  })

  it('displays available sensors', () => {
    const wrapper = mount(SensorSelector, {
      global: {
        plugins: [createPinia()]
      }
    })

    const store = useSensorStore()

    // ✅ Mock sensors
    store.sensors = {
      17: { uav_id: 17, uav_label: 'UAV Alpha', active: true, detections: [] },
      18: { uav_id: 18, uav_label: 'UAV Beta', active: true, detections: [] }
    }

    expect(wrapper.findAll('option')).toHaveLength(2)
    expect(wrapper.text()).toContain('UAV Alpha')
  })

  it('selects sensor on click', async () => {
    const wrapper = mount(SensorSelector, {
      global: {
        plugins: [createPinia()]
      }
    })

    const store = useSensorStore()
    const selectSpy = vi.spyOn(store, 'selectSensor')

    await wrapper.find('select').setValue('17')

    expect(selectSpy).toHaveBeenCalledWith(17)
  })
})