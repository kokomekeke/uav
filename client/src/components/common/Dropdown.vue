<script setup>
import { ref } from 'vue';
defineProps({
  title: String
})

const show = ref(false)
</script>

<template>
  <div class="dropdown relative">
    <div
      class="cursor-pointer h-10 bg-white flex border border-gray-200 rounded items-center p-3"
      v-html="title"
      @click="show = !show"
    ></div>
    <div
      class="absolute rounded shadow bg-white overflow-hidden peer-checked:flex flex-col w-full mt-1 border border-gray-200"
      v-if="show"
    >
      <slot />
    </div>
  </div>
</template>

<style scoped>

</style>