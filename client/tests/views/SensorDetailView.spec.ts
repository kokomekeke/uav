import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MainView from '@/views/SensorDetailView.vue'

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

const findButtonByText = (wrapper: VueWrapper, text: string) => {
  return wrapper.findAll('button').find((button) => 
    button.text().includes(text)
  )
}

describe('MainView.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

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

    const heatmapButton = findButtonByText(wrapper, 'Heatmap View')
    expect(heatmapButton).toBeDefined()

    await heatmapButton?.trigger('click')
    await wrapper.vm.$nextTick()
    await vi.runAllTimersAsync()

    expect(wrapper.find('[data-test="heatmap-view"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="map-view"]').exists()).toBe(false)
  })

  it('switches to spectrum view when tab is clicked', async () => {
    const wrapper = mountView()

    const spectrumButton = findButtonByText(wrapper, 'Spectrum View')
    expect(spectrumButton).toBeDefined()

    await spectrumButton?.trigger('click')
    await wrapper.vm.$nextTick()
    await vi.runAllTimersAsync()

    expect(wrapper.find('[data-test="spectrum-view"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="map-view"]').exists()).toBe(false)
  })

  it('renders both map and heatmap in split view', async () => {
    const wrapper = mountView()

    const splitButton = findButtonByText(wrapper, 'Split View')
    expect(splitButton).toBeDefined()

    await splitButton?.trigger('click')
    await wrapper.vm.$nextTick()
    await vi.runAllTimersAsync()

    expect(wrapper.findAll('[data-test="map-view"]').length).toBe(1)
    expect(wrapper.findAll('[data-test="heatmap-view"]').length).toBe(1)
  })

  it('applies active tab class correctly', async () => {
    const wrapper = mountView()

    const mapTab = findButtonByText(wrapper, 'Map View')
    const heatmapTab = findButtonByText(wrapper, 'Heatmap View')

    expect(mapTab?.classes()).toContain('bg-cyan-600')

    await heatmapTab?.trigger('click')
    await wrapper.vm.$nextTick()
    await vi.runAllTimersAsync()

    expect(heatmapTab?.classes()).toContain('bg-cyan-600')
    expect(mapTab?.classes()).not.toContain('bg-cyan-600')
  })
})