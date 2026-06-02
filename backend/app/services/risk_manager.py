from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    stake_amount: float = 1.0
    max_stake: float = 10.0
    daily_loss_limit: float = 20.0
    daily_profit_target: float = 50.0
    max_open_positions: int = 1
    min_confidence: float = 78.0
    max_consecutive_losses: int = 3
    cooldown_after_loss_sec: int = 300
    martingale: bool = False
    martingale_multiplier: float = 2.0


@dataclass
class DailyStats:
    date: date = field(default_factory=date.today)
    pnl: float = 0.0
    wins: int = 0
    losses: int = 0
    trades: int = 0
    open_positions: int = 0
    current_streak: int = 0
    current_stake: float = 1.0
    last_loss_at: datetime | None = None


class RiskDecision:
    def __init__(self, allowed: bool, reason: str, stake: float = 0.0):
        self.allowed = allowed
        self.reason  = reason
        self.stake   = stake


class RiskManager:
    """
    Protects capital by enforcing trading limits before each entry.
    Tracks daily P&L and blocks trading when safety thresholds are hit.
    """

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()
        self.stats  = DailyStats(current_stake=self.config.stake_amount)

    def _reset_if_new_day(self):
        today = date.today()
        if self.stats.date != today:
            logger.info(f"New trading day. Previous P&L: {self.stats.pnl:.2f}")
            self.stats = DailyStats(
                date=today,
                current_stake=self.config.stake_amount,
            )

    def can_trade(self, confidence: float, signal: str, win_rate: float = 0.0) -> RiskDecision:
        self._reset_if_new_day()

        if signal == "WAIT":
            return RiskDecision(False, "Sinal de espera")

        if confidence < self.config.min_confidence:
            return RiskDecision(
                False,
                f"Confiança {confidence:.1f}% abaixo do mínimo {self.config.min_confidence:.0f}%",
            )

        if self.stats.open_positions >= self.config.max_open_positions:
            return RiskDecision(
                False,
                f"Máximo de {self.config.max_open_positions} posição(ões) aberta(s)",
            )

        if self.stats.pnl <= -abs(self.config.daily_loss_limit):
            return RiskDecision(False, f"Limite de perda diária atingido (${self.stats.pnl:.2f})")

        if self.stats.pnl >= self.config.daily_profit_target:
            return RiskDecision(False, f"Meta de lucro diária atingida (${self.stats.pnl:.2f})")

        if self.stats.current_streak <= -self.config.max_consecutive_losses:
            return RiskDecision(
                False,
                f"Pausa após {abs(self.stats.current_streak)} losses seguidos — retome amanhã",
            )

        if self.stats.last_loss_at and self.config.cooldown_after_loss_sec > 0:
            elapsed = (datetime.now() - self.stats.last_loss_at).total_seconds()
            remaining = self.config.cooldown_after_loss_sec - elapsed
            if remaining > 0:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                return RiskDecision(
                    False,
                    f"Cooldown pós-loss ({mins}:{secs:02d} restantes)",
                )

        stake = self._calculate_stake(confidence, win_rate)
        return RiskDecision(True, "Operação aprovada", stake)

    def _calculate_stake(self, confidence: float = 0.0, win_rate: float = 0.0) -> float:
        """
        Stake dinâmico em três camadas:
          1. Martingale (se ativado) — multiplica após loss
          2. Kelly Criterion (baseado em win_rate histórico)
          3. Confidence scaling — boost proporcional à confiança acima do mínimo
        Resultado sempre limitado por max_stake.
        """
        base = self.config.stake_amount

        if self.config.martingale and self.stats.current_streak < 0:
            mult = self.config.martingale_multiplier ** abs(self.stats.current_streak)
            return min(base * mult, self.config.max_stake)

        # ── Kelly Criterion para binary options ───────────────────────────
        # Para ser positivo: win_rate precisa ser > 1/(1+payout) ≈ 54% com payout 0.85
        DERIV_PAYOUT = 0.85
        if win_rate >= 0.55:
            kelly = (win_rate * DERIV_PAYOUT - (1.0 - win_rate)) / DERIV_PAYOUT
            # Usa 30% do Kelly (conservador) — nunca mais que 1.6× o stake base
            kelly_factor = 1.0 + min(0.6, kelly * 0.30)
            base = base * kelly_factor

        # ── Confidence scaling ────────────────────────────────────────────
        # 78% (mínimo) → ×1.0 | 88% → ×1.25 | 95%+ → ×1.5
        min_conf = self.config.min_confidence
        if confidence > min_conf:
            conf_factor = 1.0 + (confidence - min_conf) / max(1.0, 95.0 - min_conf) * 0.5
            base = base * min(1.5, conf_factor)

        return round(min(base, self.config.max_stake), 2)

    def on_trade_opened(self):
        self.stats.open_positions += 1
        self.stats.trades += 1

    def on_trade_closed(self, pnl: float):
        self.stats.open_positions = max(0, self.stats.open_positions - 1)
        self.stats.pnl += pnl

        if pnl > 0:
            self.stats.wins += 1
            self.stats.current_streak = max(0, self.stats.current_streak) + 1
            self.stats.current_stake = self.config.stake_amount
        else:
            self.stats.losses += 1
            self.stats.current_streak = min(0, self.stats.current_streak) - 1
            self.stats.last_loss_at = datetime.now()

        logger.info(
            f"Trade closed. P&L: {pnl:+.2f} | Day: {self.stats.pnl:+.2f} "
            f"| W/L: {self.stats.wins}/{self.stats.losses} | Streak: {self.stats.current_streak}"
        )

    def rebuild_from_closed_trades(self, entries: list[tuple[float, str | None]]):
        """Reconstrói stats do dia a partir de trades já fechados (ex.: sync DERIV)."""
        self._reset_if_new_day()
        self.stats = DailyStats(current_stake=self.config.stake_amount)
        for pnl, closed_at in entries:
            self.stats.trades += 1
            self.stats.pnl += pnl
            if pnl > 0:
                self.stats.wins += 1
                self.stats.current_streak = max(0, self.stats.current_streak) + 1
            else:
                self.stats.losses += 1
                self.stats.current_streak = min(0, self.stats.current_streak) - 1
                if closed_at:
                    try:
                        self.stats.last_loss_at = datetime.fromisoformat(closed_at)
                    except ValueError:
                        self.stats.last_loss_at = datetime.now()
                else:
                    self.stats.last_loss_at = datetime.now()

    @property
    def summary(self) -> dict:
        self._reset_if_new_day()
        total = self.stats.wins + self.stats.losses or 1
        return {
            "date":             str(self.stats.date),
            "pnl":              round(self.stats.pnl, 2),
            "wins":             self.stats.wins,
            "losses":           self.stats.losses,
            "trades":           self.stats.trades,
            "accuracy":         round(self.stats.wins / total * 100, 1),
            "open_positions":   self.stats.open_positions,
            "current_streak":   self.stats.current_streak,
            "daily_limit_used": round(
                abs(self.stats.pnl) / self.config.daily_loss_limit * 100, 1,
            ) if self.stats.pnl < 0 else 0,
        }
