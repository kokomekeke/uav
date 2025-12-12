<template>
  <div class="font-mono bg-gradient-to-tr from-emerald-300 to-sgx-accent-blue
  dark:bg-gradient-to-tr dark:from-sgx-dark-blue dark:via-sgx-dark-blue dark:to-red-500">

    <SgxHeader
      :isMenuOpen="isMenuOpen"
      :isDark="isDark"
      @toggle-dark="handleToggleDark"
      class="fixed top-0 left-0 right-0 h-24 z-50 bg-gradient-to-tr from-emerald-300 to-sgx-accent-blue
             dark:bg-gradient-to-br dark:from-sgx-dark-blue dark:via-sgx-dark-blue/90 dark:to-red-500/60"
    />

    <div class="fixed top-24 left-0 right-0 h-20 pointer-events-none z-40
                bg-gradient-to-r from-emerald-300/10 via-transparent to-transparent
                dark:from-sgx-dark-blue/10 dark:via-transparent dark:to-transparent">
    </div>

    <main class="min-h-screen flex md:flex-row text-gray-200 pt-24 overflow-y-auto">
      <BurgerMenu
        :isMenuOpen="isMenuOpen"
        @update:isMenuOpen="isMenuOpen = $event"
        :class="[
          'overflow-auto transition-all duration-300',
          isMenuOpen ? 'fixed top-24 bottom-0 left-0 w-72 z-[65]' : 'relative w-1'
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import BurgerMenu from '@/components/layout/BurgerMenu.vue'
import SgxHeader from '@/components/layout/SgxHeader.vue'
import Content from '@/components/layout/Content.vue'
import 'leaflet/dist/leaflet.css'
import { useDark } from '@vueuse/core'

const packageVer = '0'
const gitHash = '0'
const isMenuOpen = ref(false)

const isDark = useDark()

const handleToggleDark = () => {
  isDark.value = !isDark.value
}

watch(isDark, (newVal) => {
  console.log('Dark mode:', newVal)
})

watch(isMenuOpen, (n) => {
  console.log('side menu new value: ', n)
})

onMounted(() => {
  console.log(`SGX-PC-1 client loaded v${packageVer} (${gitHash})`)
})

onBeforeUnmount(() => {
  console.log('Component unmounted')
})

</script>
