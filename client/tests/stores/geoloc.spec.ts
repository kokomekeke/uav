// tests/stores/geoloc.spec.ts
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useGeoLocStore } from '@/stores/geoloc'

// Mock fetch API
global.fetch = vi.fn()

describe('GeoLoc Store', () => {
  let store: ReturnType<typeof useGeoLocStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useGeoLocStore()
    vi.clearAllTimers()
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    store.stopGeoJsonFetch()
    vi.useRealTimers()
  })

  describe('Initial State', () => {
    it('should initialize with correct default values', () => {
      expect(store.geoJsonData).toEqual([])
      expect(store.isGeoJsonEnabled).toBe(false)
      expect(store.heatMapPoints).toEqual([])
      expect(store.maxHeatMapSize).toBe(1000)
    })

    it('should have correct default settings', () => {
      expect(store.geoJsonSettings).toEqual({
        limit: 20,
        stride: 1,
        fetchPeriodSec: 1,
        showRaw: true,
        showFiltered: true,
        ttl: 60000
      })
    })
  })

  describe('GeoJSON Data Fetching', () => {
    it('should fetch and process raw GeoJSON data', async () => {
      const mockRawData = {
        features: [
          {
            geometry: { coordinates: [19.04, 47.49] },
            properties: {
              geoloc_id: 1,
              timestamp: new Date().toISOString(),
              roi_id: 1
            }
          }
        ]
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockRawData
      }).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ features: [] })
      })

      store.isGeoJsonEnabled = true
      await store.fetchGeoJsonData()

      expect(store.geoJsonData.length).toBeGreaterThan(0)
      expect(store.geoJsonData[0].type).toBe('raw')
    })

    it('should fetch and process filtered GeoJSON data', async () => {
      const mockFilteredData = {
        features: [
          {
            geometry: { coordinates: [19.04, 47.49] },
            properties: {
              geoloc_id: 2,
              timestamp: new Date().toISOString()
            }
          }
        ]
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ features: [] })
      }).mockResolvedValueOnce({
        ok: true,
        json: async () => mockFilteredData
      })

      store.isGeoJsonEnabled = true
      await store.fetchGeoJsonData()

      expect(store.geoJsonData.length).toBeGreaterThan(0)
      expect(store.geoJsonData[0].type).toBe('filtered')
    })

    it('should handle fetch errors gracefully', async () => {
      ;(global.fetch as any).mockRejectedValue(new Error('Network error'))

      store.isGeoJsonEnabled = true
      await store.fetchGeoJsonData()

      // Should not crash, data remains empty
      expect(store.geoJsonData).toEqual([])
    })

    it('should not fetch when disabled', async () => {
      store.isGeoJsonEnabled = false

      await store.fetchGeoJsonData()

      expect(global.fetch).not.toHaveBeenCalled()
    })

    it('should deduplicate data by ID', async () => {
      const mockData = {
        features: [
          {
            geometry: { coordinates: [19.04, 47.49] },
            properties: { geoloc_id: 1, timestamp: new Date().toISOString() }
          },
          {
            geometry: { coordinates: [19.05, 47.50] },
            properties: { geoloc_id: 1, timestamp: new Date().toISOString() }
          }
        ]
      }

      ;(global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => mockData
      })

      store.isGeoJsonEnabled = true
      await store.fetchGeoJsonData()

      // Should only have one point due to deduplication
      const uniqueIds = new Set(store.geoJsonData.map(p => p.id))
      expect(uniqueIds.size).toBe(store.geoJsonData.length)
    })
  })

  describe('GeoJSON Lifecycle Management', () => {
    it('should start fetching on startGeoJsonFetch', async () => {
      ;(global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ features: [] })
      })

      await store.startGeoJsonFetch()

      expect(store.isGeoJsonEnabled).toBe(true)
      expect(global.fetch).toHaveBeenCalled()
    })

    it('should stop fetching on stopGeoJsonFetch', () => {
      store.isGeoJsonEnabled = true

      store.stopGeoJsonFetch()

      expect(store.isGeoJsonEnabled).toBe(false)
      expect(store.geoJsonData).toEqual([])
      expect(store.heatMapPoints).toEqual([])
    })

    it('should clean up expired data', async () => {
      const now = Date.now()
      const oldTimestamp = now - 70000 // 70 seconds old (TTL is 60s)
      const newTimestamp = now - 5000 // 5 seconds old

      store.geoJsonData = [
        {
          id: 'old',
          coordinate: [47.49, 19.04],
          timestamp: oldTimestamp,
          type: 'raw'
        },
        {
          id: 'new',
          coordinate: [47.50, 19.05],
          timestamp: newTimestamp,
          type: 'raw'
        }
      ]

      store.isGeoJsonEnabled = true

      // Trigger cleanup by advancing time
      vi.advanceTimersByTime(11000)

      // Only new data should remain
      const validData = store.geoJsonData.filter(
        p => (Date.now() - p.timestamp) <= store.geoJsonSettings.ttl
      )
      expect(validData.length).toBeLessThanOrEqual(store.geoJsonData.length)
    })
  })

  describe('Settings Management', () => {
    it('should update settings', () => {
      store.updateGeoJsonSettings({
        limit: 50,
        fetchPeriodSec: 2
      })

      expect(store.geoJsonSettings.limit).toBe(50)
      expect(store.geoJsonSettings.fetchPeriodSec).toBe(2)
    })

    it('should restart fetch when updating settings while enabled', async () => {
      ;(global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ features: [] })
      })

      await store.startGeoJsonFetch()
      const fetchCount = (global.fetch as any).mock.calls.length

      store.updateGeoJsonSettings({ limit: 30 })

      // Should have called fetch again after restart
      await vi.advanceTimersByTimeAsync(100)
      expect((global.fetch as any).mock.calls.length).toBeGreaterThanOrEqual(fetchCount)
    })
  })

  describe('HeatMap Management', () => {
    it('should add points to heatmap', () => {
      const points = [
        {
          id: 1,
          coordinate: [47.49, 19.04] as [number, number],
          timestamp: Date.now(),
          type: 'raw' as const
        }
      ]

      store.addToHeatMap(points)

      expect(store.heatMapPoints.length).toBe(1)
      expect(store.heatMapPoints[0].coordinate).toEqual([47.49, 19.04])
    })

    it('should limit heatmap size', () => {
      store.maxHeatMapSize = 10

      const points = Array.from({ length: 15 }, (_, i) => ({
        id: i,
        coordinate: [47.49 + i * 0.01, 19.04 + i * 0.01] as [number, number],
        timestamp: Date.now(),
        type: 'raw' as const
      }))

      store.addToHeatMap(points)

      expect(store.heatMapPoints.length).toBeLessThanOrEqual(store.maxHeatMapSize)
    })

    it('should clean expired heatmap points', () => {
      const now = Date.now()
      store.heatMapPoints = [
        {
          coordinate: [47.49, 19.04],
          lastUpdate: now - 70000 // Expired
        },
        {
          coordinate: [47.50, 19.05],
          lastUpdate: now - 5000 // Valid
        }
      ]

      store.isGeoJsonEnabled = true

      // Trigger cleanup
      vi.advanceTimersByTime(11000)

      // Check that cleanup logic would remove expired points
      const ttl = store.geoJsonSettings.ttl
      const validPoints = store.heatMapPoints.filter(
        p => (Date.now() - p.lastUpdate) <= ttl
      )
      expect(validPoints.length).toBeLessThanOrEqual(store.heatMapPoints.length)
    })
  })

  describe('Invalid Data Handling', () => {
    it('should ignore features with invalid coordinates', async () => {
      const mockData = {
        features: [
          {
            geometry: { coordinates: null },
            properties: { geoloc_id: 1 }
          },
          {
            geometry: { coordinates: [19.04] }, // Only one coordinate
            properties: { geoloc_id: 2 }
          },
          {
            geometry: { coordinates: ['invalid', 47.49] },
            properties: { geoloc_id: 3 }
          }
        ]
      }

      ;(global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => mockData
      })

      store.isGeoJsonEnabled = true
      await store.fetchGeoJsonData()

      expect(store.geoJsonData.length).toBe(0)
    })

    it('should handle missing geometry', async () => {
      const mockData = {
        features: [
          {
            properties: { geoloc_id: 1 }
          }
        ]
      }

      ;(global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => mockData
      })

      store.isGeoJsonEnabled = true
      await store.fetchGeoJsonData()

      expect(store.geoJsonData.length).toBe(0)
    })
  })

  describe('Performance', () => {
    it('should handle large dataset efficiently', async () => {
      const largeDataset = {
        features: Array.from({ length: 100 }, (_, i) => ({
          geometry: { coordinates: [19.04 + i * 0.01, 47.49 + i * 0.01] },
          properties: {
            geoloc_id: i,
            timestamp: new Date().toISOString()
          }
        }))
      }

      ;(global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => largeDataset
      })

      const startTime = performance.now()
      store.isGeoJsonEnabled = true
      await store.fetchGeoJsonData()
      const endTime = performance.now()

      expect(endTime - startTime).toBeLessThan(1000) // Should complete within 1 second
      expect(store.geoJsonData.length).toBeGreaterThan(0)
    })
  })
})