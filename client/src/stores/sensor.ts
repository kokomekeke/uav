import { defineStore, storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'
import axios from 'axios'
import { useConnectionStore } from '@/stores/connection'
import { Sensor, ComintDetection } from '../types/sensor'
import { Detection } from '../types/detection'

export const useSensorStore = defineStore('sensor', () => {
  const sensors = ref<{ [id: number] : Sensor}>({})
  const selectedSensor = ref(null)
  const isLoading = ref<boolean>(false)
  const errorMessage = ref('')
  const detectionInterval = ref<number | null>(null)
  const connectionStore = useConnectionStore()
  const { ipPort, isConnected } = storeToRefs(connectionStore)
  const detections = ref<Detection[]>([])

  const handleMouseOver = (sensor) => {
    selectedSensor.value = sensor
    console.log('over', sensor)
  }

  async function fetchSensors () {
    console.log('fetchSensors', ipPort.value)
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

      const sensorArray = Array.isArray(response.data) ? response.data : response.data.sensors || []
      sensorArray.forEach((sensor: Sensor) => {
        sensors.value[sensor.uav_id] = sensor
        sensors.value[sensor.uav_id].is_selected = false
        sensors.value[sensor.uav_id].detections = []
        console.log('inArray: ', sensors.value[sensor.uav_id])
      })
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
    console.log(sensor)
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
    console.log(selectedSensor.value)
    if (!selectedSensor.value) return

    delete sensors.value[selectedSensor.value.uav_id]
    const id = selectedSensor.value.uav_id
    selectedSensor.value = null

    await axios.delete(`${ipPort.value}/v1/uav/` + id).then(() => {
      console.log('sensor deleted')
    })

    console.log('new values: ', sensors.value)
  }

  // async function selectSensor (sensor: Sensor) {
  //   console.log('SELECTED SENSOR: ', sensor, 'sensor selected')
  //
  //   selectedSensor.value = sensor
  //
  //   // régi interval leállítása
  //   if (detectionInterval.value) {
  //     clearInterval(detectionInterval.value)
  //   }
  //
  //   // clearDetections()
  //   await fetchDetection(10)
  //
  //   detectionInterval.value = setInterval(() => {
  //     // clearDetections()
  //     fetchDetection(10)
  //   }, 1000)
  // }

  async function selectSensor (sensor: Sensor) {
    selectedSensor.value = sensor

    // Don't automatically check the checkbox - let user do that
    // This function just sets which sensor is "active" in the UI

    // Stop existing interval
    if (detectionInterval.value) {
      clearInterval(detectionInterval.value)
    }

    // Set up interval to fetch detections for all selected sensors
    await fetchAllSelectedDetections()

    detectionInterval.value = setInterval(() => {
      fetchAllSelectedDetections()
    }, 200)
  }
  const getSensors = computed(() => sensors.value)

  function toggleSensorSelection (sensorId: number) {
    if (!sensors.value[sensorId]) return

    // Toggle the selection
    sensors.value[sensorId].is_selected = !sensors.value[sensorId].is_selected

    // Refresh detections to reflect the new selection state
    fetchAllSelectedDetections()
  }

  async function fetchAllSelectedDetections () {
  // Clear all existing detections
    //detections.value = []

    // Find all selected sensors
    const selectedSensorIds = Object.keys(sensors.value)
      .filter(key => sensors.value[Number(key)].is_selected)
      .map(key => Number(key))

    if (selectedSensorIds.length === 0) return

    // For each selected sensor, fetch detections
    try {
      const response = await axios.get(`${ipPort.value}/v1/comintdetection/geojson/list_last/10`)

      if (!response.data || response.status !== 200) {
        throw new Error(`API hiba: ${response.status} - ${response.statusText}`)
      }

      const features = response.data.features || []

      features.forEach((f) => {
        const uavId = f.properties.uav_id
        console.log("id: ", uavId)
        // Only process if this sensor is selected
        if (!sensors.value[uavId] || !sensors.value[uavId].is_selected) return

        // Add to sensor's detection list
        sensors.value[uavId].detections.push(f)
        sensors.value[uavId].detections = sensors.value[uavId].detections.slice(-10)

        const azimuth = f.properties?.lob_azim_deg
        const lon = f.geometry?.coordinates?.[0]
        const lat = f.geometry?.coordinates?.[1]

        if (
          typeof azimuth === 'number' &&
          typeof lat === 'number' &&
          typeof lon === 'number'
        ) {
          detections.value.push({
              azimuth,
              coordinate: [lat, lon],
              uavId
            })
            detections.value = detections.value.slice(-10)
        }
      })
    } catch (error) {
      console.error('Hiba történt a fetchAllSelectedDetections során:', error)
    }
  }

  async function fetchDetection (n) {
    if (!selectedSensor.value) return

    try {
      const response = await axios.get(`${ipPort.value}/v1/comintdetection/geojson/list_last/${n}`)

      if (!response.data || response.status !== 200) {
        throw new Error(`API hiba: ${response.status} - ${response.statusText}`)
      }

      // Clear existing detections to avoid duplicates
      detections.value = []

      const features = response.data.features || []

      features.forEach((f) => {
        const uavId = f.properties.uav_id

        // Make sure the sensor exists
        if (!sensors.value[uavId]) return

        // Add to sensor's detection list
        sensors.value[uavId].detections.push(f)
        sensors.value[uavId].detections = sensors.value[uavId].detections.slice(-10)

        const azimuth = f.properties?.lob_azim_deg

        // GeoJSON uses [longitude, latitude] order
        const lon = f.geometry?.coordinates?.[0]
        const lat = f.geometry?.coordinates?.[1]

        if (
          typeof azimuth === 'number' &&
          typeof lat === 'number' &&
          typeof lon === 'number' &&
          sensors.value[uavId].is_selected
        ) {
          // Store in [latitude, longitude] format for Leaflet
          detections.value.push({
            azimuth,
            coordinate: [lat, lon],
            uavId
          })
          detections.value = detections.value.slice(-10)
        }
      })
    } catch (error) {
      console.error('Hiba történt a fetchDetection során:', error)
    }
  }

  function stopFetchingDetection () {
    if (detectionInterval.value) {
      clearInterval(detectionInterval.value)
      detectionInterval.value = null
    }
  }

  function clearDetections () {
    detections.value = []
    for (const key in sensors.value) {
      sensors.value[key].detections = []
    }
  }

  watch(selectedSensor, (newSensor) => {
    if (!newSensor) {
      stopFetchingDetection()
    }
  })

  watch(selectedSensor, (s) => {
    console.log(s.is_selected)
  })

  watch(sensors, (s) => {
    console.log('ASDAZJKDGJKWDUIWDUWD=====', s)
  }, { deep: true })

  return {
    sensors,
    selectedSensor,
    isLoading,
    errorMessage,
    getSensors,
    fetchSensors,
    addSensor,
    removeSensor,
    selectSensor,
    handleMouseOver,
    detections,
    fetchDetection,
    clearDetections,
    toggleSensorSelection,
    stopFetchingDetection
  }
})
