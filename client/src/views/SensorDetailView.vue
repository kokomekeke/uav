<script setup>
import ConfigurationView from '@/views/config/ConfigurationView.vue'
import MapComponent from '@/components/map/MapComponent.vue'
</script>

<template>
  <div class="bg-slate-400 w-full max-h-screen p-6 flex flex-row rounded">
    <configuration-view class="flex-grow w-50"></configuration-view>
    <div class="grid grid-rows-3 bg-red-500 w-full h-full ml-6">
      <div class="bg-blue-500 row-span-3 z-10">
        <map-component></map-component>
      </div>
<!--      <div class="bg-yellow-300 h-5">Spektrum helye</div>-->
    </div>
  </div>
</template>
