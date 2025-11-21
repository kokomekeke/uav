import { defineStore } from 'pinia'
import { ref } from 'vue'

interface GeoJsonPoint {
  id: number | string
  coordinate: [number, number]
  timestamp: number
  type: 'raw' | 'filtered'
  roi_id?: number
  properties?: any
}

interface HeatMapPoint {
  coordinate: [number, number]
  lastUpdate: number
}

export const useGeoLocStore = defineStore('geoloc', () => {
  // GeoJSON State
  const geoJsonData = ref<GeoJsonPoint[]>([])
  const geoJsonSettings = ref({
    limit: 20,
    stride: 1,
    fetchPeriodSec: 1,
    showRaw: true,
    showFiltered: true,
    ttl: 60000 // ✅ 60 másodperc (ms-ban)
  })
  const isGeoJsonEnabled = ref(false)

  // ✅ HeatMap points with size limit
  const heatMapPoints = ref<HeatMapPoint[]>([])
  const maxHeatMapSize = ref(1000) // ✅ 1000 pont maximum

  // Cleanup intervals
  let geoJsonIntervalId: number | null = null
  let geoJsonCleanupIntervalId: number | null = null
  let heatMapCleanupIntervalId: number | null = null

  // ============================================================================
  // GEOJSON CONTROL
  // ============================================================================
  let isFetching = false
  const seenIds = new Set<string>() // ✅ Deduplikáció

  const fetchGeoJsonData = async (): Promise<void> => {
    if (!isGeoJsonEnabled.value || isFetching) return
    isFetching = true

    const { limit, stride, showRaw, showFiltered } = geoJsonSettings.value
    const newPoints: GeoJsonPoint[] = []
    const batchIds = new Set<string>() // ✅ Batch-en belüli deduplikáció

    try {
      const start = performance.now()

      // ✅ Párhuzamos fetch-ek
      const [rawData, filteredData] = await Promise.all([
        showRaw
          ? fetch(`http://localhost:5000/v1/comintgeoloc/geojson/raw/list_last/${limit}`)
            .then(res => res.ok ? res.json() : null)
            .catch(() => null)
          : null,
        showFiltered
          ? fetch(`http://localhost:5000/v1/comintgeoloc/geojson/list_last/${limit}?stride=${stride}`)
            .then(res => res.ok ? res.json() : null)
            .catch(() => null)
          : null
      ])

      // ✅ Feldolgozás helper
      const processFeatures = (features: any[], type: 'raw' | 'filtered') => {
        features?.forEach((feature, idx) => {
          console.log('feature: ', feature)
          const coords = feature.geometry?.coordinates
          if (!coords || coords.length !== 2) return

          const [lon, lat] = coords
          if (isNaN(lat) || isNaN(lon)) return

          const id = feature.properties?.geoloc_id || `${type}-${idx}-${Date.now()}`
          console.log(id)

          // ✅ Deduplikáció
          if (seenIds.has(String(id)) || batchIds.has(String(id))) return
          batchIds.add(String(id))

          const timestamp = feature.properties?.timestamp
            ? new Date(feature.properties.timestamp).getTime()
            : Date.now()

          newPoints.push({
            id,
            coordinate: [lat, lon],
            timestamp,
            type,
            roi_id: feature.properties?.roi_id || feature.properties?.roi_identifier,
            properties: feature.properties
          })
        })
      }

      // ✅ Feldolgozás
      if (rawData?.features) processFeatures(rawData.features, 'raw')
      if (filteredData?.features) processFeatures(filteredData.features, 'filtered')

      // ✅ TTL cleanup + merge
      const now = Date.now()
      const ttl = geoJsonSettings.value.ttl

      geoJsonData.value = [
        ...geoJsonData.value.filter(p => (now - p.timestamp) <= ttl),
        ...newPoints
      ]

      // ✅ Update seen IDs
      batchIds.forEach(id => seenIds.add(id))

      // ✅ Cleanup seen IDs (max 10000)
      if (seenIds.size > 10000) {
        const arr = Array.from(seenIds)
        seenIds.clear()
        arr.slice(-5000).forEach(id => seenIds.add(id))
      }

      // ✅ Batch add to heatmap
      if (newPoints.length > 0) {
        addToHeatMap(newPoints)
      }

      console.log(`[Store] ✅ Fetch: ${(performance.now() - start).toFixed(0)}ms | New: ${newPoints.length} | Total: ${geoJsonData.value.length}`)
    } catch (error) {
      console.error('[Store] ❌ Fetch error:', error)
    } finally {
      isFetching = false
    }
  }

  const startGeoJsonFetch = async (): Promise<void> => {
    if (geoJsonIntervalId !== null) return

    console.log('[Store] 🌍 Starting GeoJSON fetch')
    isGeoJsonEnabled.value = true

    await fetchGeoJsonData()

    geoJsonIntervalId = window.setInterval(
      fetchGeoJsonData,
      geoJsonSettings.value.fetchPeriodSec * 1000
    )

    startGeoJsonCleanup()
    startHeatMapCleanup() // ✅ Heatmap cleanup is
  }

  const stopGeoJsonFetch = (): void => {
    if (geoJsonIntervalId !== null) {
      window.clearInterval(geoJsonIntervalId)
      geoJsonIntervalId = null
    }
    stopGeoJsonCleanup()
    stopHeatMapCleanup() // ✅ Heatmap cleanup stop
    isGeoJsonEnabled.value = false
    geoJsonData.value = []
    heatMapPoints.value = [] // ✅ Clear heatmap is
    seenIds.clear() // ✅ Clear dedup cache
  }

  const updateGeoJsonSettings = (settings: Partial<typeof geoJsonSettings.value>): void => {
    geoJsonSettings.value = { ...geoJsonSettings.value, ...settings }

    if (isGeoJsonEnabled.value) {
      stopGeoJsonFetch()
      startGeoJsonFetch()
    }
  }

  const startHeatMapCleanup = (): void => {
    if (heatMapCleanupIntervalId !== null) return

    console.log('[Store] 🧹 Starting HeatMap cleanup (every 5s)')

    heatMapCleanupIntervalId = window.setInterval(() => {
      const now = Date.now()
      const ttl = geoJsonSettings.value.ttl

      const beforeCount = heatMapPoints.value.length

      // ✅ TTL alapú cleanup
      heatMapPoints.value = heatMapPoints.value.filter(point => {
        const age = now - point.lastUpdate
        return age <= ttl
      })

      // ✅ Size limit ellenőrzés
      if (heatMapPoints.value.length > maxHeatMapSize.value) {
        heatMapPoints.value = heatMapPoints.value.slice(-maxHeatMapSize.value)
      }

      const cleaned = beforeCount - heatMapPoints.value.length
      if (cleaned > 0) {
        console.log(`[Store] 🧹 Cleaned ${cleaned} expired HeatMap points`)
      }
    }, 5000)
  }

  const stopHeatMapCleanup = (): void => {
    if (heatMapCleanupIntervalId !== null) {
      console.log('[Store] 🛑 Stopping HeatMap cleanup')
      window.clearInterval(heatMapCleanupIntervalId)
      heatMapCleanupIntervalId = null
    }
  }

  const startGeoJsonCleanup = (): void => {
    if (geoJsonCleanupIntervalId !== null) return

    geoJsonCleanupIntervalId = window.setInterval(() => {
      if (!isGeoJsonEnabled.value) return

      const now = Date.now()
      const ttl = geoJsonSettings.value.ttl
      const before = geoJsonData.value.length

      geoJsonData.value = geoJsonData.value.filter(p => (now - p.timestamp) <= ttl)

      const cleaned = before - geoJsonData.value.length
      if (cleaned > 0) {
        console.log(`[Store] 🧹 Cleaned ${cleaned} expired GeoJSON points`)
      }
    }, 5000)
  }

  const stopGeoJsonCleanup = (): void => {
    if (geoJsonCleanupIntervalId !== null) {
      window.clearInterval(geoJsonCleanupIntervalId)
      geoJsonCleanupIntervalId = null
    }
  }

  const addToHeatMap = (points: GeoJsonPoint[]): void => {
    const now = Date.now()

    // ✅ Batch push helyett destructuring
    const newHeatPoints: HeatMapPoint[] = points.map(point => ({
      coordinate: point.coordinate,
      lastUpdate: point.timestamp // ✅ Original timestamp használata
    }))

    // ✅ Egyetlen assignment
    heatMapPoints.value = [...heatMapPoints.value, ...newHeatPoints]

    // ✅ Size limit azonnal
    if (heatMapPoints.value.length > maxHeatMapSize.value) {
      heatMapPoints.value = heatMapPoints.value.slice(-maxHeatMapSize.value)
    }
  }

  return {
    geoJsonData,
    geoJsonSettings,
    isGeoJsonEnabled,
    startGeoJsonFetch,
    stopGeoJsonFetch,
    updateGeoJsonSettings,
    fetchGeoJsonData,
    heatMapPoints,
    maxHeatMapSize,
    addToHeatMap
  }
})
