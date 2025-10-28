<script setup>
import { ref, defineProps } from 'vue'
import ConnectionView from '@/views/ConnectionView.vue'

const props = defineProps({
  isMenuOpen: Boolean
})

const isMenuOpen = ref(props.isMenuOpen)

</script>

<template>
  <div class="relative max-h-screen">
    <button
        id="show-modal"
        @click="isMenuOpen = !isMenuOpen"
        class="fixed inset-80 flex items-center justify-center font-mono uppercase text-lg "
    >
      Show Modal
    </button>

    <ConnectionView :is-modal-visible="isMenuOpen"
                    @update:isModalVisible="isMenuOpen = $event"
                    />
  </div>
</template>

<style scoped>

</style>
