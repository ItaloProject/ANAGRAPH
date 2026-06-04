import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume?: number
}

export interface Signal {
  id: string
  time: string
  asset: string
  type: 'BUY' | 'SELL' | 'WAIT'
  confidence: number
  indicators: { rsi: number; macd: number; bb: string }
  duration: string
  result?: 'WIN' | 'LOSS' | 'PENDING'
  pnl?: number
}

export const useMarketStore = defineStore('market', () => {
  const connected = ref(false)
  const activeAsset = ref('EUR/USD')
  const currentPrice = ref(1.08750)
  const previousPrice = ref(1.08750)
  const candles = ref<Candle[]>([])
  const signals = ref<Signal[]>([])
  const accuracy = ref(72.5)
  const totalSignals = ref(0)
  const wins = ref(0)

  const priceChange = computed(() => currentPrice.value - previousPrice.value)

  function connect() {
    connected.value = true
    _generateInitialCandles()
    _generateInitialSignals()
  }

  function simulateTick() {
    if (!connected.value) return
    previousPrice.value = currentPrice.value
    const delta = (Math.random() - 0.48) * 0.0003
    currentPrice.value = parseFloat((currentPrice.value + delta).toFixed(5))

    // Update last candle or create new one
    const now = Math.floor(Date.now() / 1000)
    const last = candles.value[candles.value.length - 1]
    if (last && now - last.time < 60) {
      last.close = currentPrice.value
      last.high = Math.max(last.high, currentPrice.value)
      last.low = Math.min(last.low, currentPrice.value)
    } else {
      candles.value.push({
        time: now,
        open: last?.close ?? currentPrice.value,
        high: currentPrice.value,
        low: currentPrice.value,
        close: currentPrice.value,
      })
      if (candles.value.length > 200) candles.value.shift()
    }
  }

  function _generateInitialCandles() {
    const now = Math.floor(Date.now() / 1000)
    let price = 1.08500
    for (let i = 150; i >= 0; i--) {
      const open = price
      const change = (Math.random() - 0.48) * 0.0015
      const close = parseFloat((open + change).toFixed(5))
      const high = parseFloat((Math.max(open, close) + Math.random() * 0.0008).toFixed(5))
      const low  = parseFloat((Math.min(open, close) - Math.random() * 0.0008).toFixed(5))
      candles.value.push({ time: now - i * 60, open, high, low, close })
      price = close
    }
    currentPrice.value = price
    previousPrice.value = price
  }

  function _generateInitialSignals() {
    const types: Signal['type'][] = ['BUY', 'SELL', 'WAIT', 'BUY', 'BUY', 'SELL']
    const results: Signal['result'][] = ['WIN', 'WIN', 'LOSS', 'WIN', 'WIN', 'PENDING']
    const now = Date.now()
    signals.value = types.map((type, i) => ({
      id: `sig-${i}`,
      time: new Date(now - i * 4 * 60000).toLocaleTimeString('pt-BR'),
      asset: 'EUR/USD',
      type,
      confidence: 60 + Math.floor(Math.random() * 35),
      indicators: {
        rsi: 40 + Math.random() * 40,
        macd: (Math.random() - 0.5) * 0.003,
        bb: type === 'BUY' ? 'Below Lower' : type === 'SELL' ? 'Above Upper' : 'Middle',
      },
      duration: '5 min',
      result: results[i],
      pnl: results[i] === 'WIN' ? 8.5 : results[i] === 'LOSS' ? -5 : undefined,
    }))
    totalSignals.value = signals.value.length
    wins.value = signals.value.filter(s => s.result === 'WIN').length
  }

  function setActiveAsset(asset: string) {
    if (asset) activeAsset.value = asset
  }

  function applyTick(price: number, epoch: number) {
    previousPrice.value = currentPrice.value
    currentPrice.value  = parseFloat(price.toFixed(5))
    const now = Math.floor(epoch)
    const last = candles.value[candles.value.length - 1]
    if (last && now - last.time < 60) {
      last.close = price
      last.high  = Math.max(last.high, price)
      last.low   = Math.min(last.low,  price)
    } else {
      candles.value.push({
        time: now, open: last?.close ?? price,
        high: price, low: price, close: price,
      })
      if (candles.value.length > 300) candles.value.shift()
    }
  }

  function addSignal(signal: Signal) {
    signals.value.unshift(signal)
    totalSignals.value++
    if (signal.result === 'WIN') wins.value++
    accuracy.value = parseFloat(((wins.value / totalSignals.value) * 100).toFixed(1))
  }

  // Live indicators from backend analysis
  const liveIndicators = ref({
    rsi: 50, macd: 0, macd_signal: 0,
    bb_upper: 0, bb_lower: 0, ema9: 0, ema21: 0,
    buy_score: 0, sell_score: 0, adx: 0,
    last_signal: 'WAIT' as string,
    last_confidence: 0,
    last_reason: '',
    h1_bias:     'NEUTRAL' as string,
    h4_bias:     'NEUTRAL' as string,
    session:     '' as string,
    atr_ratio:   1.0 as number,
    patterns:    [] as string[],
    divergences: [] as string[],
    // IA avançada
    vwap:         0 as number,
    fib_level:    '' as string,
    usd_strength: 'NEUTRAL' as string,
    tick_flow: null as null | {
      velocity: number; momentum: number; imbalance: number
      smoothness: number; buy_pts: number; sell_pts: number
    },
    news: null as null | {
      sentiment: string; sentiment_score: number; risk_level: string
      recommendation: string; reason: string; high_impact_soon: boolean
      key_factor: string; events: any[]; headlines_count: number
    },
    learning: null as null | {
      total_recorded: number; win_rate: number; model_trained: boolean
      sample_count: number; storage?: string
    },
    learning_label: '' as string,
    block_reason:   '' as string,   // motivo pelo qual o bot não operou (cooldown, WS, limite, etc.)
  })

  function updateIndicators(data: Record<string, any>) {
    liveIndicators.value = {
      rsi:             data.rsi ?? 50,
      macd:            data.macd ?? 0,
      macd_signal:     data.macd_signal ?? 0,
      bb_upper:        data.bb_upper ?? 0,
      bb_lower:        data.bb_lower ?? 0,
      ema9:            data.ema9 ?? 0,
      ema21:           data.ema21 ?? 0,
      buy_score:       data.buy_score ?? 0,
      sell_score:      data.sell_score ?? 0,
      adx:             data.adx ?? 0,
      last_signal:     data.signal ?? 'WAIT',
      last_confidence: data.confidence ?? 0,
      last_reason:     data.reason ?? '',
      h1_bias:         data.h1_bias ?? 'NEUTRAL',
      h4_bias:         data.h4_bias ?? 'NEUTRAL',
      session:         data.session ?? '',
      atr_ratio:       data.atr_ratio ?? 1.0,
      patterns:        Array.isArray(data.patterns)    ? data.patterns    : [],
      divergences:     Array.isArray(data.divergences) ? data.divergences : [],
      vwap:            data.vwap ?? 0,
      fib_level:       data.fib_level ?? '',
      usd_strength:    data.usd_strength ?? 'NEUTRAL',
      tick_flow:       data.tick_flow ?? null,
      news:            data.news && Object.keys(data.news).length ? data.news : null,
      learning:        data.learning ?? null,
      learning_label:  data.learning_label ?? '',
      block_reason:    data.block_reason ?? '',
    }
  }

  return {
    connected, activeAsset, currentPrice, previousPrice,
    candles, signals, accuracy, totalSignals, wins, priceChange,
    liveIndicators,
    connect, simulateTick, addSignal, applyTick, updateIndicators, setActiveAsset,
  }
})
