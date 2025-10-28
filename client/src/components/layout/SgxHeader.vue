<script setup>
import SgxSwitchButton from '@/components/common/SgxSwitchButton.vue'
import router from '@/routes'

const props = defineProps({
  isMenuOpen: Boolean,
  isDark: Boolean
})

const emit = defineEmits(['toggle-dark'])

const toHome = () => {
  router.push({ path: '/' })
}
</script>

<template>
  <div
    class="sticky top-0 px-6 py-5 w-full h-20
           text-center text-2xl bg-inherit transition-all duration-300"
    :class="{ 'shadow-inner': isMenuOpen }"
    v-bind="$attrs"
  >
    <div class="flex flex-row items-center justify-between w-full">
      <div class="w-32"></div>
      <h1 class="p-5 font-bold tracking-widest text-cyan-300 select-none text-center" @click="toHome">
        LENA_ALTISS
      </h1>
      <div class="w-32 flex justify-end">
        <SgxSwitchButton
          class="mr-4"
          :modelValue="props.isDark"
          @update:modelValue="emit('toggle-dark')"
        />
      </div>
    </div>

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
