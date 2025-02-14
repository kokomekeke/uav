<script setup>
// import { computed } from 'vue'

defineProps({
  type: String // "success", "error", vagy "info" lehet
})

const messages = {
  success: '✅ Sikeres művelet!',
  error: '❌ Hiba történt!',
  info: 'ℹ️ Fontos információ.'
}
</script>

<template>
  <p v-if="messages[type]" :class="type">{{ messages[type] }}</p>
</template>

<style scoped>
.success { color: green; }
.error { color: red; }
.info { color: blue; }
</style>
