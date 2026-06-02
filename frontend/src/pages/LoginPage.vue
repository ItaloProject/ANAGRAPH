<template>
  <div class="login-page flex flex-center" style="min-height:100vh;width:100%">

    <!-- Background grid -->
    <div class="bg-grid" />
    <div class="scan-overlay" />

    <div class="login-card animate-float">

      <!-- Logo -->
      <div class="logo-wrap q-mb-xl">
        <div class="logo-mark-lg" />
        <div class="logo-text">
          <span class="text-neon-cyan" style="font-size:36px;font-weight:800;letter-spacing:6px;">ANA</span>
          <span style="font-size:36px;font-weight:200;color:var(--text-secondary);letter-spacing:6px;">GRAPH</span>
        </div>
        <div class="text-caption text-muted q-mt-xs" style="letter-spacing:3px;">
          AI TRADING BOT · DERIV
        </div>
      </div>

      <!-- Features -->
      <div class="features q-mb-xl">
        <div class="feature-item">
          <q-icon name="auto_graph" color="cyan" size="18px" />
          <span>Análise técnica em tempo real</span>
        </div>
        <div class="feature-item">
          <q-icon name="bolt" color="positive" size="18px" />
          <span>Sinais RSI + MACD + Bollinger</span>
        </div>
        <div class="feature-item">
          <q-icon name="security" color="purple" size="18px" />
          <span>Gerenciamento de risco automático</span>
        </div>
        <div class="feature-item">
          <q-icon name="account_balance_wallet" color="amber" size="18px" />
          <span>Conta Demo $10.000 virtual</span>
        </div>
      </div>

      <!-- Login button -->
      <q-btn
        unelevated
        class="login-btn full-width q-py-md"
        @click="loginWithDeriv"
        :loading="loading"
      >
        <div class="row items-center gap-3 justify-center">
          <img src="https://deriv.com/static/images/logo/brand/deriv-logo-red.svg"
            style="height:24px;" alt="Deriv" onerror="this.style.display='none'"
          />
          <span class="text-weight-bold" style="font-size:15px;letter-spacing:1px;">
            ENTRAR COM DERIV
          </span>
          <q-icon name="arrow_forward" size="18px" />
        </div>
      </q-btn>

      <div class="text-caption text-muted text-center q-mt-md">
        Você será redirecionado para o site da DERIV para autorizar o acesso.<br>
        O token fica salvo localmente no seu navegador para operar o bot.
      </div>

      <!-- Demo badge -->
      <div class="demo-badge q-mt-lg">
        <q-icon name="school" size="14px" />
        <span>Funciona com conta Demo — sem risco real</span>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const loading = ref(false)

// App ID registrado no portal Deriv Developers
// ⚠️  O redirect_uri abaixo DEVE estar cadastrado em:
//     https://app.deriv.com/account/api-token → OAuth Apps
//     Adicione: https://SEU_DOMINIO.vercel.app/#/auth/callback
const APP_ID = import.meta.env.VITE_DERIV_APP_ID ?? '33qwHdRH3vY9cCAeAzIa7'

function loginWithDeriv() {
  loading.value = true

  // OAuth não suporta '#' no redirect_uri.
  // Usamos path real: https://app.com/auth/callback
  // O Vercel serve index.html para qualquer path (catch-all rewrite).
  // O boot 'oauth-redirect' processa os params e redireciona para /#/
  const redirectUri = encodeURIComponent(window.location.origin + '/auth/callback')

  const url = `https://oauth.deriv.com/oauth2/authorize?app_id=${APP_ID}&l=PT&brand=deriv&redirect_uri=${redirectUri}`
  window.location.href = url
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

.features {
  display: flex; flex-direction: column; gap: 12px;
}
.feature-item {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px; color: var(--text-secondary);
  padding: 8px 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.04);
}

.login-btn {
  background: linear-gradient(135deg, #FF444C, #CC0000) !important;
  border-radius: 12px !important;
  box-shadow: 0 4px 24px rgba(255,68,76,0.4) !important;
  transition: all 0.3s ease !important;
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(255,68,76,0.6) !important;
  }
}

.demo-badge {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 8px 16px;
  background: rgba(0,255,136,0.06);
  border: 1px solid rgba(0,255,136,0.2);
  border-radius: 100px;
  font-size: 12px; color: var(--accent-green);
}

.gap-3 { gap: 12px; }
.text-muted { color: var(--text-muted); }
</style>
