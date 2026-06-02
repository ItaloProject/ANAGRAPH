import { api } from './http'

export interface BotConfig {
  api_token: string
  app_id?: string
  account_id?: string
  asset?: string
  granularity?: number
  contract_duration?: number
  stake_amount?: number
  max_stake?: number
  daily_loss_limit?: number
  daily_profit_target?: number
  limits_currency?: 'BRL'
  min_confidence?: number
  max_consecutive_losses?: number
  cooldown_after_loss_sec?: number
  analyzer_min_score?: number
  analyzer_min_gap?: number
  analyzer_min_adx?: number
  analyze_every?: number
}

export const botApi = {
  start: (config: BotConfig) => api.post('/bot/start', config),
  stop: ()                    => api.post('/bot/stop'),
  status: ()                  => api.get('/bot/status'),
  health: ()                  => api.get('/health'),
  credentials: ()             => api.get('/bot/credentials'),
  accountStatus: ()            => api.get('/account/status'),
  currencyConfig: ()            => api.get('/config/currency'),
  dailyStats: ()               => api.get('/bot/daily-stats'),
  reconcile: ()                => api.post('/bot/reconcile'),
}

function wsUrl(): string {
  // Prod: VITE_WS_BASE = wss://anagraph-api.onrender.com
  const override = import.meta.env.VITE_WS_BASE as string | undefined
  if (override) return `${override.replace(/\/$/, '')}/ws`
  if (typeof window === 'undefined') return 'ws://localhost:8001/ws'
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws`
}

export class BotWebSocket {
  private ws: WebSocket | null = null
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null

  constructor(
    private onEvent: (event: string, data: unknown) => void,
    private url = wsUrl(),
  ) {}

  connect() {
    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        console.log('[BotWS] Connected')
        this._clearReconnect()
      }

      this.ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        this.onEvent(msg.event, msg.data)
      }

      this.ws.onclose = () => {
        console.warn('[BotWS] Disconnected — reconnecting in 3s')
        this._scheduleReconnect()
      }

      this.ws.onerror = () => {
        this.ws?.close()
      }
    } catch {
      this._scheduleReconnect()
    }
  }

  disconnect() {
    this._clearReconnect()
    this.ws?.close()
    this.ws = null
  }

  ping() {
    this.ws?.send(JSON.stringify({ type: 'ping' }))
  }

  private _scheduleReconnect() {
    if (!this.reconnectTimeout) {
      this.reconnectTimeout = setTimeout(() => {
        this.reconnectTimeout = null
        this.connect()
      }, 3000)
    }
  }

  private _clearReconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
  }
}
