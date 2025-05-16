// sensor.js - Worker támogatással
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

  // Worker referencia
  let detectionWorker = null

  // Worker inicializálása
  function initWorker () {
    console.log('init worker')
    if (detectionWorker) {
      detectionWorker.terminate()
    }

    // detectionWorker = new Worker(new URL('../workers/detectionWorker.js?worker', import.meta.url), { type: 'module' })
    detectionWorker = new DetectionWorker()

    detectionWorker.onmessage = (e) => {
      const message = e.data

      switch (message.type) {
        case 'processedDetections': {
          const { detectionsByUavId, stats: workerStats } = message

          // Frissítjük a statisztikákat
          stats.value = workerStats

          const updatedSensors = { ...sensors.value }
          const maxSize = Math.abs(detectionSize.value)

          Object.entries(detectionsByUavId).forEach(([uavId, detections]) => {
            const id = parseInt(uavId)
            if (!updatedSensors[id]) return

            const newSensorDetections = [
              ...updatedSensors[id].detections,
              ...detections
            ].slice(-maxSize)

            updatedSensors[id] = {
              ...updatedSensors[id],
              detections: newSensorDetections
            }
          })

          sensors.value = updatedSensors
          break
        }

        case 'statsUpdated':
          // Statisztikák frissítése
          stats.value = message.stats
          break

        case 'error':
          console.error(message.message)
          break

        case 'workerStarted':
          console.log('Detection worker started successfully')
          // Beállítások küldése a workernek
          updateWorkerSettings()
          break
      }
    }

    // // Worker hibaesemények kezelése
    detectionWorker.onerror = (error) => {
      console.error('Worker error:', error)
      detectionWorker.terminate()
    }
  }

  // Worker beállítások frissítése
  function updateWorkerSettings () {
    if (!detectionWorker) return

    detectionWorker.postMessage({
      type: 'updateSettings',
      samplingRate: samplingRate.value,
      processThrottle: 100 // Ez egy fix érték maradt
    })
  }

  // Mintavételezési ráta
  const samplingRate = ref(20)

  // Figyelje a samplingRate változásait és frissítse a workert
  watch(samplingRate, () => {
    updateWorkerSettings()
  })

  const handleMouseOver = (sensor) => {
    selectedSensor.value = sensor
  }

  async function fetchSensors () {
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

  async function addSensor (sensor) {
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

  async function removeSensor () {
    if (!selectedSensor.value) return

    const id = selectedSensor.value.uav_id

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

  async function selectSensor (sensor: Sensor) {
    selectedSensor.value = sensor

    if (eventSourceStop) {
      eventSourceStop()
      eventSourceStop = null
    }
    initWorker()
    await startDetectionStream()
  }

  function getSensorsList () {
    return Object.values(sensors.value)
  }

  const getSensors = computed(() => sensors.value)

  function toggleSensorSelection (sensorId: number) {
    if (!sensors.value[sensorId]) return

    const updatedSensors = { ...sensors.value }
    updatedSensors[sensorId] = {
      ...updatedSensors[sensorId],
      is_selected: !updatedSensors[sensorId].is_selected
    }

    sensors.value = updatedSensors
  }

  async function startDetectionStream () {
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
          onFailed () {
            alert('Failed to reconnect')
          }
        }
      }
    )
    eventSourceStop = close

    // a parset átszervezni a workerbe, illetve minden sensornak külön workere legyen
    watch(data, (newVal) => {
      if (!newVal || !detectionWorker) return

      try {
        // const parsed = JSON.parse(newVal)

        // Detekció küldése a worker-nek
        detectionWorker.postMessage({
          type: 'newDetection',
          value: newVal
          // detection: {
          //   coordinate: [parsed.uav_pos_lat, parsed.uav_pos_lon],
          //   azimuth: parsed.lob_azim_deg,
          //   uavId: parsed.uav_id,
          //   timestamp: Date.now()
          // },
          // maxSize: detectionSize.value
        })
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
  function clearDetections () {
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

    // Worker értesítése
    if (detectionWorker) {
      detectionWorker.postMessage({
        type: 'clearDetections'
      })
    }
  }

  // Worker inicializálása a komponens létrehozásakor
  // onMounted(() => {
  //   initWorker()
  // })

  // A komponens elpusztításakor a worker leállítása
  onUnmounted(() => {
    if (detectionWorker) {
      detectionWorker.terminate()
      detectionWorker = null
    }

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
