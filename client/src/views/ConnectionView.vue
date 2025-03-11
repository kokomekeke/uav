<script setup>
import NewModal from '@/components/common/NewModal.vue'
import { ref, watch } from 'vue'
import { useConnectionStore } from '@/stores/connection'
import { storeToRefs } from 'pinia'
import { useSensorStore } from '@/stores/sensor'

const connectionStore = useConnectionStore()
const { ipPort, connectionMessage } = storeToRefs(connectionStore)
const connectToServer = connectionStore.connectToServer
const sensorStore = useSensorStore()
const props = defineProps({
  isMenuOpen: Boolean,
  isModalVisible: Boolean
})

const showModal = ref(props.isModalVisible)
const emit = defineEmits(['update:isModalVisible'])

watch(() => props.isModalVisible, (newValue) => {
  showModal.value = newValue
})

const closeModal = () => {
  showModal.value = false
  emit('update:isModalVisible', false)
}

const connect = async () => {
  const success = await connectToServer()
  if (success) {
    console.log('✅ Kapcsolódás sikeres!')
    showModal.value = false
    emit('update:isModalVisible', false)
    await sensorStore.fetchSensors()
  } else {
    console.log('❌ Kapcsolódás sikertelen!')
  }
}

watch(() => showModal.value, (newValue) => {
  console.log('Modal state changed:', newValue)
  emit('update:isModalVisible', newValue)
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
            <input v-model="ipPort" placeholder="localhost:5000" class="w-64">
          </template>
          <template #close>
            <button class="modal-default-button" @click="closeModal">Close</button>
          </template>
          <template #submit>
            <button class="modal-default-button" @click="connect">Submit</button>
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
