<script setup>
import { useRoute } from 'vue-router'
import { ref } from 'vue'
import ConfigPane from '@/views/config/ConfigPane.vue'

const route = useRoute()
const sensorId = route.params.id
const config = ref('')

</script>

<template>
    <config-pane></config-pane>
</template>
