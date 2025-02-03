<script setup>
import { ref } from 'vue'

const isMenuOpen = ref(false)

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}
</script>

<template>
  <div class="flex flex-wrap w-32 gap-4 fixed">
    <button @click="toggleMenu" value="hamburger" class="flex flex-col justify-around h-8 w-8 p-1 rounded hover:bg-gray-400">
      <!-- Hamburger Icon (3 lines) -->
      <span class="h-0.5 rounded bg-gray-600 w-full"></span>
      <span class="h-0.5 rounded bg-gray-600 w-full"></span>
      <span class="h-0.5 rounded bg-gray-600 w-full"></span>
    </button>
    <template v-if="isMenuOpen">
      <div class="text-2xl">
        <a class="item-animation p-2 self-center bg-gray-500 rounded-full" href="/">🏠</a>
        <a class="item-animation p-2.5 self-center bg-gray-400 rounded-full" href="/leaderboard">🏆</a>
        <a class="item-animation p-1 self-center bg-gray-300 rounded-full" href="/calculator">🧮</a>
      </div>
    </template>
  </div>
</template>

<style scoped>
@keyframes itemanim {
    from {
        scale: 0%
    }

    to {
        scale: 100%
    }
}

.item-animation {
    animation-name: itemanim;
}

.item-animation:nth-child(4) {
    animation-duration: 0.8s;
}

.item-animation:nth-child(2) {
    animation-duration: 0.4s;
}

.item-animation:nth-child(3) {
    animation-duration: 1.2s;
}
</style>
