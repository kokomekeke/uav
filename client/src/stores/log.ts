import {defineStore} from "pinia";
import {ref, watch} from "vue";

export const useLogStore = defineStore('log', () => {
  const logs = ref<string[]>([])

  watch(logs, (l) => {
    if (logs.value.length > 30) {
      logs.value.splice(0, logs.value.length - 30)
    }
  }, { deep: true })

  return { logs }
})
