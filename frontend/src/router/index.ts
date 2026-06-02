import { route } from 'quasar/wrappers'
import { createRouter, createMemoryHistory, createWebHistory, createWebHashHistory } from 'vue-router'
import routes from './routes'

export default route(function () {
  const createHistory = process.env.SERVER
    ? createMemoryHistory
    : (process.env.VUE_ROUTER_MODE === 'history' ? createWebHistory : createWebHashHistory)

  const router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(process.env.VUE_ROUTER_BASE),
  })

  // ── Guard de autenticação ────────────────────────────────────────────────
  // Importação lazy para evitar circular dep (Pinia ainda não inicializado no boot)
  router.beforeEach(async (to) => {
    // Rotas públicas — sempre acessíveis
    const publicPaths = ['/login', '/auth/callback']
    if (publicPaths.some(p => to.path.startsWith(p))) return true

    // Rotas protegidas — verifica token no localStorage
    const raw = localStorage.getItem('deriv_account')
    const account = raw ? JSON.parse(raw) : null
    const isLoggedIn = !!account?.token

    if (to.meta.requiresAuth && !isLoggedIn) {
      return { path: '/login' }
    }

    return true
  })

  return router
})
