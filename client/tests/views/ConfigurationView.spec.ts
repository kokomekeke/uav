import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ConfigurationView from '../../src/views/config/ConfigurationView.vue'
import axios from 'axios'
import { flushPromises } from '@vue/test-utils'

// 🔥 axios mock
vi.mock('axios', () => ({
  default: {
    post: vi.fn()
  }
}))

describe('ConfigurationView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders correctly', () => {
    const wrapper = mount(ConfigurationView)
    expect(wrapper.text()).toContain('Configuration Settings')
  })

  it('has default config values', () => {
    const wrapper = mount(ConfigurationView)
    const vm = wrapper.vm as any

    expect(vm.config.center_freq).toBe('446M')
    expect(vm.config.bandwidth).toBe('1M')
    expect(vm.config.bin_count).toBe('1024')
    expect(vm.config.pp_config.enabled).toBe(true)
  })

  it('parseFreq converts values correctly', () => {
    const wrapper = mount(ConfigurationView)
    const vm = wrapper.vm as any

    expect(vm.parseFreq('1M')).toBe(1_000_000)
    expect(vm.parseFreq('500k')).toBe(500_000)
    expect(vm.parseFreq('123')).toBe(123)
    expect(vm.parseFreq('')).toBe(0)
  })

  it('adds ROI setting', async () => {
    const wrapper = mount(ConfigurationView)
    const vm = wrapper.vm as any

    expect(vm.config.pp_config.roi_settings.length).toBe(0)

    vm.addRoiSetting()
    await wrapper.vm.$nextTick()

    expect(vm.config.pp_config.roi_settings.length).toBe(1)
  })

  it('removes ROI setting', async () => {
    const wrapper = mount(ConfigurationView)
    const vm = wrapper.vm as any

    vm.addRoiSetting()
    vm.addRoiSetting()
    await wrapper.vm.$nextTick()

    expect(vm.config.pp_config.roi_settings.length).toBe(2)

    vm.removeRoiSetting(0)
    await wrapper.vm.$nextTick()

    expect(vm.config.pp_config.roi_settings.length).toBe(1)
  })

  it('buildProtoConfig builds valid protobuf-like payload', () => {
    const wrapper = mount(ConfigurationView)
    const vm = wrapper.vm as any

    vm.addRoiSetting()
    vm.config.pp_config.roi_settings[0].center_frequency = '446M'
    vm.config.pp_config.roi_settings[0].threshold = '10'

    const payload = vm.buildProtoConfig(vm.config)

    expect(payload).toHaveProperty('config_id')
    expect(payload.cs.center_frequency).toBe(446_000_000)
    expect(payload.cs.bin_count).toBe(1024)
    expect(payload.cs.channel_gain).toEqual([50])

    expect(payload.pp.roi.length).toBe(1)
    expect(payload.pp.roi[0]).toMatchObject({
      roi_id: 1,
      center_frequency: 446_000_000,
      span: 10_000,
      threshold: 10
    })
  })

  it('calls axios.post when Save Configuration is clicked', async () => {
    ;(axios.post as any).mockResolvedValue({
      data: { success: true }
    })

    const wrapper = mount(ConfigurationView)

    const button = wrapper.find('button')
    await button.trigger('click')

    expect(axios.post).toHaveBeenCalledOnce()
    expect(axios.post).toHaveBeenCalledWith(
      'http://localhost:5000/v1/uav/1/command/CONFIG/',
      expect.any(Object)
    )
  })

  it('handles axios error gracefully', async () => {
      const error = new Error('Network error')
      ;(axios.post as any).mockRejectedValue(error)

      const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const wrapper = mount(ConfigurationView, {
        global: {
          stubs: {
            ConfigComponent: true
          }
        }
      })

      await wrapper.find('button').trigger('click')
      await flushPromises()

      expect(spy).toHaveBeenCalled()

      spy.mockRestore()
    })
})
