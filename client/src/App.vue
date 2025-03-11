<template>
<!--  <main class="bg-green-500 min-h-screen flex flex-row">-->
  <main class="bg-green-500 min-h-screen grid grid-cols-7">
    <div class="sticky top-0 px-4 py-6 col-span-7 w-full h-20 bg-gray-300 border-gray-800 p-4 text-center border-2 rounded font-mono uppercase text-lg text-black font-stretch-extra-expanded font-bold">
      <h1>App Header</h1>
    </div>
    <div class="bg-green-500 grid grid-cols-7 flex-1">
      <BurgerMenu class="burger-menu col-span-1"
                  :isMenuOpen="isMenuOpen"
      />
      <div
        class="flex flex-col transition-all duration-300 place-content-center"
        :class="isMenuOpen ? 'grid-cols-[250px,1fr]' : 'grid-cols-[60px,1fr]'"
      >
        <router-view
          :isMenuOpen="isMenuOpen"
          @update:isMenuOpen="isMenuOpen = $event"
        />
      </div>
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
