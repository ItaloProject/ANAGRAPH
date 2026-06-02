/**
 * OAuth legado DERIV — tokens retornam em ?acct1=&token1=&cur1=
 * @see https://developers.deriv.com/docs/authentication
 */

export const DEFAULT_DERIV_APP_ID = '33qwHdRH3vY9cCAeAzIa7'
export const PRODUCTION_REDIRECT_URI = 'https://anagraph-ten.vercel.app/auth/callback'

export function derivAppId(): string {
  return (import.meta.env.VITE_DERIV_APP_ID as string | undefined)?.trim() || DEFAULT_DERIV_APP_ID
}

export function derivRedirectUri(): string {
  const fromEnv = import.meta.env.VITE_DERIV_REDIRECT_URI as string | undefined
  if (fromEnv?.trim()) return fromEnv.trim()

  if (typeof window !== 'undefined') {
    if (window.location.hostname === 'anagraph-ten.vercel.app') {
      return PRODUCTION_REDIRECT_URI
    }
    return `${window.location.origin}/auth/callback`
  }
  return PRODUCTION_REDIRECT_URI
}

/** Monta URL de autorização OAuth legado. */
export function buildDerivOAuthUrl(): string {
  const params = new URLSearchParams({
    app_id: derivAppId(),
    l:      'PT',
    redirect_uri: derivRedirectUri(),
  })
  return `https://oauth.deriv.com/oauth2/authorize?${params.toString()}`
}

export interface ParsedDerivAccount {
  account: string
  token: string
  currency: string
  isVirtual: boolean
}

export function parseDerivOAuthQuery(search: string): ParsedDerivAccount[] {
  if (!search || !search.includes('acct1')) return []

  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
  const found: ParsedDerivAccount[] = []
  let i = 1

  while (params.get(`acct${i}`)) {
    const acctId = params.get(`acct${i}`)!
    found.push({
      account:   acctId,
      token:     params.get(`token${i}`) ?? '',
      currency:  (params.get(`cur${i}`) ?? 'USD').toUpperCase(),
      isVirtual: acctId.toUpperCase().startsWith('VRTC')
        || acctId.toUpperCase().startsWith('VRW')
        || acctId.toUpperCase().startsWith('DOT'),
    })
    i++
  }

  return found.filter(a => a.token)
}

export function saveDerivAccountFromQuery(search: string): ParsedDerivAccount | null {
  const accounts = parseDerivOAuthQuery(search)
  if (!accounts.length) return null

  const selected = accounts.find(a => a.isVirtual) ?? accounts[0]
  localStorage.setItem('deriv_account', JSON.stringify(selected))
  return selected
}

export function parseOAuthError(search: string): string | null {
  if (!search) return null
  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
  const error = params.get('error')
  if (!error) return null
  return params.get('error_description') || error
}

export const OAUTH_SEARCH_KEY = 'deriv_oauth_search'

export function stashOAuthSearch(search: string): void {
  sessionStorage.setItem(OAUTH_SEARCH_KEY, search)
}

export function takeOAuthSearch(): string {
  const stored = sessionStorage.getItem(OAUTH_SEARCH_KEY) ?? ''
  sessionStorage.removeItem(OAUTH_SEARCH_KEY)
  return stored
}
