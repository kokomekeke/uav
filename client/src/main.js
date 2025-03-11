import { createApp } from 'vue'
import App from './App.vue'
import './assets/tailwind.css'
import router from './routes/index.js'
import { createPinia } from 'pinia'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.config.performance = true

app.mount('#app')
