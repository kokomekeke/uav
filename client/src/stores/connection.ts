import { defineStore } from 'pinia'
import { ref } from 'vue'
import { io } from 'socket.io-client'
import { useSensorStore } from './sensor'

export const useConnectionStore = defineStore('connection', () => {
  const ipPort = ref('')
  const isConnected = ref(false)
  const connectionMessage = ref('')
  const pingInterval = ref(null)

  let socket = null
  const setIpPort = (newIpPort) => {
    ipPort.value = newIpPort
  }

  const setConnection = (newConnection) => {
    isConnected.value = newConnection
  }

  const setConnectionMessage = (message) => {
    connectionMessage.value = message
  }

  const connectToServer = () => {
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
        resolve(true) // ⬅️ Sikeres csatlakozás
      })

      socket.on('connect_error', (error) => {
        console.error('❌ Connection failed:', error)
        isConnected.value = false
        setConnectionMessage('❌error')
        resolve(false) // ⬅️ Sikertelen csatlakozás
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
