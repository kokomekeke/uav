import { defineStore } from 'pinia'
import { ref } from 'vue'
import { io } from 'socket.io-client'
import axios, { AxiosResponse } from 'axios'

// SensorData interfész
interface SensorData {
  uav_label: string
  uav_address: string
  active: boolean
}

// Csatlakozás kezelése
export const useConnectionStore = defineStore('connection', () => {
  const ipPort = ref('')
  const isConnected = ref(false)
  const connectionMessage = ref('')
  const pingInterval = ref<NodeJS.Timeout | null>(null)

  let socket: any = null

  const setIpPort = (newIpPort: string) => {
    ipPort.value = newIpPort
  }

  const setConnection = (newConnection: boolean) => {
    isConnected.value = newConnection
  }

  const setConnectionMessage = (message: string) => {
    connectionMessage.value = message
  }

  const connectToServer = (): Promise<boolean> => {
    return new Promise((resolve) => {
      stopPinging()
      socket = io(ipPort.value, {
        transports: ['websocket']
      })

      console.log('🔌 Connecting to:', ipPort.value)

      socket.on('connect', () => {
        console.log('✅ Connected to server')
        setConnectionMessage('✅success')
        isConnected.value = true
        resolve(true)
      })

      socket.on('connect_error', (error: any) => {
        console.error('❌ Connection failed:', error)
        isConnected.value = false
        setConnectionMessage('❌error')
        resolve(false)
      })

      socket.on('disconnect', () => {
        console.log('⚠️ Disconnected from server')
        setConnectionMessage('⚠️info')
      })

      socket.on('pong', () => {
        console.log('🏓 Pong received')
      })

      pingInterval.value = setInterval(() => {
        if (socket && socket.connected) {
          console.log('📡 Sending ping...')
          socket.emit('ping')
        } else {
          console.log('⏹️ No active connection, stopping ping interval...')
          stopPinging()
        }
      }, 2000)
    })
  }

  const stopPinging = () => {
    if (pingInterval.value) {
      clearInterval(pingInterval.value)
      pingInterval.value = null
    }
    if (socket) {
      socket.disconnect()
      socket = null
    }
  }

  return { ipPort, isConnected, connectionMessage, setIpPort, setConnection, setConnectionMessage, connectToServer }
})

// Szenzorok kezelése
export const useSensorStore = defineStore('sensor', () => {
  const sensors = ref<SensorData[]>([])
  const isLoading = ref<boolean>(false)
  const errorMessage = ref<string>('')

  const connectionStore = useConnectionStore()
  const { ipPort, isConnected } = connectionStore

  const addSensor = async (sensor: SensorData): Promise<void> => {
    if (!isConnected.value) {
      console.error('❌ Cannot add sensor, no connection!')
      return
    }

    try {
      const url = `${ipPort.value}/v1/uav/`
      const response: AxiosResponse = await axios.post<SensorData>(url, sensor, {
        headers: { 'Content-Type': 'application/json' }
      })

      console.log('✅ Sensor added successfully:', response.data)

      // API válasz után frissítjük a listát
      sensors.value.push(response.data)
    } catch (error) {
      console.error('❌ Error adding sensor:', error)
      errorMessage.value = 'Hiba történt a szenzor hozzáadása során.'
    }
  }

  return { sensors, isLoading, errorMessage, addSensor }
})
