/**
 * Boot: OAuth Redirect Handler
 *
 * A Deriv redireciona para https://anagraph-ten.vercel.app/auth/callback?acct1=...
 * O Vercel serve index.html para esse path (catch-all rewrite).
 * Este boot lê os parâmetros OAuth de window.location.search ANTES do router
 * inicializar, salva a conta no localStorage e redireciona para o app.
 */
import { boot } from 'quasar/wrappers'

export default boot(() => {
  const path   = window.location.pathname   // ex: "/auth/callback"
  const search = window.location.search     // ex: "?acct1=VRTCX&token1=TOKEN"

  if (!path.includes('auth/callback') || !search.includes('acct1')) return

  const params   = new URLSearchParams(search)
  const accounts: { account: string; token: string; currency: string; isVirtual: boolean }[] = []

  let i = 1
  while (params.get(`acct${i}`)) {
    const acctId = params.get(`acct${i}`)!
    accounts.push({
      account:   acctId,
      token:     params.get(`token${i}`) ?? '',
      currency:  params.get(`cur${i}`)   ?? 'USD',
      isVirtual: acctId.startsWith('VRTC'),
    })
    i++
  }

  if (!accounts.length) return

  // Prioriza conta demo; caso não exista, usa a primeira
  const selected = accounts.find(a => a.isVirtual) ?? accounts[0]

  // Salva direto no localStorage (o Pinia store lê daqui na inicialização)
  localStorage.setItem('deriv_account', JSON.stringify(selected))

  // Redireciona para o app (hash router assume o controle a partir daqui)
  window.location.replace('/#/')
})
