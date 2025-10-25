// sensor.js - Real-time optimalizált verzió
import { defineStore, storeToRefs } from 'pinia'
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, triggerRef, watch } from 'vue'
import axios from 'axios'
import { useConnectionStore } from '@/stores/connection'
import { Sensor } from '../types/sensor'
import DetectionWorker from '../workers/detectionWorker?worker'

export const useSensorStore = defineStore('sensor', () => {
  // ============================================================================
  // REAKTÍV ÁLLAPOTOK
  // ============================================================================

  const sensors = ref<{ [id: number]: Sensor }>({})
  const hoveredSensor = shallowRef(null)
  const selectedSensors = ref<number[]>([])
  const hasSelectedSensors = computed(() => selectedSensors.value.length > 0)
  const isLoading = ref<boolean>(false)
  const errorMessage = ref('')

  const connectionStore = useConnectionStore()
  const { ipPort, isConnected } = storeToRefs(connectionStore)

  const batchInterval = ref(0.01)
  const detectionSize = ref(50)
  const samplingRate = ref(0)

  // ============================================================================
  // STATISZTIKÁK
  // ============================================================================

  const stats = ref({
    totalReceived: 0,
    totalProcessed: 0,
    activeWorkers: 0
  })

  // ============================================================================
  // WORKER ÉS STREAM KEZELÉS
  // ============================================================================

  const detectionWorkers = shallowRef<Record<string, Worker>>({})
  let eventSource = null
  let cleanupFunctions = []
  let pendingUpdate = false

  // ============================================================================
  // CLEANUP HELPER
  // ============================================================================

  async function stopDetectionStream() {
    await Promise.all(cleanupFunctions.map(fn => {
      try {
        return fn()
      } catch (error) {
        console.error('Cleanup error:', error)
      }
    }))

    cleanupFunctions = []
    eventSource = null
  }

  // ============================================================================
  // WATCHES
  // ============================================================================

  watch(isConnected, async (newValue) => {
    if (newValue) {
      await fetchSensors()
    } else {
      await stopDetectionStream()
      terminateAllWorkers()
    }
  }, { immediate: true })

  watch(samplingRate, () => {
    updateAllWorkerSettings()
  }, { immediate: true })

  watch(batchInterval, async () => {
    if (eventSource) {
      await stopDetectionStream()
    }

    if (hasSelectedSensors.value) {
      await nextTick()
      await startDetectionStream()
    }
  })

  // ============================================================================
  // SENSOR CRUD MŰVELETEK
  // ============================================================================

  const handleMouseOver = (sensor) => {
    hoveredSensor.value = sensor
  }

  const getSensors = computed(() => sensors.value)

  async function fetchSensors() {
    if (!isConnected.value) return

    isLoading.value = true
    errorMessage.value = ''

    try {
      const url = `${ipPort.value}/v1/uav/`
      const response = await axios.get(url)

      if (!response?.data || response.status !== 200) {
        throw new Error(`API hiba: ${response.status}`)
      }

      const newSensors = {}
      const sensorArray = Array.isArray(response.data) ? response.data : response.data.sensors || []

      sensorArray.forEach((sensor: Sensor) => {
        const existingDetections = sensors.value[sensor.uav_id]?.detections || []
        const existingSelection = selectedSensors.value.includes(sensor.uav_id)

        newSensors[sensor.uav_id] = {
          ...sensor,
          is_selected: existingSelection,
          detections: existingDetections
        }
      })

      sensors.value = newSensors
      triggerRef(sensors)
    } catch (error) {
      errorMessage.value = error.message || 'Hiba történt a szenzorok lekérésekor'

      if (process.env.NODE_ENV === 'development') {
        sensors.value = {
          1: {
            uav_id: 1,
            uav_label: 'test001',
            uav_address: '10.1.1.113',
            active: true,
            is_selected: false,
            detections: []
          },
          2: {
            uav_id: 2,
            uav_label: 'test002',
            uav_address: '10.1.1.119',
            active: true,
            is_selected: false,
            detections: []
          }
        }
        triggerRef(sensors)
      }
    } finally {
      isLoading.value = false
    }
  }

  async function addSensor(sensor) {
    isLoading.value = true
    errorMessage.value = ''
    try {
      await axios.post(`${ipPort.value}/v1/uav`, {
        uav_label: sensor.uav_label,
        uav_address: sensor.uav_address,
        active: sensor.active
      }, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 5000
      })

      await fetchSensors()
    } catch (error) {
      errorMessage.value = 'Hiba történt a szenzor hozzáadásakor'
    } finally {
      isLoading.value = false
    }
  }

  async function removeSensor() {
    if (!hoveredSensor.value) return

    const id = hoveredSensor.value.uav_id
    isLoading.value = true
    errorMessage.value = ''

    try {
      if (detectionWorkers.value[id]) {
        await terminateWorker(id)
      }

      const updatedSensors = { ...sensors.value }
      delete updatedSensors[id]
      sensors.value = updatedSensors

      selectedSensors.value = selectedSensors.value.filter(sid => sid !== id)
      triggerRef(sensors)
      hoveredSensor.value = null

      axios.delete(`${ipPort.value}/v1/uav/${id}`, { timeout: 5000 })
        .catch(error => {
          console.error('Background delete error:', error)
          fetchSensors()
        })
    } catch (error) {
      errorMessage.value = 'Hiba történt a szenzor törlésekor'
      await fetchSensors()
    } finally {
      isLoading.value = false
    }
  }

  function toggleSensorSelection(sensorId: number) {
    const sensor = sensors.value[sensorId]
    if (!sensor) return

    sensor.is_selected = !sensor.is_selected

    if (sensor.is_selected) {
      if (!selectedSensors.value.includes(sensorId)) {
        selectedSensors.value = [...selectedSensors.value, sensorId]
      }
    } else {
      selectedSensors.value = selectedSensors.value.filter(id => id !== sensorId)
    }

    triggerRef(sensors)

    if (sensor.is_selected) {
      initWorkerForUav(sensorId)
    } else {
      terminateWorker(sensorId)
    }

    if (eventSource) {
      stopDetectionStream().then(() => {
        if (hasSelectedSensors.value) {
          startDetectionStream()
        }
      })
    }
  }

  async function selectSensor(sensor: Sensor) {
    if (!selectedSensors.value.includes(sensor.uav_id)) {
      selectedSensors.value = [...selectedSensors.value, sensor.uav_id]
    }

    if (sensors.value[sensor.uav_id]) {
      sensors.value[sensor.uav_id].is_selected = true
    }

    if (eventSource) {
      await stopDetectionStream()
    }

    for (const uavId of selectedSensors.value) {
      if (!detectionWorkers.value[uavId]) {
        await initWorkerForUav(uavId)
      }
    }

    await startDetectionStream()
  }

  // ============================================================================
  // WORKER KEZELÉS
  // ============================================================================

  async function initWorkerForUav(uavId: number) {
    if (!sensors.value[uavId]?.is_selected) return

    if (detectionWorkers.value[uavId]) {
      await terminateWorker(uavId)
    }

    const worker = new DetectionWorker()

    worker.onmessage = (e) => {
      const message = e.data
      const processTime = Date.now()

      switch (message.type) {
        case 'processedDetection': {
          const { detection, uavId } = message

          stats.value.totalReceived++
          stats.value.totalProcessed++

          // Real-time processing monitoring
          if (process.env.NODE_ENV === 'development') {
            const workerLatency = processTime - (message.timestamp || processTime)
            console.log(
              `[REAL-TIME] Detection processed | ` +
              `UAV: ${uavId} | ` +
              `Worker latency: ${workerLatency}ms | ` +
              `Total processed: ${stats.value.totalProcessed}`
            )
          }

          if (sensors.value[uavId]?.is_selected) {
            addDetectionToSensor(uavId, detection)
          }
          break
        }

        case 'statsUpdated':
          stats.value = {
            ...stats.value,
            ...message.stats,
            activeWorkers: Object.keys(detectionWorkers.value).length
          }
          break

        case 'workerStarted':
          updateWorkerSettings(uavId)
          break

        case 'error':
          console.error(`Worker error for UAV ${uavId}:`, message.message)
          errorMessage.value = `Worker error: ${message.message}`
          break
      }
    }

    worker.onerror = (error) => {
      console.error(`Worker error for UAV ${uavId}:`, error)
      terminateWorker(uavId)
    }

    const updatedWorkers = { ...detectionWorkers.value }
    updatedWorkers[uavId] = worker
    detectionWorkers.value = updatedWorkers
    stats.value.activeWorkers = Object.keys(updatedWorkers).length

    return worker
  }

  async function terminateWorker(uavId: number): Promise<void> {
    return new Promise<void>((resolve) => {
      const worker = detectionWorkers.value[uavId]
      if (!worker) {
        resolve()
        return
      }

      const timeout = setTimeout(() => {
        worker.terminate()
        resolve()
      }, 100)

      worker.postMessage({ type: 'terminate' })

      const cleanupHandler = (e: MessageEvent) => {
        if (e.data.type === 'terminated') {
          clearTimeout(timeout)
          worker.terminate()
          worker.removeEventListener('message', cleanupHandler)
          resolve()
        }
      }

      worker.addEventListener('message', cleanupHandler)
    }).then(() => {
      const updatedWorkers = { ...detectionWorkers.value }
      delete updatedWorkers[uavId]
      detectionWorkers.value = updatedWorkers
      stats.value.activeWorkers = Object.keys(updatedWorkers).length
    })
  }

  function terminateAllWorkers() {
    const promises = Object.keys(detectionWorkers.value).map(uavId =>
      terminateWorker(parseInt(uavId))
    )
    return Promise.all(promises)
  }

  function updateWorkerSettings(uavId) {
    const worker = detectionWorkers.value[uavId]
    if (!worker) return

    worker.postMessage({
      type: 'updateSettings',
      uavId,
      samplingRate: samplingRate.value
    })
  }

  function updateAllWorkerSettings() {
    Object.keys(detectionWorkers.value).forEach(uavId => {
      updateWorkerSettings(parseInt(uavId))
    })
  }

  // ============================================================================
  // STREAM KEZELÉS
  // ============================================================================

  async function startDetectionStream() {
    if (!hasSelectedSensors.value) {
      console.warn('Nincs kiválasztott szenzor, stream nem indul.')
      return
    }

    try {
      const url = `${ipPort.value}/v1/stream/comint_detection?interval=${batchInterval.value}&buffer_all_flag=false`
      eventSource = new EventSource(url, { withCredentials: true })

      cleanupFunctions.push(() => {
        if (eventSource) {
          eventSource.close()
          eventSource = null
        }
      })

      eventSource.onmessage = (event) => {
        if (!hasSelectedSensors.value || !event.data) return

        const receiveTime = Date.now()

        try {
          const parsed = JSON.parse(event.data)
          if (!Array.isArray(parsed)) return

          for (const item of parsed) {
            const measurement = item.Measurement
            if (!measurement) continue

            const backendUavId = item.id

            if (!selectedSensors.value.includes(backendUavId)) continue

            const measurementTime = new Date(measurement.time).getTime()
            const now = Date.now()

            // Real-time delay monitoring
            if (process.env.NODE_ENV === 'development') {
              console.log(
                `[REAL-TIME] UAV ${backendUavId} | ` +
                `Measurement delay: ${now - measurementTime}ms | ` +
                `Server delay: ${now - item.server_time * 1000}ms | ` +
                `Network delay: ${receiveTime - item.server_time * 1000}ms`
              )
            }

            const normalizedMeasurement = {
              ...measurement,
              headingData: measurement.headingData || measurement.heading_data
            }

            // Azonnal továbbítjuk a workernek
            const worker = detectionWorkers.value[backendUavId]
            if (worker) {
              const sendTime = Date.now()
              worker.postMessage({
                type: 'newDetection',
                measurement: normalizedMeasurement,
                uavId: backendUavId
              })

              if (process.env.NODE_ENV === 'development') {
                console.log(`[REAL-TIME] Worker send time: ${Date.now() - sendTime}ms`)
              }
            }
          }
        } catch (err) {
          console.error('Stream parsing error:', err)
        }
      }

      eventSource.onerror = async (err) => {
        console.error('Stream error:', err)
        errorMessage.value = 'Stream hiba'

        await stopDetectionStream()

        if (eventSource?.readyState === EventSource.CLOSED) {
          setTimeout(() => {
            if (hasSelectedSensors.value) {
              startDetectionStream()
            }
          }, 5000)
        }
      }
    } catch (error) {
      console.error('Failed to start detection stream:', error)
      errorMessage.value = 'Stream indítási hiba'
    }
  }

  // ============================================================================
  // DETEKCIÓ KEZELÉS
  // ============================================================================

  function addDetectionToSensor(uavId: number, detection: any) {
    const sensor = sensors.value[uavId]
    if (!sensor) return

    const addTime = Date.now()
    const maxSize = Math.abs(detectionSize.value)

    if (!sensor.detections) sensor.detections = []

    sensor.detections.push(detection)

    if (sensor.detections.length > maxSize) {
      sensor.detections = sensor.detections.slice(-maxSize)
    }

    // Real-time UI update monitoring
    if (process.env.NODE_ENV === 'development') {
      console.log(
        `[REAL-TIME] Detection added to sensor | ` +
        `UAV: ${uavId} | ` +
        `Total detections: ${sensor.detections.length} | ` +
        `Add time: ${Date.now() - addTime}ms`
      )
    }

    // requestAnimationFrame debounce
    if (!pendingUpdate) {
      pendingUpdate = true
      requestAnimationFrame(() => {
        const triggerTime = Date.now()
        triggerRef(sensors)

        if (process.env.NODE_ENV === 'development') {
          console.log(`[REAL-TIME] UI trigger time: ${Date.now() - triggerTime}ms`)
        }

        pendingUpdate = false
      })
    }
  }

  async function clearDetections() {
    Object.values(sensors.value).forEach(sensor => {
      sensor.detections = []
    })

    triggerRef(sensors)

    Object.values(detectionWorkers.value).forEach(worker => {
      if (worker?.postMessage) {
        worker.postMessage({ type: 'clearDetections' })
      }
    })

    stats.value = {
      totalReceived: 0,
      totalProcessed: 0,
      activeWorkers: Object.keys(detectionWorkers.value).length
    }
  }

  // ============================================================================
  // DEBUG FUNKCIÓK
  // ============================================================================

  function debugReactivity() {
    console.log('=== Sensor Store Debug ===')
    console.log('Total sensors:', Object.keys(sensors.value).length)
    console.log('Selected sensor IDs:', Array.from(selectedSensors.value))
    console.log('Active workers:', Object.keys(detectionWorkers.value).length)
    console.log('Stats:', stats.value)

    Object.entries(sensors.value).forEach(([id, sensor]) => {
      console.log(`Sensor ${id}:`, {
        label: sensor.uav_label,
        selected: sensor.is_selected,
        detectionsCount: sensor.detections?.length || 0,
        active: sensor.active
      })
    })
  }

  // ============================================================================
  // HELPER FÜGGVÉNYEK
  // ============================================================================

  function getSensorsList() {
    return Object.values(sensors.value)
  }

  // ============================================================================
  // LIFECYCLE
  // ============================================================================

  onUnmounted(async () => {
    await stopDetectionStream()
    await terminateAllWorkers()
    selectedSensors.value = []
  })

  onMounted(() => {
    if (isConnected.value) {
      fetchSensors()
    }
  })

  // ============================================================================
  // RETURN
  // ============================================================================

  return {
    sensors,
    selectedSensors,
    hoveredSensor,
    hasSelectedSensors,
    isLoading,
    errorMessage,
    detectionSize,
    stats,
    samplingRate,
    batchInterval,
    getSensors,
    getSensorsList,
    fetchSensors,
    addSensor,
    removeSensor,
    selectSensor,
    handleMouseOver,
    toggleSensorSelection,
    clearDetections,
    startDetectionStream,
    debugReactivity,
    terminateAllWorkers,
    updateAllWorkerSettings
  }
})