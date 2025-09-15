<script setup>
defineProps({
  isMenuOpen: Boolean
})
</script>

<template>
  <div
    class="sticky top-0 px-6 py-5 w-full h-20 bg-slate-950 border-b border-cyan-700
         text-center font-mono uppercase text-2xl text-cyan-400 font-bold tracking-widest
         shadow-md transition-all duration-300 backdrop-blur-sm"
    :class="{ 'shadow-inner': isMenuOpen }"
  >
    <h1>CLIENT SOFTWARE</h1>
  </div>
</template>

<style scoped>
.shadow-inner {
  box-shadow: inset 8px 0 15px -6px rgba(0, 255, 200, 0.4);
}
</style>
