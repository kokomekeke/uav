<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  modelValue: Boolean
})

const emit = defineEmits(['update:modelValue'])

const isChecked = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const handleCheckboxChange = () => {
  isChecked.value = !isChecked.value
}
</script>

<template>
  <label class="flex items-center cursor-pointer select-none text-black dark:text-white">
    <div class="relative">
      <input
        type="checkbox"
        class="sr-only"
        @change="handleCheckboxChange"
      />
      <div
        :class="{ 'bg-slate-700': isChecked }"
        class="block h-8 rounded-full box bg-dark dark:bg-dark-2 w-14"
      ></div>
      <div
        :class="{ 'translate-x-full !bg-white dark:!bg-white': isChecked }"
        class="absolute flex items-center justify-center w-6 h-6 transition bg-white border-4 border-black rounded-full dot left-1 top-1 dark:bg-dark-5"
      ></div>
    </div>
  </label>
</template>

<style scoped>

</style>
