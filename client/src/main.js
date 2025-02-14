import { createApp } from 'vue'
import { createVfm } from 'vue-final-modal'
import App from './App.vue'
import './assets/styles/index.css'
import './assets/tailwind.css'

// createApp(App).mount('#app')

const app = createApp(App)

const vfm = createVfm()
app.use(vfm).mount('#app')

app.component(
  'BurgerMenu'
)
