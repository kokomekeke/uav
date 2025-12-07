// stores/sensor.ts - OPTIMALIZÁLT VERZIÓ
import { defineStore, storeToRefs } from 'pinia'
import { ref, computed, watch, onUnmounted, shallowRef } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { useDetectionWorker } from '@/composables/useDetectionWorker'
import type { Sensor } from '@/types/sensor'
import type { RealtimeConfig } from '@/types/config'
import { useLogStore } from '@/stores/log'

export const useSensorStore = defineStore('sensor', () => {
  // ============================================================================
  // STATE - ✅ SHALLOW REFS FOR PERFORMANCE
  // ============================================================================

  const sensors = shallowRef<Record<number, Sensor>>({})
  const selectedSensor = ref<Sensor | null>(null)
  const selectedSensorIds = shallowRef<number[]>([]) // ✅ Already shallow
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

  const logStore = useLogStore()
  const {
    logs
  } = storeToRefs(logStore)

  // ============================================================================
  // DETECTION CLEANUP - VUEUSE - ✅ OPTIMALIZÁLT INTERVAL (150ms)
  // ============================================================================

  const { pause: pauseCleanup, resume: resumeCleanup } = useIntervalFn(() => {
    const now = performance.now()
    const ttl = realtimeConfig.value.detectionTTL

    if (ttl <= 0) return

    // ✅ MUTATION helyett újraépítés (shallow ref miatt nincs nagy overhead)
    const newSensors: Record<number, Sensor> = {}

    Object.entries(sensors.value).forEach(([id, sensor]) => {
      // ✅ Filter csak ha van lejárt detection
      const filtered = sensor.detections.filter(d => (now - (d.timestamp || 0)) <= ttl)

      // ✅ Csak akkor hozunk létre új objektumot, ha változott
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
  // WORKER SETUP - REFACTORED
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

  // ✅ OPTIMALIZÁLT: CIRCULAR BUFFER IMPLEMENTATION
  const addDetectionToSensor = (uavId: number, detection: any): void => {
    const sensor = sensors.value[uavId]
    if (!sensor) return

    const now = performance.now()
    const bufferSize = realtimeConfig.value.circularBufferSize
    const ttl = realtimeConfig.value.detectionTTL

    // ✅ Circular buffer logika
    let detections = sensor.detections

    // TTL cleanup csak akkor, ha szükséges (lazy)
    if (ttl > 0 && detections.length > 0) {
      const oldestTimestamp = detections[0]?.timestamp || 0
      if (now - oldestTimestamp > ttl) {
        // ✅ Csak akkor filterelünk, ha az első elem már lejárt
        detections = detections.filter(d => (now - (d.timestamp || 0)) <= ttl)
      }
    }

    // ✅ Új detection hozzáadása
    if (detections.length < bufferSize) {
      // Van hely, egyszerű push
      detections = [...detections, detection]
    } else {
      // Buffer tele, legrégebbi eldobása (shift + push optimalizáció)
      detections = [...detections.slice(1), detection]
    }

    // ✅ Csak az érintett sensor módosítása, ne full spread
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

    workerMessageCleanups.push(cleanupProcessed)
    resumeCleanup()
  }

  // ============================================================================
  // SSE STREAM
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
      const data = event.data
      logStore.logs.push(data)
      handleStreamData(data)
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
  // WATCH - ✅ OPTIMALIZÁLT: deep: false!
  // ============================================================================

  watch(selectedSensors, (newSelected) => {
    const selectedIds = newSelected.map(s => s.uav_id)
    selectedSensorIds.value = selectedIds

    if (selectedIds.length > 0) {
      if (!isWorkerReady()) initializeWorker()
      if (!isStreamConnected.value && !eventSource.value) initializeStream()
      updateSelectedUavIds(selectedIds)
    }
  }, { immediate: true, deep: false }) // ✅ DEEP FALSE!

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
    if (!selectedSensor.value) return

    const uavId = selectedSensor.value.uav_id
    const { [uavId]: removed, ...rest } = sensors.value

    sensors.value = rest
    selectedSensor.value = null
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
    streamUrl,
    realtimeConfig,

    // Computed
    selectedSensors,
    hasSelectedSensors,
    selectedSensorIds,

    // Actions
    selectSensor,
    fetchSensors,
    removeSensor,
    handleMouseOver,
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
