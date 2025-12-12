<template>
  <div>
    <CenteredModal :show="showModal" @close="closeModal">
      <template #header>
        <div class="flex items-center space-x-3">
          <img src="/sgxlogo.jpg" class="w-12 h-12 border-2 rounded-lg border-cyan-700 dark:border-cyan-400 " alt="sgx-logo"/>
          <h3 class="text-xl font-bold text-cyan-900 dark:text-cyan-400 tracking-widest">Connect to Ground Server</h3>
        </div>
      </template>

      <template #body>
        <div class="space-y-6">
          <div>
            <label class="block text-sm font-semibold mb-2 text-cyan-900 dark:text-cyan-400">Enter IP Address and Port:</label>
            <input
              v-model="ipPort"
              placeholder="http://192.168.0.82:5000"
              class="w-full p-2 border border-slate-600 rounded focus:ring-2 focus:ring-cyan-600 focus:border-cyan-600 bg-gray-50 text-gray-700
              dark:focus:ring-cyan-500 dark:focus:border-cyan-500 dark:bg-slate-800 dark:text-gray-200"
              :disabled="isConnecting || isReconnecting || isConnected"
              @keyup.enter="connect"
            >
            <p class="text-xs text-slate-500 mt-1">
              Example: http://localhost:5000 or http://192.168.1.100:5000
            </p>
          </div>

          <div class="bg-slate-800 p-4 rounded border border-slate-700">
            <div class="flex items-center justify-between mb-3">
              <span class="font-semibold text-sm text-gray-300">Connection status:</span>
              <div class="flex items-center space-x-2">
                <div
                  class="w-3 h-3 rounded-full"
                  :class="{
                    'bg-green-500 animate-pulse': isConnected,
                    'bg-red-500': isFailed,
                    'bg-yellow-500 animate-pulse': isConnecting || isReconnecting,
                    'bg-gray-500': isDisconnected
                  }"
                ></div>
                <span
                  class="text-sm font-medium"
                  :class="{
                    'text-green-400': isConnected,
                    'text-red-400': isFailed,
                    'text-yellow-400': isConnecting || isReconnecting,
                    'text-gray-400': isDisconnected
                  }"
                >
                  {{ getConnectionStateText() }}
                </span>
              </div>
            </div>

            <div v-if="isReconnecting" class="space-y-2">
              <div class="flex justify-between text-xs text-yellow-400">
                <span>Reconnecting in progress...</span>
                <span>{{ reconnectAttempts }}/{{ maxReconnectAttempts }}</span>
              </div>
              <div class="w-full bg-slate-700 rounded-full h-2">
                <div
                  class="bg-yellow-500 h-2 rounded-full transition-all duration-300"
                  :style="{ width: `${(reconnectAttempts / maxReconnectAttempts) * 100}%` }"
                ></div>
              </div>
            </div>

            <div v-if="isConnected" class="mt-3">
              <button
                @click="testConnection"
                :disabled="testingConnection"
                class="text-xs bg-cyan-600 hover:bg-cyan-500 text-white px-3 py-1 rounded transition"
              >
                {{ testingConnection ? 'Testing...' : 'Test connection' }}
              </button>
            </div>
          </div>

          <div v-if="isConnected" class="bg-slate-800 p-4 rounded border border-green-600">
            <h4 class="text-sm font-semibold text-green-400 mb-2">Server information</h4>
            <div class="text-xs text-green-300 space-y-1 font-mono">
              <div>Socket ID: {{ socket?.id || 'N/A' }}</div>
              <div>Server: {{ ipPort }}</div>
              <div>Transport: {{ socket?.io?.engine?.transport?.name || 'N/A' }}</div>
              <div>Ping: {{ lastPingTime ? `${Date.now() - lastPingTime}ms` : 'N/A' }}</div>
            </div>
          </div>
        </div>
      </template>

      <template #submit>
        <button
          class="flex-1 bg-green-600 hover:bg-green-500 px-4 py-2 rounded-xl border border-green-700 font-semibold text-white disabled:opacity-50 transition"
          @click="connect"
          :disabled="isConnecting || isReconnecting || !ipPort.trim() || isConnected"
        >
          <span class="flex items-center justify-center space-x-2">
            <svg v-if="isConnecting" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>{{ isConnecting ? 'Connecting...' : 'Connect' }}</span>
          </span>
        </button>

        <button
          v-if="canReconnect"
          class="bg-cyan-600 hover:bg-cyan-500 px-4 py-2 rounded-xl border border-cyan-700 text-white transition"
          @click="manualReconnect"
          :disabled="isConnecting || isReconnecting"
        >
          Retry
        </button>

        <button
          v-if="isConnected || isReconnecting"
          class="bg-orange-600 hover:bg-orange-500 px-4 py-2 rounded-xl border border-orange-700 text-white transition"
          @click="forceDisconnect"
        >
          Disconnect
        </button>

        <button
          v-if="isFailed || (reconnectAttempts >= maxReconnectAttempts && reconnectAttempts > 0)"
          class="bg-red-600 hover:bg-red-500 px-4 py-2 rounded-xl border border-red-700 text-white transition"
          @click="hardReset"
        >
          Full reset
        </button>

        <button
          class="bg-red-800 hover:bg-red-700 px-4 py-2 rounded-xl border border-red-900 text-white transition"
          @click="emergencyDisconnect"
        >
          🚨 Emergency
        </button>
      </template>

      <template #alert>
        <div v-if="connectionMessage" class="space-y-2">
          <div
            class="p-3 rounded-md text-sm font-mono"
            :class="{
              'bg-green-900 text-green-300 border border-green-600': connectionMessage.includes('✅'),
              'bg-red-900 text-red-300 border border-red-600': connectionMessage.includes('❌'),
              'bg-yellow-900 text-yellow-300 border border-yellow-600': connectionMessage.includes('⚠️') || connectionMessage.includes('🔄'),
              'bg-cyan-900 text-cyan-300 border border-cyan-600': connectionMessage.includes('🛑') || connectionMessage.includes('🔗'),
              'bg-slate-800 text-gray-300 border border-slate-600': true
            }"
          >
            {{ connectionMessage }}
          </div>

          <details v-if="showDebugInfo" class="text-xs text-gray-400 mt-2">
            <summary class="cursor-pointer hover:text-gray-200">Debug information</summary>
            <div class="mt-2 p-2 bg-slate-800 rounded border border-slate-600">
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
    </CenteredModal>
  </div>
</template>

<script setup>
import CenteredModal from '@/components/common/CenteredModal.vue'
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
  isModalVisible: Boolean
})

const emit = defineEmits(['update:isModalVisible'])

const showModal = ref(props.isModalVisible)
const testingConnection = ref(false)
const showDebugInfo = ref(false)
const lastPingTime = ref(null)
const lastActivity = ref(Date.now())

const canReconnect = computed(() =>
  !isConnecting.value &&
  !isReconnecting.value &&
  (isFailed.value || isDisconnected.value)
)

watch(() => props.isModalVisible, (newValue) => {
  showModal.value = newValue
})

watch(() => showModal.value, (newValue) => {
  emit('update:isModalVisible', newValue)
})

watch(connectionState, () => {
  lastActivity.value = Date.now()
})

const closeModal = () => {
  showModal.value = false
  emit('update:isModalVisible', false)
}

const connect = async () => {
  if (isConnecting.value || isConnected.value) return
  try {
    const success = await connectionStore.connectToServer()
    if (success) {
      await sensorStore.fetchSensors()
      showModal.value = false
      emit('update:isModalVisible', false)
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
      showModal.value = false
      emit('update:isModalVisible', false)
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
  testingConnection.value = false
  lastPingTime.value = null
  lastActivity.value = Date.now()
}

const emergencyDisconnect = () => {
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
    connectionStore.connectionMessage = result
      ? '✅ Connection test successful'
      : '❌ Connection test failed'
  } catch (error) {
    connectionStore.connectionMessage = `❌ Connection test error: ${error.message}`
  } finally {
    testingConnection.value = false
  }
}

const getConnectionStateText = () => {
  if (isReconnecting.value) return `Reconnect... (${reconnectAttempts.value}/${maxReconnectAttempts.value})`
  if (isConnecting.value) return 'Connect...'
  switch (connectionState.value) {
    case 'connected': return 'Connected'
    case 'connecting': return 'Connecting...'
    case 'failed': return 'Connection failed'
    case 'disconnected': return 'Disconnected'
    case 'reconnecting': return 'Reconnecting...'
    default: return 'Unknown state'
  }
}

onMounted(() => {
  if (import.meta.env.DEV) showDebugInfo.value = true
  if (socket.value) {
    socket.value.on('pong', () => {
      lastPingTime.value = Date.now()
    })
  }
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  connectionStore.cleanup()
  document.removeEventListener('keydown', handleKeydown)
})

const handleKeydown = (event) => {
  if (!showModal.value) return
  switch (event.key) {
    case 'Enter': if (event.ctrlKey) connect(); break
    case 'Escape': closeModal(); break
    case 'r': if (event.ctrlKey && canReconnect.value) manualReconnect(); break
    case 'd': if (event.ctrlKey && (isConnected.value || isReconnecting.value)) forceDisconnect(); break
  }
}
</script>
