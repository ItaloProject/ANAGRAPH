import type { BotConfig } from '../services/botApi'

/** Perfil oficial ANAGRAPH — qualidade e confluência máxima */
export const CONSERVATIVE_PROFILE: Required<
  Pick<
    BotConfig,
    | 'asset'
    | 'granularity'
    | 'contract_duration'
    | 'stake_amount'
    | 'max_stake'
    | 'daily_loss_limit'
    | 'daily_profit_target'
    | 'min_confidence'
    | 'max_consecutive_losses'
    | 'cooldown_after_loss_sec'
    | 'analyzer_min_score'
    | 'analyzer_min_gap'
    | 'analyzer_min_adx'
    | 'analyze_every'
  >
> = {
  asset:                   'EUR/USD',
  granularity:             900,
  contract_duration:       15,
  stake_amount:            6.0,
  max_stake:               60.0,
  daily_loss_limit:        100.0,
  daily_profit_target:     150.0,
  min_confidence:          78.0,
  max_consecutive_losses:  3,
  cooldown_after_loss_sec: 300,
  analyzer_min_score:      5,
  analyzer_min_gap:        2,
  analyzer_min_adx:        22.0,
  analyze_every:           15,
}

export function enforceConservative(cfg: BotConfig): BotConfig {
  const p = CONSERVATIVE_PROFILE
  return {
    ...cfg,
    asset:                   p.asset,
    granularity:             p.granularity,
    contract_duration:       Math.max(cfg.contract_duration ?? p.contract_duration, p.contract_duration),
    stake_amount:            cfg.stake_amount ?? p.stake_amount,
    max_stake:               cfg.max_stake ?? p.max_stake,
    daily_loss_limit:        cfg.daily_loss_limit ?? p.daily_loss_limit,
    daily_profit_target:     cfg.daily_profit_target ?? p.daily_profit_target,
    min_confidence:          Math.max(cfg.min_confidence ?? p.min_confidence, p.min_confidence),
    max_consecutive_losses:  Math.min(cfg.max_consecutive_losses ?? p.max_consecutive_losses, p.max_consecutive_losses),
    cooldown_after_loss_sec: Math.max(cfg.cooldown_after_loss_sec ?? p.cooldown_after_loss_sec, p.cooldown_after_loss_sec),
    analyzer_min_score:      Math.max(cfg.analyzer_min_score ?? p.analyzer_min_score, p.analyzer_min_score),
    analyzer_min_gap:        Math.max(cfg.analyzer_min_gap ?? p.analyzer_min_gap, p.analyzer_min_gap),
    analyzer_min_adx:        Math.max(cfg.analyzer_min_adx ?? p.analyzer_min_adx, p.analyzer_min_adx),
    analyze_every:           Math.max(cfg.analyze_every ?? p.analyze_every, p.analyze_every),
    limits_currency:         'BRL',
  }
}
