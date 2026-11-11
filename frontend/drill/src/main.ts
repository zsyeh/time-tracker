import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import HeatmapView from './views/HeatmapView.vue'
import ActivityView from './views/ActivityView.vue'
import BookActivityView from './views/BookActivityView.vue'
import PracticeView from './views/PracticeView.vue'
import QuestionView from './views/QuestionView.vue'
import PapersView from './views/PapersView.vue'
import PaperNewView from './views/PaperNewView.vue'
import PaperExamView from './views/PaperExamView.vue'
import PaperReviewView from './views/PaperReviewView.vue'
import CollectionView from './views/CollectionView.vue'
import FeelView from './views/FeelView.vue'
import InsightView from './views/InsightView.vue'
import ErrataView from './views/ErrataView.vue'
import EiCockpitView from './views/EiCockpitView.vue'
import CircuitSelectedView from './views/CircuitSelectedView.vue'
import SignalSelectedView from './views/SignalSelectedView.vue'
import SignalFormulaReviewView from './views/SignalFormulaReviewView.vue'
import AnalogSelectedView from './views/AnalogSelectedView.vue'
import DigitalSelectedView from './views/DigitalSelectedView.vue'
import CommunicationSelectedView from './views/CommunicationSelectedView.vue'
import PdfPageStatusView from './views/PdfPageStatusView.vue'
import DiagnosticDashboardView from './views/DiagnosticDashboardView.vue'
import ProgressView from './views/ProgressView.vue'
import DiagnosticQueueView from './views/DiagnosticQueueView.vue'
import NotFoundView from './views/NotFoundView.vue'
import { initializeUiPreferences } from './lib/uiPreferences'
import { routerBase } from './lib/runtimePath'
import './styles.css'

const router = createRouter({
  history: createWebHistory(routerBase),
  routes: [
    { path: '/', redirect: '/practice' },
    { path: '/practice', name: 'practice', component: PracticeView },
    { path: '/progress', name: 'progress', component: ProgressView },
    { path: '/practice/:uuid', name: 'question', component: QuestionView, props: true },
    { path: '/diagnostics', name: 'diagnostics', component: DiagnosticDashboardView },
    { path: '/diagnostic-queue', name: 'diagnostic-queue', component: DiagnosticQueueView },
    { path: '/heatmap', name: 'heatmap', component: HeatmapView },
    { path: '/selected-heatmap', name: 'selected-heatmap', component: HeatmapView, props: { selectedOnly: true } },
    { path: '/activity', name: 'activity', component: ActivityView },
    { path: '/book-activity', name: 'book-activity', component: BookActivityView },
    { path: '/paper', redirect: '/papers/new' },
    { path: '/papers', name: 'papers', component: PapersView },
    { path: '/papers/new', name: 'paper-new', component: PaperNewView },
    { path: '/papers/:uuid', name: 'paper-exam', component: PaperExamView, props: true },
    { path: '/papers/:uuid/review', name: 'paper-review', component: PaperReviewView, props: true },
    { path: '/favorites', name: 'favorites', component: CollectionView, props: { kind: 'favorite' } },
    { path: '/review-later', name: 'review-later', component: CollectionView, props: { kind: 'review_later' } },
    { path: '/feel', name: 'feel', component: FeelView },
    { path: '/insight', name: 'insight', component: InsightView },
    { path: '/errata', name: 'errata', component: ErrataView },
    { path: '/cockpit', name: 'cockpit', component: EiCockpitView },
    { path: '/circuit-selected', name: 'circuit-selected', component: CircuitSelectedView },
    { path: '/signal-selected', name: 'signal-selected', component: SignalSelectedView },
    { path: '/signal-formulas', name: 'signal-formulas', component: SignalFormulaReviewView },
    { path: '/analog-selected', name: 'analog-selected', component: AnalogSelectedView },
    { path: '/digital-selected', name: 'digital-selected', component: DigitalSelectedView },
    { path: '/communication-selected', name: 'communication-selected', component: CommunicationSelectedView },
    { path: '/selected-pdf-pages', name: 'selected-pdf-pages', component: PdfPageStatusView },
    { path: '/core-heatmap', name: 'core-heatmap', component: HeatmapView, props: { selectedOnly: true, coreOnly: true } },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundView },
  ],
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition || { top: 0 }
  },
})

initializeUiPreferences()
createApp(App).use(router).mount('#app')
