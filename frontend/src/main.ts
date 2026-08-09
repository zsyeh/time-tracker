import { createApp } from 'vue'
import {
  ElAlert, ElButton, ElCheckbox, ElDialog, ElDrawer, ElDropdown, ElDropdownItem,
  ElDropdownMenu, ElEmpty, ElForm, ElFormItem, ElIcon, ElInput, ElInputNumber,
  ElLoading, ElOption, ElPagination, ElProgress, ElRate, ElSelect, ElSlider, ElTag,
} from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import './styles.css'

const app = createApp(App)
const components = [
  ElAlert, ElButton, ElCheckbox, ElDialog, ElDrawer, ElDropdown, ElDropdownItem,
  ElDropdownMenu, ElEmpty, ElForm, ElFormItem, ElIcon, ElInput, ElInputNumber,
  ElOption, ElPagination, ElProgress, ElRate, ElSelect, ElSlider, ElTag,
]
components.forEach((component) => app.component(component.name!, component))
app.use(ElLoading)
app.mount('#app')
