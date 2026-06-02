/** Valores monetários na UI são sempre BRL; a DERIV executa em USD. */

export const DEFAULT_USD_BRL_RATE = 5.85

let usdBrlRate = DEFAULT_USD_BRL_RATE

export function setUsdBrlRate(rate: number) {
  if (rate > 0) usdBrlRate = rate
}

export function getUsdBrlRate(): number {
  return usdBrlRate
}

export function usdToBrl(usd: number): number {
  return Math.round(usd * usdBrlRate * 100) / 100
}

export function brlToUsd(brl: number): number {
  return Math.round((brl / usdBrlRate) * 10000) / 10000
}

export function formatBrl(value: number, signed = false): string {
  const abs = Math.abs(value)
  const formatted = abs.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  if (!signed) return `R$ ${formatted}`
  if (value > 0) return `+R$ ${formatted}`
  if (value < 0) return `-R$ ${formatted}`
  return `R$ ${formatted}`
}

/** Converte valor vindo da DERIV (USD) e formata em reais */
export function formatUsdAsBrl(usd: number, signed = false): string {
  return formatBrl(usdToBrl(usd), signed)
}

/** Migra config antiga salva em USD para BRL */
export function migrateConfigToBrl<T extends Record<string, unknown>>(cfg: T): T & { limits_currency: 'BRL' } {
  if (cfg.limits_currency === 'BRL') return cfg as T & { limits_currency: 'BRL' }
  const rate = getUsdBrlRate()
  return {
    ...cfg,
    stake_amount:            Math.round(((cfg.stake_amount as number) ?? 1) * rate * 100) / 100,
    max_stake:               Math.round(((cfg.max_stake as number) ?? 10) * rate * 100) / 100,
    daily_loss_limit:        Math.round(((cfg.daily_loss_limit as number) ?? 20) * rate),
    daily_profit_target:     Math.round(((cfg.daily_profit_target as number) ?? 30) * rate),
    limits_currency:         'BRL',
  }
}
