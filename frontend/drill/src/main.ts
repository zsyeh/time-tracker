import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import HeatmapView from './views/HeatmapView.vue'
import PracticeView from './views/PracticeView.vue'
import QuestionView from './views/QuestionView.vue'
import PaperView from './views/PaperView.vue'
import './styles.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/practice' },
    { path: '/practice', name: 'practice', component: PracticeView },
    { path: '/practice/:uuid', name: 'question', component: QuestionView, props: true },
    { path: '/heatmap', name: 'heatmap', component: HeatmapView },
    { path: '/paper', name: 'paper', component: PaperView },
  ],
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition || { top: 0 }
  },
})

createApp(App).use(router).mount('#app')
