// sensor.js - Több worker támogatással
import { defineStore, storeToRefs } from 'pinia'
import { computed, ref, watch, shallowRef, onUnmounted, onMounted } from 'vue'
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
  timestamp: number;
}

export const useSensorStore = defineStore('sensor', () => {
  // shallowRef használata a komplex objektumok esetén a mélyebb változások okozta újrarenderelés elkerülésére
  const sensors = shallowRef<{ [id: number] : Sensor}>({})
  const selectedSensor = shallowRef(null)
  const isLoading = ref<boolean>(false)
  const errorMessage = ref('')
  const connectionStore = useConnectionStore()
  const { ipPort, isConnected } = storeToRefs(connectionStore)
  let eventSourceStop = null

  // Inicializáljuk egy üres tömbbel, hogy mindig legyen egy kezdeti érték
  const comintDetections = shallowRef<Comint[]>([])
  const detectionSize = ref(5)

  // Statisztikák
  const stats = ref({
    totalReceived: 0,
    totalProcessed: 0,
    lastProcessingTime: 0
  })

  // Worker referenciák tárolása UAV ID-nként
  const detectionWorkers = shallowRef({})

  // Worker inicializálása egy adott UAV-hoz
  function initWorkerForUav(uavId) {
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

          // Frissítjük a statisztikákat - összesítve minden workertől
          stats.value = {
            totalReceived: stats.value.totalReceived + (workerStats.totalReceived || 0),
            totalProcessed: stats.value.totalProcessed + (workerStats.totalProcessed || 0),
            lastProcessingTime: Math.max(stats.value.lastProcessingTime, workerStats.lastProcessingTime || 0)
          }

          // Csak ennek az UAV-nak a detekciói érdekesek, mivel worker UAV-specifikus
          const updatedSensors = { ...sensors.value }
          const maxSize = Math.abs(detectionSize.value)

          if (detectionsByUavId[uavId] && updatedSensors[uavId]) {
            const newSensorDetections = [
              ...updatedSensors[uavId].detections,
              ...detectionsByUavId[uavId]
            ].slice(-maxSize)

            updatedSensors[uavId] = {
              ...updatedSensors[uavId],
              detections: newSensorDetections
            }
          }

          sensors.value = updatedSensors
          break
        }

        case 'statsUpdated':
          // Statisztikák frissítése - ez összesített érték lesz minden workertől
          stats.value = {
            ...stats.value,
            ...message.stats
          }
          break

        case 'error':
          console.error(`Worker error for UAV ${uavId}:`, message.message)
          break

        case 'workerStarted':
          console.log(`Detection worker for UAV ${uavId} started successfully`)
          // Beállítások küldése a workernek
          updateWorkerSettings(uavId)
          break
      }
    }

    // Worker hibaesemények kezelése
    worker.onerror = (error) => {
      console.error(`Worker error for UAV ${uavId}:`, error)
      worker.terminate()
      // Eltávolítjuk a hibás workert
      const updatedWorkers = { ...detectionWorkers.value }
      delete updatedWorkers[uavId]
      detectionWorkers.value = updatedWorkers
    }

    // Frissítjük a workerek listáját
    const updatedWorkers = { ...detectionWorkers.value }
    updatedWorkers[uavId] = worker
    detectionWorkers.value = updatedWorkers

    return worker
  }

  // Worker beállítások frissítése egy adott UAV-hoz
  function updateWorkerSettings(uavId) {
    const worker = detectionWorkers.value[uavId]
    if (!worker) return

    worker.postMessage({
      type: 'updateSettings',
      uavId: uavId,
      samplingRate: samplingRate.value,
      processThrottle: 100 // Ez egy fix érték maradt
    })
  }

  // Minden worker beállításának frissítése
  function updateAllWorkerSettings() {
    Object.keys(detectionWorkers.value).forEach(uavId => {
      updateWorkerSettings(parseInt(uavId))
    })
  }

  // Mintavételezési ráta
  const samplingRate = ref(20)

  // Figyelje a samplingRate változásait és frissítse a workereket
  watch(samplingRate, () => {
    updateAllWorkerSettings()
  })

  const handleMouseOver = (sensor) => {
    selectedSensor.value = sensor
  }

  async function fetchSensors() {
    if (!isConnected.value) return

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

      const newSensors = {}
      const sensorArray = Array.isArray(response.data) ? response.data : response.data.sensors || []

      sensorArray.forEach((sensor: Sensor) => {
        const existingDetections = sensors.value[sensor.uav_id]?.detections || []

        newSensors[sensor.uav_id] = {
          ...sensor,
          is_selected: sensors.value[sensor.uav_id]?.is_selected || false,
          detections: existingDetections
        }
      })

      sensors.value = newSensors
    } catch (error) {
      console.error('Hiba az API hívás során:', error)

      // Dummy adat fallback
      sensors.value = {
        1: {
          uav_id: 1,
          uav_label: 'test001',
          uav_address: '10.1.1.113',
          active: true,
          detections: []
        },
        2: {
          uav_id: 2,
          uav_label: 'test002',
          uav_address: '10.1.1.119',
          active: true,
          detections: []
        }
      }
    } finally {
      isLoading.value = false
    }
  }

  async function addSensor(sensor) {
    try {
      await axios.post(`${ipPort.value}/v1/uav`,
        {
          uav_label: sensor.uav_label,
          uav_address: sensor.uav_address,
          active: false
        },
        { headers: { 'Content-Type': 'application/json' } }
      )

      await fetchSensors()
    } catch (error) {
      console.error('Hiba az új szenzor hozzáadásakor:', error)
    }
  }

  async function removeSensor() {
    if (!selectedSensor.value) return

    const id = selectedSensor.value.uav_id

    // Worker leállítása, ha létezik
    if (detectionWorkers.value[id]) {
      detectionWorkers.value[id].terminate()
      const updatedWorkers = { ...detectionWorkers.value }
      delete updatedWorkers[id]
      detectionWorkers.value = updatedWorkers
    }

    // Klónozzuk a jelenlegi szenzorokat
    const updatedSensors = { ...sensors.value }
    delete updatedSensors[id]

    // Frissítjük a teljes objektumot
    sensors.value = updatedSensors
    selectedSensor.value = null

    try {
      await axios.delete(`${ipPort.value}/v1/uav/` + id)
      console.log('sensor deleted')
    } catch (error) {
      console.error('Hiba a szenzor törlésekor:', error)
    }
  }

  async function selectSensor(sensor: Sensor) {
    selectedSensor.value = sensor

    if (eventSourceStop) {
      eventSourceStop()
      eventSourceStop = null
    }

    // Inicializáljuk a kiválasztott UAV-hoz tartozó workert
    initWorkerForUav(sensor.uav_id)
    await startDetectionStream()
  }

  function getSensorsList () {
    return Object.values(sensors.value)
  }

  const getSensors = computed(() => sensors.value)

  function toggleSensorSelection(sensorId: number) {
    if (!sensors.value[sensorId]) return

    const updatedSensors = { ...sensors.value }
    updatedSensors[sensorId] = {
      ...updatedSensors[sensorId],
      is_selected: !updatedSensors[sensorId].is_selected
    }

    sensors.value = updatedSensors
  }

  // Detekció szétküldése a megfelelő workernek
  function routeDetectionToWorker (parsed) {
    const uavId = parsed.uav_id

    // Ha még nincs worker ennek az UAV-nak, létrehozunk egyet
    if (!detectionWorkers.value[uavId]) {
      initWorkerForUav(uavId)
    }

    // Elküldjük a detekciót a megfelelő workernek
    if (detectionWorkers.value[uavId]) {
      detectionWorkers.value[uavId].postMessage({
        type: 'newDetection',
        value: JSON.stringify(parsed)
      })
    }
  }

  async function startDetectionStream() {
    console.log('stream start')
    const batchInterval = 0.2 // 200ms
    console.log(ipPort.value)
    const { data, error, close } = useEventSource(
      `${ipPort.value}/v1/stream/comint_detection?interval=${batchInterval}`,
      [],
      {
        autoReconnect: {
          retries: 3,
          delay: 100,
          onFailed() {
            alert('Failed to reconnect')
          }
        }
      }
    )
    eventSourceStop = close

    watch(data, (newVal) => {
      if (!newVal) return

      try {
        const parsed = JSON.parse(newVal)

        // Detekció irányítása a megfelelő workerhez
        routeDetectionToWorker(parsed)
      } catch (e) {
        console.error('Hiba a detekció feldolgozása során:', e)
      }
    })

    watch(error, (err) => {
      if (err) {
        console.error('Hiba a stream során:', err)
        close()
      }
    })
  }

  // Detekciók teljes törlése
  function clearDetections() {
    // Új szenzor objektum létrehozása üres detekciókkal
    const updatedSensors = { ...sensors.value }

    Object.keys(updatedSensors).forEach(id => {
      updatedSensors[id] = {
        ...updatedSensors[id],
        detections: []
      }
    })

    sensors.value = updatedSensors
    comintDetections.value = []

    // Minden worker értesítése
    Object.entries(detectionWorkers.value).forEach(([uavId, worker]) => {
      worker.postMessage({
        type: 'clearDetections'
      })
    })
  }

  // Összes worker leállítása és resources felszabadítása
  function terminateAllWorkers() {
    Object.values(detectionWorkers.value).forEach(worker => {
      worker.terminate()
    })
    detectionWorkers.value = {}
  }

  // A komponens elpusztításakor az összes worker leállítása
  onUnmounted(() => {
    terminateAllWorkers()

    if (eventSourceStop) {
      eventSourceStop()
      eventSourceStop = null
    }
  })

  return {
    sensors,
    selectedSensor,
    isLoading,
    errorMessage,
    getSensors,
    getSensorsList,
    fetchSensors,
    addSensor,
    removeSensor,
    selectSensor,
    handleMouseOver,
    toggleSensorSelection,
    detectionSize,
    comintDetections,
    clearDetections,
    stats,
    samplingRate
  }
})
