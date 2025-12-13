import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useGeoLocStore } from '@/stores/geoloc'

describe('GeoLoc Store (persistent heatmap)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()

    // fetch mock
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

  it('adds points to heatmap and respects size limit', () => {
    const store = useGeoLocStore()

    store.heatMapSettings.maxSize = 3

    store.addToHeatMap([
      { id: 1, coordinate: [1, 1], timestamp: Date.now(), type: 'raw' },
      { id: 2, coordinate: [2, 2], timestamp: Date.now(), type: 'raw' },
      { id: 3, coordinate: [3, 3], timestamp: Date.now(), type: 'raw' },
      { id: 4, coordinate: [4, 4], timestamp: Date.now(), type: 'raw' }
    ])

    expect(store.heatMapPoints.length).toBe(3)
    // FIFO → az első kidobódik
    expect(store.heatMapPoints[0].coordinate).toEqual([2, 2])
  })

  it('clears heatmap manually', () => {
    const store = useGeoLocStore()

    store.addToHeatMap([
      { id: 1, coordinate: [1, 1], timestamp: Date.now(), type: 'raw' }
    ])

    expect(store.heatMapPoints.length).toBe(1)

    store.clearHeatMap()
    expect(store.heatMapPoints.length).toBe(0)
  })

  it('fetchGeoJsonData fetches and stores geojson points', async () => {
    const store = useGeoLocStore()
    store.isGeoJsonEnabled = true

    const mockResponse = {
      features: [
        {
          geometry: { coordinates: [19, 47] },
          properties: {
            geoloc_id: 1,
            timestamp: new Date().toISOString(),
            roi_id: 5
          }
        }
      ]
    }

    ;(fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockResponse
    })

    await store.fetchGeoJsonData()

    expect(store.geoJsonData.length).toBe(1)
    expect(store.geoJsonData[0]).toMatchObject({
      coordinate: [47, 19],
      type: 'raw'
    })

    expect(store.heatMapPoints.length).toBe(1)
  })

  it('does not duplicate geojson points (seenIds)', async () => {
    const store = useGeoLocStore()
    store.isGeoJsonEnabled = true

    const mockResponse = {
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

    ;(fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockResponse
    })

    await store.fetchGeoJsonData()
    await store.fetchGeoJsonData()

    expect(store.geoJsonData.length).toBe(1)
    expect(store.heatMapPoints.length).toBe(1)
  })

  it('startGeoJsonFetch enables fetching and sets interval', async () => {
    const store = useGeoLocStore()

    ;(fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ features: [] })
    })

    await store.startGeoJsonFetch()

    expect(store.isGeoJsonEnabled).toBe(true)

    vi.advanceTimersByTime(2000)
    expect(fetch).toHaveBeenCalled()
  })

  it('stopGeoJsonFetch stops fetching but preserves heatmap', () => {
    const store = useGeoLocStore()

    store.addToHeatMap([
      { id: 1, coordinate: [1, 1], timestamp: Date.now(), type: 'raw' }
    ])

    store.startGeoJsonFetch()
    store.stopGeoJsonFetch()

    expect(store.isGeoJsonEnabled).toBe(false)
    expect(store.geoJsonData.length).toBe(0)
    expect(store.heatMapPoints.length).toBe(1) // 🔥 perzisztens
  })

  it('clearAll clears geojson and heatmap data', () => {
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
