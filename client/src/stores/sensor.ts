// stores/sensor.ts
import { defineStore } from 'pinia'
import { ref, computed, watch, onUnmounted } from 'vue'
import { useDetectionWorker } from '@/composables/useDetectionWorker'
import type { Sensor } from '@/types/sensor'
import type { RealtimeConfig } from '@/types/config'
import type {
  ProcessedDetectionMessage,
  StatsUpdatedMessage,
  ErrorMessage,
  WorkerStartedMessage,
  MemoryStatsMessage
} from '@/types/worker'

// GeoJSON típusok
interface GeoJsonPoint {
  id: number
  coordinate: [number, number]
  timestamp: number
  type: 'raw' | 'filtered'
  roi_id?: number
  properties?: any
}

export const useSensorStore = defineStore('sensor', () => {
  // ============================================================================
  // STATE
  // ============================================================================

  const sensors = ref<Record<number, Sensor>>({})
  const selectedSensor = ref<Sensor | null>(null)
  const selectedSensorIds = ref<number[]>([])
  const isLoading = ref(false)
  const errorMessage = ref('')

  // Settings
  const batchInterval = ref(0.05)
  const detectionSize = ref(100)

  // SSE Connection
  const eventSource = ref<EventSource | null>(null)
  const isStreamConnected = ref(false)
  const streamUrl = ref('http://localhost:5000/v1/stream/comint_detection')

  const realtimeConfig = ref<RealtimeConfig>({
    maxLatencyMs: 1000,
    detectionTTL: 10000,
    enableStrictRealtime: true,
    circularBufferSize: 50
  })

  // GeoJSON State
  const geoJsonData = ref<GeoJsonPoint[]>([])
  const geoJsonSettings = ref({
    limit: 20,
    stride: 1,
    fetchPeriodSec: 1,
    showRaw: true,
    showFiltered: true,
    ttl: 10000
  })
  const isGeoJsonEnabled = ref(false)
  let geoJsonIntervalId: number | null = null
  let geoJsonCleanupIntervalId: number | null = null

  // Cleanup interval reference
  let cleanupIntervalId: number | null = null

  // ============================================================================
  // PERIODIKUS CLEANUP
  // ============================================================================

  const startPeriodicCleanup = (): void => {
    if (cleanupIntervalId !== null) {
      return
    }

    // console.log('[Store] 🧹 Starting periodic detection cleanup (every 100ms)')

    cleanupIntervalId = window.setInterval(() => {
      const now = performance.now()
      const ttl = realtimeConfig.value.detectionTTL

      if (ttl <= 0) return

      let totalCleaned = 0

      Object.entries(sensors.value).forEach(([uavId, sensor]) => {
        const beforeCount = sensor.detections.length

        sensor.detections = sensor.detections.filter(detection => {
          const age = now - (detection.timestamp || 0)
          return age <= ttl
        })

        const cleaned = beforeCount - sensor.detections.length
        totalCleaned += cleaned

        // if (cleaned > 0) {
        //   console.log(`[Store] 🧹 Cleaned ${cleaned} expired detections from sensor ${uavId}`)
        // }
      })

      // if (totalCleaned > 0) {
      //   console.log(`[Store] 🧹 Total cleaned: ${totalCleaned} detections`)
      // }
    }, 100)
  }

  const stopPeriodicCleanup = (): void => {
    if (cleanupIntervalId !== null) {
      // console.log('[Store] 🛑 Stopping periodic cleanup')
      window.clearInterval(cleanupIntervalId)
      cleanupIntervalId = null
    }
  }

  // ============================================================================
  // GEOJSON FETCH
  // ============================================================================

  let isFetching = false

  const fetchGeoJsonData = async (): Promise<void> => {

    if (!isGeoJsonEnabled.value) return
    if (isFetching) {
      console.warn('[Store] ⏳ Previous fetch still running, skipping...')
      return
    }
    isFetching = true

    const { limit, stride, showRaw, showFiltered } = geoJsonSettings.value
    const newPoints: GeoJsonPoint[] = []

    try {
      const start = performance.now()

      // 🚀 PÁRHUZAMOS FETCH-EK
      const [rawData, filteredData] = await Promise.all([
        // RAW fetch
        showRaw
          ? fetch(`http://localhost:5000/v1/comintgeoloc/geojson/raw/list_last/${limit}`)
            .then(res => res.ok ? res.json() : null)
            .catch(err => {
              console.error('[Store] ❌ RAW fetch error:', err)
              return null
            })
          : Promise.resolve(null),

        // FILTERED fetch
        showFiltered
          ? fetch(`http://localhost:5000/v1/comintgeoloc/geojson/list_last/${limit}?stride=${stride}`)
            .then(res => res.ok ? res.json() : null)
            .catch(err => {
              console.error('[Store] ❌ FILTERED fetch error:', err)
              return null
            })
          : Promise.resolve(null)
      ])

      const fetchEnd = performance.now()
      console.log(`[Store] ⚡ Fetch completed in ${(fetchEnd - start).toFixed(2)}ms`)

      // === PROCESS RAW DATA ===
      if (rawData?.features) {
        rawData.features.forEach((feature: any, idx: number) => {
          console.log('feature: ', feature)
          const coords = feature.geometry?.coordinates
          if (!coords || coords.length !== 2) return

          const [lon, lat] = coords
          if (isNaN(lat) || isNaN(lon)) return

          const detectionTimestamp = feature.properties?.timestamp
            ? new Date(feature.properties.timestamp).getTime()
            : Date.now() - Math.random() * 5000

          newPoints.push({
            id: feature.properties?.geoloc_id || `raw-${idx}-${Math.random()}`,
            coordinate: [lat, lon] as [number, number],
            timestamp: detectionTimestamp,
            type: 'raw' as const,
            roi_id: feature.properties?.roi_id,
            properties: feature.properties
          })
        })
      }

      // === PROCESS FILTERED DATA ===
      if (filteredData?.features) {
        filteredData.features.forEach((feature: any, idx: number) => {
          const coords = feature.geometry?.coordinates
          if (!coords || coords.length !== 2) return

          const [lon, lat] = coords
          if (isNaN(lat) || isNaN(lon)) return

          const detectionTimestamp = feature.properties?.timestamp
            ? new Date(feature.properties.timestamp).getTime()
            : Date.now() - Math.random() * 5000

          newPoints.push({
            id: feature.properties?.geoloc_id || `filtered-${idx}-${Math.random()}`,
            coordinate: [lat, lon] as [number, number],
            timestamp: detectionTimestamp,
            type: 'filtered' as const,
            roi_id: feature.properties?.roi_identifier,
            properties: feature.properties
          })
        })
      }

      // === MERGE WITH CLEANUP ===
      const now = Date.now()
      const ttl = geoJsonSettings.value.ttl

      const existingPoints = geoJsonData.value.filter(point =>
        (now - point.timestamp) <= ttl
      )

      geoJsonData.value = [...existingPoints, ...newPoints]

      const totalTime = performance.now() - start
      console.log(`[Store] ✅ Total: ${totalTime.toFixed(2)}ms | Points: ${newPoints.length} | Total: ${geoJsonData.value.length}`)
    } catch (error) {
      console.error('[Store] ❌ Failed to fetch GeoJSON:', error)
    } finally {
      isFetching = false
    }

  }

  // ============================================================================
  // GEOJSON CLEANUP
  // ============================================================================

  const startGeoJsonCleanup = (): void => {
    if (geoJsonCleanupIntervalId !== null) return

    console.log('[Store] 🧹 Starting GeoJSON cleanup (every 5s)')

    geoJsonCleanupIntervalId = window.setInterval(() => {
      if (!isGeoJsonEnabled.value) return

      const now = Date.now()
      const ttl = geoJsonSettings.value.ttl

      const beforeCount = geoJsonData.value.length
      geoJsonData.value = geoJsonData.value.filter(point => {
        const age = now - point.timestamp
        return age <= ttl
      })

      const cleaned = beforeCount - geoJsonData.value.length
      if (cleaned > 0) {
        console.log(`[Store] 🧹 Cleaned ${cleaned} expired GeoJSON points`)
      }
    }, 5000) // 5 másodpercenként
  }

  const stopGeoJsonCleanup = (): void => {
    if (geoJsonCleanupIntervalId !== null) {
      console.log('[Store] 🛑 Stopping GeoJSON cleanup')
      window.clearInterval(geoJsonCleanupIntervalId)
      geoJsonCleanupIntervalId = null
    }
  }

  async function startGeoJsonFetch (): Promise<void> {
    if (geoJsonIntervalId !== null) return

    console.log('[Store] 🌍 Starting GeoJSON periodic fetch')
    isGeoJsonEnabled.value = true

    // Initial fetch — wait for completion
    await fetchGeoJsonData()
    console.log('first fetch completed')

    // Start periodic fetch
    geoJsonIntervalId = window.setInterval(fetchGeoJsonData, geoJsonSettings.value.fetchPeriodSec * 1000)

    // Start cleanup is
    startGeoJsonCleanup()
  }

  const stopGeoJsonFetch = (): void => {
    if (geoJsonIntervalId !== null) {
      console.log('[Store] 🛑 Stopping GeoJSON fetch')
      window.clearInterval(geoJsonIntervalId)
      geoJsonIntervalId = null
    }
    stopGeoJsonCleanup()
    isGeoJsonEnabled.value = false
    geoJsonData.value = []
  }

  const updateGeoJsonSettings = (settings: Partial<typeof geoJsonSettings.value>): void => {
    geoJsonSettings.value = { ...geoJsonSettings.value, ...settings }
    console.log('[Store] ⚙️ GeoJSON settings updated:', geoJsonSettings.value)

    // Restart if active
    if (isGeoJsonEnabled.value) {
      stopGeoJsonFetch()
      startGeoJsonFetch()
    }
  }

  // ============================================================================
  // WORKER SETUP
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
    // console.log('[Store] 🚀 Initializing detection worker...')

    initWorker()

    const cleanupProcessed = onWorkerMessage<ProcessedDetectionMessage>(
      'processedDetection',
      (data) => {
        const { detection, uavId } = data
        const now = performance.now()

        if (!sensors.value[uavId]) {
          console.warn(`[Store] ⚠️ Received detection for unknown sensor: ${uavId}`)
          return
        }

        if (typeof detection.timestamp === 'number') {
          const latency = now - detection.timestamp
          const hasDetections = sensors.value[uavId].detections.length > 0

          // console.log(`[Store] ⏱️ Sensor ${uavId} latency: ${latency.toFixed(2)}ms (buffer: ${sensors.value[uavId].detections.length})`)

          if (realtimeConfig.value.enableStrictRealtime &&
              hasDetections &&
              latency > realtimeConfig.value.maxLatencyMs) {
            console.warn(
              `[Store] ❌ Dropped detection due to high latency: ${latency.toFixed(2)}ms > ${realtimeConfig.value.maxLatencyMs}ms`
            )
            return
          }

          if (!hasDetections && latency > realtimeConfig.value.maxLatencyMs) {
            console.warn(
              `[Store] ⚠️ High latency on first detection: ${latency.toFixed(2)}ms, but allowing (empty buffer)`
            )
          }
        }

        if (realtimeConfig.value.detectionTTL > 0) {
          const beforeCount = sensors.value[uavId].detections.length

          sensors.value[uavId].detections = sensors.value[uavId].detections.filter(d => {
            const age = now - (d.timestamp || 0)
            return age <= realtimeConfig.value.detectionTTL
          })

          const cleaned = beforeCount - sensors.value[uavId].detections.length
          // if (cleaned > 0) {
          //   console.log(`[Store] 🧹 Cleaned ${cleaned} expired detections during insert (sensor ${uavId})`)
          // }
        }

        const buffer = sensors.value[uavId].detections
        const maxSize = realtimeConfig.value.circularBufferSize

        if (buffer.length >= maxSize) {
          sensors.value[uavId].detections = buffer.slice(1)
        }

        sensors.value[uavId].detections.push(detection)

        // console.log(`[Store] ✅ Sensor ${uavId} detections: ${sensors.value[uavId].detections.length}`)
      }
    )

    const cleanupStats = onWorkerMessage<StatsUpdatedMessage>(
      'statsUpdated',
      (data) => {
        console.log('[Store] 📊 Worker stats:', data.stats)
      }
    )

    const cleanupError = onWorkerMessage<ErrorMessage>(
      'error',
      (data) => {
        console.error('[Store] ❌ Worker error:', data.message)
        errorMessage.value = data.message
      }
    )

    const cleanupStarted = onWorkerMessage<WorkerStartedMessage>(
      'workerStarted',
      (data) => {
        console.log(`[Store] ✅ Worker started - version: ${data.version}`)
      }
    )

    const cleanupUavIds = onWorkerMessage<{ uavIds: number[] }>(
      'uavIdsUpdated',
      (data) => {
        // console.log('[Store] 📋 Worker confirmed UAV IDs:', data.uavIds)
      }
    )

    const cleanupMemory = onWorkerMessage<MemoryStatsMessage>(
      'memoryStats',
      (data) => {
        const usedMB = (data.memory.usedJSHeapSize / 1024 / 1024).toFixed(2)
        const totalMB = (data.memory.totalJSHeapSize / 1024 / 1024).toFixed(2)
        console.log(`[Store] 💾 Worker memory: ${usedMB}MB / ${totalMB}MB`)
      }
    )

    workerMessageCleanups.push(
      cleanupProcessed,
      cleanupStats,
      cleanupError,
      cleanupStarted,
      cleanupUavIds,
      cleanupMemory
    )

    console.log('[Store] ✅ Worker initialized and handlers registered')
    startPeriodicCleanup()
  }

  // ============================================================================
  // SSE STREAM CONNECTION
  // ============================================================================

  const initializeStream = (): void => {
    if (eventSource.value) {
      console.log('[Store] 📡 Stream already connected')
      return
    }

    console.log('[Store] 📡 Initializing SSE stream connection to:', streamUrl.value)

    try {
      eventSource.value = new EventSource(streamUrl.value)

      eventSource.value.onopen = () => {
        console.log('[Store] 📡 ✅ SSE Stream connected')
        isStreamConnected.value = true
      }

      eventSource.value.onmessage = (event: MessageEvent) => {
        // console.log('[Store] 📥 SSE message received, data length:', event.data?.length)

        if (!event.data) {
          console.warn('[Store] ⚠️ Empty SSE message received')
          return
        }

        if (!isWorkerReady()) {
          console.warn('[Store] ⚠️ Worker not ready when stream data arrived, initializing...')
          initializeWorker()
        }

        handleStreamData(event.data)
      }

      eventSource.value.onerror = (error: Event) => {
        console.error('[Store] 📡 ❌ SSE Stream error:', error)
        isStreamConnected.value = false

        if (eventSource.value?.readyState === EventSource.CLOSED) {
          console.log('[Store] 📡 Stream closed, attempting to reconnect in 5 seconds...')
          setTimeout(() => {
            if (!isStreamConnected.value) {
              console.log('[Store] 📡 Reconnecting...')
              disconnectStream()
              initializeStream()
            }
          }, 5000)
        }
      }

      console.log('[Store] 📡 SSE Stream listener registered')
    } catch (error) {
      console.error('[Store] 📡 Failed to initialize SSE stream:', error)
      errorMessage.value = 'Failed to connect to stream'
    }
  }

  const disconnectStream = (): void => {
    if (eventSource.value) {
      console.log('[Store] 📡 Disconnecting SSE stream...')
      eventSource.value.close()
      eventSource.value = null
      isStreamConnected.value = false
      console.log('[Store] 📡 ✅ SSE Stream disconnected')
    }
  }

  // ============================================================================
  // COMPUTED
  // ============================================================================

  const selectedSensors = computed(() => {
    return Object.values(sensors.value).filter(sensor => sensor.is_selected)
  })

  const hasSelectedSensors = computed(() => {
    return selectedSensors.value.length > 0
  })

  // ============================================================================
  // WATCH
  // ============================================================================

  watch(
    selectedSensors,
    (newSelected) => {
      selectedSensorIds.value = newSelected.map(s => s.uav_id)
      // console.log('[Store] 📋 Selected sensor IDs updated:', selectedSensorIds.value)
    },
    { immediate: true, deep: true }
  )

  watch(
    selectedSensors,
    (newSelected) => {
      const selectedIds = newSelected.map(s => s.uav_id)
      // console.log('[Store] 📤 Selected sensors changed:', selectedIds)

      if (selectedIds.length > 0) {
        if (!isWorkerReady()) {
          console.warn('[Store] ⚠️ Sensors selected but worker not ready, initializing...')
          initializeWorker()
        }

        if (!isStreamConnected.value && !eventSource.value) {
          console.log('[Store] 📡 Sensors selected, initializing stream...')
          initializeStream()
        }

        updateSelectedUavIds(selectedIds)
      } else {
        console.log('[Store] No sensors selected')
      }
    },
    { immediate: true, deep: true }
  )

  // ============================================================================
  // ACTIONS
  // ============================================================================

  const selectSensor = (uavId: number): void => {
    if (sensors.value[uavId]) {
      sensors.value[uavId].is_selected = !sensors.value[uavId].is_selected
      console.log(`[Store] Sensor ${uavId} ${sensors.value[uavId].is_selected ? 'selected' : 'deselected'}`)
    }
  }

  const updateRealtimeConfig = (config: Partial<RealtimeConfig>): void => {
    realtimeConfig.value = { ...realtimeConfig.value, ...config }
    console.log('[Store] ⚙️ Realtime config updated:', realtimeConfig.value)
  }

  const handleStreamData = (rawData: string): void => {
    // console.log('[Store] 📥 handleStreamData called, data length:', rawData?.length)

    if (!isWorkerReady()) {
      console.warn('[Store] ⚠️ Worker not initialized when stream data arrived, initializing now...')
      initializeWorker()
    }

    // console.log('[Store] 📤 Sending to worker...')
    sendDetection(rawData)
  }

  const fetchSensors = async (): Promise<void> => {
    isLoading.value = true
    errorMessage.value = ''

    try {
      const response = await fetch('http://localhost:5000/v1/uav')

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

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
      console.log('[Store] ✅ Sensors fetched:', Object.keys(sensorsMap).length)
    } catch (error) {
      console.error('[Store] ❌ Failed to fetch sensors:', error)
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
      console.log(`[Store] Sensor ${uavId} removed`)
    }
  }

  const handleMouseOver = (sensor: Sensor): void => {
    selectedSensor.value = sensor
  }

  const clearAllDetections = (): void => {
    Object.values(sensors.value).forEach(sensor => {
      sensor.detections = []
    })
    clearDetections()
    console.log('[Store] 🧹 All detections cleared')
  }

  const debugReactivity = (): void => {
    console.log('=== SENSOR STORE DEBUG ===')
    console.log('Total sensors:', Object.keys(sensors.value).length)
    console.log('Selected sensors:', selectedSensors.value.length)
    console.log('Has selections:', hasSelectedSensors.value)
    console.log('Worker ready:', isWorkerReady())
    console.log('Stream connected:', isStreamConnected.value)
    console.log('Cleanup interval active:', cleanupIntervalId !== null)
    console.log('GeoJSON enabled:', isGeoJsonEnabled.value)
    console.log('GeoJSON points:', geoJsonData.value.length)
    console.log('Settings:', {
      batchInterval: batchInterval.value,
      detectionSize: detectionSize.value,
      streamUrl: streamUrl.value
    })
    console.log('Realtime config:', realtimeConfig.value)
    console.log('GeoJSON settings:', geoJsonSettings.value)

    selectedSensors.value.forEach(sensor => {
      console.log(`Sensor ${sensor.uav_id}:`, {
        label: sensor.uav_label,
        detections: sensor.detections.length
      })
    })
  }

  // ============================================================================
  // LIFECYCLE
  // ============================================================================

  onUnmounted(() => {
    console.log('[Store] 🧹 Cleaning up...')
    stopPeriodicCleanup()
    stopGeoJsonFetch()
    disconnectStream()
    workerMessageCleanups.forEach(cleanup => cleanup())
    terminateWorker()
    console.log('[Store] ✅ Cleanup complete')
  })

  // ============================================================================
  // RETURN
  // ============================================================================

  return {
    // State
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

    // Computed
    selectedSensors,
    hasSelectedSensors,

    // Actions
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
    fetchGeoJsonData
  }
})
