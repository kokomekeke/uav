import { createWebHistory, createRouter } from 'vue-router'

import SensorView from '../views/SensorDetailView.vue'
import HomeView from '@/views/HomeView.vue'

const routes = [
  { path: '/', component: HomeView },
  { path: '/sensor/:id', component: SensorView }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
