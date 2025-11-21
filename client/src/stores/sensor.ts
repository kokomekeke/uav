// stores/sensor.ts - OPTIMALIZÁLT VERZIÓ
import { defineStore } from 'pinia'
import { ref, computed, watch, onUnmounted, shallowRef } from 'vue'
import { useDetectionWorker } from '@/composables/useDetectionWorker'
import type { Sensor } from '@/types/sensor'
import type { RealtimeConfig } from '@/types/config'
import { data } from 'autoprefixer'

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

  // Cleanup intervals
  let cleanupIntervalId: number | null = null

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
      updateDetections(data)
    })

    workerMessageCleanups.push(cleanupProcessed)
    startPeriodicCleanup()
  }

  const updateDetections = (data) => {
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
          ...sensors.value[uavId],
          detections
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
    // console.log('GeoJSON enabled:', isGeoJsonEnabled.value)
    // console.log('GeoJSON points:', geoJsonData.value.length)
    // console.log('HeatMap points:', heatMapPoints.value.length)
    // console.log('Seen IDs cache:', seenIds.size)
  }

  // ============================================================================
  // LIFECYCLE
  // ============================================================================

  onUnmounted(() => {
    stopPeriodicCleanup()
    // stopGeoJsonFetch()
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
    selectedSensorIds
  }
})
