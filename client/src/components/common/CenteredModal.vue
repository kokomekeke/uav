<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed inset-0 z-[9999] flex items-center justify-center backdrop-blur-sm bg-black bg-opacity-70"
    >
      <div class="rounded-2xl shadow-2xl p-6 w-full max-w-3xl relative bg-cyan-100 border-cyan-900 border-2 dark:bg-slate-900 dark:border-cyan-700 ">
        <!-- SgxHeader -->
        <div class="flex justify-between items-center border-b-2 border-slate-700 pb-3 mb-4">
          <slot name="header"></slot>
          <button
            class="text-gray-900 hover:text-cyan-500 dark:text-gray-400 dark:hover:text-cyan-400 transition"
            @click="$emit('close')"
          >
            ✖
          </button>
        </div>

        <!-- Body -->
        <div class="max-h-[70vh] overflow-y-auto text-gray-200">
          <slot name="body"></slot>
        </div>

        <!-- Footer / Submit -->
        <div v-if="$slots.submit" class="mt-6 border-t-2 border-slate-700 pt-3 flex flex-wrap gap-2 justify-end">
          <slot name="submit"></slot>
        </div>

        <!-- Alert -->
        <div v-if="$slots.alert" class="mt-4">
          <slot name="alert"></slot>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  show: Boolean
})
defineEmits(['close'])
</script>
