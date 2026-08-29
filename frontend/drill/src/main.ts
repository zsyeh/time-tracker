import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import HeatmapView from './views/HeatmapView.vue'
import ActivityView from './views/ActivityView.vue'
import PracticeView from './views/PracticeView.vue'
import QuestionView from './views/QuestionView.vue'
import PaperView from './views/PaperView.vue'
import CollectionView from './views/CollectionView.vue'
import FeelView from './views/FeelView.vue'
import InsightView from './views/InsightView.vue'
import './styles.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/practice' },
    { path: '/practice', name: 'practice', component: PracticeView },
    { path: '/practice/:uuid', name: 'question', component: QuestionView, props: true },
    { path: '/heatmap', name: 'heatmap', component: HeatmapView },
    { path: '/activity', name: 'activity', component: ActivityView },
    { path: '/paper', name: 'paper', component: PaperView },
    { path: '/favorites', name: 'favorites', component: CollectionView, props: { kind: 'favorite' } },
    { path: '/review-later', name: 'review-later', component: CollectionView, props: { kind: 'review_later' } },
    { path: '/feel', name: 'feel', component: FeelView },
    { path: '/insight', name: 'insight', component: InsightView },
  ],
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition || { top: 0 }
  },
})

createApp(App).use(router).mount('#app')
