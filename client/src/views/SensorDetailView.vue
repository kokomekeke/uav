<script setup>
import { useRoute } from 'vue-router'
import { ref } from 'vue'
import ConfigPane from '@/views/config/ConfigPane.vue'

const route = useRoute()
const sensorId = route.params.id
const config = ref('')

</script>

<template>
<!--  <div class="p-6">-->
<!--    <p>config 1:</p>-->
<!--    <label>config 1:</label>-->
<!--    <input v-model="config">-->
<!--    <p> {{ config }}</p>-->
<!--    <p> {{ sensorId }} </p>-->
    <config-pane></config-pane>
<!--  </div>-->
</template>
