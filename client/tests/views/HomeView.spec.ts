// tests/views/HomeView.spec.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import HomeView from '@/views/HomeView.vue'

describe('HomeView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const mountHome = () =>
    mount(HomeView, {
      global: {
        plugins: [createPinia()],
        stubs: {
          ConnectionView: {
            name: 'ConnectionView',
            template: `
              <div data-test="connection-view">
                <button
                  data-test="emit-close"
                  @click="$emit('update:isModalVisible', false)"
                >
                  close
                </button>
              </div>
            `,
            props: ['isModalVisible'],
            emits: ['update:isModalVisible']
          }

        }
      }
    })

  it('renders correctly', () => {
    const wrapper = mountHome()
    expect(wrapper.exists()).toBe(true)
  })

  it('renders Show Modal button', () => {
    const wrapper = mountHome()
    const button = wrapper.find('#show-modal')
    expect(button.exists()).toBe(true)
    expect(button.text()).toContain('Show Modal')
  })

  it('modal is closed by default', () => {
    const wrapper = mountHome()
    const vm = wrapper.vm as any
    expect(vm.isMenuOpen).toBeFalsy()
  })

  it('toggles modal visibility on button click', async () => {
    const wrapper = mountHome()
    const button = wrapper.find('#show-modal')

    const vm = wrapper.vm as any
    expect(vm.isMenuOpen).toBe(false)

    await button.trigger('click')
    expect(vm.isMenuOpen).toBe(true)

    await button.trigger('click')
    expect(vm.isMenuOpen).toBe(false)
  })

  it('passes is-modal-visible prop to ConnectionView', async () => {
    const wrapper = mountHome()
    const vm = wrapper.vm as any

    vm.isMenuOpen = true
    await wrapper.vm.$nextTick()

    const connectionView = wrapper.find('[data-test="connection-view"]')
    expect(connectionView.exists()).toBe(true)
  })

  it('updates modal visibility from child event', async () => {
    const wrapper = mountHome()
    const vm = wrapper.vm as any

    vm.isMenuOpen = true
    await wrapper.vm.$nextTick()
    expect(vm.isMenuOpen).toBe(true)

    // emit from child
    wrapper.findComponent({ name: 'ConnectionView' })
      .vm.$emit('update:isModalVisible', false)

    await wrapper.vm.$nextTick()
    expect(vm.isMenuOpen).toBe(false)
  })
})

// tests/views/HomeView.spec.ts
// import { describe, it, expect, beforeEach, vi } from 'vitest'
// import { mount, VueWrapper } from '@vue/test-utils'
// import { createPinia, setActivePinia } from 'pinia'
// import HomeView from '@/views/HomeView.vue'
//
// // Mock router
// const mockPush = vi.fn()
// vi.mock('vue-router', () => ({
//   useRouter: () => ({
//     push: mockPush
//   }),
//   RouterLink: {
//     template: '<a><slot /></a>',
//     props: ['to']
//   }
// }))
//
// describe('HomeView', () => {
//   let wrapper: VueWrapper
//
//   beforeEach(() => {
//     setActivePinia(createPinia())
//
//     wrapper = mount(HomeView, {
//       global: {
//         plugins: [createPinia()],
//         stubs: {
//           ConfigurationView: true,
//           MapComponent: true,
//           HeatmapComponent: true,
//           SpectrumWaterfall: true,
//           RouterLink: {
//             template: '<a><slot /></a>',
//             props: ['to']
//           }
//         }
//       }
//     })
//   })
//
//   describe('Component Rendering', () => {
//     it('should render correctly', () => {
//       expect(wrapper.exists()).toBe(true)
//     })
//
//     it('should have configuration panel', () => {
//       const config = wrapper.find('.flex-1')
//       expect(config.exists()).toBe(true)
//     })
//
//     it('should have view panel with tabs', () => {
//       const viewPanel = wrapper.find('.flex-\\[2\\]')
//       expect(viewPanel.exists()).toBe(true)
//     })
//
//     it('should render log button in top-right corner', () => {
//       const logButton = wrapper.find('.absolute.top-4.right-6')
//       expect(logButton.exists()).toBe(true)
//     })
//   })
//
//   describe('View Mode Tabs', () => {
//     it('should display all view mode buttons', () => {
//       const buttons = wrapper.findAll('button')
//       const buttonTexts = buttons.map(btn => btn.text())
//
//       expect(buttonTexts).toContain(expect.stringContaining('Map View'))
//       expect(buttonTexts).toContain(expect.stringContaining('Heatmap View'))
//       expect(buttonTexts).toContain(expect.stringContaining('Spectrum View'))
//       expect(buttonTexts).toContain(expect.stringContaining('Split View'))
//     })
//
//     it('should default to map view', () => {
//       const vm = wrapper.vm as any
//       expect(vm.viewMode).toBe('map')
//     })
//
//     it('should highlight active tab', () => {
//       const activeButton = wrapper.findAll('button').find(btn =>
//         btn.classes().includes('bg-cyan-600')
//       )
//       expect(activeButton).toBeDefined()
//     })
//
//     it('should switch to heatmap view', async () => {
//       const heatmapButton = wrapper.findAll('button').find(btn =>
//         btn.text().includes('Heatmap View')
//       )
//
//       if (heatmapButton) {
//         await heatmapButton.trigger('click')
//         const vm = wrapper.vm as any
//         expect(vm.viewMode).toBe('heatmap')
//       }
//     })
//
//     it('should switch to spectrum view', async () => {
//       const spectrumButton = wrapper.findAll('button').find(btn =>
//         btn.text().includes('Spectrum View')
//       )
//
//       if (spectrumButton) {
//         await spectrumButton.trigger('click')
//         const vm = wrapper.vm as any
//         expect(vm.viewMode).toBe('spectrum')
//       }
//     })
//
//     it('should switch to split view', async () => {
//       const splitButton = wrapper.findAll('button').find(btn =>
//         btn.text().includes('Split View')
//       )
//
//       if (splitButton) {
//         await splitButton.trigger('click')
//         const vm = wrapper.vm as any
//         expect(vm.viewMode).toBe('split')
//       }
//     })
//   })
//
//   describe('View Mode Display', () => {
//     it('should show map component in map view', async () => {
//       const vm = wrapper.vm as any
//       vm.viewMode = 'map'
//       await wrapper.vm.$nextTick()
//
//       const mapView = wrapper.find('.w-full.h-full.p-4')
//       expect(mapView.exists()).toBe(true)
//     })
//
//     it('should show heatmap component in heatmap view', async () => {
//       const vm = wrapper.vm as any
//       vm.viewMode = 'heatmap'
//       await wrapper.vm.$nextTick()
//
//       // Heatmap component should be rendered
//       expect(wrapper.html()).toContain('heatmap')
//     })
//
//     it('should show spectrum component in spectrum view', async () => {
//       const vm = wrapper.vm as any
//       vm.viewMode = 'spectrum'
//       await wrapper.vm.$nextTick()
//
//       // Spectrum component should be rendered
//       expect(wrapper.html()).toContain('spectrum')
//     })
//
//     it('should show both map and heatmap in split view', async () => {
//       const vm = wrapper.vm as any
//       vm.viewMode = 'split'
//       await wrapper.vm.$nextTick()
//
//       const splitView = wrapper.find('.flex.flex-col.gap-4')
//       expect(splitView.exists()).toBe(true)
//     })
//   })
//
//   describe('Info Badge', () => {
//     it('should display "Real-time Tracking" for map view', async () => {
//       const vm = wrapper.vm as any
//       vm.viewMode = 'map'
//       await wrapper.vm.$nextTick()
//
//       expect(wrapper.text()).toContain('Real-time Tracking')
//     })
//
//     it('should display "Density Analysis" for heatmap view', async () => {
//       const vm = wrapper.vm as any
//       vm.viewMode = 'heatmap'
//       await wrapper.vm.$nextTick()
//
//       expect(wrapper.text()).toContain('Density Analysis')
//     })
//
//     it('should display "Spectrum Analysis" for spectrum view', async () => {
//       const vm = wrapper.vm as any
//       vm.viewMode = 'spectrum'
//       await wrapper.vm.$nextTick()
//
//       expect(wrapper.text()).toContain('Spectrum Analysis')
//     })
//
//     it('should display "Dual View" for split view', async () => {
//       const vm = wrapper.vm as any
//       vm.viewMode = 'split'
//       await wrapper.vm.$nextTick()
//
//       expect(wrapper.text()).toContain('Dual View')
//     })
//   })
//
//   describe('CSS Styling', () => {
//     it('should apply correct layout classes', () => {
//       const mainContainer = wrapper.find('.relative.flex.flex-row')
//       expect(mainContainer.exists()).toBe(true)
//     })
//
//     it('should have responsive design classes', () => {
//       const panels = wrapper.findAll('.rounded-2xl')
//       expect(panels.length).toBeGreaterThanOrEqual(2)
//     })
//
//     it('should apply dark mode styles', () => {
//       const darkElements = wrapper.findAll('[class*="dark:"]')
//       expect(darkElements.length).toBeGreaterThan(0)
//     })
//
//     it('should have shadow effects', () => {
//       const shadowElements = wrapper.findAll('.shadow-lg')
//       expect(shadowElements.length).toBeGreaterThan(0)
//     })
//   })
//
//   describe('Log Button', () => {
//     it('should navigate to /log route on click', () => {
//       const logLink = wrapper.find('a[href="/log"]')
//       expect(logLink.exists()).toBe(true)
//     })
//
//     it('should have log icon animation', () => {
//       const logLines = wrapper.findAll('.log-lines span')
//       expect(logLines.length).toBe(4)
//     })
//   })
//
//   describe('Tab Helper Function', () => {
//     it('should correctly identify active tab', () => {
//       const vm = wrapper.vm as any
//       vm.viewMode = 'map'
//
//       expect(vm.isActiveTab('map')).toBe(true)
//       expect(vm.isActiveTab('heatmap')).toBe(false)
//     })
//
//     it('should work for all view modes', () => {
//       const vm = wrapper.vm as any
//
//       const modes = ['map', 'heatmap', 'split', 'spectrum']
//
//       modes.forEach(mode => {
//         vm.viewMode = mode
//         expect(vm.isActiveTab(mode)).toBe(true)
//       })
//     })
//   })
//
//   describe('Component Integration', () => {
//     it('should pass down necessary props', () => {
//       const config = wrapper.findComponent({ name: 'ConfigurationView' })
//       expect(config.exists()).toBe(true)
//     })
//
//     it('should render stubs correctly', () => {
//       // All major components should be present (as stubs)
//       expect(wrapper.html()).toContain('configuration-view')
//     })
//   })
//
//   describe('Layout Responsiveness', () => {
//     it('should have flex layout', () => {
//       const container = wrapper.find('.flex.flex-row')
//       expect(container.exists()).toBe(true)
//     })
//
//     it('should have proper spacing', () => {
//       const gapElements = wrapper.findAll('[class*="gap-"]')
//       expect(gapElements.length).toBeGreaterThan(0)
//     })
//
//     it('should have overflow handling', () => {
//       const overflowElements = wrapper.findAll('.overflow-hidden, .overflow-auto')
//       expect(overflowElements.length).toBeGreaterThan(0)
//     })
//   })
//
//   describe('View Transitions', () => {
//     it('should transition smoothly between views', async () => {
//       const vm = wrapper.vm as any
//
//       vm.viewMode = 'map'
//       await wrapper.vm.$nextTick()
//       expect(vm.viewMode).toBe('map')
//
//       vm.viewMode = 'heatmap'
//       await wrapper.vm.$nextTick()
//       expect(vm.viewMode).toBe('heatmap')
//     })
//
//     it('should maintain state during view changes', async () => {
//       const vm = wrapper.vm as any
//       const originalMode = vm.viewMode
//
//       vm.viewMode = 'split'
//       await wrapper.vm.$nextTick()
//
//       vm.viewMode = originalMode
//       await wrapper.vm.$nextTick()
//
//       expect(wrapper.exists()).toBe(true)
//     })
//   })
//
//   describe('Accessibility', () => {
//     it('should have descriptive button text', () => {
//       const buttons = wrapper.findAll('button')
//       buttons.forEach(button => {
//         expect(button.text().length).toBeGreaterThan(0)
//       })
//     })
//
//     it('should have proper semantic HTML', () => {
//       const sections = wrapper.findAll('.flex-1, .flex-\\[2\\]')
//       expect(sections.length).toBeGreaterThanOrEqual(2)
//     })
//   })
//
//   describe('Edge Cases', () => {
//     it('should handle rapid tab switching', async () => {
//       const vm = wrapper.vm as any
//
//       vm.viewMode = 'map'
//       await wrapper.vm.$nextTick()
//
//       vm.viewMode = 'heatmap'
//       vm.viewMode = 'spectrum'
//       vm.viewMode = 'split'
//       await wrapper.vm.$nextTick()
//
//       expect(vm.viewMode).toBe('split')
//     })
//
//     it('should render without errors', () => {
//       expect(() => {
//         mount(HomeView, {
//           global: {
//             plugins: [createPinia()],
//             stubs: {
//               ConfigurationView: true,
//               MapComponent: true,
//               HeatmapComponent: true,
//               SpectrumWaterfall: true
//             }
//           }
//         })
//       }).not.toThrow()
//     })
//   })
// })