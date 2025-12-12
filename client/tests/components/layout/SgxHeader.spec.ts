import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SgxHeader from '@/components/layout/SgxHeader.vue'
import SgxSwitchButton from '@/components/common/SgxSwitchButton.vue'

import router from '@/routes'

vi.mock('@/routes', () => ({
  default: {
    push: vi.fn()
  }
}))

describe('SgxHeader', () => {
  const factory = (props = {}) =>
    mount(SgxHeader, {
      props: {
        isMenuOpen: false,
        isDark: false,
        ...props
      },
      global: {
        stubs: {
          SgxSwitchButton
        }
      }
    })

  it('renders correctly', () => {
    const wrapper = factory()
    expect(wrapper.exists()).toBe(true)
  })

  it('navigates to home when title is clicked', async () => {
    const wrapper = factory()

    await wrapper.find('h1').trigger('click')

    expect(router.push).toHaveBeenCalledWith({ path: '/' })
  })

  it('emits toggle-dark when switch toggles', async () => {
    const wrapper = factory({ isDark: false })

    const switchButton = wrapper.findComponent(SgxSwitchButton)
    await switchButton.vm.$emit('update:modelValue', true)

    expect(wrapper.emitted('toggle-dark')).toBeTruthy()
  })

  it('applies shadow when menu is open', () => {
    const wrapper = factory({ isMenuOpen: true })

    expect(wrapper.classes()).toContain('shadow-inner')
  })

  it('does not apply shadow when menu is closed', () => {
    const wrapper = factory({ isMenuOpen: false })

    expect(wrapper.classes()).not.toContain('shadow-inner')
  })
})
