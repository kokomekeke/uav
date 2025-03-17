<template>
  <main class="bg-green-500 min-h-screen grid grid-rows-[auto,1fr]">
    <!-- Fejléc -->
    <div class="sticky top-0 px-4 py-6 w-full h-20 bg-gray-300 border-gray-800 text-center border-2 rounded font-mono uppercase text-lg text-black font-bold">
      <h1>App Header</h1>
    </div>

    <!-- Tartalom -->
    <div
      class="bg-green-500 grid transition-all duration-300 flex-1"
      :class="isMenuOpen ? 'grid-cols-[200px,1fr]' : 'grid-cols-[50px,1fr]'"
    >
      <!-- Burger Menü -->
      <BurgerMenu class="burger-menu"
                  :isMenuOpen="isMenuOpen"
      />

      <!-- Fő Tartalom -->
      <div class="p-4">
        <router-view
          :isMenuOpen="isMenuOpen"
          @update:isMenuOpen="isMenuOpen = $event"
        />
      </div>

      <!-- Jobb oldali content -->
      <div class="fixed top-20 h-full right-0 w-64 bg-gray-500 p-4 shadow-lg">
        egyeb content
      </div>
    </div>
  </main>
</template>


<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import BurgerMenu from '@/components/layout/BurgerMenu.vue'

const packageVer = '0'
const gitHash = '0'
const isMenuOpen = ref(false)

onMounted(() => {
  console.log(`SGX-PC-1 client loaded v${packageVer} (${gitHash})`)
})

onBeforeUnmount(() => {
  console.log('Component unmounted')
})

</script>

<style src="./assets/tailwind.css">
.burger-menu {
  position: fixed;
  top: 10px;
  left: 10px;
  z-index: 1000;
}
</style>
