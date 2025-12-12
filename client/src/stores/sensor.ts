// stores/sensor.ts - OPTIMALIZÁLT VERZIÓ
import { defineStore, storeToRefs } from 'pinia'
import { ref, computed, watch, onUnmounted, shallowRef } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { useDetectionWorker } from '@/composables/useDetectionWorker'
import type { Sensor } from '@/types/sensor'
import type { RealtimeConfig } from '@/types/config'
import { useLogStore } from '@/stores/log'
import { useConnectionStore } from '@/stores/connection' // ✅ ÚJ

export const useSensorStore = defineStore('sensor', () => {
  // ============================================================================
  // CONNECTION STORE INTEGRATION - ✅ ÚJ
  // ============================================================================

  const connectionStore = useConnectionStore()
  const { ipPort, isConnected } = storeToRefs(connectionStore)

  // ✅ Computed URL a connection store-ból
  const urlBase = computed(() => {
    const base = ipPort.value.endsWith('/') ? ipPort.value : `${ipPort.value}/`
    return `${base}v1/`
  })

  const streamUrl = computed(() => {
    return `${urlBase.value}stream/comint_detection`
  })

  // ============================================================================
  // STATE - ✅ SHALLOW REFS FOR PERFORMANCE
  // ============================================================================

  const sensors = shallowRef<Record<number, Sensor>>({})
  const selectedSensor = ref<Sensor | null>(null)
  const selectedSensorIds = shallowRef<number[]>([])
  const isLoading = ref(false)
  const errorMessage = ref('')

  const batchInterval = ref(0.05)
  const detectionSize = ref(100)

  const eventSource = ref<EventSource | null>(null)
  const isStreamConnected = ref(false)

  const realtimeConfig = ref<RealtimeConfig>({
    maxLatencyMs: 1000,
    detectionTTL: 10000,
    enableStrictRealtime: true,
    circularBufferSize: 50,
    interval: 100
  })

  const logStore = useLogStore()

  // ============================================================================
  // DETECTION CLEANUP
  // ============================================================================

  const { pause: pauseCleanup, resume: resumeCleanup } = useIntervalFn(() => {
    const now = performance.now()
    const ttl = realtimeConfig.value.detectionTTL

    if (ttl <= 0) return

    const newSensors: Record<number, Sensor> = {}

    Object.entries(sensors.value).forEach(([id, sensor]) => {
      const filtered = sensor.detections.filter(d => (now - (d.timestamp || 0)) <= ttl)

      if (filtered.length !== sensor.detections.length) {
        newSensors[+id] = {
          ...sensor,
          detections: filtered
        }
      } else {
        newSensors[+id] = sensor
      }
    })

    sensors.value = newSensors
  }, () => realtimeConfig.value.interval, { immediate: false })

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

  const addDetectionToSensor = (uavId: number, detection: any): void => {
    const sensor = sensors.value[uavId]
    if (!sensor) return

    const now = performance.now()
    const bufferSize = realtimeConfig.value.circularBufferSize
    const ttl = realtimeConfig.value.detectionTTL

    let detections = sensor.detections

    if (ttl > 0 && detections.length > 0) {
      const oldestTimestamp = detections[0]?.timestamp || 0
      if (now - oldestTimestamp > ttl) {
        detections = detections.filter(d => (now - (d.timestamp || 0)) <= ttl)
      }
    }

    if (detections.length < bufferSize) {
      detections = [...detections, detection]
    } else {
      detections = [...detections.slice(1), detection]
    }

    sensors.value = {
      ...sensors.value,
      [uavId]: { ...sensor, detections }
    }
  }

  const initializeWorker = (): void => {
    initWorker()

    const cleanupProcessed = onWorkerMessage('processedDetection', (data: any) => {
      const { detection, uavId } = data
      addDetectionToSensor(uavId, detection)
    })

    const cleanupMeasurement = onWorkerMessage('processedMeasurement', (data: any) => {
      const { measurement, uavId, timestamp } = data

      const measurementItem = {
        Measurement: measurement,
        timestamp: timestamp || Date.now()
      }

      addDetectionToSensor(uavId, measurementItem)
    })

    const cleanupTelemetry = onWorkerMessage('processedTelemetry', (data: any) => {
      const { telemetry, uavId } = data
    })

    workerMessageCleanups.push(cleanupProcessed, cleanupMeasurement, cleanupTelemetry)
    resumeCleanup()
  }

  // ============================================================================
  // SSE STREAM
  // ============================================================================

  const initializeStream = (): void => {
    // ✅ Csak connected állapotban
    if (!isConnected.value) {
      console.warn('[SensorStore] Cannot initialize stream - not connected')
      return
    }

    if (eventSource.value) return

    eventSource.value = new EventSource(streamUrl.value)

    eventSource.value.onopen = () => {
      isStreamConnected.value = true
      console.log('[SensorStore] ✅ Stream connected')
    }

    eventSource.value.onmessage = (event: MessageEvent) => {
      if (!event.data) return
      if (!isWorkerReady()) initializeWorker()
      const data = event.data
      logStore.logs.push(data)
      handleStreamData(data)
    }

    eventSource.value.onerror = () => {
      isStreamConnected.value = false
      if (eventSource.value?.readyState === EventSource.CLOSED) {
        setTimeout(() => {
          if (!isStreamConnected.value && isConnected.value) {
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
    const selectedIds = newSelected.map(s => s.uav_id)
    selectedSensorIds.value = selectedIds

    if (selectedIds.length > 0) {
      if (!isWorkerReady()) initializeWorker()
      if (!isStreamConnected.value && !eventSource.value) initializeStream()
      updateSelectedUavIds(selectedIds)
    } else {
      updateSelectedUavIds([])
    }
  }, { immediate: true, deep: false })

  // ✅ ÚJ: Connection state figyelés
  watch(isConnected, (connected) => {
    if (!connected) {
      // Ha megszakadt a kapcsolat, töröljük a sensorokat
      console.log('[SensorStore] Connection lost - clearing sensors')
      disconnectStream()
      sensors.value = {}
      selectedSensorIds.value = []
    }
  })

  // ============================================================================
  // ACTIONS
  // ============================================================================

  const selectSensor = (uavId: number): void => {
    const sensor = sensors.value[uavId]
    if (!sensor) return

    sensors.value = {
      ...sensors.value,
      [uavId]: {
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
    // ✅ Kapcsolat ellenőrzés
    if (!isConnected.value) {
      errorMessage.value = 'Not connected to server'
      console.warn('[SensorStore] Cannot fetch sensors - not connected')
      return
    }

    isLoading.value = true
    errorMessage.value = ''

    try {
      const url = `${urlBase.value}uav`
      console.log(`[SensorStore] Fetching sensors from: ${url}`)

      const response = await fetch(url)
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
      console.log(`[SensorStore] ✅ Loaded ${Object.keys(sensorsMap).length} sensors`)
    } catch (error) {
      errorMessage.value = 'Failed to load sensors'
      console.error('[SensorStore] Fetch error:', error)
    } finally {
      isLoading.value = false
    }
  }

  const removeSensor = async (uavId: number): Promise<void> => {
    // ✅ Kapcsolat ellenőrzés
    if (!isConnected.value) {
      errorMessage.value = 'Not connected to server'
      throw new Error('Not connected to server')
    }

    isLoading.value = true
    errorMessage.value = ''

    try {
      const url = `${urlBase.value}uav/${uavId}`
      console.log(`[SensorStore] Deleting sensor from: ${url}`)

      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }

      const { [uavId]: removed, ...rest } = sensors.value
      sensors.value = rest

      if (selectedSensor.value?.uav_id === uavId) {
        selectedSensor.value = null
      }

      console.log(`[SensorStore] ✅ Sensor ${uavId} deleted successfully`)
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : 'Failed to delete sensor'
      console.error('[SensorStore] Delete error:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  const setCurrentSensor = (sensor: Sensor): void => {
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
    console.log('Connected:', isConnected.value)
    console.log('Base URL:', urlBase.value)
    console.log('Sensors:', Object.keys(sensors.value).length)
    console.log('Selected:', selectedSensors.value.length)
    console.log('Worker ready:', isWorkerReady())
    console.log('Stream connected:', isStreamConnected.value)
  }

  const cleanup = (): void => {
    pauseCleanup()
    disconnectStream()
    workerMessageCleanups.forEach(cleanup => cleanup())
    terminateWorker()

    sensors.value = {}
    selectedSensorIds.value = []
    isStreamConnected.value = false
  }

  // ============================================================================
  // LIFECYCLE
  // ============================================================================

  onUnmounted(() => {
    cleanup()
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
    streamUrl: computed(() => streamUrl.value), // ✅ Computed
    urlBase: computed(() => urlBase.value), // ✅ Computed
    realtimeConfig,

    // Computed
    selectedSensors,
    hasSelectedSensors,
    selectedSensorIds,
    isConnected, // ✅ ÚJ - connection state

    // Actions
    selectSensor,
    fetchSensors,
    removeSensor,
    setCurrentSensor,
    clearDetections: clearAllDetections,
    addDetectionToSensor,

    // Worker
    initializeWorker,
    isWorkerReady,
    handleStreamData,

    // Stream
    initializeStream,
    disconnectStream,

    // Config
    updateRealtimeConfig,

    // Cleanup
    cleanup,

    // Debug
    debugReactivity
  }
})