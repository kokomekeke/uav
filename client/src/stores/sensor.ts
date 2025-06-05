// sensor.js - Frissített verzió, JSON parsing workerben történik
import { defineStore, storeToRefs } from 'pinia'
import { computed, ref, watch, shallowRef, onUnmounted, onMounted, triggerRef } from 'vue'
import axios from 'axios'
import { useConnectionStore } from '@/stores/connection'
import { Sensor } from '../types/sensor'
import { useEventSource } from '@vueuse/core'
import DetectionWorker from '../workers/detectionWorker?worker'

// Memória-hatékony interface a detekciókhoz
// interface Comint {
//   coordinate: [number, number];
//   azimuth: number;
//   uavId: number;
//   roi_id: number | null;
//   timestamp: number;
// }
export const useSensorStore = defineStore('sensor', () => {
  // Reaktív állapotok
  const sensors = ref<{ [id: number]: Sensor }>({})
  const selectedSensor = shallowRef(null)
  const isLoading = ref<boolean>(false)
  const errorMessage = ref('')
  const connectionStore = useConnectionStore()
  const { ipPort, isConnected } = storeToRefs(connectionStore)
  const batchInterval = ref(0.001) // Minimálisra csökkentve (1ms)
  let eventSourceStop = null

  // Detekciók tárolása
  const detectionSize = ref(50) // Növelve a real-time élményért

  // Statisztikák
  const stats = ref({
    totalReceived: 0,
    totalProcessed: 0,
    lastProcessingTime: 0,
    activeWorkers: 0
  })

  // Worker referenciák tárolása UAV ID-nként
  const detectionWorkers = shallowRef<Record<string, Worker>>({})

  // Mintavételezési ráta - real-time optimalizálva
  const samplingRate = ref(1) // 1ms = gyakorlatilag minden adat

  // Optimalizált watch-ok - debounce nélkül
  watch(isConnected, (newValue) => {
    if (newValue) {
      fetchSensors()
    } else {
      terminateAllWorkers()
      if (eventSourceStop) {
        eventSourceStop()
        eventSourceStop = null
      }
    }
  }, { immediate: true })

  watch(samplingRate, () => {
    updateAllWorkerSettings()
  }, { immediate: true })

  // Batch interval változás - azonnali újraindítás
  watch(batchInterval, async (newVal) => {
    if (eventSourceStop) {
      eventSourceStop()
      eventSourceStop = null
    }

    if (selectedSensor.value) {
      await nextTick() // Egy frame várakozás
      await startDetectionStream()
    }
  }, { immediate: true })

  const handleMouseOver = (sensor) => {
    selectedSensor.value = sensor
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
        const existingSelection = sensors.value[sensor.uav_id]?.is_selected || false

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
        const fallbackSensors = {
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
        sensors.value = fallbackSensors
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
        timeout: 5000 // Timeout csökkentése
      })

      await fetchSensors()
    } catch (error) {
      errorMessage.value = 'Hiba történt a szenzor hozzáadásakor'
    } finally {
      isLoading.value = false
    }
  }

  async function removeSensor() {
    if (!selectedSensor.value) return

    const id = selectedSensor.value.uav_id
    isLoading.value = true
    errorMessage.value = ''

    try {
      // Worker azonnali leállítása
      if (detectionWorkers.value[id]) {
        detectionWorkers.value[id].terminate()
        const updatedWorkers = { ...detectionWorkers.value }
        delete updatedWorkers[id]
        detectionWorkers.value = updatedWorkers
        stats.value.activeWorkers = Object.keys(updatedWorkers).length
      }

      // Szenzor azonnali eltávolítása
      const updatedSensors = { ...sensors.value }
      delete updatedSensors[id]
      sensors.value = updatedSensors
      triggerRef(sensors)
      selectedSensor.value = null

      // API hívás háttérben
      axios.delete(`${ipPort.value}/v1/uav/${id}`, { timeout: 5000 })
        .catch(error => {
          console.error('Background delete error:', error)
          fetchSensors() // Újra szinkronizálás hiba esetén
        })

    } catch (error) {
      errorMessage.value = 'Hiba történt a szenzor törlésekor'
      await fetchSensors()
    } finally {
      isLoading.value = false
    }
  }

  async function selectSensor(sensor: Sensor) {
    selectedSensor.value = sensor

    // Előző stream azonnali leállítása
    if (eventSourceStop) {
      eventSourceStop()
      eventSourceStop = null
    }

    // Worker párhuzamos inicializálása
    initWorkerForUav(sensor.uav_id)

    // Stream indítása párhuzamosan
    await startDetectionStream()
  }

  function initWorkerForUav(uavId) {
    if (!sensors.value[uavId]?.is_selected) return

    // Régi worker azonnali leállítása
    if (detectionWorkers.value[uavId]) {
      detectionWorkers.value[uavId].terminate()
    }

    const worker = new DetectionWorker()

    // Optimalizált message handler
    worker.onmessage = (e) => {
      const message = e.data

      switch (message.type) {
        case 'processedDetections': {
          const { detectionsByUavId, stats: workerStats } = message

          // Statisztikák batch frissítése
          stats.value = {
            totalReceived: stats.value.totalReceived + (workerStats.totalReceived || 0),
            totalProcessed: stats.value.totalProcessed + (workerStats.totalProcessed || 0),
            lastProcessingTime: Math.max(stats.value.lastProcessingTime, workerStats.lastProcessingTime || 0),
            activeWorkers: Object.keys(detectionWorkers.value).length
          }

          // Detekciók azonnali hozzáadása
          if (detectionsByUavId[uavId]?.length > 0) {
            addDetectionsToSensor(uavId, detectionsByUavId[uavId])
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
          // Beállítások azonnali küldése
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
      worker.terminate()

      const updatedWorkers = { ...detectionWorkers.value }
      delete updatedWorkers[uavId]
      detectionWorkers.value = updatedWorkers
      stats.value.activeWorkers = Object.keys(updatedWorkers).length
    }

    // Worker azonnali regisztrálása
    const updatedWorkers = { ...detectionWorkers.value }
    updatedWorkers[uavId] = worker
    detectionWorkers.value = updatedWorkers
    stats.value.activeWorkers = Object.keys(updatedWorkers).length

    return worker
  }

  async function startDetectionStream() {
    if (!selectedSensor.value) return

    try {
      const { data, error, close } = useEventSource(
        `${ipPort.value}/v1/stream/comint_detection?interval=${batchInterval.value}`,
        [],
        {
          withCredentials: true,
          autoReconnect: {
            retries: 5,
            delay: 50, // Gyorsabb újracsatlakozás
            onFailed() {
              errorMessage.value = 'Kapcsolat megszakadt'
            }
          }
        }
      )

      eventSourceStop = close

      // Optimalizált data watcher - közvetlen továbbítás
      watch(data, (rawJsonString) => {
        if (rawJsonString) {
          routeRawDetectionToWorker(rawJsonString)
        }
      }, { immediate: true })

      watch(error, (err) => {
        if (err) {
          console.error('Stream error:', err)
          errorMessage.value = 'Stream hiba'
          close()
        }
      }, { immediate: true })

    } catch (error) {
      console.error('Failed to start detection stream:', error)
      errorMessage.value = 'Stream indítási hiba'
    }
  }

  // Optimalizált detekció hozzáadás - minimális objektum manipuláció
  function addDetectionsToSensor(uavId: number, newDetections: any[]) {
    const sensor = sensors.value[uavId]
    if (!sensor) return

    const maxSize = Math.abs(detectionSize.value)
    const existingDetections = sensor.detections || []

    // Egyszerű array műveletek
    const combinedDetections = [...existingDetections, ...newDetections]
    if (combinedDetections.length > maxSize) {
      combinedDetections.splice(0, combinedDetections.length - maxSize)
    }

    // Közvetlen mutáció a gyorsaság érdekében
    sensor.detections = combinedDetections

    // Reaktivitás trigger
    triggerRef(sensors)
  }

  function updateSensorReactive(uavId: number, updates: Partial<Sensor>) {
    const sensor = sensors.value[uavId]
    if (!sensor) return

    // Közvetlen mutáció
    Object.assign(sensor, updates)
    triggerRef(sensors)
  }

  function updateWorkerSettings(uavId) {
    const worker = detectionWorkers.value[uavId]
    if (!worker) return

    worker.postMessage({
      type: 'updateSettings',
      uavId,
      samplingRate: samplingRate.value,
      processThrottle: 10 // Minimális throttle
    })
  }

  function updateAllWorkerSettings() {
    Object.keys(detectionWorkers.value).forEach(uavId => {
      updateWorkerSettings(parseInt(uavId))
    })
  }

  function getSensorsList() {
    return Object.values(sensors.value)
  }

  function toggleSensorSelection(sensorId: number) {
    const sensor = sensors.value[sensorId]
    if (!sensor) return

    sensor.is_selected = !sensor.is_selected
    triggerRef(sensors)
  }

  // Optimalizált routing - minimális regex használat
  function routeRawDetectionToWorker(rawJsonString) {
    try {
      // Gyors UAV ID kinyerés
      const uavIdMatch = rawJsonString.match(/"uav_id"\s*:\s*(\d+)/)
      if (!uavIdMatch) return

      const uavId = parseInt(uavIdMatch[1])

      // Worker létrehozása ha nem létezik
      if (!detectionWorkers.value[uavId]) {
        initWorkerForUav(uavId)
      }

      // Közvetlen továbbítás
      const worker = detectionWorkers.value[uavId]
      if (worker) {
        worker.postMessage({
          type: 'newDetection',
          value: rawJsonString
        })

        // Statisztikák gyors frissítése
        stats.value.totalReceived++
      }
    } catch (error) {
      console.error('Routing error:', error)
    }
  }

  function clearDetections() {
    // Minden szenzor detekciójának azonnali törlése
    Object.values(sensors.value).forEach(sensor => {
      sensor.detections = []
    })

    triggerRef(sensors)

    // Worker értesítések párhuzamosan
    Object.values(detectionWorkers.value).forEach(worker => {
      if (worker?.postMessage) {
        worker.postMessage({ type: 'clearDetections' })
      }
    })

    // Statisztikák nullázása
    stats.value = {
      totalReceived: 0,
      totalProcessed: 0,
      lastProcessingTime: 0,
      activeWorkers: Object.keys(detectionWorkers.value).length
    }
  }

  function terminateAllWorkers() {
    Object.entries(detectionWorkers.value).forEach(([uavId, worker]) => {
      if (worker?.terminate) {
        worker.terminate()
      }
    })

    detectionWorkers.value = {}
    stats.value.activeWorkers = 0
  }

  function debugReactivity() {
    console.log('=== Sensor Store Debug ===')
    console.log('Total sensors:', Object.keys(sensors.value).length)
    console.log('Selected sensor:', selectedSensor.value?.uav_id || 'none')
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

  // Cleanup
  onUnmounted(() => {
    terminateAllWorkers()
    if (eventSourceStop) {
      eventSourceStop()
      eventSourceStop = null
    }
  })

  // Inicializálás
  onMounted(() => {
    if (isConnected.value) {
      fetchSensors()
    }
  })

  return {
    // Állapotok
    sensors,
    selectedSensor,
    isLoading,
    errorMessage,
    detectionSize,
    stats,
    samplingRate,
    batchInterval,

    // Computed
    getSensors,

    // Metódusok
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