import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useGeoLocStore } from '@/stores/geoloc'

describe('GeoLoc Store – persistent heatmap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()

    global.fetch = vi.fn()
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('initializes with default state', () => {
    const store = useGeoLocStore()

    expect(store.geoJsonData.length).toBe(0)
    expect(store.heatMapPoints.length).toBe(0)
    expect(store.isGeoJsonEnabled).toBe(false)
    expect(store.heatMapSettings.enabled).toBe(true)
  })

  it('adds points to heatmap and respects FIFO size limit', () => {
    const store = useGeoLocStore()
    store.heatMapSettings.maxSize = 3

    store.addToHeatMap([
      { id: 1, coordinate: [1, 1], timestamp: Date.now(), type: 'raw' },
      { id: 2, coordinate: [2, 2], timestamp: Date.now(), type: 'raw' },
      { id: 3, coordinate: [3, 3], timestamp: Date.now(), type: 'raw' },
      { id: 4, coordinate: [4, 4], timestamp: Date.now(), type: 'raw' }
    ])

    expect(store.heatMapPoints.length).toBe(3)
    expect(store.heatMapPoints[0].coordinate).toEqual([2, 2])
  })

  it('clearHeatMap removes all heatmap points', () => {
    const store = useGeoLocStore()

    store.addToHeatMap([
      { id: 1, coordinate: [1, 1], timestamp: Date.now(), type: 'raw' }
    ])

    expect(store.heatMapPoints.length).toBe(1)

    store.clearHeatMap()
    expect(store.heatMapPoints.length).toBe(0)
  })

  it('fetchGeoJsonData fetches raw + filtered and populates geoJsonData and heatMap', async () => {
    const store = useGeoLocStore()
    store.isGeoJsonEnabled = true

    const rawResponse = {
      features: [
        {
          geometry: { coordinates: [19, 47] },
          properties: {
            geoloc_id: 1,
            timestamp: new Date().toISOString()
          }
        }
      ]
    }

    const filteredResponse = {
      features: [
        {
          geometry: { coordinates: [20, 48] },
          properties: {
            geoloc_id: 2,
            timestamp: new Date().toISOString()
          }
        }
      ]
    }

    ;(fetch as any)
      .mockResolvedValueOnce({ ok: true, json: async () => rawResponse })
      .mockResolvedValueOnce({ ok: true, json: async () => filteredResponse })

    await store.fetchGeoJsonData()

    expect(store.geoJsonData.length).toBe(2)
    expect(store.heatMapPoints.length).toBe(2)

    expect(store.geoJsonData[0].type).toBe('raw')
    expect(store.geoJsonData[1].type).toBe('filtered')
  })

  it('does not duplicate points with same geoloc_id', async () => {
    const store = useGeoLocStore()
    store.isGeoJsonEnabled = true

    const response = {
      features: [
        {
          geometry: { coordinates: [19, 47] },
          properties: {
            geoloc_id: 123,
            timestamp: new Date().toISOString()
          }
        }
      ]
    }

    ;(fetch as any)
      .mockResolvedValueOnce({ ok: true, json: async () => response })
      .mockResolvedValueOnce({ ok: true, json: async () => response })

    await store.fetchGeoJsonData()
    await store.fetchGeoJsonData()

    expect(store.geoJsonData.length).toBe(1)
    expect(store.heatMapPoints.length).toBe(1)
  })

  it('startGeoJsonFetch enables fetch and schedules interval', async () => {
    const store = useGeoLocStore()

    ;(fetch as any)
      .mockResolvedValue({ ok: true, json: async () => ({ features: [] }) })

    await store.startGeoJsonFetch()

    expect(store.isGeoJsonEnabled).toBe(true)

    vi.advanceTimersByTime(1100)
    expect(fetch).toHaveBeenCalled()
  })

  it('stopGeoJsonFetch clears geoJsonData but preserves heatmap', () => {
    const store = useGeoLocStore()

    store.addToHeatMap([
      { id: 1, coordinate: [1, 1], timestamp: Date.now(), type: 'raw' }
    ])

    store.startGeoJsonFetch()
    store.stopGeoJsonFetch()

    expect(store.isGeoJsonEnabled).toBe(false)
    expect(store.geoJsonData.length).toBe(0)
    expect(store.heatMapPoints.length).toBe(1) // ✅ perzisztens
  })

  it('clearAll clears everything', () => {
    const store = useGeoLocStore()

    store.addToHeatMap([
      { id: 1, coordinate: [1, 1], timestamp: Date.now(), type: 'raw' }
    ])

    store.geoJsonData.push({
      id: 'x',
      coordinate: [1, 1],
      timestamp: Date.now(),
      type: 'raw'
    })

    store.clearAll()

    expect(store.geoJsonData.length).toBe(0)
    expect(store.heatMapPoints.length).toBe(0)
  })
})
