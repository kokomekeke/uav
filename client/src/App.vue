<template>
  <div>
    <BurgerMenu></BurgerMenu>
    <button id="show-modal" @click="showModal = true">Show Modal</button>

    <Teleport to="body">
      <NewModal :show="showModal" @close="showModal = false">
        <template #header>
          <h3>Connect to ground server</h3>
        </template>
        <template #body>
          <label>Enter IP Address and Port:</label>
          <input v-model="ipPort" placeholder="192.168.1.100:8080">
        </template>
        <template #close>
          <button class="modal-default-button" @click="closeModal">Close</button>
        </template>
        <template #submit>
          <button class="modal-default-button" @click="connectToServer">Submit</button>
        </template>
      </NewModal>
    </Teleport>
    <p v-if="connectionMessage">{{ connectionMessage }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import NewModal from '@/components/NewModal.vue'
import BurgerMenu from '@/components/buttons/BurgerMenu.vue'

const showModal = ref(true)
const ipPort = ref('') // IP:Port beviteli mező
const connectionMessage = ref('')

const closeModal = () => {
  showModal.value = false
}
const connectToServer = () => {
  connectionMessage.value = '' // Hibaüzenet törlése

  const ipPortPattern = /^(\d{1,3}\.){3}\d{1,3}:\d{1,5}$/
  if (!ipPortPattern.test(ipPort.value)) {
    connectionMessage.value = '❌ Invalid IP or Port format!'
    return
  }

  const [ip, port] = ipPort.value.split(':')

  try {
    const socket = new WebSocket(`ws://${ip}:${port}`)

    socket.onopen = () => {
      connectionMessage.value = '✅ Connected successfully!'
      showModal.value = false // Modal bezárása
    }

    socket.onerror = () => {
      connectionMessage.value = '❌ Connection failed!'
    }
  } catch (error) {
    connectionMessage.value = '❌ Error connecting to server!'
  }
}
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}
</style>
