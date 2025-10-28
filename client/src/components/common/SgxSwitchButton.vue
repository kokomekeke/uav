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
  <label
    class="relative inline-flex items-center cursor-pointer select-none"
  >
    <input
      type="checkbox"
      class="sr-only peer"
      @change="handleCheckboxChange"
      :checked="isChecked"
    />

    <!-- háttér -->
    <div
      class="
        w-14 h-8 rounded-full
        transition-colors duration-300 ease-in-out
        bg-emerald-300 dark:bg-dark-3
        peer-checked:bg-sgx-deep-blue
        shadow-inner
      "
    ></div>

    <!-- pötty -->
    <div
      class="
        absolute left-1 top-1 w-6 h-6
        bg-sgx-accent-blue dark:bg-dark-5
        border border-gray-400 dark:border-gray-700
        rounded-full shadow-md
        transition-all duration-300 ease-in-out
        peer-checked:translate-x-6
      "
    ></div>
  </label>
</template>

<style scoped>

</style>
