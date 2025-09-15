<script setup>
const props = defineProps({
  isMenuOpen: Boolean
})
</script>

<template>
  <section class="bg-slate-900 p-4 transition-all" :class="isMenuOpen ? 'ml-64' : 'ml-0'">
    <router-view :isMenuOpen="isMenuOpen" @update:isMenuOpen="$emit('update:isMenuOpen', $event)" />
  </section>
</template>

<style scoped>

</style>