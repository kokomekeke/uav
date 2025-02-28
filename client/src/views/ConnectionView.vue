<script setup>

import NewModal from '@/components/common/NewModal.vue'

import { ref, watch } from 'vue'
import { io } from 'socket.io-client'

const ipPort = defineModel({ default: '192.168.1.100:8080' })
const pingInterval = ref(null)
const connectionMessage = ref('')

const isConnected = ref(false)

let socket = null

const props = defineProps({
  isMenuOpen: Boolean,
  isModalVisible: Boolean
})

const showModal = ref(props.isModalVisible)
const emit = defineEmits(['update:isModalVisible', 'update:isConnected', 'update:connectionMessage'])

watch(() => props.isModalVisible, (newValue) => {
  showModal.value = newValue
})

const closeModal = () => {
  showModal.value = false
  emit('update:isModalVisible', false)
  // stopPinging() // Biztosítjuk, hogy az interval leáll
}

const connectToServer = () => {
  stopPinging()
  socket = io(ipPort.value, {
    transports: ['websocket']
  })

  console.log('🔌 Connecting to:', ipPort.value)

  socket.on('connect', () => {
    console.log('✅ Connected to server')
    connectionMessage.value = '✅success'
    isConnected.value = true

    emit('update:isConnected', true)
    emit('update:connectionMessage', connectionMessage.value)
    console.log(connectionMessage.value)
    emit('update:ipPort', ipPort.value)

    setTimeout(() => {
      console.log('successs')
      showModal.value = false
      emit('update:isModalVisible', false)
    }, 3000)
  })

  socket.on('connect_error', (error) => {
    console.error('❌ Connection failed:', error)
    isConnected.value = false
    connectionMessage.value = '❌error'
    emit('update:isConnected', false)
    emit('update:connectionMessage', connectionMessage.value)
    emit('update:ipPort', ipPort.value)
  })

  socket.on('disconnect', () => {
    console.log('⚠️ Disconnected from server')
    connectionMessage.value = '⚠️info'
    emit('update:isConnected', false)
    emit('update:connectionMessage', connectionMessage.value)
    emit('update:ipPort', ipPort.value)
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
}

const stopPinging = () => {
  console.log('valami')
  if (pingInterval.value) {
    console.log('⏹️ Stopping ping interval...')
    clearInterval(pingInterval.value)
    pingInterval.value = null
  }
  if (socket) {
    console.log('🔌 Disconnecting from server...')
    socket.disconnect() // Leállítja a kapcsolatot
    socket = null
  }
}

watch(() => showModal.value, (newValue) => {
  console.log('Modal state changed:', newValue)
  emit('update:isModalVisible', newValue)
})

watch(() => showModal, (newModal) => {
  console.log('Új érték kiválasztva:', newModal)
})

watch(connectionMessage, (newValue) => {
  console.log('🔄 connectionMessage változott:', newValue)
})

</script>

<template>
  <div>
      <Teleport to="body">
        <NewModal :show="showModal" @close="showModal = false">
          <template #header>
            <div>
              <img src="/sgxlogo.jpg" class="border-4 border-gray-100 rounded-sd" alt="sgx-logo"/>
            </div>
            <h3>Connect to ground server</h3>
          </template>
          <template #body>
            <label>Enter IP Address and Port:</label>
            <input v-model="ipPort" placeholder="192.168.1.100:8080" class="w-64">
          </template>
          <template #close>
            <button class="modal-default-button" @click="closeModal">Close</button>
          </template>
          <template #submit>
            <button class="modal-default-button" @click="connectToServer">Submit</button>
          </template>
          <template #alert>
            <p v-if="connectionMessage" :class="{
            'text-green-500': connectionMessage.includes('✅'),
            'text-red-500': connectionMessage.includes('❌'),
            'text-yellow-500': connectionMessage.includes('⚠️')
          }">
            {{ connectionMessage }}
          </p>
          </template>
        </NewModal>
      </Teleport>
    </div>
</template>

<style scoped>

</style>
