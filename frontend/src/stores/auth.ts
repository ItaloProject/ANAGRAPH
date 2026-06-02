import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface DerivAccount {
  account:   string
  token:     string
  currency:  string
  isVirtual: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const account = ref<DerivAccount | null>(
    JSON.parse(localStorage.getItem('deriv_account') || 'null')
  )

  const isLoggedIn  = computed(() => !!account.value?.token)
  const isDemo      = computed(() => account.value?.isVirtual ?? true)
  const accountLabel = computed(() => {
    if (!account.value) return ''
    return account.value.isVirtual
      ? `Demo · ${account.value.account}`
      : `Real · ${account.value.account}`
  })

  function setAccount(acc: DerivAccount) {
    account.value = acc
    localStorage.setItem('deriv_account', JSON.stringify(acc))
  }

  function loginWithServerSession(session: {
    account_id: string
    is_demo?: boolean
    currency?: string
  }) {
    setAccount({
      account:   session.account_id,
      token:     'server',
      currency:  session.currency ?? 'USD',
      isVirtual: session.is_demo ?? true,
    })
  }

  function loginWithManualToken(accountId: string, token: string, currency = 'USD') {
    const id = accountId.trim().toUpperCase()
    setAccount({
      account:   accountId.trim(),
      token:     token.trim(),
      currency:  currency.toUpperCase(),
      isVirtual: id.startsWith('VRTC') || id.startsWith('VRW') || id.startsWith('DOT'),
    })
  }

  function logout() {
    account.value = null
    localStorage.removeItem('deriv_account')
  }

  return { account, isLoggedIn, isDemo, accountLabel, setAccount, loginWithServerSession, loginWithManualToken, logout }
})
