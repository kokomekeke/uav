import { createApp } from 'vue'
import App from './App.vue'
import './assets/tailwind.css'
import router from './routes/index.js'

const app = createApp(App)

app.use(router)
app.config.performance = true

app.mount('#app')
