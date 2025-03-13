import { defineStore, storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'
import axios from 'axios'
import { useConnectionStore } from '@/stores/connection'

export const useSensorStore = defineStore('sensor', () => {
  const sensors = ref([])
  const newSensor = ref('')
  const selectedSensor = ref(null)
  const isLoading = ref<boolean>(false)
  const errorMessage = ref('')

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
      console.log('response data: ', response.data)
      sensors.value = Array.isArray(response.data) ? response.data : response.data.sensors || []
    } catch (error) {
      console.error('Hiba az API hívás során:', error)
      sensors.value = [
        { uav_label: 'test01', ip: '10.1.1.113' },
        { uav_label: 'test02', ip: '10.1.1.119' }
      ]
      console.log('szenzór:: ', sensors.value)
    } finally {
      isLoading.value = false
    }
  }

  async function addSensor () {
    console.log('newSensor: ', newSensor.value)
    if (newSensor.value.trim() === '') return
    console.log('...')
    try {
      await axios.post(`${ipPort.value}/v1/uav/`, { sensor: newSensor.value })

      // API sikeres válasz után frissítjük a listát
      await fetchSensors()
      sensors.value = [...sensors.value]
      console.log('✅ Szenzorok frissítve:', sensors.value)
      newSensor.value = ''
    } catch (error) {
      console.error('Hiba az új szenzor hozzáadásakor:', error)
      sensors.value.push(newSensor.value)
      newSensor.value = ''
    }
  }

  watch(sensors, (newSensors) => {
    console.log('🔄 Szenzor lista frissítve:', newSensors)
  }, { deep: true })

  watch(newSensor, (n) => {
    console.log('N', n)
  })

  async function removeSensor () {
    console.log(selectedSensor)
    if (!selectedSensor.value) return // Ha nincs kiválasztott szenzor, kilépünk

    sensors.value = sensors.value.filter(s => s.uav_label !== selectedSensor.value.uav_label)
    const id = selectedSensor.value.uav_id
    selectedSensor.value = null

//     ide kéne a backend endpointot aktiválni
    await axios.delete(`${ipPort.value}/v1/uav/` + id).then(response => {
      console.log("juhuuuuu");
    });
    console.log('new values::::', sensors.value)
  }

  function selectSensor (sensor) {
    console.log(sensor, 'sensor selected')
    selectedSensor.value = sensor
  }
  const getSensors = computed(() => [...sensors.value])
  return {
    sensors,
    newSensor,
    selectedSensor,
    isLoading,
    errorMessage,
    getSensors,
    fetchSensors,
    addSensor,
    removeSensor,
    selectSensor,
    handleMouseOver
  }
})
