<template>
  <q-page class="live-page">

    <!-- ── Ticker Bar ── -->
    <div class="ticker-bar q-mb-md">

      <!-- Linha 1: preço + sparkline + sessão + status -->
      <div class="row items-center justify-between flex-wrap" style="gap:10px;">

        <!-- Preço principal -->
        <div class="row items-center" style="gap:14px;">
          <div class="row items-center gap-2">
            <div :class="['ticker-dot', bot.running ? 'dot-green' : 'dot-red']" />
            <span class="ticker-asset">{{ marketStore.activeAsset }}</span>
          </div>

          <div class="row items-center gap-2">
            <span
              class="ticker-price font-mono"
              :class="marketStore.priceChange >= 0 ? 'text-neon-green' : 'text-neon-red'"
            >
              {{ marketStore.currentPrice.toFixed(5) }}
            </span>
            <span
              class="ticker-change"
              :class="marketStore.priceChange >= 0 ? 'text-neon-green' : 'text-neon-red'"
            >
              {{ marketStore.priceChange >= 0 ? '▲' : '▼' }}
              {{ Math.abs(marketStore.priceChange * 10000).toFixed(1) }} pips
            </span>
          </div>

          <!-- Sparkline -->
          <div class="sparkline-wrap gt-xs">
            <svg :width="sparkW" :height="sparkH" :viewBox="`0 0 ${sparkW} ${sparkH}`" class="sparkline-svg">
              <!-- Área de fundo -->
              <defs>
                <linearGradient :id="`sg`" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" :stop-color="sparklineColor" stop-opacity="0.25" />
                  <stop offset="100%" :stop-color="sparklineColor" stop-opacity="0" />
                </linearGradient>
              </defs>
              <path :d="sparklineArea" :fill="`url(#sg)`" />
              <polyline
                :points="sparklinePoints"
                fill="none"
                :stroke="sparklineColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <!-- Ponto atual -->
              <circle :cx="sparkW" :cy="sparklineLastY" r="3" :fill="sparklineColor" />
            </svg>
          </div>
        </div>

        <!-- Direita: sessão + bot + sync + refresh -->
        <div class="row items-center" style="gap:8px;">
          <div v-if="marketStore.liveIndicators.session" class="session-pill" :class="sessionClass">
            <q-icon name="schedule" size="11px" />
            {{ marketStore.liveIndicators.session }}
          </div>
          <div class="row items-center gap-2">
            <div :class="['ticker-dot', bot.connected ? 'dot-green' : 'dot-amber']" style="width:6px;height:6px;" />
            <span class="text-caption" :class="bot.running ? 'text-neon-green' : 'text-muted'">
              {{ bot.running ? 'LIVE' : 'OFF' }}
            </span>
          </div>
          <span v-if="bot.lastSyncAt" class="text-caption text-muted gt-sm">{{ bot.lastSyncAt }}</span>
          <q-btn flat round dense size="xs" icon="sync" color="cyan"
            @click="refreshLive" :loading="refreshing" />
        </div>
      </div>

      <!-- Linha 2: indicadores rápidos -->
      <div class="row items-center q-mt-sm" style="gap:6px; flex-wrap:wrap;">
        <div class="indicator-pill">
          <span class="text-muted">RSI</span>
          <span :class="marketStore.liveIndicators.rsi < 30 ? 'text-neon-green' : marketStore.liveIndicators.rsi > 70 ? 'text-neon-red' : 'text-neon-cyan'">
            {{ marketStore.liveIndicators.rsi.toFixed(1) }}
          </span>
        </div>
        <div class="indicator-pill">
          <span class="text-muted">MACD</span>
          <span :class="marketStore.liveIndicators.macd > marketStore.liveIndicators.macd_signal ? 'text-neon-green' : 'text-neon-red'">
            {{ marketStore.liveIndicators.macd > 0 ? '+' : '' }}{{ marketStore.liveIndicators.macd.toFixed(5) }}
          </span>
        </div>
        <div class="indicator-pill">
          <span class="text-muted">ADX</span>
          <span :class="marketStore.liveIndicators.adx >= 22 ? 'text-neon-green' : 'text-neon-amber'">
            {{ marketStore.liveIndicators.adx.toFixed(1) }}
          </span>
        </div>
        <div class="indicator-pill" v-if="marketStore.liveIndicators.atr_ratio">
          <span class="text-muted">ATR</span>
          <span :class="atrClass">{{ marketStore.liveIndicators.atr_ratio.toFixed(2) }}×</span>
        </div>
        <div class="mtf-pill" :class="`bias-${(marketStore.liveIndicators.h1_bias || 'neutral').toLowerCase()}`">
          <span class="mtf-label">H1</span>
          <span class="mtf-val">{{ marketStore.liveIndicators.h1_bias || 'NEUTRAL' }}</span>
        </div>
        <div class="mtf-pill" :class="`bias-${(marketStore.liveIndicators.h4_bias || 'neutral').toLowerCase()}`">
          <span class="mtf-label">H4</span>
          <span class="mtf-val">{{ marketStore.liveIndicators.h4_bias || 'NEUTRAL' }}</span>
        </div>
        <div class="adaptive-pill q-ml-auto" :class="`regime-${bot.adaptive.regime}`">
          <q-icon name="auto_fix_high" size="10px" />
          {{ adaptiveLabel }}
        </div>
      </div>

    </div>

    <!-- ── Stats cards ── -->
    <div class="row q-col-gutter-md q-mb-md">

      <!-- Saldo do dia -->
      <div class="col-6 col-md">
        <div class="balance-card">
          <div class="balance-label">SALDO DO DIA</div>
          <div class="balance-value" :class="bot.displayStatsBrl.pnl >= 0 ? 'text-neon-green' : 'text-neon-red'">
            {{ bot.formatBrl(bot.displayStatsBrl.pnl, true) }}
          </div>
          <div class="balance-sub text-muted">
            {{ bot.displayStatsBrl.wins }}W / {{ bot.displayStatsBrl.losses }}L
            · {{ bot.displayStatsBrl.accuracy }}%
          </div>
        </div>
      </div>

      <!-- Wins -->
      <div class="col-6 col-md">
        <div class="balance-card border-glow-green">
          <div class="balance-label">WINS</div>
          <div class="balance-value text-neon-green">{{ bot.displayStatsBrl.wins }}</div>
          <div class="balance-sub text-neon-green">{{ bot.formatBrl(bot.totalWinPnlBrl, true) }}</div>
        </div>
      </div>

      <!-- Losses -->
      <div class="col-6 col-md">
        <div class="balance-card border-glow-red">
          <div class="balance-label">LOSSES</div>
          <div class="balance-value text-neon-red">{{ bot.displayStatsBrl.losses }}</div>
          <div class="balance-sub text-neon-red">-{{ bot.formatBrl(bot.totalLossPnlBrl) }}</div>
        </div>
      </div>

      <!-- Limite diário -->
      <div class="col-6 col-md">
        <div class="balance-card">
          <div class="balance-label">LIMITE DIÁRIO</div>
          <div class="balance-value text-neon-cyan">{{ bot.displayStatsBrl.daily_limit_used }}%</div>
          <div class="balance-sub text-muted">usado</div>
          <div class="limit-bar q-mt-xs">
            <div class="limit-fill" :style="{
              width: bot.displayStatsBrl.daily_limit_used + '%',
              background: bot.displayStatsBrl.daily_limit_used > 70 ? 'var(--accent-red)' : 'var(--accent-cyan)'
            }" />
          </div>
        </div>
      </div>
    </div>

    <!-- ── Análise em Tempo Real ── -->
    <div class="analysis-bar q-mb-md">
      <div class="row items-center justify-between q-mb-sm">
        <div class="row items-center gap-2">
          <q-spinner-dots v-if="bot.running" color="cyan" size="16px" />
          <span class="text-caption text-muted" style="letter-spacing:1.5px;">
            PREVISÃO — VAI SUBIR OU DESCER? · só opera com confluência forte
          </span>
        </div>
        <q-btn flat dense size="sm" icon="refresh" color="cyan" label="Forçar análise"
          @click="forceAnalyze" :loading="analyzing" />
      </div>

      <!-- Sinal + Scores + Confiança -->
      <div class="row items-center q-gutter-sm q-mb-xs">
        <div class="analysis-chip" :class="`chip-${marketStore.liveIndicators.last_signal.toLowerCase()}`">
          <q-icon
            :name="marketStore.liveIndicators.last_signal === 'BUY' ? 'trending_up' :
                   marketStore.liveIndicators.last_signal === 'SELL' ? 'trending_down' : 'pause'"
            size="16px"
          />
          <span class="text-weight-bold" style="font-size:13px;">{{ directionLabel(marketStore.liveIndicators.last_signal) }}</span>
          <span class="text-caption">{{ marketStore.liveIndicators.last_confidence }}%</span>
        </div>

        <!-- Barra de confiança -->
        <div class="confidence-bar-wrap">
          <div class="confidence-bar">
            <div
              class="confidence-fill"
              :style="{
                width: marketStore.liveIndicators.last_confidence + '%',
                background: marketStore.liveIndicators.last_confidence >= 80 ? 'var(--accent-green)' :
                            marketStore.liveIndicators.last_confidence >= 60 ? 'var(--accent-cyan)' : 'var(--accent-amber)'
              }"
            />
          </div>
          <span class="text-caption text-muted">{{ marketStore.liveIndicators.last_confidence }}% confiança</span>
        </div>

        <!-- Scores buy vs sell -->
        <div class="score-pill score-buy">↑ {{ marketStore.liveIndicators.buy_score }}</div>
        <div class="score-pill score-sell">↓ {{ marketStore.liveIndicators.sell_score }}</div>

        <!-- Min confiança adaptativo -->
        <div class="adaptive-pill q-ml-auto" :class="`regime-${bot.adaptive.regime}`">
          <q-icon name="auto_fix_high" size="10px" />
          {{ adaptiveLabel }} · {{ bot.adaptive.min_confidence }}%
          <span v-if="bot.adaptive.window_trades >= 5" class="text-caption q-ml-xs">
            (WR {{ bot.adaptive.win_rate_window }}%)
          </span>
        </div>
      </div>

      <!-- Linha 3: Divergências detectadas (laranja) + Padrões (roxo) -->
      <div
        v-if="marketStore.liveIndicators.divergences?.length || marketStore.liveIndicators.patterns?.length"
        class="row q-gutter-xs q-mb-xs"
      >
        <div
          v-for="div in marketStore.liveIndicators.divergences"
          :key="div"
          class="divergence-chip"
        >
          <q-icon name="show_chart" size="10px" />
          {{ div }}
        </div>
        <div
          v-for="pat in marketStore.liveIndicators.patterns"
          :key="pat"
          class="pattern-chip"
        >
          <q-icon name="candlestick_chart" size="10px" />
          {{ pat }}
        </div>
      </div>

      <!-- Motivo ou aguardando -->
      <div v-if="marketStore.liveIndicators.last_reason" class="reason-bar q-mt-xs">
        <q-icon name="info_outline" size="12px" style="color:var(--text-muted);" />
        <span class="text-caption text-muted q-ml-xs">{{ marketStore.liveIndicators.last_reason }}</span>
      </div>
      <div v-else-if="bot.running" class="reason-bar q-mt-xs">
        <q-spinner-dots color="cyan" size="14px" />
        <span class="text-caption text-muted q-ml-xs">Aguardando primeira análise do bot...</span>
      </div>
      <div v-else class="reason-bar q-mt-xs">
        <q-icon name="warning_amber" size="12px" color="amber" />
        <span class="text-caption text-muted q-ml-xs">Inicie o bot em Configurações para ver análises ao vivo</span>
      </div>
    </div>

    <!-- ── Painel de Inteligência IA ── -->
    <div class="ai-panel q-mb-md" v-if="ind.tick_flow || ind.news || ind.learning">
      <div class="ai-panel-header">
        <q-icon name="psychology" size="14px" color="cyan" />
        <span>INTELIGÊNCIA IA</span>
        <span v-if="ind.learning_label" class="ai-learn-badge">{{ ind.learning_label }}</span>
      </div>

      <div class="ai-grid">

        <!-- Notícias -->
        <div class="ai-card" :class="ind.news ? `news-${(ind.news.recommendation||'OK').toLowerCase()}` : ''">
          <div class="ai-card-label">NOTÍCIAS / MACRO</div>
          <template v-if="ind.news">
            <div class="ai-sentiment-row">
              <span class="sentiment-badge" :class="`sent-${ind.news.sentiment}`">
                {{ ind.news.sentiment === 'bullish' ? '📈 ALTA' : ind.news.sentiment === 'bearish' ? '📉 BAIXA' : '➡ NEUTRO' }}
              </span>
              <span class="sentiment-score" :class="ind.news.sentiment_score > 0 ? 'text-neon-green' : ind.news.sentiment_score < 0 ? 'text-neon-red' : 'text-muted'">
                {{ ind.news.sentiment_score > 0 ? '+' : '' }}{{ ind.news.sentiment_score }}
              </span>
            </div>
            <div class="ai-rec" :class="`rec-${(ind.news.recommendation||'OK').toLowerCase()}`">
              {{ ind.news.recommendation }} · risco {{ ind.news.risk_level }}
            </div>
            <div class="ai-sub" v-if="ind.news.reason">{{ ind.news.reason }}</div>
            <div class="ai-event" v-if="ind.news.high_impact_soon">
              ⚡ Evento iminente!
            </div>
            <div class="ai-event" v-for="ev in (ind.news.events || []).slice(0, 2)" :key="ev.event">
              {{ ev.currency }} {{ ev.event }} ({{ ev.minutes_away }}min)
            </div>
          </template>
          <div v-else class="ai-sub text-muted">Configure ANTHROPIC_API_KEY no servidor</div>
        </div>

        <!-- Aprendizado -->
        <div class="ai-card">
          <div class="ai-card-label">APRENDIZADO IA</div>
          <template v-if="ind.learning && ind.learning.model_trained">
            <div class="ai-wp-row">
              <span class="text-muted" style="font-size:11px;">Win Prob.</span>
              <span class="ai-wp-val" :class="ind.learning.win_rate >= 60 ? 'text-neon-green' : ind.learning.win_rate >= 50 ? 'text-neon-cyan' : 'text-neon-red'">
                {{ ind.learning.win_rate.toFixed(1) }}%
              </span>
            </div>
            <div class="ai-bar">
              <div class="ai-bar-fill" :style="{
                width: ind.learning.win_rate + '%',
                background: ind.learning.win_rate >= 60 ? 'var(--accent-green)' : ind.learning.win_rate >= 50 ? 'var(--accent-cyan)' : 'var(--accent-red)'
              }" />
            </div>
            <div class="ai-sub">{{ ind.learning.total_recorded }} amostras registradas</div>
          </template>
          <template v-else-if="ind.learning">
            <div class="ai-sub text-muted">Coletando amostras...</div>
            <div class="ai-sub">{{ ind.learning.total_recorded }} / 20 para treinamento</div>
          </template>
          <div v-else class="ai-sub text-muted">Sem dados ainda</div>
        </div>

        <!-- Tick Flow -->
        <div class="ai-card">
          <div class="ai-card-label">FLUXO DE MERCADO</div>
          <template v-if="ind.tick_flow">
            <div class="flow-pressure-bar">
              <div class="flow-sell-fill" :style="{width: ((1 - ind.tick_flow.imbalance) * 100).toFixed(0) + '%'}" />
              <div class="flow-buy-fill"  :style="{width: (ind.tick_flow.imbalance * 100).toFixed(0) + '%'}" />
            </div>
            <div class="flow-labels">
              <span class="text-neon-red" style="font-size:10px;">VENDA {{ ((1-ind.tick_flow.imbalance)*100).toFixed(0) }}%</span>
              <span class="text-neon-green" style="font-size:10px;">COMPRA {{ (ind.tick_flow.imbalance*100).toFixed(0) }}%</span>
            </div>
            <div class="ai-sub q-mt-xs">
              Mom: <span :class="ind.tick_flow.momentum > 0 ? 'text-neon-green' : 'text-neon-red'">{{ ind.tick_flow.momentum > 0 ? '+' : '' }}{{ (ind.tick_flow.momentum * 100).toFixed(3) }}%</span>
              · Vel: {{ ind.tick_flow.velocity }}tk/s
            </div>
          </template>
          <div v-else class="ai-sub text-muted">Aguardando ticks...</div>
        </div>

      </div>

      <!-- Footer: VWAP + Fib + DXY -->
      <div class="ai-footer" v-if="ind.vwap || ind.fib_level || ind.usd_strength !== 'NEUTRAL'">
        <div class="ai-footer-item" v-if="ind.vwap">
          <span class="text-muted">VWAP</span>
          <span class="font-mono text-neon-cyan">{{ ind.vwap.toFixed(5) }}</span>
        </div>
        <div class="ai-footer-item" v-if="ind.fib_level">
          <span class="text-muted">Fibonacci</span>
          <span class="text-neon-amber font-mono">{{ ind.fib_level }}</span>
        </div>
        <div class="ai-footer-item" v-if="ind.usd_strength !== 'NEUTRAL'">
          <span class="text-muted">DXY (USD)</span>
          <span :class="ind.usd_strength === 'STRONG' ? 'text-neon-red' : 'text-neon-green'">
            {{ ind.usd_strength === 'STRONG' ? 'FORTE ↑' : 'FRACO ↓' }}
          </span>
        </div>
      </div>
    </div>

    <!-- ── Posição Aberta ── -->
    <div class="q-mb-md">
      <div v-if="openTrade" class="open-position animate-float">
        <div class="op-header">
          <div class="row items-center gap-2">
            <div class="live-dot" />
            <span class="text-weight-bold" style="letter-spacing:1px;">OPERAÇÃO ABERTA</span>
          </div>
          <div class="countdown" :class="countdown <= 10 ? 'text-neon-red animate-pulse-red' : 'text-neon-cyan'">
            {{ countdownLabel }}
          </div>
        </div>

        <div class="op-body">
          <!-- Direção -->
          <div class="op-direction" :class="openTrade.signal === 'BUY' ? 'dir-buy' : 'dir-sell'">
            <q-icon :name="openTrade.signal === 'BUY' ? 'arrow_upward' : 'arrow_downward'" size="40px" />
            <div class="dir-label">{{ openTrade.contract_type === 'RISE' ? 'SOBE ↑' : 'DESCE ↓' }}</div>
          </div>

          <!-- Detalhes -->
          <div class="op-details">
            <div class="op-row">
              <span class="op-key">Ativo</span>
              <span class="op-val text-neon-cyan">{{ openTrade.asset }}</span>
            </div>
            <div class="op-row">
              <span class="op-key">Entrada</span>
              <span class="op-val font-mono">{{ (openTrade.entry_price || marketStore.currentPrice).toFixed(5) }}</span>
            </div>
            <div class="op-row">
              <span class="op-key">Stake</span>
              <span class="op-val text-neon-cyan font-mono">{{ bot.formatUsdAsBrl(openTrade.stake) }}</span>
            </div>
            <div class="op-row">
              <span class="op-key">Duração</span>
              <span class="op-val">{{ openTrade.duration }}</span>
            </div>
            <div class="op-row">
              <span class="op-key">Retorno est.</span>
              <span class="op-val text-neon-green font-mono">{{ bot.formatUsdAsBrl(openTrade.payout) }}</span>
            </div>
            <div class="op-row">
              <span class="op-key">P&L atual</span>
              <span class="op-val font-mono" :class="openTrade.pnl >= 0 ? 'text-neon-green' : 'text-neon-red'">
                {{ bot.formatUsdAsBrl(openTrade.pnl, true) }}
              </span>
            </div>
            <div class="op-row">
              <span class="op-key">Confiança</span>
              <span class="op-val text-neon-cyan">{{ openTrade.confidence }}%</span>
            </div>
          </div>

          <!-- Indicadores que geraram o sinal -->
          <div class="op-reason">
            <div class="text-caption text-muted q-mb-xs" style="letter-spacing:1px;">MOTIVO DO SINAL</div>
            <div class="reason-text">{{ openTrade.reason }}</div>
          </div>
        </div>
      </div>

      <!-- Sem operação aberta -->
      <div v-else class="waiting-card">
        <q-icon name="radar" size="48px" style="color:var(--text-muted);opacity:0.4;" />
        <div class="text-subtitle1 text-muted q-mt-sm">Analisando direção do preço...</div>
        <div class="text-caption text-muted q-mt-xs">
          {{ bot.running
            ? 'O bot decide se EUR/USD vai SUBIR ou DESCER e aposta na DERIV'
            : 'Inicie em Configurações — duração mín. 15 min' }}
        </div>
      </div>
    </div>

    <!-- ── Histórico de Operações ── -->
    <div class="trade-history">
      <div class="history-header">
        <span class="text-weight-bold text-secondary" style="letter-spacing:1px;">HISTÓRICO DE HOJE</span>
        <span class="text-caption text-muted">
          {{ allTrades.length }} registro(s)
          <span v-if="bot.trades.length > allTrades.length" class="text-amber">
            · {{ bot.trades.length }} na DERIV
          </span>
        </span>
      </div>

      <div v-if="allTrades.length === 0" class="empty-history">
        <span class="text-muted text-caption">Nenhuma operação ainda</span>
      </div>

      <div
        v-for="trade in allTrades"
        :key="trade.groupKey"
        class="trade-item"
        :class="trade.status === 'WIN' ? 'item-win' : trade.status === 'LOSS' ? 'item-loss' : 'item-open'"
      >
        <!-- Ícone resultado -->
        <div class="trade-icon" :class="trade.status === 'WIN' ? 'icon-win' : trade.status === 'LOSS' ? 'icon-loss' : 'icon-open'">
          <q-icon
            :name="trade.status === 'WIN' ? 'check' : trade.status === 'LOSS' ? 'close' : 'hourglass_empty'"
            size="18px"
          />
        </div>

        <!-- Info -->
        <div class="trade-info">
          <div class="row items-center gap-2">
            <span :class="['signal-badge', `signal-${trade.signal.toLowerCase()}`]" style="font-size:10px;padding:2px 8px;">
              {{ trade.contract_type === 'RISE' ? '↑ SOBE' : '↓ DESCE' }}
            </span>
            <span class="text-caption font-mono" style="color:var(--text-muted);">{{ formatTime(trade.opened_at) }}</span>
            <q-badge v-if="trade.dupCount > 1" color="amber" :label="`×${trade.dupCount}`" class="q-ml-xs" />
          </div>
          <div class="text-caption text-muted q-mt-xs">
            {{ trade.asset }} · {{ bot.formatUsdAsBrl(trade.stake) }} stake · {{ trade.duration }}
          </div>
        </div>

        <!-- P&L -->
        <div class="trade-pnl">
          <div
            v-if="trade.status === 'WIN' || trade.status === 'LOSS'"
            class="pnl-value font-mono text-weight-bold"
            :class="trade.pnl > 0 ? 'text-neon-green' : 'text-neon-red'"
          >
            {{ bot.formatUsdAsBrl(trade.pnl, true) }}
          </div>
          <div v-else-if="trade.status === 'ERROR'" class="text-caption text-neon-red">falhou</div>
          <div v-else class="text-caption text-neon-cyan">em aberto</div>

          <div
            class="result-label"
            :class="{
              'text-neon-green': trade.status === 'WIN',
              'text-neon-red': trade.status === 'LOSS' || trade.status === 'ERROR',
              'text-neon-cyan': trade.status === 'OPEN',
              'text-muted': !['WIN','LOSS','OPEN','ERROR'].includes(trade.status),
            }"
          >
            {{ trade.status === 'WIN' ? '✓ GANHOU' : trade.status === 'LOSS' ? '✗ PERDEU' :
               trade.status === 'ERROR' ? '✗ ERRO' : trade.status === 'OPEN' ? '⋯ ABERTA' : '⋯' }}
          </div>
        </div>
      </div>
    </div>

    <!-- ── Notificação WIN/LOSS ── -->
    <transition name="result-pop">
      <div
        v-if="resultNotif"
        class="result-overlay"
        :class="resultNotif === 'WIN' ? 'notif-win' : 'notif-loss'"
        @click="dismissResult"
      >
        <q-icon :name="resultNotif === 'WIN' ? 'emoji_events' : 'sentiment_dissatisfied'" size="64px" />
        <div class="notif-text">{{ resultNotif === 'WIN' ? 'GANHOU!' : 'PERDEU' }}</div>
        <div class="notif-pnl">{{ lastClosedPnl }}</div>
        <div class="notif-hint text-caption q-mt-sm">Toque para fechar</div>
      </div>
    </transition>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useBotStore } from '../stores/bot'
import { useMarketStore } from '../stores/market'
import { api } from '../services/http'
import type { TradeRecord } from '../stores/bot'

const bot         = useBotStore()
const marketStore = useMarketStore()
const analyzing   = ref(false)
const refreshing  = ref(false)

// Atalho para liveIndicators (usado no painel de IA)
const ind = computed(() => marketStore.liveIndicators)

// ── Sparkline ──────────────────────────────────────────────────────────────
const sparkW = 120
const sparkH = 32

const sparklinePoints = computed(() => {
  const src = marketStore.candles.slice(-80)
  if (src.length < 2) return `0,${sparkH / 2} ${sparkW},${sparkH / 2}`
  const prices = src.map(c => c.close)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 0.00001
  const pad = 3
  return prices.map((p, i) => {
    const x = (i / (prices.length - 1)) * sparkW
    const y = sparkH - pad - ((p - min) / range) * (sparkH - pad * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})

const sparklineArea = computed(() => {
  const src = marketStore.candles.slice(-80)
  if (src.length < 2) return ''
  const prices = src.map(c => c.close)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 0.00001
  const pad = 3
  const pts = prices.map((p, i) => {
    const x = (i / (prices.length - 1)) * sparkW
    const y = sparkH - pad - ((p - min) / range) * (sparkH - pad * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return `M ${pts[0]} L ${pts.slice(1).join(' L ')} L ${sparkW},${sparkH} L 0,${sparkH} Z`
})

const sparklineLastY = computed(() => {
  const src = marketStore.candles.slice(-80)
  if (src.length < 2) return sparkH / 2
  const prices = src.map(c => c.close)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 0.00001
  const pad = 3
  const last = prices[prices.length - 1]
  return sparkH - pad - ((last - min) / range) * (sparkH - pad * 2)
})

const sparklineColor = computed(() => {
  const src = marketStore.candles.slice(-80)
  if (src.length < 2) return '#00D4FF'
  return src[src.length - 1].close >= src[0].close ? '#00FF88' : '#FF4466'
})

async function refreshLive() {
  refreshing.value = true
  try {
    await bot.fetchAccountStatus()
    await bot.syncFromBackend()
    await bot.fetchDailyStats()
    const open = bot.trades.find(t => t.status === 'OPEN')
    if (open && open.expires_at && open.expires_at <= Math.floor(Date.now() / 1000)) {
      await bot.reconcileTrades()
    }
    if (!bot.connected) bot.connectBackend()
  } finally {
    setTimeout(() => { refreshing.value = false }, 500)
  }
}

async function forceAnalyze() {
  analyzing.value = true
  try {
    await api.post('/bot/analyze-now')
    await bot.syncFromBackend()
  } catch { /* bot offline */ }
  finally { setTimeout(() => { analyzing.value = false }, 1000) }
}

const NOTIFIED_STORAGE_KEY = 'anagraph_notified_trades'

function loadNotifiedIds(): Set<string> {
  try {
    const raw = sessionStorage.getItem(NOTIFIED_STORAGE_KEY)
    return new Set(raw ? (JSON.parse(raw) as string[]) : [])
  } catch {
    return new Set()
  }
}

function persistNotifiedIds(ids: Set<string>) {
  sessionStorage.setItem(NOTIFIED_STORAGE_KEY, JSON.stringify([...ids].slice(-50)))
}

function markClosedTradesAsNotified(trades: TradeRecord[]) {
  for (const t of trades) {
    if (t.status === 'WIN' || t.status === 'LOSS') notifiedTradeIds.add(t.id)
  }
  persistNotifiedIds(notifiedTradeIds)
}

const countdown       = ref(0)
const resultNotif     = ref<'WIN' | 'LOSS' | null>(null)
const lastClosedPnl   = ref('')
let countdownInterval: ReturnType<typeof setInterval> | null = null
let reconcilePending  = false
let resultTimeout: ReturnType<typeof setTimeout> | null = null
const notifiedTradeIds = loadNotifiedIds()
let suppressNotifications = true

const openTrade  = computed(() => bot.trades.find((t: TradeRecord) => t.status === 'OPEN') ?? null)

interface GroupedTrade extends TradeRecord {
  groupKey: string
  dupCount: number
}

/** Agrupa entradas idênticas (mesmo horário/sinal/resultado) — bug antigo abriu vários contratos juntos */
const allTrades = computed((): GroupedTrade[] => {
  const groups = new Map<string, GroupedTrade>()
  for (const t of bot.trades) {
    const sec = t.opened_at?.slice(0, 19) ?? t.id
    const key = `${sec}|${t.signal}|${t.stake}|${t.status}|${t.pnl}`
    const existing = groups.get(key)
    if (existing) {
      existing.dupCount += 1
    } else {
      groups.set(key, { ...t, groupKey: key, dupCount: 1 })
    }
  }
  return [...groups.values()].slice(0, 20)
})

// Só notifica trades fechados novos — nunca re-dispara ao voltar à página
watch(() => bot.trades, (trades) => {
  if (suppressNotifications) return
  for (const trade of trades) {
    if (trade.status !== 'WIN' && trade.status !== 'LOSS') continue
    if (notifiedTradeIds.has(trade.id)) continue
    notifiedTradeIds.add(trade.id)
    persistNotifiedIds(notifiedTradeIds)
    showResult(trade.status, trade.pnl)
    break
  }
}, { deep: true })

// Countdown timer for open trade (uses expires_at from DERIV)
watch(openTrade, (trade) => {
  if (countdownInterval) clearInterval(countdownInterval)
  if (!trade) { countdown.value = 0; return }

  const tick = () => {
    if (trade.expires_at) {
      countdown.value = Math.max(0, trade.expires_at - Math.floor(Date.now() / 1000))
    } else {
      const match = trade.duration.match(/(\d+)m/)
      countdown.value = match ? parseInt(match[1]) * 60 : 300
    }
  }

  tick()
  countdownInterval = setInterval(async () => {
    tick()
    if (
      trade.expires_at
      && trade.expires_at <= Math.floor(Date.now() / 1000)
      && !reconcilePending
    ) {
      reconcilePending = true
      await bot.reconcileTrades()
      reconcilePending = false
    }
  }, 1000)
})

const countdownLabel = computed(() => {
  const s = countdown.value
  if (s <= 0) return '0:00'
  const m = Math.floor(s / 60)
  const sec = s % 60
  return m > 0 ? `${m}:${sec.toString().padStart(2, '0')}` : `${s}s`
})

function showResult(type: 'WIN' | 'LOSS', pnl: number) {
  if (resultTimeout) clearTimeout(resultTimeout)
  resultNotif.value   = type
  lastClosedPnl.value = bot.formatUsdAsBrl(pnl, true)
  resultTimeout = setTimeout(dismissResult, 3000)
}

function dismissResult() {
  if (resultTimeout) {
    clearTimeout(resultTimeout)
    resultTimeout = null
  }
  resultNotif.value = null
}

function directionLabel(signal: string) {
  if (signal === 'BUY') return 'SOBE ↑'
  if (signal === 'SELL') return 'DESCE ↓'
  return 'AGUARDAR'
}

const atrClass = computed(() => {
  const r = marketStore.liveIndicators.atr_ratio ?? 1
  if (r > 2.0) return 'text-neon-red'
  if (r < 0.5) return 'text-neon-amber'
  return 'text-neon-green'
})

const sessionClass = computed(() => {
  const s = marketStore.liveIndicators.session || ''
  if (s.includes('+')) return 'session-premium'
  if (s.includes('London')) return 'session-london'
  if (s.includes('New York') || s.includes('York')) return 'session-ny'
  return 'session-off'
})

const adaptiveLabel = computed(() => {
  const r = bot.adaptive.regime
  if (r === 'reward')  return '🟢 Recompensa'
  if (r === 'caution') return '🟡 Cautela'
  if (r === 'danger')  return '🔴 Perigo'
  return '⚪ Neutro'
})

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

let syncInterval: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  suppressNotifications = true
  if (!bot.connected) bot.connectBackend()
  markClosedTradesAsNotified(bot.trades)
  await bot.fetchCurrencyConfig()
  await refreshLive()
  markClosedTradesAsNotified(bot.trades)
  suppressNotifications = false
  syncInterval = setInterval(() => { if (bot.running) bot.syncFromBackend() }, 5000)
})

onUnmounted(() => {
  if (countdownInterval) clearInterval(countdownInterval)
  if (syncInterval) clearInterval(syncInterval)
  dismissResult()
})
</script>

<style lang="scss" scoped>

// ── AI Intelligence Panel ─────────────────────────────────────────────────────
.ai-panel {
  background: var(--bg-surface);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 14px;
  padding: 14px 16px;
}
.ai-panel-header {
  display: flex; align-items: center; gap: 6px;
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  color: var(--text-muted); text-transform: uppercase;
  margin-bottom: 12px;
  .ai-learn-badge {
    margin-left: auto; font-size: 10px; font-weight: 600;
    color: var(--accent-cyan); background: rgba(0,212,255,0.1);
    border-radius: 4px; padding: 1px 6px;
  }
}
.ai-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  @media (max-width: 699px) { grid-template-columns: 1fr; }
}
.ai-card {
  background: rgba(0,0,0,0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 10px 12px;
  &.news-avoid  { border-color: rgba(255,68,102,0.4); background: rgba(255,68,102,0.04); }
  &.news-caution{ border-color: rgba(255,184,0,0.3);  background: rgba(255,184,0,0.03); }
  &.news-ok     { border-color: rgba(0,255,136,0.2);  background: rgba(0,255,136,0.03); }
}
.ai-card-label {
  font-size: 9px; font-weight: 700; letter-spacing: 1.5px;
  color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;
}
.ai-sentiment-row {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;
}
.sentiment-badge {
  font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px;
  &.sent-bullish { background: rgba(0,255,136,0.15); color: var(--accent-green); }
  &.sent-bearish { background: rgba(255,68,102,0.15); color: var(--accent-red); }
  &.sent-neutral { background: rgba(255,255,255,0.08); color: var(--text-muted); }
}
.sentiment-score { font-size: 13px; font-weight: 700; font-family: monospace; }
.ai-rec {
  font-size: 10px; font-weight: 600; margin-bottom: 4px;
  &.rec-ok     { color: var(--accent-green); }
  &.rec-caution{ color: var(--accent-amber); }
  &.rec-avoid  { color: var(--accent-red); }
}
.ai-sub  { font-size: 10px; color: var(--text-muted); margin-top: 3px; }
.ai-event { font-size: 10px; color: var(--accent-amber); margin-top: 3px; }
.ai-wp-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; }
.ai-wp-val { font-size: 18px; font-weight: 700; font-family: monospace; }
.ai-bar {
  height: 4px; background: rgba(255,255,255,0.08); border-radius: 2px;
  overflow: hidden; margin-bottom: 5px;
}
.ai-bar-fill { height: 100%; border-radius: 2px; transition: width 0.6s; }
.flow-pressure-bar {
  display: flex; height: 6px; border-radius: 3px; overflow: hidden; margin-bottom: 5px;
}
.flow-sell-fill { background: var(--accent-red); transition: width 0.5s; }
.flow-buy-fill  { background: var(--accent-green); transition: width 0.5s; }
.flow-labels { display: flex; justify-content: space-between; }
.ai-footer {
  display: flex; flex-wrap: wrap; gap: 12px;
  margin-top: 10px; padding-top: 10px;
  border-top: 1px solid var(--border-subtle);
}
.ai-footer-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px;
  .font-mono { font-family: monospace; font-weight: 600; }
}

.live-page {
  background: var(--bg-deep);
  min-height: 100vh;
  padding: 24px;
  @media (max-width: 1023px) { padding: 16px; }
  @media (max-width: 599px)  { padding: 10px; }
}

// ── Ticker bar ───────────────────────────────────────────────────────────────
.ticker-bar {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 14px 18px;

  @media (max-width: 599px) { padding: 10px 12px; }
}

.ticker-dot {
  border-radius: 50%;
  &.dot-green { width: 8px; height: 8px; background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); animation: pulse-green 2s ease-in-out infinite; }
  &.dot-red   { width: 8px; height: 8px; background: var(--accent-red); }
  &.dot-amber { width: 8px; height: 8px; background: var(--accent-amber); animation: pulse-cyan 2s ease-in-out infinite; }
}

.ticker-asset {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: var(--text-secondary);
}

.ticker-price {
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.5px;

  @media (max-width: 599px) { font-size: 20px; }
}

.ticker-change {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.sparkline-wrap {
  display: flex;
  align-items: center;
}

.sparkline-svg {
  display: block;
  border-radius: 4px;
}

.gap-2 { gap: 8px; }

// ── Balance cards ──
.balance-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 16px 20px;
  height: 100%;
  transition: border-color 0.3s;
  &:hover { border-color: var(--border-glow); }

  @media (max-width: 599px) { padding: 12px 14px; border-radius: 10px; }
}
.balance-label {
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  color: var(--text-muted); margin-bottom: 6px;
  @media (max-width: 599px) { letter-spacing: 1px; }
}
.balance-value {
  font-size: 28px; font-weight: 700; line-height: 1;
  font-family: 'Roboto Mono', monospace;
  @media (max-width: 599px) { font-size: 20px; }
}
.balance-sub   { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
.limit-bar     { height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
.limit-fill    { height: 100%; border-radius: 2px; transition: width 0.5s ease; }

// ── Open position ──
.open-position {
  background: var(--bg-surface);
  border: 1px solid rgba(0,212,255,0.3);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: var(--glow-cyan);
}
.op-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px;
  background: rgba(0,212,255,0.06);
  border-bottom: 1px solid rgba(0,212,255,0.1);
}
.countdown {
  font-size: 28px; font-weight: 700;
  font-family: 'Roboto Mono', monospace;
}
.op-body {
  display: grid;
  grid-template-columns: 120px 1fr 1fr;
  gap: 0;
  padding: 20px;
  gap: 16px;
}
.op-direction {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border-radius: 12px; padding: 16px;
  &.dir-buy  { background: rgba(0,255,136,0.1); color: var(--accent-green); border: 1px solid rgba(0,255,136,0.3); }
  &.dir-sell { background: rgba(255,68,102,0.1); color: var(--accent-red);   border: 1px solid rgba(255,68,102,0.3); }
}
.dir-label { font-size: 12px; font-weight: 700; letter-spacing: 2px; margin-top: 4px; }
.op-details { display: flex; flex-direction: column; gap: 8px; }
.op-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
}
.op-key { font-size: 11px; color: var(--text-muted); }
.op-val { font-size: 13px; font-weight: 600; }
.op-reason {
  background: rgba(0,0,0,0.2); border-radius: 10px; padding: 12px;
  border: 1px solid var(--border-subtle);
}
.reason-text { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

// ── Waiting ──
.waiting-card {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 48px;
  text-align: center;
}

// ── Trade history ──
.trade-history {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  overflow: hidden;
}
.history-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-subtle);
}
.empty-history {
  padding: 32px; text-align: center;
}
.trade-item {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  transition: background 0.2s;
  &:hover { background: rgba(255,255,255,0.02); }
  &.item-win  { border-left: 3px solid rgba(0,255,136,0.5); }
  &.item-loss { border-left: 3px solid rgba(255,68,102,0.5); }
  &.item-open { border-left: 3px solid rgba(0,212,255,0.5); }
  &:last-child { border-bottom: none; }
}
.trade-icon {
  width: 36px; height: 36px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  &.icon-win  { background: rgba(0,255,136,0.15); color: var(--accent-green); }
  &.icon-loss { background: rgba(255,68,102,0.15); color: var(--accent-red); }
  &.icon-open { background: rgba(0,212,255,0.15); color: var(--accent-cyan); }
}
.trade-info { flex: 1; }
.trade-pnl  { text-align: right; }
.pnl-value  { font-size: 18px; font-family: 'Roboto Mono', monospace; }
.result-label { font-size: 10px; font-weight: 700; letter-spacing: 1.5px; margin-top: 2px; }

// ── Result notification ──
.result-overlay {
  position: fixed; inset: 0; z-index: 9999;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  cursor: pointer;
  &.notif-win  { background: rgba(0,255,136,0.15); }
  &.notif-loss { background: rgba(255,68,102,0.15); }
}
.notif-hint { color: var(--text-muted); opacity: 0.8; }
.notif-text {
  font-size: 64px; font-weight: 900; letter-spacing: 6px;
  margin-top: 16px;
  .notif-win &  { color: var(--accent-green); text-shadow: var(--glow-green); }
  .notif-loss & { color: var(--accent-red);   text-shadow: var(--glow-red); }
}
.notif-pnl  { font-size: 36px; font-weight: 700; font-family: 'Roboto Mono', monospace; margin-top: 8px; }

.result-pop-enter-active, .result-pop-leave-active { transition: all 0.3s ease; }
.result-pop-enter-from, .result-pop-leave-to { opacity: 0; transform: scale(0.8); }

// Analysis bar
.analysis-bar {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 14px 18px;
  @media (max-width: 599px) { padding: 12px; }
}

.confidence-bar-wrap {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 100px;
  max-width: 160px;
  flex: 1;
}
.confidence-bar {
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
}
.confidence-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s ease;
}
.analysis-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 100px;
  font-size: 12px; font-weight: 700; letter-spacing: 1px;
  &.chip-buy  { background: rgba(0,255,136,0.12); color: var(--accent-green); border: 1px solid rgba(0,255,136,0.3); }
  &.chip-sell { background: rgba(255,68,102,0.12); color: var(--accent-red);   border: 1px solid rgba(255,68,102,0.3); }
  &.chip-wait { background: rgba(255,184,0,0.08);  color: var(--accent-amber); border: 1px solid rgba(255,184,0,0.2); }
}
.score-pill {
  display: inline-flex; align-items: center;
  padding: 4px 10px; border-radius: 100px; font-size: 12px; font-weight: 700;
  &.score-buy  { background: rgba(0,255,136,0.08); color: var(--accent-green); }
  &.score-sell { background: rgba(255,68,102,0.08); color: var(--accent-red); }
}
.indicator-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 8px; font-size: 11px;
  background: rgba(0,0,0,0.2); border: 1px solid var(--border-subtle);
  .text-muted { color: var(--text-muted); }
}
.reason-bar {
  display: flex; align-items: flex-start;
  padding: 6px 10px; border-radius: 8px;
  background: rgba(0,0,0,0.15);
  border: 1px solid var(--border-subtle);
}

// misc
.font-mono  { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }
.text-secondary { color: var(--text-secondary); }
.gap-2 { gap: 8px; }
@keyframes animate-pulse-red {
  0%,100% { text-shadow: 0 0 8px rgba(255,68,102,0.4); }
  50%      { text-shadow: 0 0 24px rgba(255,68,102,0.9); }
}
.animate-pulse-red { animation: animate-pulse-red 0.8s ease-in-out infinite; }

// ── Session pill ──────────────────────────────────────────────────────────
.session-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 100px; font-size: 11px; font-weight: 600;
  &.session-premium { background: rgba(139,92,246,0.15); color: var(--accent-purple); border: 1px solid rgba(139,92,246,0.3); }
  &.session-london  { background: rgba(0,212,255,0.10); color: var(--accent-cyan);   border: 1px solid rgba(0,212,255,0.25); }
  &.session-ny      { background: rgba(0,255,136,0.10); color: var(--accent-green);  border: 1px solid rgba(0,255,136,0.25); }
  &.session-off     { background: rgba(255,255,255,0.04); color: var(--text-muted);  border: 1px solid var(--border-subtle); }
}

// ── MTF bias pill ─────────────────────────────────────────────────────────
.mtf-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 8px; font-size: 11px; font-weight: 700;
  .mtf-label { color: var(--text-muted); font-weight: 400; }
  &.bias-bull    { background: rgba(0,255,136,0.1); color: var(--accent-green); border: 1px solid rgba(0,255,136,0.25); }
  &.bias-bear    { background: rgba(255,68,102,0.1); color: var(--accent-red);  border: 1px solid rgba(255,68,102,0.25); }
  &.bias-neutral { background: rgba(255,255,255,0.04); color: var(--text-muted); border: 1px solid var(--border-subtle); }
}

// ── Adaptive regime pill ──────────────────────────────────────────────────
.adaptive-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 8px; font-size: 11px; font-weight: 600;
  border: 1px solid var(--border-subtle);
  background: rgba(255,255,255,0.04);
  color: var(--text-secondary);
  &.regime-reward  { background: rgba(0,255,136,0.08); color: var(--accent-green); border-color: rgba(0,255,136,0.2); }
  &.regime-caution { background: rgba(255,184,0,0.08); color: var(--accent-amber); border-color: rgba(255,184,0,0.2); }
  &.regime-danger  { background: rgba(255,68,102,0.08); color: var(--accent-red);  border-color: rgba(255,68,102,0.2); }
}

// ── Divergence chips ──────────────────────────────────────────────────────
.divergence-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 700;
  background: rgba(255,184,0,0.12); color: var(--accent-amber);
  border: 1px solid rgba(255,184,0,0.3);
  letter-spacing: 0.5px;
}

// ── Pattern chips ─────────────────────────────────────────────────────────
.pattern-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 600;
  background: rgba(139,92,246,0.12); color: var(--accent-purple);
  border: 1px solid rgba(139,92,246,0.25);
  letter-spacing: 0.5px;
}
</style>
