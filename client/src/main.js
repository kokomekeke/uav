import { createApp } from 'vue'
import { createVfm } from 'vue-final-modal'
import App from './App.vue'

// createApp(App).mount('#app')

const app = createApp(App)

const vfm = createVfm()
app.use(vfm).mount('#app')

app.component(
  'BurgerMenu'
)
