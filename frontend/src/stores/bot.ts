import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { botApi, BotWebSocket, type BotConfig } from '../services/botApi'
import { useMarketStore } from './market'
import {
  setUsdBrlRate, usdToBrl, formatUsdAsBrl, formatBrl, getUsdBrlRate,
} from '../utils/currency'

export interface TradeRecord {
  id: string
  signal: string
  asset: string
  stake: number
  confidence: number
  reason: string
  status: 'OPEN' | 'WIN' | 'LOSS' | 'ERROR'
  pnl: number
  payout: number
  entry_price: number
  expires_at: number | null
  opened_at: string
  closed_at: string | null
  duration: string
  contract_type: string
}

export interface BotStats {
  date: string
  pnl: number
  wins: number
  losses: number
  trades: number
  accuracy: number
  open_positions: number
  current_streak: number
  daily_limit_used: number
}

export interface AdaptiveState {
  min_confidence: number
  min_score: number
  win_rate_window: number
  regime: 'neutral' | 'reward' | 'caution' | 'danger'
  adjustments: number
  window_trades: number
  window_size: number
}

export interface MtfState {
  h1_bias: string
  h4_bias: string
  candles_h1: number
  candles_h4: number
}

export interface BotSnapshot {
  running?: boolean
  stats?: BotStats
  trades_list?: TradeRecord[]
  last_signal?: Record<string, unknown>
  current_price?: number
  asset?: string
  contract_duration?: number
  adaptive?: AdaptiveState
  mtf?: MtfState
}

function normalizeTrade(data: Record<string, unknown>): TradeRecord {
  return {
    entry_price: 0,
    expires_at: null,
    contract_type: data.signal === 'BUY' ? 'RISE' : 'FALL',
    ...data,
  } as TradeRecord
}

export const useBotStore = defineStore('bot', () => {
  const market = useMarketStore()

  const running       = ref(false)
  const connected     = ref(false)
  const backendOnline = ref(false)
  const lastSyncAt    = ref<string>('')
  const trades        = ref<TradeRecord[]>([])
  const lastSignal    = ref<Record<string, unknown> | null>(null)
  const stats         = ref<BotStats>({
    date: '', pnl: 0, wins: 0, losses: 0, trades: 0,
    accuracy: 0, open_positions: 0, current_streak: 0, daily_limit_used: 0,
  })

  const adaptive = ref<AdaptiveState>({
    min_confidence: 78, min_score: 5, win_rate_window: 0,
    regime: 'neutral', adjustments: 0, window_trades: 0, window_size: 30,
  })
  const mtf = ref<MtfState>({ h1_bias: 'NEUTRAL', h4_bias: 'NEUTRAL', candles_h1: 0, candles_h4: 0 })

  const accountBalance   = ref<number | null>(null)
  const accountLoadFailed = ref(false)
  const accountCurrency  = ref('USD')
  const accountLoginId   = ref('')
  const accountIsDemo    = ref(true)
  const openContracts    = ref(0)

  let ws: BotWebSocket | null = null
  const notifiedTradeIds = new Set<string>()

  async function requestNotificationPermission() {
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (Notification.permission === 'default') {
      try { await Notification.requestPermission() } catch { /* ignore */ }
    }
  }

  function notifyTradeIfBackground(trade: TradeRecord) {
    if (typeof document === 'undefined' || document.visibilityState === 'visible') return
    if (!('Notification' in window) || Notification.permission !== 'granted') return
    if (notifiedTradeIds.has(trade.id)) return
    notifiedTradeIds.add(trade.id)

    const isWin = trade.status === 'WIN'
    const pnlBrl = formatBrl(usdToBrl(trade.pnl))
    try {
      new Notification(isWin ? 'ANAGRAPH — GANHOU' : 'ANAGRAPH — PERDEU', {
        body: `${trade.signal} · ${pnlBrl}`,
        icon: '/favicon.ico',
        tag: trade.id,
      })
    } catch { /* Safari/iOS */ }
  }

  function recomputeStatsFromTrades(): BotStats {
    const closed = trades.value.filter(t => t.status === 'WIN' || t.status === 'LOSS')
    const wins = closed.filter(t => t.status === 'WIN')
    const losses = closed.filter(t => t.status === 'LOSS')
    const pnl = closed.reduce((s, t) => s + (t.pnl || 0), 0)
    const total = wins.length + losses.length
    const openCount = trades.value.filter(t => t.status === 'OPEN').length
    return {
      date: stats.value.date || new Date().toISOString().slice(0, 10),
      pnl: Math.round(pnl * 100) / 100,
      wins: wins.length,
      losses: losses.length,
      trades: closed.length + openCount,
      accuracy: total ? Math.round((wins.length / total) * 1000) / 10 : 0,
      open_positions: openCount,
      current_streak: stats.value.current_streak,
      daily_limit_used: stats.value.daily_limit_used,
    }
  }

  const displayStats = computed((): BotStats => {
    const backend = stats.value
    const derived = recomputeStatsFromTrades()
    const backendHasActivity = (backend.wins + backend.losses) > 0 || backend.pnl !== 0
    if (backendHasActivity) return backend
    if (derived.wins + derived.losses > 0 || derived.pnl !== 0) return derived
    return backend
  })

  const displayStatsBrl = computed((): BotStats => {
    const s = displayStats.value
    return { ...s, pnl: usdToBrl(s.pnl) }
  })

  async function fetchCurrencyConfig() {
    try {
      const res = await botApi.currencyConfig()
      setUsdBrlRate(res.data.usd_brl_rate as number)
    } catch { /* usa cotação padrão */ }
  }

  function applySnapshot(data: BotSnapshot) {
    if (data.running !== undefined) running.value = data.running
    if (data.stats) stats.value = data.stats
    if (Array.isArray(data.trades_list)) {
      trades.value = data.trades_list.map(t => normalizeTrade(t as unknown as Record<string, unknown>))
    } else if (data.running === false) {
      trades.value = []
    }
    if (data.last_signal && Object.keys(data.last_signal).length > 0) {
      lastSignal.value = data.last_signal
      market.updateIndicators(data.last_signal)
    }
    if (data.adaptive) adaptive.value = data.adaptive
    if (data.mtf) mtf.value = data.mtf
    if (data.current_price && data.current_price > 0) {
      if (data.asset) market.setActiveAsset(data.asset)
      market.applyTick(data.current_price, Math.floor(Date.now() / 1000))
    }
    lastSyncAt.value = new Date().toLocaleTimeString('pt-BR')
  }

  function connectBackend() {
    if (ws) return
    ws = new BotWebSocket((event, data) => {
      connected.value = true
      backendOnline.value = true
      _handleEvent(event, data as Record<string, unknown>)
    })
    ws.connect()
  }

  function disconnectBackend() {
    ws?.disconnect()
    ws = null
    connected.value = false
  }

  function _handleEvent(event: string, data: Record<string, unknown>) {
    if (event === 'tick') {
      market.applyTick(data.price as number, data.epoch as number)
      return
    }
    if (event === 'signal') {
      lastSignal.value = data
      market.updateIndicators(data)
      return
    }
    if (event === 'trade') {
      const normalized = normalizeTrade(data)
      const idx = trades.value.findIndex(t => t.id === normalized.id)
      if (idx >= 0) trades.value[idx] = normalized
      else trades.value.unshift(normalized)
      if (normalized.status === 'WIN' || normalized.status === 'LOSS') {
        notifyTradeIfBackground(normalized)
        fetchAccountStatus()
      }
      return
    }
    if (event === 'stats') {
      stats.value = data as unknown as BotStats
      return
    }
    if (event === 'status') {
      applySnapshot(data as BotSnapshot)
      return
    }
  }

  async function fetchDailyStats() {
    try {
      const res = await botApi.dailyStats()
      const data = res.data as { stats?: BotStats; trades_list?: TradeRecord[] }
      if (data.stats && (data.stats.wins + data.stats.losses > 0 || data.stats.pnl !== 0)) {
        if ((stats.value.wins + stats.value.losses) === 0 && stats.value.pnl === 0) {
          stats.value = data.stats
        }
        if (Array.isArray(data.trades_list) && trades.value.length === 0) {
          trades.value = data.trades_list.map(t =>
            normalizeTrade(t as unknown as Record<string, unknown>)
          )
        }
      }
    } catch { /* offline */ }
  }

  async function syncFromBackend() {
    try {
      const res = await botApi.status()
      backendOnline.value = true
      applySnapshot(res.data as BotSnapshot)
      running.value = !!res.data?.running
      if ((stats.value.wins + stats.value.losses) === 0 && stats.value.pnl === 0) {
        await fetchDailyStats()
      }
    } catch {
      backendOnline.value = false
    }
  }

  async function reconcileTrades() {
    try {
      const res = await botApi.reconcile()
      if (res.data?.error) return false
      applySnapshot(res.data as BotSnapshot)
      return true
    } catch {
      return false
    }
  }

  async function startBot(config: BotConfig) {
    try {
      await botApi.start(config)
      running.value = true
      await syncFromBackend()
    } catch {
      throw new Error('Falha ao iniciar bot: verifique se o backend está rodando')
    }
  }

  async function stopBot() {
    try {
      await botApi.stop()
      running.value = false
      trades.value = []
      stats.value = {
        date: '', pnl: 0, wins: 0, losses: 0, trades: 0,
        accuracy: 0, open_positions: 0, current_streak: 0, daily_limit_used: 0,
      }
    } catch {
      running.value = false
    }
  }

  async function fetchAccountStatus() {
    try {
      const res = await botApi.accountStatus()
      applyAccount(res.data)
      accountLoadFailed.value = false
    } catch {
      accountLoadFailed.value = true
      try {
        const res = await botApi.health()
        if (res.data?.account) {
          applyAccount(res.data.account)
          accountLoadFailed.value = false
        }
      } catch { /* offline */ }
    }
  }

  function applyAccount(d: Record<string, unknown>) {
    accountBalance.value  = (d.balance as number) ?? null
    accountCurrency.value = (d.currency as string) ?? 'USD'
    accountLoginId.value  = (d.loginid as string) ?? ''
    accountIsDemo.value   = (d.is_demo as boolean) ?? true
    openContracts.value   = (d.open_contracts as number) ?? 0
    backendOnline.value   = true
  }

  async function checkBackend() {
    try {
      await fetchCurrencyConfig()
      const res = await botApi.health()
      backendOnline.value = true
      running.value = res.data.bot_running
      if (res.data.account) applyAccount(res.data.account)
      else await fetchAccountStatus()
      if (res.data.bot_running) await syncFromBackend()
      else if (res.data.autostart_enabled) {
        try {
          await botApi.ensureRunning()
          await syncFromBackend()
        } catch { /* autostart pending */ }
      }
    } catch {
      backendOnline.value = false
    }
  }

  const winRate = computed(() => {
    const total = stats.value.wins + stats.value.losses
    return total ? Math.round((stats.value.wins / total) * 100) : 0
  })

  const totalWinPnl = computed(() =>
    trades.value.filter(t => t.status === 'WIN').reduce((s, t) => s + t.pnl, 0)
  )

  const totalLossPnl = computed(() =>
    trades.value.filter(t => t.status === 'LOSS').reduce((s, t) => s + Math.abs(t.pnl), 0)
  )

  const accountBalanceBrl = computed(() =>
    accountBalance.value !== null ? usdToBrl(accountBalance.value) : null,
  )

  const totalWinPnlBrl = computed(() => usdToBrl(totalWinPnl.value))
  const totalLossPnlBrl = computed(() => usdToBrl(totalLossPnl.value))

  return {
    running, connected, backendOnline, lastSyncAt,
    trades, lastSignal, stats, displayStats, displayStatsBrl, winRate,
    adaptive, mtf,
    totalWinPnl, totalLossPnl, totalWinPnlBrl, totalLossPnlBrl,
    accountBalance, accountBalanceBrl, accountLoadFailed, accountCurrency, accountLoginId, accountIsDemo, openContracts,
    usdBrlRate: getUsdBrlRate, formatUsdAsBrl, formatBrl, usdToBrl,
    connectBackend, disconnectBackend,
    startBot, stopBot, checkBackend, syncFromBackend, reconcileTrades, fetchDailyStats,
    fetchCurrencyConfig, applySnapshot, fetchAccountStatus, requestNotificationPermission,
  }
})
