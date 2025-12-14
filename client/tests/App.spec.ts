// tests/App.spec.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick, ref } from 'vue'
import App from '@/App.vue'

const mockIsDark = ref(false)
vi.mock('@vueuse/core', () => ({
  useDark: () => mockIsDark
}))

const mockComponents = {
  SgxHeader: {
    template: `
      <div data-test="header" @click="$emit('toggle-dark')">
        <slot />
      </div>
    `,
    props: ['isMenuOpen', 'isDark'],
    emits: ['toggle-dark']
  },
  BurgerMenu: {
    template: `
      <div data-test="menu" @click="$emit('update:isMenuOpen', !isMenuOpen)">
        <slot />
      </div>
    `,
    props: ['isMenuOpen'],
    emits: ['update:isMenuOpen']
  },
  Content: {
    template: `
      <div data-test="content" @click="$emit('update:isMenuOpen', !isMenuOpen)">
        <slot />
      </div>
    `,
    props: ['isMenuOpen'],
    emits: ['update:isMenuOpen']
  }
}

describe('App.vue', () => {
  let wrapper: VueWrapper<any>
  let consoleLogSpy: any

  beforeEach(() => {
    mockIsDark.value = false

    setActivePinia(createPinia())

    consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
  })

  const mountApp = () =>
    mount(App, {
      global: {
        plugins: [createPinia()],
        stubs: mockComponents
      }
    })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    consoleLogSpy.mockRestore()
  })

  describe('Layout Structure', () => {
    it('renders main layout container with gradient background', () => {
      wrapper = mountApp()
      const root = wrapper.find('.font-mono')

      expect(root.exists()).toBe(true)
      expect(root.classes()).toContain('bg-gradient-to-tr')
    })

    it('renders fixed header at the top', () => {
      wrapper = mountApp()
      const header = wrapper.findComponent('[data-test="header"]')

      expect(header.exists()).toBe(true)
      expect(header.classes()).toContain('fixed')
      expect(header.classes()).toContain('top-0')
      expect(header.classes()).toContain('z-50')
    })

    it('renders fade overlay below header', () => {
      wrapper = mountApp()
      const fadeOverlay = wrapper.findAll('.fixed').filter(
        el => el.classes().includes('pointer-events-none')
      )[0]

      expect(fadeOverlay.exists()).toBe(true)
      expect(fadeOverlay.classes()).toContain('top-24')
      expect(fadeOverlay.classes()).toContain('z-40')
    })

    it('renders main container with proper padding', () => {
      wrapper = mountApp()
      const main = wrapper.find('main')

      expect(main.exists()).toBe(true)
      expect(main.classes()).toContain('pt-24') // padding for fixed header
      expect(main.classes()).toContain('min-h-screen')
      expect(main.classes()).toContain('overflow-y-auto')
    })

    it('renders all child components', () => {
      wrapper = mountApp()

      expect(wrapper.findComponent('[data-test="header"]').exists()).toBe(true)
      expect(wrapper.findComponent('[data-test="menu"]').exists()).toBe(true)
      expect(wrapper.findComponent('[data-test="content"]').exists()).toBe(true)
    })
  })

  describe('Menu State Management', () => {
    it('initializes with menu closed', () => {
      wrapper = mountApp()

      expect(wrapper.vm.isMenuOpen).toBe(false)
    })

    it('passes isMenuOpen=false by default to all children', () => {
      wrapper = mountApp()

      expect(wrapper.findComponent('[data-test="header"]').props('isMenuOpen')).toBe(false)
      expect(wrapper.findComponent('[data-test="menu"]').props('isMenuOpen')).toBe(false)
      expect(wrapper.findComponent('[data-test="content"]').props('isMenuOpen')).toBe(false)
    })

    it('updates isMenuOpen when BurgerMenu emits update event', async () => {
      wrapper = mountApp()
      const menu = wrapper.findComponent('[data-test="menu"]')

      await menu.trigger('click')
      await nextTick()

      expect(wrapper.vm.isMenuOpen).toBe(true)
      expect(menu.props('isMenuOpen')).toBe(true)
    })

    it('updates isMenuOpen when Content emits update event', async () => {
      wrapper = mountApp()
      const content = wrapper.findComponent('[data-test="content"]')

      await content.trigger('click')
      await nextTick()

      expect(wrapper.vm.isMenuOpen).toBe(true)
      expect(content.props('isMenuOpen')).toBe(true)
    })

    it('applies correct positioning classes when menu is closed', () => {
      wrapper = mountApp()
      const menu = wrapper.findComponent('[data-test="menu"]')

      expect(menu.classes()).toContain('relative')
      expect(menu.classes()).toContain('w-1')
    })

    it('applies correct positioning classes when menu is open', async () => {
      wrapper = mountApp()
      const menu = wrapper.findComponent('[data-test="menu"]')

      await menu.trigger('click')
      await nextTick()

      expect(menu.classes()).toContain('fixed')
      expect(menu.classes()).toContain('w-72')
      expect(menu.classes()).toContain('top-24')
      expect(menu.classes()).toContain('z-[65]')
    })

    it('applies correct margin to content when menu is closed', () => {
      wrapper = mountApp()
      const content = wrapper.findComponent('[data-test="content"]')

      expect(content.classes()).toContain('ml-0')
    })

    it('applies correct margin to content when menu is open', async () => {
      wrapper = mountApp()
      const menu = wrapper.findComponent('[data-test="menu"]')
      const content = wrapper.findComponent('[data-test="content"]')

      await menu.trigger('click')
      await nextTick()

      expect(content.classes()).toContain('ml-72')
    })
  })


  describe('Dark Mode', () => {
    it('initializes with dark mode disabled', () => {
      wrapper = mountApp()

      expect(wrapper.vm.isDark).toBe(false)
      expect(wrapper.findComponent('[data-test="header"]').props('isDark')).toBe(false)
    })

    it('toggles dark mode when header emits toggle-dark', async () => {
      wrapper = mountApp()
      const header = wrapper.findComponent('[data-test="header"]')

      expect(header.props('isDark')).toBe(false)

      await header.trigger('click') // triggers emit('toggle-dark')
      await nextTick()

      expect(mockIsDark.value).toBe(true)
      expect(header.props('isDark')).toBe(true)
    })

    it('toggles dark mode multiple times correctly', async () => {
      wrapper = mountApp()
      const header = wrapper.findComponent('[data-test="header"]')

      // First toggle: false -> true
      await header.trigger('click')
      await nextTick()
      expect(mockIsDark.value).toBe(true)

      // Second toggle: true -> false
      await header.trigger('click')
      await nextTick()
      expect(mockIsDark.value).toBe(false)

      // Third toggle: false -> true
      await header.trigger('click')
      await nextTick()
      expect(mockIsDark.value).toBe(true)
    })

    it('logs dark mode changes', async () => {
      wrapper = mountApp()
      const header = wrapper.findComponent('[data-test="header"]')

      await header.trigger('click')
      await nextTick()

      expect(consoleLogSpy).toHaveBeenCalledWith('Dark mode:', true)
    })
  })

  describe('Lifecycle Hooks', () => {
    it('logs on mount with version info', () => {
      wrapper = mountApp()

      expect(consoleLogSpy).toHaveBeenCalledWith(
        expect.stringContaining('SGX-PC-1 client loaded')
      )
    })

    it('logs on unmount', () => {
      wrapper = mountApp()
      consoleLogSpy.mockClear()

      wrapper.unmount()

      expect(consoleLogSpy).toHaveBeenCalledWith('Component unmounted')
    })

    it('cleans up without errors on unmount', () => {
      wrapper = mountApp()

      expect(() => wrapper.unmount()).not.toThrow()
    })
  })


  describe('Watchers', () => {
    it('logs when isMenuOpen changes', async () => {
      wrapper = mountApp()
      consoleLogSpy.mockClear()

      const menu = wrapper.findComponent('[data-test="menu"]')
      await menu.trigger('click')
      await nextTick()

      expect(consoleLogSpy).toHaveBeenCalledWith('side menu new value: ', true)
    })

    it('logs when isDark changes', async () => {
      wrapper = mountApp()
      consoleLogSpy.mockClear()

      const header = wrapper.findComponent('[data-test="header"]')
      await header.trigger('click')
      await nextTick()

      expect(consoleLogSpy).toHaveBeenCalledWith('Dark mode:', true)
    })
  })


  describe('Integration', () => {
    it('updates all components when menu state changes', async () => {
      wrapper = mountApp()
      const header = wrapper.findComponent('[data-test="header"]')
      const menu = wrapper.findComponent('[data-test="menu"]')
      const content = wrapper.findComponent('[data-test="content"]')

      // Open menu
      await menu.trigger('click')
      await nextTick()

      expect(header.props('isMenuOpen')).toBe(true)
      expect(menu.props('isMenuOpen')).toBe(true)
      expect(content.props('isMenuOpen')).toBe(true)
    })

    it('handles rapid menu toggles correctly', async () => {
      wrapper = mountApp()
      const menu = wrapper.findComponent('[data-test="menu"]')

      await menu.trigger('click')
      await menu.trigger('click')
      await menu.trigger('click')
      await nextTick()

      expect(wrapper.vm.isMenuOpen).toBe(true)
    })

    it('maintains independent state for menu and dark mode', async () => {
      wrapper = mountApp()
      const header = wrapper.findComponent('[data-test="header"]')
      const menu = wrapper.findComponent('[data-test="menu"]')

      await header.trigger('click')
      await nextTick()
      expect(mockIsDark.value).toBe(true)
      expect(wrapper.vm.isMenuOpen).toBe(false)

      await menu.trigger('click')
      await nextTick()
      expect(mockIsDark.value).toBe(true)
      expect(wrapper.vm.isMenuOpen).toBe(true)
    })
  })
})
