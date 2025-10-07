<template>
  <div class="flex md:flex-col font-mono bg-gradient-to-tr from-sgx-accent-light-blue to-sgx-accent-blue">
    <Header
      @click="toHome"
      :isMenuOpen="isMenuOpen"
      class="basis-24"
    />
    <main class="min-h-screen flex md:flex-row text-gray-200">
      <BurgerMenu
        :class="[
          'h-full overflow-auto transition-all duration-300',
          isMenuOpen ? 'fixed top-0 left-0 w-72 z-[9999]' : 'relative w-1'
        ]"
      />
      <Content
          :isMenuOpen="isMenuOpen"
          @update:isMenuOpen="isMenuOpen = $event"
          class="transition-all duration-300 flex-1"
          :class="isMenuOpen ? 'ml-72' : 'ml-0'"
        />
    </main>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import BurgerMenu from '@/components/layout/BurgerMenu.vue'
import router from '@/routes'
import Header from '@/components/layout/Header.vue'
import Content from '@/components/layout/Content.vue'
import 'leaflet/dist/leaflet.css'
import { useDark } from '@vueuse/core'

const packageVer = '0'
const gitHash = '0'
const isMenuOpen = ref(false)
const isDark = useDark()

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

</style>
