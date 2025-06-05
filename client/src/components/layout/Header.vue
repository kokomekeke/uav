<script setup>
defineProps({
  isMenuOpen: Boolean
})

</script>
<template>
  <div
    class="z-999 sticky top-0 px-4 py-6 w-full h-20 bg-slate-500 border-b-cyan-950
         text-center border-b-4 font-mono uppercase text-2xl text-black font-[1000] tracking-wide
         shadow-inset-red transition-all duration-300 overflow-hidden"
    :class="{ 'shadow-left-inset': isMenuOpen }"

    style="background-image: url('https://www.transparenttextures.com/patterns/asfalt-dark.png');
           text-shadow: -1px -1px 0 rgb(70, 70, 70), 1px -1px 0 rgb(70, 70, 70),
                        -1px 1px 0 rgb(70, 70, 70), 1px 1px 0 rgb(70, 70, 70);"
  >
    <h1>CLIENT SOFTWARE</h1>
  </div>
</template>


<style scoped>
.shadow-left-inset {
  box-shadow: inset 10px 0 10px -5px rgba(0, 0, 0, 0.8);
}
</style>