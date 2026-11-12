import '../shared/design/tokens.css'
import '../shared/design/controls.css'
import { createApp } from 'vue'
import { ElLoading } from 'element-plus'
import './elementStyles'
import App from './App.vue'
import { elementComponents } from './elementComponents'
import router from './router'
import { initializeUiPreferences } from './lib/uiPreferences'
import '../shared/design/element-adapter.css'
import './styles.css'

initializeUiPreferences()
const app = createApp(App)
elementComponents.forEach((component) => app.component(component.name!, component))
app.use(ElLoading)
app.use(router)
router.isReady().then(() => app.mount('#app'))
