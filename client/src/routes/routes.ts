import HomeView from '@/views/HomeView.vue'

export default [
  {
    path: '/',
    name: 'Home',
    component: HomeView
  },
  {
    path: '/sensor/:id',
    name: 'Sensor',
    component: () => import('@/views/SensorDetailView.vue')
  }
]
