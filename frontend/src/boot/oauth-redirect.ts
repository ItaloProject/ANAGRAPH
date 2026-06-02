/**
 * Intercepta retorno OAuth da DERIV antes do router (path /auth/callback).
 */
import { boot } from 'quasar/wrappers'
import { parseOAuthError, stashOAuthSearch } from '../utils/derivOAuth'

export default boot(() => {
  const search = window.location.search
  if (!search) return

  const oauthError = parseOAuthError(search)
  if (oauthError) {
    sessionStorage.setItem('oauth_error', oauthError)
    window.location.replace(`${window.location.origin}/#/login`)
    return
  }

  if (!search.includes('acct1=')) return

  stashOAuthSearch(search)
  window.location.replace(`${window.location.origin}/#/auth/callback`)
})
