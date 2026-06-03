/*
 * Registro do Service Worker do ANAGRAPH PWA.
 * Usa a API nativa do browser (sem dependência externa).
 */

if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register(
        `${process.env.SERVICE_WORKER_FILE ?? '/sw.js'}`,
        { scope: '/' },
      )

      reg.addEventListener('updatefound', () => {
        const newSW = reg.installing
        if (!newSW) return

        newSW.addEventListener('statechange', () => {
          if (newSW.state === 'installed' && navigator.serviceWorker.controller) {
            // Nova versão disponível — recarrega automaticamente
            console.log('[ANAGRAPH PWA] Nova versão disponível. Atualizando...')
            window.location.reload()
          }
        })
      })

      console.log('[ANAGRAPH PWA] Service worker registrado:', reg.scope)
    } catch (err) {
      console.error('[ANAGRAPH PWA] Erro ao registrar service worker:', err)
    }
  })
}
