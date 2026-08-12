import { createApp } from 'vue'
import { ElLoading } from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import { elementComponents } from './elementComponents'
import router from './router'
import './styles.css'

const app = createApp(App)
elementComponents.forEach((component) => app.component(component.name!, component))
app.use(ElLoading)
app.use(router)
router.isReady().then(() => app.mount('#app'))
