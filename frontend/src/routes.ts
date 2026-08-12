import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/today' },
  { path: '/today', name: 'today', component: () => import('./views/TodayView.vue') },
  { path: '/trends', name: 'trends', component: () => import('./views/TrendsView.vue') },
  { path: '/sessions', name: 'sessions', component: () => import('./views/HistoryView.vue') },
  {
    path: '/sessions/:uuid',
    name: 'session-detail',
    component: () => import('./views/SessionDetailView.vue'),
    props: true,
  },
  { path: '/issues', name: 'issues', component: () => import('./views/IssuesView.vue') },
  { path: '/settings', name: 'settings', component: () => import('./views/SettingsView.vue') },
  {
    path: '/share/:token',
    name: 'public-share',
    component: () => import('./views/PublicShareView.vue'),
    props: true,
    meta: { public: true },
  },
]
