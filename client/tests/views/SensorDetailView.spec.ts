// tests/views/MainView.spec.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MainView from '@/views/MainView.vue'

// === STUB CHILD COMPONENTS ===
const stubs = {
  ConfigurationView: {
    template: '<div data-test="config-view" />'
  },
  MapComponent: {
    template: '<div data-test="map-view" />'
  },
  HeatmapComponent: {
    template: '<div data-test="heatmap-view" />'
  },
  SpectrumWaterfall: {
    template: '<div data-test="spectrum-view" />'
  },
  RouterLink: {
    template: '<a><slot /></a>',
    props: ['to']
  }
}

const mountView = () =>
  mount(MainView, {
    global: {
      stubs
    }
  })

describe('MainView.vue', () => {
  it('renders configuration panel', () => {
    const wrapper = mountView()
    expect(wrapper.find('[data-test="config-view"]').exists()).toBe(true)
  })

  it('defaults to map view', () => {
    const wrapper = mountView()

    expect(wrapper.find('[data-test="map-view"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="heatmap-view"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="spectrum-view"]').exists()).toBe(false)
  })

  it('switches to heatmap view when tab is clicked', async () => {
    const wrapper = mountView()

    await wrapper.find('button:contains("Heatmap View")').trigger('click')

    expect(wrapper.find('[data-test="heatmap-view"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="map-view"]').exists()).toBe(false)
  })

  it('switches to spectrum view when tab is clicked', async () => {
    const wrapper = mountView()

    await wrapper.find('button:contains("Spectrum View")').trigger('click')

    expect(wrapper.find('[data-test="spectrum-view"]').exists()).toBe(true)
  })

  it('renders both map and heatmap in split view', async () => {
    const wrapper = mountView()

    await wrapper.find('button:contains("Split View")').trigger('click')

    expect(wrapper.findAll('[data-test="map-view"]').length).toBe(1)
    expect(wrapper.findAll('[data-test="heatmap-view"]').length).toBe(1)
  })

  it('applies active tab class correctly', async () => {
    const wrapper = mountView()

    const mapTab = wrapper.find('button:contains("Map View")')
    const heatmapTab = wrapper.find('button:contains("Heatmap View")')

    expect(mapTab.classes()).toContain('bg-cyan-600')

    await heatmapTab.trigger('click')

    expect(heatmapTab.classes()).toContain('bg-cyan-600')
    expect(mapTab.classes()).not.toContain('bg-cyan-600')
  })
})
