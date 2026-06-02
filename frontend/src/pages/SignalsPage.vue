<template>
  <q-page class="signals-page">

    <!-- ── Cabeçalho ── -->
    <div class="signals-header">
      <div>
        <div class="text-weight-bold text-neon-cyan" style="font-size:18px;letter-spacing:3px;">SINAIS</div>
        <div class="text-caption text-muted">Operações do robô hoje</div>
      </div>

      <!-- Filtros -->
      <div class="filter-row">
        <button
          v-for="f in filters" :key="f.value"
          class="filter-btn"
          :class="[`filter-${f.value.toLowerCase()}`, { 'filter-active': activeFilter === f.value }]"
          @click="activeFilter = f.value"
        >
          {{ f.label }}
          <span class="filter-count">{{ filterCount(f.value) }}</span>
        </button>
      </div>
    </div>

    <!-- ── Summary cards ── -->
    <div class="row q-col-gutter-md q-px-md q-pb-md">

      <div class="col-6 col-sm-3">
        <div class="sum-card">
          <span class="sum-label">ACURÁCIA</span>
          <span class="sum-val" :class="accuracyColor">{{ bot.displayStats.accuracy.toFixed(1) }}%</span>
          <div class="accuracy-bar q-mt-xs">
            <div class="accuracy-fill" :style="{ width: bot.displayStats.accuracy + '%', background: accuracyGradient }" />
          </div>
        </div>
      </div>

      <div class="col-6 col-sm-3">
        <div class="sum-card">
          <span class="sum-label">PNL HOJE</span>
          <span class="sum-val font-mono" :class="bot.displayStatsBrl.pnl >= 0 ? 'text-neon-green' : 'text-neon-red'">
            {{ bot.displayStatsBrl.pnl >= 0 ? '+' : '' }}{{ bot.formatBrl(bot.displayStatsBrl.pnl) }}
          </span>
          <span class="sum-sub text-muted">{{ bot.displayStats.trades }} operações</span>
        </div>
      </div>

      <div class="col-6 col-sm-3">
        <div class="sum-card border-glow-green">
          <span class="sum-label">WINS</span>
          <span class="sum-val text-neon-green">{{ bot.displayStats.wins }}</span>
          <span class="sum-sub text-neon-green">+{{ bot.formatBrl(bot.totalWinPnlBrl) }}</span>
        </div>
      </div>

      <div class="col-6 col-sm-3">
        <div class="sum-card border-glow-red">
          <span class="sum-label">LOSSES</span>
          <span class="sum-val text-neon-red">{{ bot.displayStats.losses }}</span>
          <span class="sum-sub text-neon-red">-{{ bot.formatBrl(bot.totalLossPnlBrl) }}</span>
        </div>
      </div>
    </div>

    <!-- ── Lista de sinais ── -->
    <div class="q-px-md q-pb-md">

      <!-- Vazio -->
      <div v-if="filteredTrades.length === 0" class="empty-state">
        <q-icon name="radar" size="48px" style="opacity:.25;" />
        <div class="text-muted q-mt-sm">
          {{ bot.trades.length === 0
            ? 'Nenhuma operação hoje — inicie o bot em Configurações'
            : 'Nenhuma operação com esse filtro' }}
        </div>
      </div>

      <!-- Cards de trade -->
      <div
        v-for="trade in filteredTrades"
        :key="trade.id"
        class="trade-card"
        :class="`tc-${trade.status.toLowerCase()}`"
      >
        <!-- Linha 1: direção + ativo + horário + resultado -->
        <div class="tc-row1">
          <div class="row items-center gap-2">
            <div :class="['dir-badge', trade.signal === 'BUY' ? 'dir-buy' : 'dir-sell']">
              <q-icon :name="trade.signal === 'BUY' ? 'trending_up' : 'trending_down'" size="14px" />
              {{ trade.signal === 'BUY' ? 'SOBE ↑' : 'DESCE ↓' }}
            </div>
            <span class="text-caption text-muted">{{ trade.asset }}</span>
            <span class="text-caption text-muted">·</span>
            <span class="text-caption text-muted font-mono">{{ formatTime(trade.opened_at) }}</span>
          </div>

          <div class="row items-center gap-2">
            <div
              class="result-badge"
              :class="{
                'rb-win':  trade.status === 'WIN',
                'rb-loss': trade.status === 'LOSS',
                'rb-open': trade.status === 'OPEN',
                'rb-err':  trade.status === 'ERROR',
              }"
            >
              <q-icon
                :name="trade.status === 'WIN' ? 'check_circle' : trade.status === 'LOSS' ? 'cancel' : trade.status === 'OPEN' ? 'hourglass_empty' : 'error'"
                size="12px"
              />
              {{ trade.status }}
            </div>
            <span
              class="tc-pnl font-mono"
              :class="trade.status === 'WIN' ? 'text-neon-green' : trade.status === 'LOSS' ? 'text-neon-red' : 'text-muted'"
            >
              <template v-if="trade.status === 'OPEN'">···</template>
              <template v-else>
                {{ trade.pnl >= 0 ? '+' : '' }}{{ bot.formatBrl(bot.usdToBrl(trade.pnl)) }}
              </template>
            </span>
          </div>
        </div>

        <!-- Linha 2: confiança + stake + duração -->
        <div class="tc-row2">
          <div class="conf-wrap">
            <div class="conf-bar">
              <div
                class="conf-fill"
                :style="{
                  width: trade.confidence + '%',
                  background: trade.confidence >= 80 ? 'var(--accent-green)' :
                              trade.confidence >= 60 ? 'var(--accent-cyan)' : 'var(--accent-amber)'
                }"
              />
            </div>
            <span class="text-caption text-muted" style="white-space:nowrap;">{{ trade.confidence }}% conf.</span>
          </div>

          <div class="row items-center gap-2 text-caption text-muted">
            <span>Stake: <span class="font-mono">{{ bot.formatUsdAsBrl(trade.stake) }}</span></span>
            <span>·</span>
            <span>{{ trade.duration }}</span>
            <span>·</span>
            <span>{{ trade.contract_type }}</span>
          </div>
        </div>

        <!-- Linha 3: motivo (collapsible) -->
        <div v-if="trade.reason" class="tc-reason">
          <q-icon name="info_outline" size="11px" style="opacity:.5;flex-shrink:0;" />
          <span class="text-caption text-muted">{{ trade.reason }}</span>
        </div>
      </div>
    </div>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useBotStore } from 'stores/bot'

const bot = useBotStore()

const activeFilter = ref('ALL')

const filters = [
  { label: 'Todos',  value: 'ALL'  },
  { label: '↑ Sobe', value: 'BUY'  },
  { label: '↓ Desce',value: 'SELL' },
  { label: 'Win',    value: 'WIN'  },
  { label: 'Loss',   value: 'LOSS' },
  { label: 'Aberto', value: 'OPEN' },
]

function filterCount(val: string): number {
  if (val === 'ALL')  return bot.trades.length
  if (val === 'BUY' || val === 'SELL') return bot.trades.filter(t => t.signal === val).length
  return bot.trades.filter(t => t.status === val).length
}

const filteredTrades = computed(() => {
  const v = activeFilter.value
  if (v === 'ALL')  return bot.trades
  if (v === 'BUY' || v === 'SELL') return bot.trades.filter(t => t.signal === v)
  return bot.trades.filter(t => t.status === v)
})

const accuracyColor = computed(() => {
  const a = bot.displayStats.accuracy
  return a >= 65 ? 'text-neon-green' : a >= 50 ? 'text-neon-amber' : 'text-neon-red'
})
const accuracyGradient = computed(() => {
  const a = bot.displayStats.accuracy
  return a >= 65 ? 'var(--accent-green)' : a >= 50 ? 'var(--accent-amber)' : 'var(--accent-red)'
})

function formatTime(iso: string) {
  try { return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return iso?.slice(11, 19) ?? '—' }
}
</script>

<style lang="scss" scoped>
.signals-page {
  background: var(--bg-deep);
  min-height: 100vh;
}

.font-mono { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }
.gap-2 { gap: 8px; }

// ── Header ────────────────────────────────────────────────────────────────────
.signals-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--border-subtle);

  @media (max-width: 599px) { padding: 12px; }
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.filter-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  cursor: pointer;
  border: 1px solid var(--border-subtle);
  background: rgba(255,255,255,0.03);
  color: var(--text-muted);
  transition: all 0.15s;

  &:hover { color: var(--text-primary); border-color: rgba(255,255,255,0.15); }

  &.filter-active {
    &.filter-all  { border-color: var(--accent-cyan);   background: rgba(0,212,255,0.12);  color: var(--accent-cyan);  }
    &.filter-buy  { border-color: var(--accent-green);  background: rgba(0,255,136,0.12);  color: var(--accent-green); }
    &.filter-sell { border-color: var(--accent-red);    background: rgba(255,68,102,0.12); color: var(--accent-red);  }
    &.filter-win  { border-color: var(--accent-green);  background: rgba(0,255,136,0.12);  color: var(--accent-green); }
    &.filter-loss { border-color: var(--accent-red);    background: rgba(255,68,102,0.12); color: var(--accent-red);  }
    &.filter-open { border-color: var(--accent-cyan);   background: rgba(0,212,255,0.08);  color: var(--accent-cyan);  }
  }
}
.filter-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.08);
  border-radius: 100px;
  padding: 0 5px;
  min-width: 18px;
  height: 16px;
  font-size: 10px;
}

// ── Summary cards ─────────────────────────────────────────────────────────────
.sum-card {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 14px 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  transition: border-color 0.2s;
  &:hover { border-color: var(--border-glow); }

  @media (max-width: 599px) { padding: 12px; border-radius: 10px; }
}
.sum-label { font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: var(--text-muted); }
.sum-val   { font-size: 24px; font-weight: 700; line-height: 1; @media (max-width: 599px) { font-size: 20px; } }
.sum-sub   { font-size: 11px; }

.accuracy-bar  { height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
.accuracy-fill { height: 100%; border-radius: 2px; transition: width 0.8s ease; }

// ── Trade cards ───────────────────────────────────────────────────────────────
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.trade-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  margin-bottom: 8px;
  border-left: 3px solid transparent;
  transition: border-color 0.15s, background 0.15s;

  &:hover { background: rgba(255,255,255,0.015); }

  &.tc-win   { border-left-color: rgba(0,255,136,0.5);  }
  &.tc-loss  { border-left-color: rgba(255,68,102,0.5); }
  &.tc-open  { border-left-color: rgba(0,212,255,0.5);  }
  &.tc-error { border-left-color: rgba(255,255,255,0.1); }

  @media (max-width: 599px) { padding: 12px; border-radius: 10px; }
}

.tc-row1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
}

.tc-row2 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.tc-reason {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(0,0,0,0.15);
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
}

.tc-pnl {
  font-size: 16px;
  font-weight: 700;
  @media (max-width: 599px) { font-size: 14px; }
}

// Direction badge
.dir-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;

  &.dir-buy  { background: rgba(0,255,136,0.12); border: 1px solid rgba(0,255,136,0.35); color: var(--accent-green); }
  &.dir-sell { background: rgba(255,68,102,0.12); border: 1px solid rgba(255,68,102,0.35); color: var(--accent-red); }
}

// Result badge
.result-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;

  &.rb-win  { background: rgba(0,255,136,0.12); color: var(--accent-green); }
  &.rb-loss { background: rgba(255,68,102,0.12); color: var(--accent-red); }
  &.rb-open { background: rgba(0,212,255,0.12); color: var(--accent-cyan); }
  &.rb-err  { background: rgba(255,255,255,0.06); color: var(--text-muted); }
}

// Confidence bar
.conf-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 120px;
  max-width: 220px;
}
.conf-bar  { flex: 1; height: 4px; background: rgba(255,255,255,0.08); border-radius: 2px; overflow: hidden; }
.conf-fill { height: 100%; border-radius: 2px; transition: width 0.4s ease; }
</style>
