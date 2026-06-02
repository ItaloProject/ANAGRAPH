/** Backend hospedado no Render (bot + credenciais DERIV). */
export const RENDER_API_BASE = 'https://anagraph-api.onrender.com/api'
export const RENDER_WS_BASE  = 'wss://anagraph-api.onrender.com'

function isProdHost(hostname: string): boolean {
  return hostname.includes('vercel.app') || hostname === 'anagraph-ten.vercel.app'
}

export function resolveApiBase(): string {
  const fromEnv = import.meta.env.VITE_API_BASE as string | undefined
  if (fromEnv?.trim()) return fromEnv.trim().replace(/\/$/, '')

  if (typeof window !== 'undefined' && isProdHost(window.location.hostname)) {
    return RENDER_API_BASE
  }
  return '/api'
}

export function resolveWsBase(): string {
  const fromEnv = import.meta.env.VITE_WS_BASE as string | undefined
  if (fromEnv?.trim()) return fromEnv.trim().replace(/\/$/, '')

  if (typeof window !== 'undefined' && isProdHost(window.location.hostname)) {
    return RENDER_WS_BASE
  }
  if (typeof window === 'undefined') return 'ws://localhost:8001'

  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}`
}
