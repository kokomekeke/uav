// sensor.js - Frissített verzió, JSON parsing workerben történik
import { defineStore, storeToRefs } from 'pinia'
import { computed, ref, watch, shallowRef, onUnmounted, onMounted, triggerRef, nextTick } from 'vue'
import axios from 'axios'
import { useConnectionStore } from '@/stores/connection'
import { Sensor } from '../types/sensor'
import { useEventSource } from '@vueuse/core'
import DetectionWorker from '../workers/detectionWorker?worker'

// Memória-hatékony interface a detekciókhoz
interface Comint {
  coordinate: [number, number];
  azimuth: number;
  uavId: number;
  roi_id: number | null;
  timestamp: number;
}

export const useSensorStore = defineStore('sensor', () => {
  // Reaktív állapotok
  const sensors = ref<{ [id: number]: Sensor }>({})
  const selectedSensor = shallowRef(null)
  const isLoading = ref<boolean>(false)
  const errorMessage = ref('')
  const connectionStore = useConnectionStore()
  const { ipPort, isConnected } = storeToRefs(connectionStore)
  const batchInterval = ref(0.1)
  let eventSourceStop = null

  // Detekciók tárolása
  // const comintDetections = shallowRef<Comint[]>([])
  const detectionSize = ref(5)

  // Statisztikák
  const stats = ref({
    totalReceived: 0,
    totalProcessed: 0,
    lastProcessingTime: 0,
    activeWorkers: 0
  })

  // Worker referenciák tárolása UAV ID-nként
  const detectionWorkers = shallowRef({})

  // Mintavételezési ráta
  const samplingRate = ref(20)

  // Reaktivitás segédfüggvények
  function updateSensorReactive (uavId: number, updates: Partial<Sensor>) {
    // Teljes sensors objektum újralétrehozása a reaktivitás biztosítására
    const newSensors = { ...sensors.value }

    if (newSensors[uavId]) {
      newSensors[uavId] = {
        ...newSensors[uavId],
        ...updates
      }

      sensors.value = newSensors
      triggerRef(sensors)

      console.log(`Sensor ${uavId} updated reactively:`, updates)
    }
  }

  function addDetectionsToSensor (uavId: number, newDetections: any[]) {
    const newSensors = { ...sensors.value }
    const maxSize = Math.abs(detectionSize.value)

    if (newSensors[uavId]) {
      // Új detekciók array létrehozása
      const existingDetections = [...(newSensors[uavId].detections || [])]
      const combinedDetections = [...existingDetections, ...newDetections]
        .slice(-maxSize)

      // Teljes szenzor objektum újralétrehozása
      newSensors[uavId] = {
        ...newSensors[uavId],
        detections: combinedDetections
      }

      sensors.value = newSensors
      triggerRef(sensors)

      console.log(`Added ${newDetections.length} detections to sensor ${uavId}, total: ${combinedDetections.length}`)
    }
  }

  // Worker inicializálása egy adott UAV-hoz
  function initWorkerForUav (uavId) {
    console.log(`Initializing worker for UAV ${uavId}`)

    // Ha már létezik worker ehhez az UAV-hoz, leállítjuk
    if (detectionWorkers.value[uavId]) {
      detectionWorkers.value[uavId].terminate()
    }

    // Új worker létrehozása az UAV-hoz
    const worker = new DetectionWorker()

    worker.onmessage = (e) => {
      const message = e.data

      switch (message.type) {
        case 'processedDetections': {
          const { detectionsByUavId, stats: workerStats } = message

          // Frissítjük a statisztikákat
          stats.value = {
            totalReceived: stats.value.totalReceived + (workerStats.totalReceived || 0),
            totalProcessed: stats.value.totalProcessed + (workerStats.totalProcessed || 0),
            lastProcessingTime: Math.max(stats.value.lastProcessingTime, workerStats.lastProcessingTime || 0),
            activeWorkers: Object.keys(detectionWorkers.value).length
          }

          // Detekciók hozzáadása reaktív módon
          if (detectionsByUavId[uavId] && detectionsByUavId[uavId].length > 0) {
            addDetectionsToSensor(uavId, detectionsByUavId[uavId])
          }
          break
        }

        case 'statsUpdated':
          // Statisztikák frissítése
          stats.value = {
            ...stats.value,
            ...message.stats,
            activeWorkers: Object.keys(detectionWorkers.value).length
          }
          break

        case 'uavIdAssigned':
          console.log(`Worker auto-assigned to UAV ${message.uavId}`)
          break

        case 'settingsUpdated':
          console.log(`Worker settings updated for UAV ${uavId}:`, message.settings)
          break

        case 'error':
          console.error(`Worker error for UAV ${uavId}:`, message.message)
          errorMessage.value = `Worker error for UAV ${uavId}: ${message.message}`
          break

        case 'workerStarted':
          console.log(`Detection worker for UAV ${uavId} started successfully at ${new Date(message.timestamp)}`)
          // Beállítások küldése a workernek
          updateWorkerSettings(uavId)
          break
      }
    }

    // Worker hibaesemények kezelése
    worker.onerror = (error) => {
      console.error(`Worker error for UAV ${uavId}:`, error)
      errorMessage.value = `Worker error for UAV ${uavId}: ${error.message}`
      worker.terminate()

      // Eltávolítjuk a hibás workert reaktív módon
      const updatedWorkers = { ...detectionWorkers.value }
      delete updatedWorkers[uavId]
      detectionWorkers.value = updatedWorkers

      // Statisztikák frissítése
      stats.value = {
        ...stats.value,
        activeWorkers: Object.keys(updatedWorkers).length
      }
    }

    // Frissítjük a workerek listáját reaktív módon
    const updatedWorkers = { ...detectionWorkers.value }
    updatedWorkers[uavId] = worker
    detectionWorkers.value = updatedWorkers

    // Statisztikák frissítése
    stats.value = {
      ...stats.value,
      activeWorkers: Object.keys(updatedWorkers).length
    }

    return worker
  }

  // Worker beállítások frissítése egy adott UAV-hoz
  function updateWorkerSettings (uavId) {
    const worker = detectionWorkers.value[uavId]
    if (!worker) return

    worker.postMessage({
      type: 'updateSettings',
      uavId,
      samplingRate: samplingRate.value,
      processThrottle: 100
    })

    console.log(`Updated worker settings for UAV ${uavId}`)
  }

  // Minden worker beállításának frissítése
  function updateAllWorkerSettings () {
    Object.keys(detectionWorkers.value).forEach(uavId => {
      updateWorkerSettings(parseInt(uavId))
    })
  }

  // Figyelje a samplingRate változásait és frissítse a workereket
  watch(samplingRate, () => {
    console.log('Sampling rate changed:', samplingRate.value)
    updateAllWorkerSettings()
  })

  // Mouse over handler
  const handleMouseOver = (sensor) => {
    selectedSensor.value = sensor
  }

  // Szenzorok lekérése az API-ból
  async function fetchSensors () {
    if (!isConnected.value) {
      console.log('Not connected, skipping sensor fetch')
      return
    }

    isLoading.value = true
    errorMessage.value = ''

    try {
      const url = `${ipPort.value}/v1/uav/`
      console.log('Fetching sensors from:', url)
      const response = await axios.get(url)

      if (!response || !response.data) {
        throw new Error('Üres API válasz')
      }

      if (response.status !== 200) {
        throw new Error(`API hiba: ${response.status} - ${response.statusText}`)
      }

      // Új szenzorok objektum létrehozása
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

      // Reaktív frissítés
      sensors.value = newSensors
      triggerRef(sensors)

      console.log('Sensors fetched successfully:', Object.keys(newSensors).length)
    } catch (error) {
      console.error('Hiba az API hívás során:', error)
      errorMessage.value = error.message || 'Hiba történt a szenzorok lekérésekor'

      // Dummy adat fallback csak fejlesztés alatt
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
        console.log('Using fallback sensor data')
      }
    } finally {
      isLoading.value = false
    }
  }

  // Új szenzor hozzáadása
  async function addSensor (sensor) {
    isLoading.value = true
    errorMessage.value = ''
    try {
      await axios.post(`${ipPort.value}/v1/uav`,
        {
          uav_label: sensor.uav_label,
          uav_address: sensor.uav_address,
          active: sensor.active
        },
        { headers: { 'Content-Type': 'application/json' } }
      )

      console.log('Sensor added successfully')
      await fetchSensors()
    } catch (error) {
      console.error('Hiba az új szenzor hozzáadásakor:', error)
      errorMessage.value = 'Hiba történt a szenzor hozzáadásakor'
    } finally {
      isLoading.value = false
    }
  }

  // Szenzor eltávolítása
  async function removeSensor () {
    if (!selectedSensor.value) return

    const id = selectedSensor.value.uav_id
    isLoading.value = true
    errorMessage.value = ''

    try {
      // Worker leállítása, ha létezik
      if (detectionWorkers.value[id]) {
        detectionWorkers.value[id].terminate()

        const updatedWorkers = { ...detectionWorkers.value }
        delete updatedWorkers[id]
        detectionWorkers.value = updatedWorkers

        // Statisztikák frissítése
        stats.value = {
          ...stats.value,
          activeWorkers: Object.keys(updatedWorkers).length
        }
      }

      // Szenzor eltávolítása reaktív módon
      const updatedSensors = { ...sensors.value }
      delete updatedSensors[id]
      sensors.value = updatedSensors
      triggerRef(sensors)

      selectedSensor.value = null

      // API hívás
      await axios.delete(`${ipPort.value}/v1/uav/` + id)
      console.log('Sensor deleted successfully')
    } catch (error) {
      console.error('Hiba a szenzor törlésekor:', error)
      errorMessage.value = 'Hiba történt a szenzor törlésekor'

      // Hibás törlés esetén újra lekérjük a szenzorokat
      await fetchSensors()
    } finally {
      isLoading.value = false
    }
  }

  // Szenzor kiválasztása
  async function selectSensor (sensor: Sensor) {
    selectedSensor.value = sensor

    // Korábbi stream leállítása
    if (eventSourceStop) {
      eventSourceStop()
      eventSourceStop = null
    }

    console.log('Sensor selected:', sensor.uav_id)

    // Inicializáljuk a kiválasztott UAV-hoz tartozó workert
    initWorkerForUav(sensor.uav_id)

    // Stream indítása
    await startDetectionStream()
  }

  // Szenzorok listájának lekérése
  function getSensorsList () {
    return Object.values(sensors.value)
  }

  // Computed property a szenzorokhoz
  const getSensors = computed(() => sensors.value)

  // Szenzor kiválasztás toggle
  function toggleSensorSelection (sensorId: number) {
    if (!sensors.value[sensorId]) return

    const isCurrentlySelected = sensors.value[sensorId].is_selected

    updateSensorReactive(sensorId, {
      is_selected: !isCurrentlySelected
    })

    console.log(`Sensor ${sensorId} selection toggled to:`, !isCurrentlySelected)
  }

  // Raw detekció küldése a megfelelő workernek - JSON parsing nélkül
  function routeRawDetectionToWorker (rawJsonString) {
    // Először megpróbáljuk kinyerni az UAV ID-t a JSON-ból, hogy tudjuk melyik workernek küldjük
    try {
      // Egyszerű regex alapú UAV ID kinyerés, teljes parsing nélkül
      const uavIdMatch = rawJsonString.match(/"uav_id"\s*:\s*(\d+)/)

      if (!uavIdMatch) {
        console.warn('No UAV ID found in raw detection data')
        return
      }

      const uavId = parseInt(uavIdMatch[1])

      // Ha még nincs worker ennek az UAV-nak, létrehozunk egyet
      if (!detectionWorkers.value[uavId]) {
        console.log(`Creating worker for new UAV: ${uavId}`)
        initWorkerForUav(uavId)
      }

      // Elküldjük a RAW JSON string-et a megfelelő workernek
      if (detectionWorkers.value[uavId]) {
        detectionWorkers.value[uavId].postMessage({
          type: 'newDetection',
          value: rawJsonString // RAW JSON string, nem parsed objektum
        })

        // Statisztikák frissítése
        stats.value = {
          ...stats.value,
          totalReceived: stats.value.totalReceived + 1
        }
      } else {
        console.warn(`No worker available for UAV ${uavId}`)
      }
    } catch (error) {
      console.error('Error routing raw detection to worker:', error)
      errorMessage.value = 'Hiba a detekció továbbítása során'
    }
  }

  watch(batchInterval, async (newVal) => {
    console.log('Batch interval changed to:', newVal)

    // Előző stream leállítása
    if (eventSourceStop) {
      eventSourceStop()
      eventSourceStop = null
    }

    // Ha van kiválasztott szenzor, újraindítjuk a streamet az új intervallummal
    if (selectedSensor.value) {
      try {
        await startDetectionStream()
        console.log('Detection stream restarted with new interval:', newVal)
      } catch (err) {
        console.error('Stream restart error:', err)
        errorMessage.value = 'Hiba a stream újraindítása során'
      }
    }
  })

  // Detekciós stream indítása
  async function startDetectionStream () {
    if (!selectedSensor.value) {
      console.log('No sensor selected, cannot start stream')
      return
    }

    console.log('Starting detection stream with interval:', batchInterval.value)

    try {
      const { data, error, close } = useEventSource(
        `${ipPort.value}/v1/stream/comint_detection?interval=${batchInterval.value}`,
        [],
        {
          withCredentials: true,
          autoReconnect: {
            retries: 3,
            delay: 100,
            onFailed () {
              console.error('Failed to reconnect EventSource')
              errorMessage.value = 'Kapcsolat megszakadt, újracsatlakozás sikertelen'
            }
          }
        }
      )

      eventSourceStop = close

      // Data watcher - RAW string-et küldünk a workernek
      watch(data, (rawJsonString) => {
        if (!rawJsonString) return
        // RAW JSON string küldése a workernek - nincs parsing itt
        routeRawDetectionToWorker(rawJsonString)
      })

      // Error watcher
      watch(error, (err) => {
        if (err) {
          console.error('Hiba a stream során:', err)
          errorMessage.value = 'Stream hiba történt'
          close()
        }
      })

      console.log('Detection stream started successfully')
    } catch (error) {
      console.error('Failed to start detection stream:', error)
      errorMessage.value = 'Nem sikerült elindítani a detekciós streamet'
    }
  }

  // Detekciók teljes törlése
  function clearDetections () {
    console.log('Clearing all detections')

    // Új szenzor objektum létrehozása üres detekciókkal
    const newSensors = {}

    Object.entries(sensors.value).forEach(([id, sensor]) => {
      newSensors[id] = {
        ...sensor,
        detections: [] // Új üres array
      }
    })

    // Reaktív frissítés
    sensors.value = newSensors
    triggerRef(sensors)

    // comintDetections.value = []

    // Minden worker értesítése
    Object.entries(detectionWorkers.value).forEach(([uavId, worker]) => {
      if (worker && worker.postMessage) {
        worker.postMessage({
          type: 'clearDetections'
        })
      }
    })

    // Statisztikák nullázása
    stats.value = {
      totalReceived: 0,
      totalProcessed: 0,
      lastProcessingTime: 0,
      activeWorkers: Object.keys(detectionWorkers.value).length
    }

    console.log('All detections cleared')
  }

  // Összes worker leállítása és resources felszabadítása
  function terminateAllWorkers () {
    console.log('Terminating all workers')

    Object.entries(detectionWorkers.value).forEach(([uavId, worker]) => {
      if (worker && worker.terminate) {
        worker.terminate()
        console.log(`Worker for UAV ${uavId} terminated`)
      }
    })

    detectionWorkers.value = {}

    // Statisztikák frissítése
    stats.value = {
      ...stats.value,
      activeWorkers: 0
    }
  }

  // Debug funkció a reaktivitás tesztelésére
  function debugReactivity () {
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

    // Worker statisztikák lekérése
    Object.entries(detectionWorkers.value).forEach(([uavId, worker]) => {
      if (worker && worker.postMessage) {
        worker.postMessage({
          type: 'getStats'
        })
      }
    })
  }

  // Komponens elpusztításakor cleanup
  onUnmounted(() => {
    console.log('SensorStore cleanup')

    terminateAllWorkers()

    if (eventSourceStop) {
      eventSourceStop()
      eventSourceStop = null
    }
  })

  // Komponens mount-korás inicializálás
  onMounted(() => {
    console.log('SensorStore mounted')

    // Kapcsolat ellenőrzése
    if (isConnected.value) {
      fetchSensors()
    }
  })

  // Connection watcher
  watch(isConnected, (newValue) => {
    if (newValue) {
      console.log('Connection established, fetching sensors')
      fetchSensors()
    } else {
      console.log('Connection lost')
      terminateAllWorkers()
      if (eventSourceStop) {
        eventSourceStop()
        eventSourceStop = null
      }
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

    // Computed
    getSensors,

    // Metódusok

    // Metódusok
    getSensorsList,
    fetchSensors,
    addSensor,
    removeSensor,
    selectSensor,
    handleMouseOver,
    toggleSensorSelection,
    clearDetections,
    batchInterval,
    startDetectionStream,
    debugReactivity,

    // Belső metódusok (teszteléshez)
    terminateAllWorkers,
    updateAllWorkerSettings
  }
})
