import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SgxSwitchButton from '@/components/common/SgxSwitchButton.vue'

describe('SgxSwitchButton', () => {
  const factory = (modelValue = false) =>
    mount(SgxSwitchButton, {
      props: { modelValue }
    })

  it('renders correctly', () => {
    const wrapper = factory()
    expect(wrapper.exists()).toBe(true)
  })

  it('reflects modelValue in checkbox state', () => {
    const wrapper = factory(true)
    const input = wrapper.find('input')

    expect((input.element as HTMLInputElement).checked).toBe(true)
  })

  it('emits update:modelValue when toggled', async () => {
    const wrapper = factory(false)
    const input = wrapper.find('input')

    await input.trigger('change')

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([true])
  })

  it('toggles from true to false', async () => {
    const wrapper = factory(true)
    const input = wrapper.find('input')

    await input.trigger('change')

    expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
  })
})
