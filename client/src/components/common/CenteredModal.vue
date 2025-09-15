<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed inset-0 z-[9999] flex items-center justify-center bg-black bg-opacity-70 backdrop-blur-sm"
    >
      <div class="bg-slate-900 border border-cyan-700 rounded-2xl shadow-2xl p-6 w-full max-w-3xl relative">
        <!-- Header -->
        <div class="flex justify-between items-center border-b border-slate-700 pb-3 mb-4">
          <slot name="header"></slot>
          <button
            class="text-gray-400 hover:text-cyan-400 transition"
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
        <div v-if="$slots.submit" class="mt-6 border-t border-slate-700 pt-3 flex flex-wrap gap-2 justify-end">
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