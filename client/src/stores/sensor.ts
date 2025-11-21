// stores/sensor.ts - OPTIMALIZÁLT VERZIÓ
import { defineStore } from 'pinia'
import { ref, computed, watch, onUnmounted, shallowRef } from 'vue'
import { useDetectionWorker } from '@/composables/useDetectionWorker'
import type { Sensor } from '@/types/sensor'
import type { RealtimeConfig } from '@/types/config'

// ============================================================================
// TYPES
// ============================================================================

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

export const useSensorStore = defineStore('sensor', () => {
  // ============================================================================
  // STATE
  // ============================================================================

  const sensors = shallowRef<Record<number, Sensor>>({})
  const selectedSensor = ref<Sensor | null>(null)
  const selectedSensorIds = ref<number[]>([])
  const isLoading = ref(false)
  const errorMessage = ref('')

  const batchInterval = ref(0.05)
  const detectionSize = ref(100)

  const eventSource = ref<EventSource | null>(null)
  const isStreamConnected = ref(false)
  const streamUrl = ref('http://localhost:5000/v1/stream/comint_detection')

  const realtimeConfig = ref<RealtimeConfig>({
    maxLatencyMs: 1000,
    detectionTTL: 10000,
    enableStrictRealtime: true,
    circularBufferSize: 50,
    interval: 100
  })

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
  let cleanupIntervalId: number | null = null
  let geoJsonIntervalId: number | null = null
  let geoJsonCleanupIntervalId: number | null = null
  let heatMapCleanupIntervalId: number | null = null // ✅ ÚJ

  // ============================================================================
  // 🔥 ÚJ: HEATMAP CLEANUP
  // ============================================================================

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

  // ============================================================================
  // 🔥 OPTIMALIZÁLT: BATCH UPDATE A HEATMAP-hez
  // ============================================================================

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

  // ============================================================================
  // DETECTION CLEANUP (eredeti, de tisztított)
  // ============================================================================

  const startPeriodicCleanup = (): void => {
    if (cleanupIntervalId !== null) return

    cleanupIntervalId = window.setInterval(() => {
      const now = performance.now()
      const ttl = realtimeConfig.value.detectionTTL

      if (ttl <= 0) return

      const newSensors: Record<number, Sensor> = {}

      Object.entries(sensors.value).forEach(([id, sensor]) => {
        newSensors[+id] = {
          ...sensor,
          detections: sensor.detections.filter(d => (now - (d.timestamp || 0)) <= ttl)
        }
      })

      sensors.value = newSensors
    }, realtimeConfig.value.interval)
  }

  const stopPeriodicCleanup = (): void => {
    if (cleanupIntervalId !== null) {
      window.clearInterval(cleanupIntervalId)
      cleanupIntervalId = null
    }
  }

  // ============================================================================
  // 🔥 OPTIMALIZÁLT: GEOJSON FETCH with DEDUPLICATION
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

  // ============================================================================
  // GEOJSON CLEANUP (eredeti)
  // ============================================================================

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

  // ============================================================================
  // GEOJSON CONTROL
  // ============================================================================

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

  // ============================================================================
  // WORKER SETUP (eredeti, de tisztított)
  // ============================================================================

  const {
    initWorker,
    onWorkerMessage,
    updateSelectedUavIds,
    sendDetection,
    clearDetections,
    terminateWorker,
    isWorkerReady
  } = useDetectionWorker()

  const workerMessageCleanups: Array<() => void> = []

  const initializeWorker = (): void => {
    initWorker()

    const cleanupProcessed = onWorkerMessage('processedDetection', (data: any) => {
      const { detection, uavId } = data
      const now = performance.now()
      const ms = Math.floor(now % 1000)
      const sec = Math.floor((now / 1000) % 60)
      const min = Math.floor((now / (1000 * 60)) % 60)
      const hour = Math.floor((now / (1000 * 60 * 60)) % 24)

      const human = `${hour}h ${min}m ${sec}s ${ms}ms`
      console.log('human: ', human)

      if (!sensors.value[uavId]) return

      if (realtimeConfig.value.detectionTTL > 0) {
        const detections = sensors.value[uavId].detections.filter(
          d => (now - (d.timestamp || 0)) <= realtimeConfig.value.detectionTTL
        )
        sensors.value = {
          ...sensors.value,
          [uavId]: {
            ...sensors.value[uavId], // ← spreadeljük a régi szenzort
            detections // ← csak ezt írjuk felül
          }
        }
      }

      const buffer = sensors.value[uavId].detections
      if (buffer.length >= realtimeConfig.value.circularBufferSize) {
        sensors.value = {
          ...sensors.value,
          [uavId]: {
            ...sensors.value[uavId],
            detections: buffer.slice(-realtimeConfig.value.circularBufferSize)
          }
        }
      }

      sensors.value = {
        ...sensors.value,
        [uavId]: {
          ...sensors.value[uavId],
          detections: [
            ...sensors.value[uavId].detections,
            detection
          ]
        }
      }
    })

    workerMessageCleanups.push(cleanupProcessed)
    startPeriodicCleanup()
  }

  // ============================================================================
  // SSE STREAM (eredeti)
  // ============================================================================

  const initializeStream = (): void => {
    if (eventSource.value) return

    eventSource.value = new EventSource(streamUrl.value)

    eventSource.value.onopen = () => {
      isStreamConnected.value = true
    }

    eventSource.value.onmessage = (event: MessageEvent) => {
      if (!event.data) return
      if (!isWorkerReady()) initializeWorker()
      handleStreamData(event.data)
    }

    eventSource.value.onerror = () => {
      isStreamConnected.value = false
      if (eventSource.value?.readyState === EventSource.CLOSED) {
        setTimeout(() => {
          if (!isStreamConnected.value) {
            disconnectStream()
            initializeStream()
          }
        }, 5000)
      }
    }
  }

  const disconnectStream = (): void => {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
      isStreamConnected.value = false
    }
  }

  // ============================================================================
  // COMPUTED
  // ============================================================================

  const selectedSensors = computed(() =>
    Object.values(sensors.value).filter(s => s.is_selected)
  )

  const hasSelectedSensors = computed(() => selectedSensors.value.length > 0)

  // ============================================================================
  // WATCH
  // ============================================================================
  watch(selectedSensors, (newSelected) => {
    // 1. Update IDs
    const selectedIds = newSelected.map(s => s.uav_id)
    selectedSensorIds.value = selectedIds

    // 2. Initialize worker/stream ha szükséges
    if (selectedIds.length > 0) {
      if (!isWorkerReady()) initializeWorker()
      if (!isStreamConnected.value && !eventSource.value) initializeStream()
      updateSelectedUavIds(selectedIds)
    }
  }, { immediate: true, deep: false })

  // ============================================================================
  // ACTIONS
  // ============================================================================

  const selectSensor = (uavId: number): void => {
    const sensor = sensors.value[uavId]
    if (!sensor) return

    sensors.value = {
      ...sensors.value,
      [uavId]: { // ← Helyes kulcs
        ...sensor,
        is_selected: !sensor.is_selected
      }
    }
  }

  const updateRealtimeConfig = (config: Partial<RealtimeConfig>): void => {
    realtimeConfig.value = { ...realtimeConfig.value, ...config }
  }

  const handleStreamData = (rawData: string): void => {
    if (!isWorkerReady()) initializeWorker()
    sendDetection(rawData)
  }

  const fetchSensors = async (): Promise<void> => {
    isLoading.value = true
    errorMessage.value = ''

    try {
      const response = await fetch('http://localhost:5000/v1/uav')
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)

      const data = await response.json()
      const sensorsMap: Record<number, Sensor> = {}

      data.forEach((sensorData: any) => {
        sensorsMap[sensorData.uav_id] = {
          ...sensorData,
          is_selected: sensors.value[sensorData.uav_id]?.is_selected || false,
          detections: sensors.value[sensorData.uav_id]?.detections || []
        }
      })

      sensors.value = sensorsMap
    } catch (error) {
      errorMessage.value = 'Failed to load sensors'
    } finally {
      isLoading.value = false
    }
  }

  const removeSensor = (): void => {
    if (selectedSensor.value) {
      const uavId = selectedSensor.value.uav_id
      delete sensors.value[uavId]
      selectedSensor.value = null
    }
  }

  const handleMouseOver = (sensor: Sensor): void => {
    selectedSensor.value = sensor
  }

  const clearAllDetections = (): void => {
    const newSensors: Record<number, Sensor> = {}

    Object.entries(sensors.value).forEach(([id, sensor]) => {
      newSensors[+id] = {
        ...sensor,
        detections: []
      }
    })

    sensors.value = newSensors
    clearDetections()
  }

  const debugReactivity = (): void => {
    console.log('=== SENSOR STORE DEBUG ===')
    console.log('Sensors:', Object.keys(sensors.value).length)
    console.log('Selected:', selectedSensors.value.length)
    console.log('Worker ready:', isWorkerReady())
    console.log('Stream connected:', isStreamConnected.value)
    console.log('GeoJSON enabled:', isGeoJsonEnabled.value)
    console.log('GeoJSON points:', geoJsonData.value.length)
    console.log('HeatMap points:', heatMapPoints.value.length)
    console.log('Seen IDs cache:', seenIds.size)
  }

  // ============================================================================
  // LIFECYCLE
  // ============================================================================

  onUnmounted(() => {
    stopPeriodicCleanup()
    stopGeoJsonFetch()
    disconnectStream()
    workerMessageCleanups.forEach(cleanup => {
      cleanup()
      console.log('cleanup: ', cleanup)
    })
    terminateWorker()
  })

  // ============================================================================
  // RETURN
  // ============================================================================

  return {
    sensors,
    selectedSensor,
    isLoading,
    errorMessage,
    batchInterval,
    detectionSize,
    isStreamConnected,
    streamUrl,
    geoJsonData,
    geoJsonSettings,
    isGeoJsonEnabled,
    selectedSensors,
    hasSelectedSensors,
    initializeWorker,
    initializeStream,
    disconnectStream,
    selectSensor,
    handleStreamData,
    fetchSensors,
    removeSensor,
    handleMouseOver,
    clearDetections: clearAllDetections,
    debugReactivity,
    isWorkerReady,
    realtimeConfig,
    updateRealtimeConfig,
    startPeriodicCleanup,
    stopPeriodicCleanup,
    selectedSensorIds,
    startGeoJsonFetch,
    stopGeoJsonFetch,
    updateGeoJsonSettings,
    fetchGeoJsonData,
    heatMapPoints,
    maxHeatMapSize,
    addToHeatMap // ✅ Export if needed
  }
})
