<template>
  <main class="bg-slate-900 min-h-screen flex flex-col font-mono text-gray-200">
    <Header
      @click="toHome"
      :isMenuOpen="isMenuOpen"
      class="z-50 transition-all duration-300"
    />
    <div class="flex flex-row flex-1">
      <BurgerMenu class="burger-menu max-h-screen overflow-auto z-[9999]" :isMenuOpen="isMenuOpen" />
      <Content
        :isMenuOpen="isMenuOpen"
        @update:isMenuOpen="isMenuOpen = $event"
        class="transition-all duration-300 flex-1"
        :class="isMenuOpen ? 'ml-72' : 'ml-0'"
      />
    </div>
  </main>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import BurgerMenu from '@/components/layout/BurgerMenu.vue'
import router from '@/routes'
import Header from '@/components/layout/Header.vue'
import Content from '@/components/layout/Content.vue'
import 'leaflet/dist/leaflet.css'

const packageVer = '0'
const gitHash = '0'
const isMenuOpen = ref(false)

onMounted(() => {
  console.log(`SGX-PC-1 client loaded v${packageVer} (${gitHash})`)
})

onBeforeUnmount(() => {
  console.log('Component unmounted')
})

const toHome = () => {
  router.push({ path: '/' })
}
</script>

<style src="./assets/tailwind.css">
.burger-menu {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1000;
}
</style>
