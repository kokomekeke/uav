import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { io, Socket } from 'socket.io-client'

export const useConnectionStore = defineStore('connection', () => {
  const socket = ref<Socket | null>(null)
  const ipPort = ref('http://localhost:5000')
  const connectionState = ref('disconnected')
  const connectionMessage = ref('')
  const isReconnecting = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = ref(5)

  const lastPingSent = ref<number | null>(null)
  const lastPongReceived = ref<number | null>(null)
  const currentPing = ref<number | null>(null)

  let connectTimeout = null
  let reconnectTimeout = null
  let pingInterval = null
  let connectionCheckInterval = null

  const CONNECT_TIMEOUT = 15000
  const RECONNECT_DELAY = 3000
  const PING_INTERVAL = 30000
  const CONNECTION_CHECK_INTERVAL = 5000

  const isConnected = computed(() => connectionState.value === 'connected')
  const isConnecting = computed(() => connectionState.value === 'connecting')
  const isFailed = computed(() => connectionState.value === 'failed')
  const isDisconnected = computed(() => connectionState.value === 'disconnected')

  const pingMs = computed(() => currentPing.value)

  const ipPortModel = computed({
    get: () => ipPort.value,
    set: (value) => {
      ipPort.value = value.trim()
    }
  })

  const clearAllTimeouts = () => {
    if (connectTimeout) {
      clearTimeout(connectTimeout)
      connectTimeout = null
    }
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    if (pingInterval) {
      clearInterval(pingInterval)
      pingInterval = null
    }
    if (connectionCheckInterval) {
      clearInterval(connectionCheckInterval)
      connectionCheckInterval = null
    }
  }

  const updateConnectionState = (state, message = '') => {
    connectionState.value = state
    connectionMessage.value = message
    console.log(`🔗 Connection state: ${state}`, message ? `- ${message}` : '')
  }

  const cleanupSocket = () => {
    if (socket.value) {
      try {
        socket.value.removeAllListeners()
        if (socket.value.connected) {
          socket.value.disconnect()
        }
        socket.value = null
      } catch (error) {
        console.error('Socket cleanup error:', error)
        socket.value = null
      }
    }
  }

  const setupSocketEventListeners = () => {
    if (!socket.value) return

    socket.value.on('connect', () => {
      console.log('✅ Socket connected:', socket.value?.id)
      updateConnectionState('connected', '✅ Successfully connected to the server')
      reconnectAttempts.value = 0
      isReconnecting.value = false
      clearAllTimeouts()
      startPingInterval()
      startConnectionCheck()
    })

    socket.value.on('disconnect', (reason) => {
      console.log('❌ Socket disconnected:', reason)
      updateConnectionState('disconnected', `🛑 Connection lost: ${reason}`)
      clearAllTimeouts()

      lastPingSent.value = null
      lastPongReceived.value = null
      currentPing.value = null

      if (reason !== 'io client disconnect' && reason !== 'transport close') {
        attemptReconnect()
      }
    })

    socket.value.on('connect_error', (error) => {
      console.error('❌ Connection error:', error)
      updateConnectionState('failed', `❌ Connection error: ${error.message}`)
      clearAllTimeouts()
      attemptReconnect()
    })

    socket.value.on('error', (error) => {
      console.error('❌ Socket error:', error)
      updateConnectionState('failed', `❌ Socket error: ${error}`)
      attemptReconnect()
    })

    socket.value.on('pong', (data) => {
      lastPongReceived.value = Date.now()
      if (lastPingSent.value) {
        currentPing.value = lastPongReceived.value - lastPingSent.value
        console.log('🏓 Pong received, ping:', currentPing.value, 'ms')
      }
    })

    socket.value.on('reconnect', () => {
      console.log('🔄 Reconnected to server')
      updateConnectionState('connected', '🔄 Reconnected')
      isReconnecting.value = false
      reconnectAttempts.value = 0
    })
  }

  const startPingInterval = () => {
    clearInterval(pingInterval)

    sendPing()

    pingInterval = setInterval(() => {
      sendPing()
    }, PING_INTERVAL)
  }

  const sendPing = () => {
    if (socket.value && socket.value.connected) {
      lastPingSent.value = Date.now()
      socket.value.emit('ping', { timestamp: lastPingSent.value })
      console.log('🏓 Ping sent at', lastPingSent.value)
    }
  }

  const startConnectionCheck = () => {
    clearInterval(connectionCheckInterval)
    connectionCheckInterval = setInterval(() => {
      if (socket.value && !socket.value.connected && connectionState.value === 'connected') {
        console.log('⚠️ Connection state mismatch detected')
        updateConnectionState('disconnected', '⚠️ Connection lost')
        attemptReconnect()
      }
    }, CONNECTION_CHECK_INTERVAL)
  }

  const attemptReconnect = () => {
    if (isReconnecting.value || reconnectAttempts.value >= maxReconnectAttempts.value) {
      if (reconnectAttempts.value >= maxReconnectAttempts.value) {
        updateConnectionState('failed', `❌ Reconnection failed after ${maxReconnectAttempts.value} attempts`)
      }
      return
    }

    isReconnecting.value = true
    reconnectAttempts.value++
    updateConnectionState('reconnecting', `🔄 Reconnecting... (${reconnectAttempts.value}/${maxReconnectAttempts.value})`)

    reconnectTimeout = setTimeout(async () => {
      try {
        await connectToServer(true)
      } catch (error) {
        console.error('Reconnect attempt failed:', error)
        if (reconnectAttempts.value < maxReconnectAttempts.value) {
          attemptReconnect()
        } else {
          isReconnecting.value = false
          updateConnectionState('failed', '❌ All reconnection attempts failed')
        }
      }
    }, RECONNECT_DELAY)
  }

  const connectToServer = async (isReconnectAttempt = false) => {
    if (!isReconnectAttempt && (isConnecting.value || isConnected.value)) {
      console.log('Already connecting or connected')
      return true
    }

    try {
      updateConnectionState('connecting', '🔄 Connecting to the server...')
      clearAllTimeouts()
      cleanupSocket()

      console.log(`🔗 Attempting to connect to: ${ipPort.value}`)

      socket.value = io(ipPort.value, {
        timeout: CONNECT_TIMEOUT,
        forceNew: true,
        reconnection: false,
        transports: ['websocket', 'polling'],
        upgrade: true,
        rememberUpgrade: true,
        pingTimeout: 60000,
        pingInterval: 25000,
        maxHttpBufferSize: 1e6,
        withCredentials: true,
        autoConnect: false
      })

      setupSocketEventListeners()

      const connectPromise = new Promise((resolve, reject) => {
        const cleanup = () => {
          if (socket.value) {
            socket.value.off('connect', onConnect)
            socket.value.off('connect_error', onError)
          }
        }

        const onConnect = () => {
          cleanup()
          resolve(true)
        }

        const onError = (error) => {
          cleanup()
          reject(error)
        }

        socket.value.once('connect', onConnect)
        socket.value.once('connect_error', onError)
        socket.value.connect()
      })

      const timeoutPromise = new Promise((_, reject) => {
        connectTimeout = setTimeout(() => {
          reject(new Error('Connection timeout'))
        }, CONNECT_TIMEOUT)
      })

      await Promise.race([connectPromise, timeoutPromise])
      clearTimeout(connectTimeout)
      return true
    } catch (error) {
      console.error('❌ Connection failed:', error)
      clearAllTimeouts()
      cleanupSocket()

      if (!isReconnectAttempt) {
        updateConnectionState('failed', `❌ Connection failed: ${error.message}`)
        attemptReconnect()
      }

      return false
    }
  }

  const manualReconnect = async () => {
    console.log('🔄 Manual reconnect initiated')
    reconnectAttempts.value = 0
    isReconnecting.value = false
    clearAllTimeouts()
    return await connectToServer()
  }

  const forceDisconnect = () => {
    console.log('🛑 Force disconnect initiated')
    clearAllTimeouts()
    isReconnecting.value = false
    reconnectAttempts.value = 0

    if (socket.value) {
      try {
        if (socket.value.connected) {
          socket.value.emit('force_disconnect')
        }
        socket.value.disconnect()
      } catch (error) {
        console.error('Force disconnect error:', error)
      }
    }

    cleanupSocket()
    updateConnectionState('disconnected', '🛑 Connection forcibly disconnected')
  }

  const hardReset = () => {
    console.log('💥 Hard reset initiated')
    forceDisconnect()

    connectionState.value = 'disconnected'
    connectionMessage.value = ''
    isReconnecting.value = false
    reconnectAttempts.value = 0
    lastPingSent.value = null
    lastPongReceived.value = null
    currentPing.value = null

    setTimeout(() => {
      updateConnectionState('disconnected', '🔄 System reset to default state')
    }, 1000)
  }

  const cleanup = () => {
    console.log('🧹 Cleaning up connection store')
    clearAllTimeouts()
    cleanupSocket()
    isReconnecting.value = false
    reconnectAttempts.value = 0
  }

  const testConnection = async () => {
    if (!socket.value || !socket.value.connected) {
      return false
    }

    try {
      return new Promise((resolve) => {
        const timeout = setTimeout(() => resolve(false), 5000)

        socket.value.once('pong', () => {
          clearTimeout(timeout)
          resolve(true)
        })

        socket.value.emit('ping', { timestamp: Date.now() })
      })
    } catch (error) {
      console.error('Connection test failed:', error)
      return false
    }
  }

  return {
    socket,
    ipPort,
    connectionState,
    connectionMessage,
    isReconnecting,
    reconnectAttempts,
    maxReconnectAttempts,

    lastPingSent,
    lastPongReceived,
    currentPing,
    pingMs,

    ipPortModel,

    isConnected,
    isConnecting,
    isFailed,
    isDisconnected,

    connectToServer,
    manualReconnect,
    forceDisconnect,
    hardReset,
    cleanup,
    testConnection
  }
})