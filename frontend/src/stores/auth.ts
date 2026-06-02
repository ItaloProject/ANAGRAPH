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

  function logout() {
    account.value = null
    localStorage.removeItem('deriv_account')
  }

  return { account, isLoggedIn, isDemo, accountLabel, setAccount, logout }
})
