<script setup>
import ConfigurationView from '@/views/config/ConfigurationView.vue'
import MapComponent from '@/components/map/MapComponent.vue'
</script>

<template>
  <!--
    FONTOS:
    - pt-20: "kitolja" a tartalmat a sticky header alól (ha a header h-20).
    - min-h-screen: legalább a viewport magasságát foglalja el, de nem fixeli a belső görgetést.
    - px-6 pb-6: kis belső margó a jobb/oldalaknak, de a top már pt-20.
  -->
  <div class="flex flex-row gap-6 w-full min-h-screen pt-20 px-6 pb-6 bg-slate-900 text-gray-100">
    <!-- Left panel: belső görgetés, így nem lóghat a header fölé -->
    <div class="flex-1 bg-slate-800 rounded-2xl shadow-lg p-4 border border-slate-700 overflow-auto">
      <!-- configuration-view maga is magas tartalmat tartalmazhat, így legyen w-full (de a scroll a panelen belül lesz) -->
      <configuration-view class="w-full"></configuration-view>
    </div>

    <!-- Right panel: a map + vezérlők együtt, a panel belső görgetése megakadályozza, hogy a tartalom a header fölé lógjon -->
    <div class="flex-[2] bg-slate-800 rounded-2xl shadow-lg p-4 border border-slate-700 overflow-auto flex flex-col">
      <!-- Map komponens: töltsön ki annyi magasságot, amennyit a panel enged (flex-1) -->
      <div class="flex-1 overflow-hidden rounded-xl">
        <map-component class="w-full h-full"></map-component>
      </div>

      <!-- Ha van kontrollsáv a map komponensen kívül, itt helyezd el.
           Mivel a jobb panel overflow-auto, ezek is belsőleg görgethetők. -->
      <!-- Példa: ha a map komponens már tartalmazza a vezérlőket, akkor ez a blokk üres lehet. -->
      <!--
      <div class="mt-4">
        <controls-component />
      </div>
      -->
    </div>
  </div>
</template>

<style scoped>
/* nincs speciális stílus szükség erre a fájlra */
</style>


