<template>
  <div>
    <Teleport to="body">
      <NewModal :show="showModal" @close="closeModal" class="grid grid-cols-2">
        <template #header>
          <div>
            <img src="/sgxlogo.jpg" class="border-4 border-gray-100 rounded-sd" alt="sgx-logo"/>
          </div>
          <h3>Connect to ground server</h3>
        </template>

        <template #body>
          <div class="space-y-4">
            <!-- IP Address Input -->
            <div>
              <label class="block text-sm font-medium mb-2">Enter IP Address and Port:</label>
              <input
                v-model="ipPort"
                placeholder="http://192.168.0.82:5000"
                class="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                :disabled="isConnecting || isReconnecting || isConnected"
                @keyup.enter="connect"
              >
              <p class="text-xs text-gray-500 mt-1">
                Example: http://localhost:5000 or http://192.168.1.100:5000
              </p>
            </div>

            <!-- Connection Status Display -->
            <div class="bg-gray-50 p-3 rounded-md">
              <div class="flex items-center justify-between mb-2">
                <span class="font-medium text-sm">Connection status:</span>
                <div class="flex items-center space-x-2">
                  <!-- Status indicator -->
                  <div
                    class="w-3 h-3 rounded-full"
                    :class="{
                      'bg-green-500 animate-pulse': isConnected,
                      'bg-red-500': isFailed,
                      'bg-yellow-500 animate-pulse': isConnecting || isReconnecting,
                      'bg-gray-400': isDisconnected
                    }"
                  ></div>
                  <span
                    class="text-sm font-medium"
                    :class="{
                      'text-green-600': isConnected,
                      'text-red-600': isFailed,
                      'text-yellow-600': isConnecting || isReconnecting,
                      'text-gray-600': isDisconnected
                    }"
                  >
                    {{ getConnectionStateText() }}
                  </span>
                </div>
              </div>

              <!-- Reconnection Progress -->
              <div v-if="isReconnecting" class="space-y-2">
                <div class="flex justify-between text-xs text-yellow-700">
                  <span>Reconnecting in progress...</span>
                  <span>{{ reconnectAttempts }}/{{ maxReconnectAttempts }}</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                  <div
                    class="bg-yellow-500 h-2 rounded-full transition-all duration-300"
                    :style="{ width: `${(reconnectAttempts / maxReconnectAttempts) * 100}%` }"
                  ></div>
                </div>
              </div>

              <!-- Connection Test Button -->
              <div v-if="isConnected" class="mt-2">
                <button
                  @click="testConnection"
                  :disabled="testingConnection"
                  class="text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 px-2 py-1 rounded transition-colors"
                >
                  {{ testingConnection ? 'Testing...' : 'Test connection' }}
                </button>
              </div>
            </div>

            <!-- Server Info -->
            <div v-if="isConnected" class="bg-green-50 p-3 rounded-md">
              <h4 class="text-sm font-medium text-green-800 mb-1">Server information</h4>
              <div class="text-xs text-green-700 space-y-1">
                <div>Socket ID: {{ socket?.id || 'N/A' }}</div>
                <div>Server: {{ ipPort }}</div>
                <div>Transport: {{ socket?.io?.engine?.transport?.name || 'N/A' }}</div>
                <div>Ping: {{ lastPingTime ? `${Date.now() - lastPingTime}ms` : 'N/A' }}</div>
              </div>
            </div>
          </div>
        </template>

        <template #submit>
          <div class="grid grid-cols-3 gap-2">
            <!-- Connect & Retry Buttons -->
            <div class="col-span-3 flex gap-2">
              <!-- Connect Button (szélesebb) -->
              <button
                class="modal-default-button flex-[2] bg-green-400 hover:bg-green-500 p-2 rounded-2xl border-2 border-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                @click="connect"
                :disabled="isConnecting || isReconnecting || !ipPort.trim() || isConnected"
              >
                <span class="flex items-center space-x-1">
                  <svg v-if="isConnecting" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>{{ isConnecting ? 'Connecting...' : 'Connect' }}</span>
                </span>
              </button>

              <!-- Retry Button (keskenyebb) -->
              <button
                v-if="canReconnect"
                class="modal-default-button flex-1 bg-blue-400 hover:bg-blue-500 p-2 rounded-2xl border-2 border-blue-600 transition-all"
                @click="manualReconnect"
                :disabled="isConnecting || isReconnecting"
              >
                Retry
              </button>
            </div>

            <!-- Disconnect Button -->
            <button
              v-if="isConnected || isReconnecting"
              class="modal-default-button bg-orange-400 hover:bg-orange-500 p-2 rounded-2xl border-2 border-orange-600 transition-all col-span-3"
              @click="forceDisconnect"
            >
              Disconnect
            </button>

            <!-- Hard Reset Button -->
            <button
              v-if="isFailed || (reconnectAttempts >= maxReconnectAttempts && reconnectAttempts > 0)"
              class="col-span-3 modal-default-button bg-red-500 hover:bg-red-600 p-2 rounded-2xl border-2 border-red-700 text-white transition-all"
              @click="hardReset"
            >
              Full reset
            </button>

            <!-- Force Disconnect (Emergency) -->
            <button
              class="col-span-3 w-full modal-default-button bg-red-700 hover:bg-red-800 p-2 rounded-2xl border-2 border-red-900 text-white transition-all"
              @click="emergencyDisconnect"
              title="Emergency disconnect and reload page"
            >
              🚨 Emergency
            </button>
          </div>
        </template>


        <template #close>
          <button
            class="modal-default-button w-full bg-gray-400 hover:bg-gray-500 p-2 rounded-2xl border-2 border-gray-600 mt-2 transition-all"
            @click="closeModal"
          >
            Close
          </button>
        </template>

        <template #alert>
          <div v-if="connectionMessage" class="space-y-2">
            <div
              class="p-3 rounded-md text-sm"
              :class="{
                'bg-green-100 text-green-800': connectionMessage.includes('✅'),
                'bg-red-100 text-red-800': connectionMessage.includes('❌'),
                'bg-yellow-100 text-yellow-800': connectionMessage.includes('⚠️') || connectionMessage.includes('🔄'),
                'bg-blue-100 text-blue-800': connectionMessage.includes('🛑') || connectionMessage.includes('🔗'),
                'bg-gray-100 text-gray-800': !connectionMessage.includes('✅') && !connectionMessage.includes('❌') && !connectionMessage.includes('⚠️') && !connectionMessage.includes('🔄') && !connectionMessage.includes('🛑') && !connectionMessage.includes('🔗')
              }"
            >
              {{ connectionMessage }}
            </div>

            <!-- Debug Information -->
            <details v-if="showDebugInfo" class="text-xs">
              <summary class="cursor-pointer text-gray-600 hover:text-gray-800">Debug information</summary>
              <div class="mt-2 p-2 bg-gray-100 rounded text-gray-700 font-mono">
                <div>Connection State: {{ connectionState }}</div>
                <div>Reconnect Attempts: {{ reconnectAttempts }}/{{ maxReconnectAttempts }}</div>
                <div>Is Reconnecting: {{ isReconnecting }}</div>
                <div>Socket Connected: {{ socket?.connected || false }}</div>
                <div>Socket ID: {{ socket?.id || 'null' }}</div>
                <div>Last Activity: {{ lastActivity ? new Date(lastActivity).toLocaleTimeString() : 'N/A' }}</div>
              </div>
            </details>
          </div>
        </template>
      </NewModal>
    </Teleport>
  </div>
</template>

<script setup>
import NewModal from '@/components/common/NewModal.vue'
import { ref, watch, onUnmounted, computed, onMounted } from 'vue'
import { useConnectionStore } from '@/stores/connection'
import { storeToRefs } from 'pinia'
import { useSensorStore } from '@/stores/sensor'

const connectionStore = useConnectionStore()
const {
  ipPort,
  connectionMessage,
  isReconnecting,
  reconnectAttempts,
  maxReconnectAttempts,
  connectionState,
  socket,
  isConnected,
  isConnecting,
  isFailed,
  isDisconnected
} = storeToRefs(connectionStore)

const sensorStore = useSensorStore()

const props = defineProps({
  isMenuOpen: Boolean,
  isModalVisible: Boolean
})

const emit = defineEmits(['update:isModalVisible'])

// Local state
const showModal = ref(props.isModalVisible)
const testingConnection = ref(false)
const showDebugInfo = ref(false)
const lastPingTime = ref(null)
const lastActivity = ref(Date.now())

// Computed properties
const canReconnect = computed(() =>
  !isConnecting.value &&
  !isReconnecting.value &&
  (isFailed.value || isDisconnected.value)
)

// Watchers
watch(() => props.isModalVisible, (newValue) => {
  showModal.value = newValue
})

watch(() => showModal.value, (newValue) => {
  emit('update:isModalVisible', newValue)
})

// Update last activity when connection state changes
watch(connectionState, () => {
  lastActivity.value = Date.now()
})

// Methods
const closeModal = () => {
  showModal.value = false
  emit('update:isModalVisible', false)
}

const connect = async () => {
  if (isConnecting.value || isConnected.value) return

  try {
    const success = await connectionStore.connectToServer()
    if (success) {
      console.log('✅ Connection successful!')
      // Fetch sensors after successful connection
      try {
        await sensorStore.fetchSensors()
        // Close modal only after successful sensor fetch
        showModal.value = false
        emit('update:isModalVisible', false)
      } catch (error) {
        console.error('Sensor fetch failed:', error)
        // Keep modal open if sensor fetch fails
      }
    } else {
      console.log('❌ Connection failed!')
    }
  } catch (error) {
    console.error('Connection error:', error)
  }
}

const manualReconnect = async () => {
  if (isConnecting.value || isReconnecting.value) return

  try {
    const success = await connectionStore.manualReconnect()
    if (success) {
      await sensorStore.fetchSensors()
      if (showModal.value) {
        showModal.value = false
        emit('update:isModalVisible', false)
      }
    }
  } catch (error) {
    console.error('Manual reconnect error:', error)
  }
}

const forceDisconnect = () => {
  connectionStore.forceDisconnect()
}

const hardReset = () => {
  connectionStore.hardReset()
  // Reset local state
  testingConnection.value = false
  lastPingTime.value = null
  lastActivity.value = Date.now()
}

const emergencyDisconnect = () => {
  // Nuclear option - force disconnect and reload page
  connectionStore.hardReset()
  setTimeout(() => {
    if (confirm('Reload connection Proceed?')) {
      window.location.reload()
    }
  }, 1000)
}

const testConnection = async () => {
  if (testingConnection.value) return

  testingConnection.value = true
  lastPingTime.value = Date.now()

  try {
    const result = await connectionStore.testConnection()
    if (result) {
      connectionStore.connectionMessage = '✅ Connection test successful'
    } else {
      connectionStore.connectionMessage = '❌ Connection test failed'
    }
  } catch (error) {
    connectionStore.connectionMessage = `❌ Connection test error: ${error.message}`
  } finally {
    testingConnection.value = false
  }
}

const getConnectionStateText = () => {
  if (isReconnecting.value) {
    return `Reconnect... (${reconnectAttempts.value}/${maxReconnectAttempts.value})`
  }
  if (isConnecting.value) return 'Connect...'

  switch (connectionState.value) {
    case 'connected': return 'Connected'
    case 'connecting': return 'Connected...'
    case 'failed': return 'Connection failed'
    case 'disconnected': return 'Disconnected'
    case 'reconnecting': return 'Reconnecting...'
    default: return 'Unknown state'
  }
}

// Lifecycle
onMounted(() => {
  // Enable debug info in development
  if (import.meta.env.DEV) {
    showDebugInfo.value = true
  }

  // Listen for socket events to update ping time
  if (socket.value) {
    socket.value.on('pong', () => {
      lastPingTime.value = Date.now()
    })
  }
})

onUnmounted(() => {
  connectionStore.cleanup()
})

// Keyboard shortcuts
const handleKeydown = (event) => {
  if (!showModal.value) return

  switch (event.key) {
    case 'Enter':
      if (event.ctrlKey) {
        connect()
      }
      break
    case 'Escape':
      closeModal()
      break
    case 'r':
      if (event.ctrlKey && canReconnect.value) {
        event.preventDefault()
        manualReconnect()
      }
      break
    case 'd':
      if (event.ctrlKey && (isConnected.value || isReconnecting.value)) {
        event.preventDefault()
        forceDisconnect()
      }
      break
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.modal-default-button {
  transition: all 0.2s ease-in-out;
  min-width: 100px;
  font-size: 0.875rem;
}

.modal-default-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.modal-default-button:active:not(:disabled) {
  transform: translateY(0);
}

.modal-default-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
  transform: none;
}

/* Animation for status indicator */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Smooth transitions for state changes */
.space-y-4 > * + * {
  margin-top: 1rem;
}

.space-y-2 > * + * {
  margin-top: 0.5rem;
}

/* Focus styles for accessibility */
input:focus,
button:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

button:focus:not(:focus-visible) {
  outline: none;
}

/* Responsive design */
@media (max-width: 640px) {
  .modal-default-button {
    min-width: 80px;
    font-size: 0.75rem;
    padding: 0.5rem;
  }

  .flex.flex-wrap.gap-2 {
    gap: 0.25rem;
  }
}
</style>