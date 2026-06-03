/**
 * Service Worker customizado do ANAGRAPH PWA.
 * Estende o service worker gerado pelo Workbox.
 *
 * Funcionalidades:
 * - Notifica o app quando uma nova versão está disponível
 * - Skip waiting automático (atualiza sem precisar fechar o app)
 * - Precaching de todos os assets do shell
 */

import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { clientsClaim } from 'workbox-core'

declare const self: ServiceWorkerGlobalScope & typeof globalThis

// Assume o controle imediatamente (sem esperar fechar todas as abas)
self.skipWaiting()
clientsClaim()

// Remove caches de versões antigas
cleanupOutdatedCaches()

// Precache dos assets injetados pelo Quasar/Vite (lista gerada no build)
precacheAndRoute(self.__WB_MANIFEST)

// Notifica o app quando uma nova versão está instalada
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})
