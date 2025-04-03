import { defineStore, storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'
import axios from 'axios'
import { useConnectionStore } from '@/stores/connection'
import { Sensor } from "../types/sensor"

export const useSensorStore = defineStore('sensor', () => {
  const sensors = ref<Sensor[]>([])
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
      console.log('response data: ', response.data)
      sensors.value = Array.isArray(response.data) ? response.data : response.data.sensors || []
    } catch (error) {
      console.error('Hiba az API hívás során:', error)
      sensors.value = [
        { uav_label: 'test001', ip: '10.1.1.113' },
        { uav_label: 'test002', ip: '10.1.1.119' }
      ]
      console.log('szenzór:: ', sensors.value)
    } finally {
      isLoading.value = false
    }
  }

  async function addSensor (sensor) {
    console.log(sensor)
    console.log(ipPort.value)
    console.log('JSON sent:', JSON.stringify({
      uav_label: sensor.uav_label,
      uav_address: sensor.uav_address,
      active: false
    }))
    try {
      await axios.post(`${ipPort.value}/v1/uav`,
        {
          uav_label: sensor.uav_label,
          uav_address: sensor.uav_address,
          active: false
        },
        { headers: { 'Content-Type': 'application/json' } }
      ).catch(
        (error) => {
          console.error('❌ Hiba az API hívás során:', error.response ? error.response.data : error.message)
        }
      )

      // API sikeres válasz után frissítjük a listát
      await fetchSensors()
      sensors.value = [...sensors.value]
      console.log('✅ Szenzorok frissítve:', sensors.value)
    } catch (error) {
      console.error('Hiba az új szenzor hozzáadásakor:', error)
    }
  }

  watch(sensors, (newSensors) => {
    console.log('🔄 Szenzor lista frissítve:', newSensors)
  }, { deep: true })


  async function removeSensor () {
    console.log(selectedSensor)
    if (!selectedSensor.value) return // Ha nincs kiválasztott szenzor, kilépünk

    sensors.value = sensors.value.filter(s => s.uav_label !== selectedSensor.value.uav_label)
    const id = selectedSensor.value.uav_id
    selectedSensor.value = null

    //     ide kéne a backend endpointot aktiválni
    await axios.delete(`${ipPort.value}/v1/uav/` + id).then(response => {
      console.log('juhuuuuu')
    })
    console.log('new values::::', sensors.value)
  }

  async function selectSensor(sensor) {
    console.log(sensor, 'sensor selected')
    selectedSensor.value = sensor

    // Meglévő timer törlése, ha már fut
    if (detectionInterval.value) {
      clearInterval(detectionInterval.value);
    }

    // Azonnal meghívjuk az API-t egyszer
    fetchDetection(10);

    // Timer beállítása, hogy 1 másodpercenként lefusson a fetchDetection
    detectionInterval.value = setInterval(() => {
      fetchDetection(10);
    }, 10); // 1000 ms = 1 sec
  }

  const getSensors = computed(() => [...sensors.value])

  async function fetchDetection(n) {
    if (!selectedSensor.value) return; // Ha nincs kiválasztott szenzor, kilépünk

    try {
      const response = await axios.get(`${ipPort.value}/v1/comintdetection/geojson/list_last/${n}`);
      console.log("API válasz:", response.data);

      selectedSensor.value.detections = response.data;

      console.log("DETECTIONS LIST: ", selectedSensor.value)
      if (!response.data) {
        throw new Error('Üres API válasz');
      }

      if (response.status !== 200) {
        throw new Error(`API hiba: ${response.status} - ${response.statusText}`);
      }

      return response.data;
    } catch (error) {
      console.error("Hiba történt a fetchDetection során:", error);
    }
  }

  function stopFetchingDetection() {
    if (detectionInterval.value) {
      clearInterval(detectionInterval.value);
      detectionInterval.value = null;
    }
  }

  watch(selectedSensor, (newSensor) => {
    if (!newSensor) {
      stopFetchingDetection(); // Ha nincs szenzor kiválasztva, leállítjuk az intervalt
    }
  });

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
