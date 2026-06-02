import { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    component: () => import('pages/LoginPage.vue'),
  },
  {
    path: '/auth/callback',
    component: () => import('pages/AuthCallbackPage.vue'),
  },
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '',          component: () => import('pages/DashboardPage.vue') },
      { path: 'live',      component: () => import('pages/LivePage.vue') },
      { path: 'chart',     component: () => import('pages/ChartPage.vue') },
      { path: 'signals',   component: () => import('pages/SignalsPage.vue') },
      { path: 'backtest',  component: () => import('pages/BacktestPage.vue') },
      { path: 'settings',  component: () => import('pages/SettingsPage.vue') },
    ],
  },
  { path: '/:catchAll(.*)*', component: () => import('pages/ErrorNotFound.vue') },
]

export default routes
