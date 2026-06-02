<template>
  <div class="callback-page flex flex-center">
    <div class="bg-grid" />

    <!-- Carregando -->
    <div v-if="state === 'loading'" class="callback-card text-center animate-float">
      <div class="logo-mark-sm q-mx-auto q-mb-lg" />
      <q-spinner-dots color="cyan" size="48px" />
      <div class="text-neon-cyan q-mt-lg" style="letter-spacing:2px;font-weight:700;">
        AUTENTICANDO...
      </div>
      <div class="text-caption text-muted q-mt-sm">Conectando com a DERIV</div>
    </div>

    <!-- Seleção de conta (demo + real) -->
    <div v-else-if="state === 'select'" class="callback-card animate-float">
      <div class="logo-mark-sm q-mx-auto q-mb-lg" />
      <div class="text-weight-bold text-neon-cyan text-center q-mb-xs" style="font-size:18px;letter-spacing:2px;">
        ESCOLHA A CONTA
      </div>
      <div class="text-caption text-muted text-center q-mb-lg">
        A DERIV retornou {{ accounts.length }} conta(s)
      </div>

      <div class="account-list">
        <button
          v-for="acc in accounts"
          :key="acc.account"
          class="account-btn"
          :class="acc.isVirtual ? 'btn-demo' : 'btn-real'"
          @click="selectAccount(acc)"
        >
          <div class="row items-center gap-3">
            <q-icon
              :name="acc.isVirtual ? 'school' : 'account_balance'"
              size="24px"
              :color="acc.isVirtual ? 'positive' : 'amber'"
            />
            <div class="text-left">
              <div class="text-weight-bold" style="font-size:14px;">
                {{ acc.isVirtual ? 'Conta Demo' : 'Conta Real' }}
              </div>
              <div class="text-caption" style="opacity:.7;">
                {{ acc.account }} · {{ acc.currency }}
              </div>
            </div>
            <q-space />
            <q-badge
              :color="acc.isVirtual ? 'positive' : 'warning'"
              :label="acc.isVirtual ? 'DEMO' : 'REAL'"
              rounded
            />
          </div>
          <div v-if="acc.isVirtual" class="demo-hint q-mt-xs">
            Recomendado — sem risco financeiro
          </div>
        </button>
      </div>
    </div>

    <!-- Erro -->
    <div v-else-if="state === 'error'" class="callback-card text-center animate-float">
      <div class="logo-mark-sm q-mx-auto q-mb-lg" />
      <q-icon name="error_outline" color="negative" size="52px" />
      <div class="text-neon-red q-mt-md text-weight-bold" style="font-size:16px;">
        Falha na autenticação
      </div>
      <div class="text-caption text-muted q-mt-sm q-mb-lg">{{ errorMsg }}</div>
      <q-btn unelevated color="cyan" text-color="black" label="Tentar novamente"
        to="/login" icon="arrow_back" style="font-weight:700;" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import type { DerivAccount } from '../stores/auth'

const router    = useRouter()
const route     = useRoute()
const authStore = useAuthStore()

type State = 'loading' | 'select' | 'error'
const state    = ref<State>('loading')
const errorMsg = ref('')
const accounts = ref<DerivAccount[]>([])

onMounted(() => {
  // ── Com hash routing, a Deriv redireciona para:
  //    https://app.com/#/auth/callback?acct1=VRTCX&token1=TOKEN
  // Vue Router com hash history já parseia corretamente:
  //    route.query = { acct1: 'VRTCX', token1: 'TOKEN', ... }
  //
  // Fallback: se chegou por URL normal (sem hash), usa window.location.search
  const q = Object.keys(route.query).length
    ? route.query
    : Object.fromEntries(new URLSearchParams(window.location.search))

  const found: DerivAccount[] = []
  let i = 1
  while (q[`acct${i}`]) {
    const acctId = String(q[`acct${i}`])
    found.push({
      account:   acctId,
      token:     String(q[`token${i}`] ?? ''),
      currency:  String(q[`cur${i}`] ?? 'USD'),
      isVirtual: acctId.startsWith('VRTC'),
    })
    i++
  }

  if (!found.length) {
    errorMsg.value = 'Nenhuma conta encontrada na resposta da DERIV. Tente fazer login novamente.'
    state.value = 'error'
    return
  }

  accounts.value = found

  // Se só há uma conta — seleciona automaticamente
  if (found.length === 1) {
    selectAccount(found[0])
    return
  }

  // Se há demo + real — mostra seletor
  state.value = 'select'
})

function selectAccount(acc: DerivAccount) {
  authStore.setAccount(acc)
  router.push('/')
}
</script>

<style lang="scss" scoped>
.callback-page {
  background: var(--bg-deep);
  min-height: 100vh;
  width: 100%;
  position: relative;
  overflow: hidden;
}

.bg-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
}

.callback-card {
  position: relative; z-index: 1;
  width: 100%; max-width: 420px;
  background: var(--bg-glass);
  backdrop-filter: blur(24px);
  border: 1px solid var(--border-glow);
  border-radius: 20px;
  padding: 40px 32px;
  box-shadow: var(--glow-cyan), 0 40px 80px rgba(0,0,0,0.5);

  @media (max-width: 599px) {
    margin: 16px;
    padding: 28px 20px;
  }
}

.logo-mark-sm {
  width: 14px; height: 14px;
  background: var(--accent-cyan);
  border-radius: 3px;
  box-shadow: var(--glow-cyan);
  transform: rotate(45deg);
}

.account-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.account-btn {
  width: 100%;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
  background: rgba(255,255,255,0.03);
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;

  &:hover { transform: translateY(-2px); }

  &.btn-demo {
    border-color: rgba(0,255,136,0.3);
    background: rgba(0,255,136,0.05);
    &:hover { border-color: rgba(0,255,136,0.6); box-shadow: 0 4px 20px rgba(0,255,136,0.15); }
  }
  &.btn-real {
    border-color: rgba(255,184,0,0.3);
    background: rgba(255,184,0,0.05);
    &:hover { border-color: rgba(255,184,0,0.6); box-shadow: 0 4px 20px rgba(255,184,0,0.15); }
  }
}

.demo-hint {
  font-size: 10px;
  color: var(--accent-green);
  opacity: 0.7;
  padding-left: 36px;
}

.gap-3 { gap: 12px; }
.text-muted { color: var(--text-muted); }
</style>
