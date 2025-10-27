// stores/sensor.ts
import { defineStore } from 'pinia'
import { ref, computed, watch, onUnmounted } from 'vue'
import { useDetectionWorker } from '@/composables/useDetectionWorker'
import type { Sensor } from '@/types/sensor'
import type {
  ProcessedDetectionMessage,
  StatsUpdatedMessage,
  ErrorMessage,
  WorkerStartedMessage,
  MemoryStatsMessage
} from '@/types/worker'

export const useSensorStore = defineStore('sensor', () => {
  // ============================================================================
  // STATE
  // ============================================================================

  const sensors = ref<Record<number, Sensor>>({})
  const selectedSensor = ref<Sensor | null>(null)
  const isLoading = ref(false)
  const errorMessage = ref('')

  // Settings
  const batchInterval = ref(0.05)
  const detectionSize = ref(100)

  // SSE Connection
  const eventSource = ref<EventSource | null>(null)
  const isStreamConnected = ref(false)
  const streamUrl = ref('http://localhost:5000/v1/stream/comint_detection')

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

  /**
   * Worker inicializálása és message handlerek regisztrálása
   */
  const initializeWorker = (): void => {
    console.log('[Store] 🚀 Initializing detection worker...')

    initWorker()

    // Processed detection handler
    const cleanupProcessed = onWorkerMessage<ProcessedDetectionMessage>(
      'processedDetection',
      (data) => {
        const { detection, uavId } = data
        if (typeof detection.timestamp === 'number') {
          const diff = performance.now() - detection.timestamp
          console.log(`⏱️ Latency (now - detection.timestamp): ${diff.toFixed(2)} ms`)
        }
        console.log('[Store] 📥 Detection received from worker:', { uavId, coordinate: detection.coordinate })

        if (sensors.value[uavId]) {
          // Detekció hozzáadása
          sensors.value[uavId].detections.push(detection)

          // Limit detections (memória optimalizálás)
          const maxDetections = detectionSize.value
          if (sensors.value[uavId].detections.length > maxDetections) {
            sensors.value[uavId].detections.shift()
          }

          console.log(`[Store] Sensor ${uavId} now has ${sensors.value[uavId].detections.length} detections`)
        } else {
          console.warn(`[Store] ⚠️ Received detection for unknown sensor: ${uavId}`)
        }
      }
    )

    // Stats handler
    const cleanupStats = onWorkerMessage<StatsUpdatedMessage>(
      'statsUpdated',
      (data) => {
        console.log('[Store] Worker stats:', data.stats)
      }
    )

    // Error handler
    const cleanupError = onWorkerMessage<ErrorMessage>(
      'error',
      (data) => {
        console.error('[Store] Worker error:', data.message)
        errorMessage.value = data.message
      }
    )

    // Worker started handler
    const cleanupStarted = onWorkerMessage<WorkerStartedMessage>(
      'workerStarted',
      (data) => {
        console.log(`[Store] ✅ Worker started - version: ${data.version}`)
      }
    )

    // UAV IDs updated handler
    const cleanupUavIds = onWorkerMessage<{ uavIds: number[] }>(
      'uavIdsUpdated',
      (data) => {
        console.log('[Store] Worker confirmed UAV IDs:', data.uavIds)
      }
    )

    // Memory stats handler
    const cleanupMemory = onWorkerMessage<MemoryStatsMessage>(
      'memoryStats',
      (data) => {
        const usedMB = (data.memory.usedJSHeapSize / 1024 / 1024).toFixed(2)
        const totalMB = (data.memory.totalJSHeapSize / 1024 / 1024).toFixed(2)
        console.log(`[Store] Worker memory: ${usedMB}MB / ${totalMB}MB`)
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
  }

  // ============================================================================
  // SSE STREAM CONNECTION
  // ============================================================================

  /**
   * SSE stream kapcsolat inicializálása
   */
  const initializeStream = (): void => {
    if (eventSource.value) {
      console.log('[Store] 📡 Stream already connected')
      return
    }

    console.log('[Store] 📡 Initializing SSE stream connection to:', streamUrl.value)

    try {
      eventSource.value = new EventSource(streamUrl.value)

      // Connection opened
      eventSource.value.onopen = () => {
        console.log('[Store] 📡 ✅ SSE Stream connected')
        isStreamConnected.value = true
      }

      // Message received
      eventSource.value.onmessage = (event: MessageEvent) => {
        console.log('[Store] 📥 SSE message received, data length:', event.data?.length)

        if (!event.data) {
          console.warn('[Store] ⚠️ Empty SSE message received')
          return
        }

        // Ensure worker is initialized
        if (!isWorkerReady()) {
          console.warn('[Store] ⚠️ Worker not ready when stream data arrived, initializing...')
          initializeWorker()
        }

        // Send to worker
        handleStreamData(event.data)
      }

      // Error handling
      eventSource.value.onerror = (error: Event) => {
        console.error('[Store] 📡 ❌ SSE Stream error:', error)
        isStreamConnected.value = false

        // Reconnect logic
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

  /**
   * SSE stream kapcsolat bontása
   */
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

  // Watch selectedSensors és automatikusan inicializál mindent
  watch(
    selectedSensors,
    (newSelected) => {
      const selectedIds = newSelected.map(s => s.uav_id)
      console.log('[Store] 📤 Selected sensors changed:', selectedIds)

      // Ha van kiválasztott szenzor
      if (selectedIds.length > 0) {
        // 1. Worker inicializálása ha szükséges
        if (!isWorkerReady()) {
          console.warn('[Store] ⚠️ Sensors selected but worker not ready, initializing...')
          initializeWorker()
        }

        // 2. Stream inicializálása ha szükséges
        if (!isStreamConnected.value && !eventSource.value) {
          console.log('[Store] 📡 Sensors selected, initializing stream...')
          initializeStream()
        }

        // 3. Worker ID-k frissítése
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

  /**
   * Szenzor kiválasztása/deselect
   */
  const selectSensor = (uavId: number): void => {
    if (sensors.value[uavId]) {
      sensors.value[uavId].is_selected = !sensors.value[uavId].is_selected
      console.log(`[Store] Sensor ${uavId} ${sensors.value[uavId].is_selected ? 'selected' : 'deselected'}`)
    }
  }

  /**
   * Stream adat kezelése (workernek továbbítás)
   */
  const handleStreamData = (rawData: string): void => {
    console.log('[Store] 📥 handleStreamData called, data length:', rawData?.length)

    // Lazy initialization
    if (!isWorkerReady()) {
      console.warn('[Store] ⚠️ Worker not initialized when stream data arrived, initializing now...')
      initializeWorker()
    }

    console.log('[Store] 📤 Sending to worker...')
    sendDetection(rawData)
  }

  /**
   * Szenzorok lekérése API-ból
   */
  const fetchSensors = async (): Promise<void> => {
    isLoading.value = true
    errorMessage.value = ''

    try {
      const response = await fetch('http://localhost:5000/v1/uav')

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      // Transform data - megtartjuk a meglévő is_selected és detections értékeket
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
      console.error('[Store] Failed to fetch sensors:', error)
      errorMessage.value = 'Failed to load sensors'
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Szenzor eltávolítása
   */
  const removeSensor = (): void => {
    if (selectedSensor.value) {
      const uavId = selectedSensor.value.uav_id
      delete sensors.value[uavId]
      selectedSensor.value = null
      console.log(`[Store] Sensor ${uavId} removed`)
    }
  }

  /**
   * Mouse hover handler
   */
  const handleMouseOver = (sensor: Sensor): void => {
    selectedSensor.value = sensor
  }

  /**
   * Detekciók törlése
   */
  const clearAllDetections = (): void => {
    Object.values(sensors.value).forEach(sensor => {
      sensor.detections = []
    })
    clearDetections()
    console.log('[Store] All detections cleared')
  }

  /**
   * Debug reaktivitás
   */
  const debugReactivity = (): void => {
    console.log('=== SENSOR STORE DEBUG ===')
    console.log('Total sensors:', Object.keys(sensors.value).length)
    console.log('Selected sensors:', selectedSensors.value.length)
    console.log('Has selections:', hasSelectedSensors.value)
    console.log('Worker ready:', isWorkerReady())
    console.log('Stream connected:', isStreamConnected.value)
    console.log('Settings:', {
      batchInterval: batchInterval.value,
      detectionSize: detectionSize.value,
      streamUrl: streamUrl.value
    })

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

  // Cleanup on unmount
  onUnmounted(() => {
    console.log('[Store] 🧹 Cleaning up...')

    // Disconnect stream
    disconnectStream()

    // Cleanup worker
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
    isWorkerReady
  }
})