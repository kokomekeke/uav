import { defineStore, storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'
import axios from 'axios'
import { useConnectionStore } from '@/stores/connection'
import { Sensor, ComintDetection } from '../types/sensor'

export const useSensorStore = defineStore('sensor', () => {
  const sensors = ref<{ [id: number] : Sensor}>({})
  const selectedSensor = ref(null)
  const isLoading = ref<boolean>(false)
  const errorMessage = ref('')
  const detectionInterval = ref<number | null>(null)
  const connectionStore = useConnectionStore()
  const { ipPort, isConnected } = storeToRefs(connectionStore)

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
      console.log('sensorArray', sensorArray)
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

  async function selectSensor(sensor: Sensor) {
      console.log('SELECTED SENSOR: ', sensor, 'sensor selected')

      selectedSensor.value = sensor

      // checkbox szinkronizálás
      //Object.values(sensors.value).forEach(s => {
        //s.is_selected = s === sensor
      //    })

      // régi interval leállítása
      if (detectionInterval.value) {
        clearInterval(detectionInterval.value)
      }

      //clearDetections()
      await fetchDetection(10)

      detectionInterval.value = setInterval(() => {
        //clearDetections()
        fetchDetection(10)
      }, 1000)
    }


  const getSensors = computed(() => sensors.value)

  async function fetchDetection (n) {
    if (!selectedSensor.value) return

    try {
      const response = await axios.get(`${ipPort.value}/v1/comintdetection/geojson/list_last/${n}`)

      if (!response.data || response.status !== 200) {
        throw new Error(`API hiba: ${response.status} - ${response.statusText}`)
      }

      const features = response.data.features || []

      features.forEach((f) => {
        console.log("f", f )
        console.log(sensors.value[f.properties.uav_id])
        sensors.value[f.properties.uav_id].detections.push(f)
        console.log("vmilyen uzenet:", sensors.value[f.properties.uav_id].detections)
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
    console.log("ASDAZJKDGJKWDUIWDUWD=====", s)
  }, { deep: true })

  // function featureToComintDetection (feature: any): ComintDetection {
  //   const props = feature.properties ?? {}
  //   const coords = feature.geometry?.coordinates ?? [null, null]
  //   const [lon, lat] = coords
  //
  //   if (props.detection_id == null || props.uav_id == null || lat == null || lon == null) {
  //     throw new Error('featureToComintDetection: Kötelező mezők hiányoznak (detection_id, uav_id, lat, lon)')
  //   }
  //
  //   const detection: ComintDetection = {
  //     detection_id: props.detection_id,
  //     uav_id: props.uav_id,
  //     uav_event_id: props.uav_event_id ?? null,
  //     frequency: props.frequency != null ? BigInt(props.frequency) : undefined,
  //     signal_strength: props.signal_strength ?? undefined,
  //     bandwidth: props.bandwidth != null ? BigInt(props.bandwidth) : undefined,
  //     snr: props.snr ?? undefined,
  //     lob_azim_deg: props.lob_azim_deg ?? undefined,
  //     lob_elev_deg: props.lob_elev_deg ?? undefined,
  //     precision: props.precision ?? undefined,
  //     timestamp: props.timestamp ? new Date(props.timestamp) : undefined,
  //     uav_pos_lat: lat,
  //     uav_pos_lon: lon,
  //     uav_pos_altitude: props.uav_pos_altitude ?? null,
  //     uav_pos_q0: null,
  //     uav_pos_q1: null,
  //     uav_pos_q2: null,
  //     uav_pos_q3: null,
  //     roi_identifier: props.roi_id ?? null
  //   }
  //
  //   return detection
  // }

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
    fetchDetection,
    stopFetchingDetection
  }
})
