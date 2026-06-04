"""
AdaptiveController — self-adjusting parameter engine for ANAGRAPH.

Monitors the rolling win rate of the last N closed trades and
tightens / relaxes thresholds to protect capital during drawdowns
and optimize selectivity during high-performance windows.

Rules (applied after every closed trade):
  win_rate >= 65%  → reward:  relax min_confidence by 1pt (floor kept)
  win_rate 50-65%  → neutral: no change
  win_rate 35-50%  → caution: tighten min_confidence by 1pt
  win_rate  < 35%  → danger:  tighten min_confidence by 2pt, min_score += 1

Hard floors (never goes below):
  min_confidence = 78.0
  min_score      = 5
  min_adx        = 20.0

Hard ceilings (never goes above):
  min_confidence = 92.0
  min_score      = 9
  min_adx        = 35.0
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

FLOOR_CONFIDENCE = 78.0
FLOOR_SCORE      = 5
FLOOR_ADX        = 20.0

CEIL_CONFIDENCE  = 92.0
CEIL_SCORE       = 9
CEIL_ADX         = 35.0


@dataclass
class AdaptiveState:
    min_confidence: float = FLOOR_CONFIDENCE
    min_score:      int   = FLOOR_SCORE
    min_adx:        float = FLOOR_ADX
    win_rate:       float = 0.0
    regime:         str   = "neutral"   # "reward", "neutral", "caution", "danger"
    adjustments:    int   = 0
    window_trades:  int   = 0


class AdaptiveController:
    """
    Thread-safe (single-process asyncio) controller.
    Call `record(won)` after each closed trade.
    Read `.state` for current recommended thresholds.
    """

    def __init__(
        self,
        window: int = 30,
        base_confidence: float = FLOOR_CONFIDENCE,
        base_score:      int   = FLOOR_SCORE,
        base_adx:        float = FLOOR_ADX,
    ):
        self._window          = window
        self._base_confidence = base_confidence
        self._base_score      = base_score
        self._base_adx        = base_adx
        self._results: deque[bool] = deque(maxlen=window)
        self.state = AdaptiveState(
            min_confidence=base_confidence,
            min_score=base_score,
            min_adx=base_adx,
        )

    def record(self, won: bool):
        """Call after every closed trade with the outcome."""
        self._results.append(won)
        self._recompute()

    def _recompute(self):
        n = len(self._results)
        if n < 5:
            return  # not enough data yet

        wins     = sum(self._results)
        win_rate = wins / n * 100
        state    = self.state

        state.win_rate      = round(win_rate, 1)
        state.window_trades = n

        # ── Regime classification ────────────────────────────────────────
        if win_rate >= 65:
            regime = "reward"
        elif win_rate >= 50:
            regime = "neutral"
        elif win_rate >= 35:
            regime = "caution"
        else:
            regime = "danger"

        prev_regime = state.regime
        state.regime = regime

        # ── Threshold adjustment (only when regime changes or reinforced) ─
        if regime == "reward":
            # Earned the right to relax slightly
            if state.min_confidence > self._base_confidence:
                state.min_confidence = max(
                    self._base_confidence,
                    round(state.min_confidence - 1.0, 1),
                )
            if state.min_score > self._base_score:
                state.min_score = max(self._base_score, state.min_score - 1)
            if prev_regime != "reward":
                state.adjustments += 1
                logger.info(
                    f"[AdaptiveCtrl] REWARD — WR={win_rate:.1f}% | "
                    f"conf={state.min_confidence} score={state.min_score}"
                )

        elif regime == "caution" and prev_regime not in ("caution", "danger"):
            state.min_confidence = min(
                CEIL_CONFIDENCE,
                round(state.min_confidence + 1.0, 1),
            )
            state.adjustments += 1
            logger.info(
                f"[AdaptiveCtrl] CAUTION — WR={win_rate:.1f}% | "
                f"conf={state.min_confidence} score={state.min_score}"
            )

        elif regime == "danger":
            state.min_confidence = min(
                CEIL_CONFIDENCE,
                round(state.min_confidence + 2.0, 1),
            )
            state.min_score = min(CEIL_SCORE, state.min_score + 1)
            if prev_regime != "danger":
                state.adjustments += 1
            logger.warning(
                f"[AdaptiveCtrl] DANGER — WR={win_rate:.1f}% | "
                f"conf={state.min_confidence} score={state.min_score}"
            )

    def snapshot(self) -> dict:
        return {
            "min_confidence": self.state.min_confidence,
            "min_score":      self.state.min_score,
            "min_adx":        self.state.min_adx,
            "win_rate_window": self.state.win_rate,
            "regime":         self.state.regime,
            "adjustments":    self.state.adjustments,
            "window_trades":  self.state.window_trades,
            "window_size":    self._window,
        }
