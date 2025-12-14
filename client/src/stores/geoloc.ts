// stores/geoloc.ts - PERZISZTENS HEATMAP VERZIÓ
import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

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
  // ✅ SHALLOW REFS FOR ARRAYS
  const geoJsonData = shallowRef<GeoJsonPoint[]>([])
  const geoJsonSettings = ref({
    limit: 20,
    stride: 1,
    fetchPeriodSec: 1,
    showRaw: true,
    showFiltered: true,
    ttl: 3600000  // ✅ 1 óra (3600s) - hosszabb megőrzés
  })
  const isGeoJsonEnabled = ref(false)

  // ✅ HEATMAP SETTINGS - Perzisztens mód
  const heatMapSettings = ref({
    enabled: true,
    maxSize: 10000,         // ✅ 10k pont maximum
    enableTTLCleanup: false, // ✅ NINCS automatikus TTL-alapú törlés!
    enableSizeLimit: true    // ✅ Csak size limit van
  })

  // ✅ SHALLOW REF FOR HEATMAP
  const heatMapPoints = shallowRef<HeatMapPoint[]>([])

  // Cleanup intervals
  let geoJsonIntervalId: number | null = null
  let geoJsonCleanupIntervalId: number | null = null
  let heatMapCleanupIntervalId: number | null = null

  // ✅ DEDUPLIKÁCIÓ - Map (gyorsabb lookup)
  const seenIds = new Map<string, number>() // id -> timestamp

  let isFetching = false

  // ============================================================================
  // GEOJSON CONTROL - ✅ OPTIMALIZÁLT
  // ============================================================================

  const fetchGeoJsonData = async (): Promise<void> => {
    if (!isGeoJsonEnabled.value || isFetching) return
    isFetching = true

    const { limit, stride, showRaw, showFiltered, ttl } = geoJsonSettings.value
    const newPoints: GeoJsonPoint[] = []

    try {
      const start = performance.now()
      const now = Date.now()

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
          const coords = feature.geometry?.coordinates
          if (!coords || coords.length !== 2) return

          const [lon, lat] = coords
          if (isNaN(lat) || isNaN(lon)) return

          const id = String(feature.properties?.geoloc_id || `${type}-${idx}-${Date.now()}`)

          // ✅ Deduplikáció Map-pel
          if (seenIds.has(id)) return
          seenIds.set(id, now)

          const timestamp = feature.properties?.timestamp
            ? new Date(feature.properties.timestamp).getTime()
            : now

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

      // ✅ OPTIMALIZÁLT MERGE: Filter + push helyett új array
      const existingValid = geoJsonData.value.filter(p => (now - p.timestamp) <= ttl)
      geoJsonData.value = [...existingValid, ...newPoints]

      // ✅ Cleanup seen IDs (csak ha túl nagy)
      if (seenIds.size > 10000) {
        const entries = Array.from(seenIds.entries())
        seenIds.clear()
        // Csak a legfrissebb 5000-et tartjuk meg
        entries
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5000)
          .forEach(([id, ts]) => seenIds.set(id, ts))
      }

      // ✅ Batch add to heatmap
      if (newPoints.length > 0) {
        addToHeatMap(newPoints)
      }

      console.log(`[GeoLocStore] ✅ Fetch: ${(performance.now() - start).toFixed(0)}ms | New: ${newPoints.length} | Total GeoJSON: ${geoJsonData.value.length} | HeatMap: ${heatMapPoints.value.length}`)
    } catch (error) {
      console.error('[GeoLocStore] ❌ Fetch error:', error)
    } finally {
      isFetching = false
    }
  }

  const startGeoJsonFetch = async (): Promise<void> => {
    if (geoJsonIntervalId !== null) return

    console.log('[GeoLocStore] 🌍 Starting GeoJSON fetch')
    isGeoJsonEnabled.value = true

    await fetchGeoJsonData()

    geoJsonIntervalId = window.setInterval(
      fetchGeoJsonData,
      geoJsonSettings.value.fetchPeriodSec * 1000
    )

    startGeoJsonCleanup()
    startHeatMapCleanup()
  }

  const stopGeoJsonFetch = (): void => {
    if (geoJsonIntervalId !== null) {
      window.clearInterval(geoJsonIntervalId)
      geoJsonIntervalId = null
    }
    stopGeoJsonCleanup()
    stopHeatMapCleanup()
    isGeoJsonEnabled.value = false

    // ✅ NE töröljük a heatmap pontokat automatikusan!
    geoJsonData.value = []
    seenIds.clear()

    console.log('[GeoLocStore] ⏸️ Fetch stopped (HeatMap points preserved)')
  }

  const updateGeoJsonSettings = (settings: Partial<typeof geoJsonSettings.value>): void => {
    geoJsonSettings.value = { ...geoJsonSettings.value, ...settings }

    if (isGeoJsonEnabled.value) {
      stopGeoJsonFetch()
      startGeoJsonFetch()
    }
  }

  // ✅ GEOJSON CLEANUP - Csak GeoJSON adatokat tisztít
  const startGeoJsonCleanup = (): void => {
    if (geoJsonCleanupIntervalId !== null) return

    geoJsonCleanupIntervalId = window.setInterval(() => {
      if (!isGeoJsonEnabled.value) return

      const now = Date.now()
      const ttl = geoJsonSettings.value.ttl
      const before = geoJsonData.value.length

      // ✅ Új array referencia (shallow ref miatt jó)
      geoJsonData.value = geoJsonData.value.filter(p => (now - p.timestamp) <= ttl)

      const cleaned = before - geoJsonData.value.length
      if (cleaned > 0) {
        console.log(`[GeoLocStore] 🧹 Cleaned ${cleaned} expired GeoJSON points`)
      }
    }, 10000) // 10s
  }

  const stopGeoJsonCleanup = (): void => {
    if (geoJsonCleanupIntervalId !== null) {
      window.clearInterval(geoJsonCleanupIntervalId)
      geoJsonCleanupIntervalId = null
    }
  }

  // ✅ HEATMAP CLEANUP - PERZISZTENS MÓD (csak size limit!)
  const startHeatMapCleanup = (): void => {
    if (heatMapCleanupIntervalId !== null) return

    if (!heatMapSettings.value.enableTTLCleanup) {
      console.log('[GeoLocStore] ℹ️ HeatMap TTL cleanup DISABLED (persistent mode)')
      return
    }

    console.log('[GeoLocStore] 🧹 Starting HeatMap TTL cleanup')

    heatMapCleanupIntervalId = window.setInterval(() => {
      const now = Date.now()
      const ttl = geoJsonSettings.value.ttl

      const beforeCount = heatMapPoints.value.length

      // ✅ TTL alapú cleanup (ha enabled)
      let cleaned = heatMapPoints.value.filter(point => {
        const age = now - point.lastUpdate
        return age <= ttl
      })

      // ✅ Size limit mindig él!
      if (heatMapSettings.value.enableSizeLimit &&
          cleaned.length > heatMapSettings.value.maxSize) {
        cleaned = cleaned.slice(-heatMapSettings.value.maxSize)
      }

      heatMapPoints.value = cleaned

      const removedCount = beforeCount - heatMapPoints.value.length
      if (removedCount > 0) {
        console.log(`[GeoLocStore] 🧹 Cleaned ${removedCount} HeatMap points`)
      }
    }, 30000) // ✅ 30s (ritkábban fut)
  }

  const stopHeatMapCleanup = (): void => {
    if (heatMapCleanupIntervalId !== null) {
      console.log('[GeoLocStore] 🛑 Stopping HeatMap cleanup')
      window.clearInterval(heatMapCleanupIntervalId)
      heatMapCleanupIntervalId = null
    }
  }

  // ✅ OPTIMALIZÁLT: Batch add - FRISS TIMESTAMP MINDIG!
  const addToHeatMap = (points: GeoJsonPoint[]): void => {
    const now = Date.now()

    const newHeatPoints: HeatMapPoint[] = points.map(point => ({
      coordinate: point.coordinate,
      lastUpdate: now  // ✅ Mindig friss timestamp! Így sosem öregszik el
    }))

    // ✅ Egyetlen merge
    let combined = [...heatMapPoints.value, ...newHeatPoints]

    // ✅ Size limit azonnal (FIFO - legrégebbiek eldobása)
    if (heatMapSettings.value.enableSizeLimit &&
        combined.length > heatMapSettings.value.maxSize) {
      const toRemove = combined.length - heatMapSettings.value.maxSize
      combined = combined.slice(toRemove) // Legrégebbiek törlése
    }

    heatMapPoints.value = combined
    console.log(`[GeoLocStore] 📍 HeatMap: +${newHeatPoints.length} new | Total: ${heatMapPoints.value.length}/${heatMapSettings.value.maxSize}`)
  }

  const clearHeatMap = (): void => {
    heatMapPoints.value = []
    console.log('[GeoLocStore] 🧹 HeatMap manually cleared')
  }

  const clearAll = (): void => {
    geoJsonData.value = []
    heatMapPoints.value = []
    seenIds.clear()
    console.log('[GeoLocStore] 🧹 All data cleared')
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
    heatMapSettings,
    addToHeatMap,
    clearHeatMap,

    clearAll
  }
})