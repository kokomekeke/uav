// tests/components/SimpleButton.spec.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SimpleButton from '@/components/SimpleButton.vue'

describe('SimpleButton', () => {
  it('renders properly', () => {
    const wrapper = mount(SimpleButton, {
      props: { label: 'Click me' }
    })

    expect(wrapper.text()).toContain('Click me')
  })

  it('emits click event', async () => {
    const wrapper = mount(SimpleButton)

    await wrapper.trigger('click')

    expect(wrapper.emitted()).toHaveProperty('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('is disabled when prop is true', () => {
    const wrapper = mount(SimpleButton, {
      props: { disabled: true }
    })

    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })
})