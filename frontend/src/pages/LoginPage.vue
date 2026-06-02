<template>
  <div class="login-page flex flex-center" style="min-height:100vh;width:100%">

    <div class="bg-grid" />
    <div class="scan-overlay" />

    <div class="login-card animate-float">

      <div class="logo-wrap q-mb-lg">
        <div class="logo-mark-lg" />
        <div class="logo-text">
          <span class="text-neon-cyan" style="font-size:36px;font-weight:800;letter-spacing:6px;">ANA</span>
          <span style="font-size:36px;font-weight:200;color:var(--text-secondary);letter-spacing:6px;">GRAPH</span>
        </div>
        <div class="text-caption text-muted q-mt-xs" style="letter-spacing:3px;">
          AI TRADING BOT · DERIV
        </div>
      </div>

      <q-banner v-if="oauthError" dense rounded class="bg-negative text-white q-mb-md">
        OAuth: {{ oauthError }}
      </q-banner>

      <!-- Entrada principal: servidor já configurado -->
      <template v-if="serverSession?.available">
        <div class="server-ready q-mb-md">
          <q-icon name="check_circle" color="positive" size="20px" />
          <div>
            <div class="text-weight-bold text-neon-green">Servidor pronto</div>
            <div class="text-caption text-muted">
              Conta {{ serverSession.is_demo ? 'Demo' : 'Real' }} · {{ serverSession.account_hint }}
            </div>
          </div>
        </div>

        <q-btn
          unelevated
          class="login-btn full-width q-py-md"
          :loading="entering"
          @click="enterWithServer"
        >
          <span class="text-weight-bold" style="font-size:15px;letter-spacing:1px;">
            ENTRAR NO ANAGRAPH
          </span>
          <q-icon name="arrow_forward" class="q-ml-sm" />
        </q-btn>

        <div class="text-caption text-muted text-center q-mt-sm">
          Usa as credenciais seguras do servidor — sem OAuth.
        </div>
      </template>

      <template v-else-if="checkingServer">
        <div class="text-center q-py-lg">
          <q-spinner-dots color="cyan" size="40px" />
          <div class="text-caption text-muted q-mt-sm">Conectando ao servidor...</div>
        </div>
      </template>

      <template v-else>
        <q-banner dense rounded class="bg-warning text-black q-mb-md">
          Servidor offline ou sem credenciais. Use OAuth ou token manual abaixo.
        </q-banner>
      </template>

      <q-separator class="q-my-lg" color="grey-9" />

      <div class="text-caption text-muted q-mb-sm" style="letter-spacing:1px;">OUTRAS OPÇÕES</div>

      <q-btn
        outline
        color="negative"
        class="full-width q-mb-sm"
        no-caps
        :loading="oauthLoading"
        @click="loginWithDeriv"
      >
        <span class="text-weight-bold">Entrar com OAuth DERIV</span>
      </q-btn>

      <q-expansion-item
        dense
        icon="vpn_key"
        label="Colar token API manualmente"
        header-class="text-cyan"
        class="manual-token q-mt-xs"
      >
        <div class="q-pa-sm">
          <q-input
            v-model="manualAccount"
            dense
            outlined
            dark
            label="Account ID (ex: DOT91884478)"
            class="q-mb-sm"
          />
          <q-input
            v-model="manualToken"
            dense
            outlined
            dark
            type="password"
            label="API Token"
            class="q-mb-sm"
          />
          <q-btn
            flat
            no-caps
            color="cyan"
            class="full-width"
            label="Entrar com token"
            :disable="!manualAccount.trim() || !manualToken.trim()"
            @click="enterWithManualToken"
          />
        </div>
      </q-expansion-item>

      <div class="demo-badge q-mt-lg">
        <q-icon name="school" size="14px" />
        <span>Funciona com conta Demo — sem risco real</span>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import { buildDerivOAuthUrl } from '../utils/derivOAuth'
import { botApi } from '../services/botApi'
import { useAuthStore } from '../stores/auth'

interface ServerSession {
  available: boolean
  account_id?: string
  account_hint?: string
  is_demo?: boolean
  currency?: string
}

const $q         = useQuasar()
const router     = useRouter()
const authStore  = useAuthStore()

const checkingServer = ref(true)
const entering       = ref(false)
const oauthLoading   = ref(false)
const serverSession  = ref<ServerSession | null>(null)
const oauthError     = ref(sessionStorage.getItem('oauth_error') ?? '')
const manualAccount  = ref('')
const manualToken    = ref('')

onMounted(async () => {
  if (oauthError.value) sessionStorage.removeItem('oauth_error')

  try {
    const { data } = await botApi.credentials()
    if (data.token_configured && data.account_configured) {
      serverSession.value = {
        available:     true,
        account_id:    data.account_id,
        account_hint:  data.account_id_hint,
        is_demo:       data.is_demo ?? true,
        currency:      'USD',
      }
    } else {
      serverSession.value = { available: false }
    }
  } catch {
    serverSession.value = { available: false }
  } finally {
    checkingServer.value = false
  }
})

function enterWithServer() {
  if (!serverSession.value?.available || !serverSession.value.account_id) return
  entering.value = true
  authStore.loginWithServerSession({
    account_id: serverSession.value.account_id,
    is_demo:    serverSession.value.is_demo,
    currency:   serverSession.value.currency,
  })
  router.push('/')
}

function enterWithManualToken() {
  authStore.loginWithManualToken(manualAccount.value, manualToken.value)
  $q.notify({ type: 'positive', message: 'Token salvo localmente', position: 'top-right' })
  router.push('/')
}

function loginWithDeriv() {
  oauthLoading.value = true
  window.location.href = buildDerivOAuthUrl()
}
</script>

<style lang="scss" scoped>
.login-page {
  background: var(--bg-deep);
  min-height: 100vh;
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

.login-card {
  position: relative; z-index: 1;
  width: 100%; max-width: 440px;
  background: var(--bg-glass);
  backdrop-filter: blur(24px);
  border: 1px solid var(--border-glow);
  border-radius: 24px;
  padding: 48px 40px;
  box-shadow: var(--glow-cyan), 0 40px 80px rgba(0,0,0,0.6);
}

.logo-wrap {
  display: flex; flex-direction: column; align-items: center;
}
.logo-mark-lg {
  width: 16px; height: 16px;
  background: var(--accent-cyan);
  border-radius: 4px;
  box-shadow: var(--glow-cyan);
  transform: rotate(45deg);
  margin-bottom: 16px;
}
.logo-text { display: flex; align-items: baseline; }

.server-ready {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px;
  background: rgba(0,255,136,0.06);
  border: 1px solid rgba(0,255,136,0.25);
  border-radius: 12px;
}

.login-btn {
  background: linear-gradient(135deg, #00d4ff, #0099cc) !important;
  border-radius: 12px !important;
  box-shadow: 0 4px 24px rgba(0,212,255,0.35) !important;
  color: #000 !important;
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0,212,255,0.5) !important;
  }
}

.manual-token {
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  overflow: hidden;
}

.demo-badge {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 8px 16px;
  background: rgba(0,255,136,0.06);
  border: 1px solid rgba(0,255,136,0.2);
  border-radius: 100px;
  font-size: 12px; color: var(--accent-green);
}

.text-muted { color: var(--text-muted); }
</style>
