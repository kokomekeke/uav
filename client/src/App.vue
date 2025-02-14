<template>
  <div class="min-h-screen flex flex-col">
<!--    <SensorPane></SensorPane>-->
    <BurgerMenu class="burger-menu"/>
    <button id="show-modal" @click="showModal = true">Show Modal</button>

    <Teleport to="body">
      <NewModal :show="showModal" @close="showModal = false">
        <template #header>
          <img src="/sgxlogo.jpg"/>
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
        <template #alert>
          <AlertBox :type="connectionMessage"/>
        </template>
      </NewModal>
    </Teleport>
    <p v-if="connectionMessage" :class="{'text-green-500': connectionMessage.includes('✅'), 'text-red-500': connectionMessage.includes('❌')}">
      {{ connectionMessage }}
    </p>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import NewModal from '@/components/NewModal.vue'
import BurgerMenu from '@/components/buttons/BurgerMenu.vue'
import { io } from 'socket.io-client'
// import SensorPane from '@/components/sidebar-components/SensorPane.vue'
import AlertBox from '@/components/alerts/AlertBox.vue'
import axios from 'axios'

const showModal = ref(true)
const ipPort = ref('http://192.168.1.245:5000') // IP:Port beviteli mező
const connectionMessage = ref('')
const pingInterval = ref(null)
let socket = null // Tároljuk a socket példányt

const packageVer = '0'
const gitHash = '0'
const info = ref(null)

onMounted(() => {
  console.log(`SGX-PC-1 client loaded v${packageVer} (${gitHash})`)
  console.log('hajajj', info.value)
})

const closeModal = () => {
  showModal.value = false
  stopPinging() // Biztosítjuk, hogy az interval leáll
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

const connectToServer = () => {
  stopPinging() // Ha van már aktív kapcsolat, először leállítjuk

  socket = io(ipPort.value, {
    transports: ['websocket']
  })

  console.log('🔌 Connecting to:', ipPort.value)

  socket.on('connect', () => {
    console.log('✅ Connected to server')
    connectionMessage.value = 'success'
    setTimeout(() => {
      showModal.value = false
    }, 3000)
  })

  socket.on('connect_error', (error) => {
    console.error('❌ Connection failed:', error)
    connectionMessage.value = 'error'
  })

  socket.on('disconnect', () => {
    console.log('⚠️ Disconnected from server')
    connectionMessage.value = 'info'
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
      stopPinging() // Ha nincs kapcsolat, állítsuk le az időzítőt
    }
  }, 2000)
}

const getSensors = () => {
  axios.get(ipPort.value)
    .then(response => {
      // Ellenőrizzük, hogy a válasz megfelelő formátumban van-e
      if (Array.isArray(response.data.bpi)) {
        // Ha valóban lista (tömb) a válasz, akkor beállítjuk a `info` változót
        info.value = response.data.bpi
        console.log('iiii', info.value)
      } else {
        // Ha nem lista, akkor egy új lista elemet adunk hozzá
        info.value = [response.data.bpi]
        console.log('iiik', info.value)
      }
    })
    .catch(error => {
      console.error('API hívás hiba:', error)
      connectionMessage.value = '❌ Hiba történt a szenzorok betöltésekor.'
    })
}

</script>

<style src="./assets/styles/app.css">
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}

.burger-menu {
  position: fixed;
  top: 10px;
  left: 10px;
  z-index: 1000;
}
</style>
