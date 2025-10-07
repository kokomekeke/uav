<script setup>
defineProps({
  isMenuOpen: Boolean
})
</script>

<template>
  <div
    class="sticky top-0 px-6 py-5 w-full h-20
           text-center text-2xl bg-inherit transition-all duration-300"
    :class="{ 'shadow-inner': isMenuOpen }"
    v-bind="$attrs"
  >
    <h1 class="p-5 font-bold tracking-widest text-cyan-300 select-none">
      LENA_ALTISS
    </h1>
    <div
      class="absolute bottom-0 left-1/2 -translate-x-1/2 w-1/2 border-b-2 border-blue-300"
    ></div>
  </div>
</template>

<style scoped>
.shadow-inner {
  box-shadow: inset 8px 0 15px -6px rgba(0, 255, 200, 0.4);
}
</style>
