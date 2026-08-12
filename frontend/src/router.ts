import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './routes'

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition || { top: 0 }
  },
})
