<template>
  <div class="flex flex-center" style="background:var(--bg-deep);min-height:100vh;width:100%;">
    <div class="text-center animate-float">
      <div class="logo-mark-lg q-mx-auto q-mb-lg" />
      <div v-if="loading">
        <q-spinner-dots color="cyan" size="48px" />
        <div class="text-neon-cyan q-mt-md" style="letter-spacing:2px;">CONECTANDO...</div>
        <div class="text-caption text-muted q-mt-sm">Autenticando com DERIV</div>
      </div>
      <div v-else-if="error">
        <q-icon name="error_outline" color="negative" size="48px" />
        <div class="text-neon-red q-mt-md">Falha na autenticação</div>
        <div class="text-caption text-muted q-mt-sm">{{ error }}</div>
        <q-btn unelevated color="cyan" label="Tentar novamente" to="/login" class="q-mt-lg" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router    = useRouter()
const authStore = useAuthStore()
const loading   = ref(true)
const error     = ref('')

onMounted(async () => {
  // DERIV redireciona com ?acct1=VRTCXXXXX&token1=TOKEN&cur1=USD
  const params = new URLSearchParams(window.location.search)

  // Coletar todas as contas retornadas (pode retornar demo + real)
  const accounts: { account: string; token: string; currency: string; isVirtual: boolean }[] = []
  let i = 1
  while (params.get(`acct${i}`)) {
    const acct = params.get(`acct${i}`)!
    accounts.push({
      account:   acct,
      token:     params.get(`token${i}`) || '',
      currency:  params.get(`cur${i}`) || 'USD',
      isVirtual: acct.startsWith('VRTC'),
    })
    i++
  }

  if (!accounts.length) {
    error.value = 'Nenhuma conta encontrada na resposta da DERIV'
    loading.value = false
    return
  }

  // Prioriza conta virtual/demo
  const demo = accounts.find(a => a.isVirtual) || accounts[0]
  authStore.setAccount(demo)

  loading.value = false
  router.push('/')
})
</script>

<style scoped>
.logo-mark-lg {
  width: 20px; height: 20px;
  background: var(--accent-cyan);
  border-radius: 4px;
  box-shadow: var(--glow-cyan);
  transform: rotate(45deg);
}
.text-muted { color: var(--text-muted); }
</style>
