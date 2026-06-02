/**
 * Sincroniza com o servidor quando o app está em segundo plano (aba minimizada / celular).
 * O robô opera no backend — este boot só mantém a UI atualizada ao voltar.
 */
import { boot } from 'quasar/wrappers'
import { useBotStore } from '../stores/bot'

const SYNC_VISIBLE_MS = 120_000
const SYNC_HIDDEN_MS  = 45_000

export default boot(() => {
  const botStore = useBotStore()
  let syncTimer: ReturnType<typeof setInterval> | null = null

  function scheduleSync() {
    if (syncTimer) clearInterval(syncTimer)
    const interval = document.hidden ? SYNC_HIDDEN_MS : SYNC_VISIBLE_MS
    syncTimer = setInterval(() => {
      botStore.syncFromBackend()
      if (botStore.running) botStore.fetchAccountStatus()
    }, interval)
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      botStore.syncFromBackend()
      botStore.connectBackend()
      botStore.fetchAccountStatus()
    }
    scheduleSync()
  })

  window.addEventListener('focus', () => {
    botStore.syncFromBackend()
    botStore.connectBackend()
  })

  window.addEventListener('online', () => {
    botStore.checkBackend()
    botStore.connectBackend()
  })

  botStore.requestNotificationPermission()
  scheduleSync()
})
