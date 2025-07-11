<script setup>
import { ref, defineProps } from 'vue'
import ConnectionView from '@/views/ConnectionView.vue'
import { useConnectionStore } from '@/stores/connection';

const connectionStore = useConnectionStore()
// const showModal = defineModel('showModal', { default: true })
// const isConnected = defineModel('isConnected')
// const connectionMessage = defineModel('connectionMessage')

const props = defineProps({
  ipPort: String
})

const port = ref(props.ipPort)
</script>

<template>
  <div class="relative max-h-screen">
    <button id="show-modal" @click="connectionStore.showModal = !connectionStore.showModal" class="fixed inset-80 flex items-center justify-center font-mono uppercase text-lg ">
      Show Modal
    </button>

    <ConnectionView :is-modal-visible="connectionStore.showModal"
                    @update:isModalVisible="connectionStore.showModal = $event"
                    @update:isConnected="connectionStore.isConnected = $event"
                    v-model="port"/>
  </div>
</template>

<style scoped>

</style>
