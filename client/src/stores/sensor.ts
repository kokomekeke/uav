// sensor.js optimalizált változat
import { defineStore, storeToRefs } from 'pinia'
import { computed, ref, watch, shallowRef } from 'vue'
import axios from 'axios'
import { useConnectionStore } from '@/stores/connection'
import { Sensor } from '../types/sensor'
import { useEventSource } from '@vueuse/core'

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

  // Feldolgozás közben használt változók
  let lastProcessTime = 0
  const processThrottle = 100 // ms - nagyobb érték kevesebb feldolgozást jelent
  const samplingRate = ref(20)

  // Statisztikák
  const stats = ref({
    totalReceived: 0,
    totalProcessed: 0,
    lastProcessingTime: 0
  })

  // Buffer feldolgozáshoz - a bufferben gyűjtjük az adatokat a feldolgozás előtt
  const detectionBuffer = shallowRef<Comint[]>([])
  const isProcessingBuffer = ref(false)

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
    const { data, error, close } = useEventSource(`${ipPort.value}/v1/stream/comint_detection`, [], {
      autoReconnect: {
        retries: 3,
        delay: 100,
        onFailed () {
          alert('Failed to reconnect')
        }
      }
    })
    eventSourceStop = close

    watch(data, (newVal) => {
      if (!newVal) return

      try {
        const parsed = JSON.parse(newVal)
        stats.value.totalReceived++

        detectionBuffer.value.push({
          coordinate: [parsed.uav_pos_lat, parsed.uav_pos_lon],
          azimuth: parsed.lob_azim_deg,
          uavId: parsed.uav_id,
          timestamp: Date.now()
        })
        const now = Date.now()
        if (now - lastProcessTime > processThrottle && !isProcessingBuffer.value) {
          processDetectionBuffer()
          lastProcessTime = now
        } else {
          console.log('Waiting for processing')
        }
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

  function processDetectionBuffer () {
    if (detectionBuffer.value.length === 0 || isProcessingBuffer.value) return

    isProcessingBuffer.value = true
    const processStart = performance.now()

    try {
      samplingRate.value = 20

      // minden samplingRatedik elemet tart csak meg
      // const newDetections: Comint[] = detectionBuffer.value.filter((_, index) => index % samplingRate.value === 0)
      const lastTimestampsByUav: Record<number, number> = {}

      function isSampled (detection: Comint) {
        const now = detection.timestamp
        const last = lastTimestampsByUav[detection.uavId] || 0

        if (now - last >= samplingRate.value) {
          lastTimestampsByUav[detection.uavId] = now
          return true
        }
        return false
      }

      const newDetections = detectionBuffer.value.filter(isSampled)
      stats.value.totalProcessed += newDetections.length

      if (newDetections.length > 0) {
        const detectionsByUavId: Record<string, Comint[]> = {}

        for (const det of newDetections) {
          if (!detectionsByUavId[det.uavId]) {
            detectionsByUavId[det.uavId] = []
          }
          detectionsByUavId[det.uavId].push(det)
        }

        // Új szenzor objektum létrehozása a módosításokkal
        const updatedSensors = { ...sensors.value }
        const maxSize = Math.abs(detectionSize.value)

        // Frissítjük a szenzorok detekcióit
        Object.entries(detectionsByUavId).forEach(([uavId, detections]) => {
          const id = parseInt(uavId)
          if (!updatedSensors[id]) return

          const newSensorDetections = [
            ...updatedSensors[id].detections,
            ...detections
          ].slice(-maxSize) // Korlátozzuk a méretet

          // Frissítjük a szenzor detekciós listáját
          updatedSensors[id] = {
            ...updatedSensors[id],
            detections: newSensorDetections
          }
        })
        sensors.value = updatedSensors
      }
      // Buffer ürítése
      detectionBuffer.value = []
    } catch (e) {
      console.error('Hiba a detekciók feldolgozása során:', e)
    } finally {
      stats.value.lastProcessingTime = performance.now() - processStart
      isProcessingBuffer.value = false
    }
  }

  // Automatikus feldolgozás időzítő beállítása
  let bufferProcessInterval = null

  function startAutoProcessing () {
    // Megállítjuk a korábbi időzítőt, ha van
    if (bufferProcessInterval) {
      clearInterval(bufferProcessInterval)
    }

    // Új időzítő indítása
    bufferProcessInterval = setInterval(() => {
      if (detectionBuffer.value.length > 0) {
        processDetectionBuffer()
      }
    }, processThrottle * 2) // Nagyobb időintervallum a feldolgozáshoz
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
    detectionBuffer.value = []

    // Statisztikák nullázása
    stats.value = {
      totalReceived: 0,
      totalProcessed: 0,
      lastProcessingTime: 0
    }
  }

  // Komponens indításánál indítjuk a feldolgozást
  startAutoProcessing()

  return {
    sensors,
    selectedSensor,
    isLoading,
    errorMessage,
    getSensors,
    getSensorsList, // Új metódus a szenzorok lekérdezésére
    fetchSensors,
    addSensor,
    removeSensor,
    selectSensor,
    handleMouseOver,
    toggleSensorSelection,
    detectionSize,
    comintDetections,
    clearDetections, // Új metódus a detekciók törlésére
    stats,
    samplingRate
  }
})
