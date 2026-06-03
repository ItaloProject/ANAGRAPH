import { register } from 'register-service-worker'

register(process.env.SERVICE_WORKER_FILE as string, {
  ready () {
    console.log('[ANAGRAPH PWA] Service worker ativo — modo offline disponível.')
  },

  registered () {
    console.log('[ANAGRAPH PWA] Service worker registrado.')
  },

  cached () {
    console.log('[ANAGRAPH PWA] Assets em cache — app disponível offline.')
  },

  updatefound () {
    console.log('[ANAGRAPH PWA] Nova versão disponível, baixando...')
  },

  updated () {
    console.log('[ANAGRAPH PWA] Nova versão pronta. Recarregando...')
    // Recarrega automaticamente ao detectar nova versão
    window.location.reload()
  },

  offline () {
    console.warn('[ANAGRAPH PWA] Sem conexão — usando cache local.')
  },

  error (err) {
    console.error('[ANAGRAPH PWA] Erro no service worker:', err)
  },
})
