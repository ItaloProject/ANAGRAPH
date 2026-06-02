"""
Walk-forward backtester for ANAGRAPH.

For each candle i (starting at min_candles):
  - Runs the full analyzer (MTF-lite: primary TF only, no live HTF fetching)
  - If signal BUY/SELL and confidence >= min_confidence:
      entry  = open[i+1]   (next candle open — trade placed immediately after signal)
      exit   = close[i+1]  (15-minute contract expires at next candle close)
      win    = exit > entry (BUY) or exit < entry (SELL)
  - Tracks P&L with fixed stake
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services.analyzer import AnalyzerService

logger = logging.getLogger(__name__)

PAYOUT_RATIO = 0.85  # Deriv Rise/Fall typical payout (85% profit on win)


@dataclass
class BacktestTrade:
    index:      int
    time:       int
    signal:     str
    confidence: float
    entry:      float
    exit:       float
    stake:      float
    pnl:        float
    won:        bool
    session:    str
    reason:     str
    patterns:   list[str] = field(default_factory=list)


@dataclass
class BacktestResult:
    total_signals:  int = 0
    total_trades:   int = 0
    wins:           int = 0
    losses:         int = 0
    win_rate:       float = 0.0
    pnl:            float = 0.0
    max_drawdown:   float = 0.0
    profit_factor:  float = 0.0
    sharpe:         float = 0.0
    avg_confidence: float = 0.0
    trades:         list[BacktestTrade] = field(default_factory=list)
    equity_curve:   list[dict]          = field(default_factory=list)
    by_session:     dict[str, dict]     = field(default_factory=dict)
    by_signal:      dict[str, dict]     = field(default_factory=dict)
    by_pattern:     dict[str, dict]     = field(default_factory=dict)
    params:         dict                = field(default_factory=dict)


def run_backtest(
    candles:        list[dict],
    min_confidence: float = 78.0,
    min_score:      int   = 5,
    min_score_gap:  int   = 2,
    min_adx:        float = 22.0,
    stake:          float = 6.0,
    min_candles:    int   = 60,  # warmup bars before first trade
) -> BacktestResult:
    """
    Synchronous walk-forward backtest. Runs in a thread pool from async routes.
    """
    analyzer = AnalyzerService(
        min_score=min_score,
        min_score_gap=min_score_gap,
        min_adx=min_adx,
    )

    result = BacktestResult(params={
        "min_confidence": min_confidence,
        "min_score":      min_score,
        "min_score_gap":  min_score_gap,
        "min_adx":        min_adx,
        "stake":          stake,
        "candles_total":  len(candles),
    })

    equity         = 0.0
    peak_equity    = 0.0
    max_dd         = 0.0
    gross_wins     = 0.0
    gross_losses   = 0.0
    conf_sum       = 0.0
    session_stats: dict[str, dict] = {}
    signal_stats:  dict[str, dict] = {}
    pattern_stats: dict[str, dict] = {}

    # Walk forward: need i+1 candle for exit price
    for i in range(min_candles, len(candles) - 1):
        window = candles[:i + 1]
        try:
            analysis = analyzer.analyze(window)
        except Exception as e:
            logger.debug(f"Backtest analyze error at i={i}: {e}")
            continue

        if analysis.signal not in ("BUY", "SELL"):
            continue

        result.total_signals += 1

        if analysis.confidence < min_confidence:
            continue

        result.total_trades += 1

        entry = float(candles[i + 1]["open"])
        exit_ = float(candles[i + 1]["close"])
        ts    = int(candles[i]["time"])

        if analysis.signal == "BUY":
            won = exit_ > entry
        else:
            won = exit_ < entry

        pnl = round(stake * PAYOUT_RATIO if won else -stake, 2)
        equity = round(equity + pnl, 2)

        # Drawdown
        if equity > peak_equity:
            peak_equity = equity
        dd = peak_equity - equity
        if dd > max_dd:
            max_dd = dd

        if pnl > 0:
            result.wins += 1
            gross_wins  += pnl
        else:
            result.losses += 1
            gross_losses  += abs(pnl)

        conf_sum += analysis.confidence

        trade = BacktestTrade(
            index=i, time=ts, signal=analysis.signal,
            confidence=analysis.confidence,
            entry=entry, exit=exit_,
            stake=stake, pnl=pnl, won=won,
            session=analysis.session,
            reason=analysis.reason,
            patterns=list(analysis.patterns or []),
        )
        result.trades.append(trade)

        # Equity curve (every trade)
        result.equity_curve.append({
            "time":   ts,
            "equity": equity,
            "trade":  result.total_trades,
        })

        # Stats by session
        sess = analysis.session or "Desconhecida"
        if sess not in session_stats:
            session_stats[sess] = {"trades": 0, "wins": 0, "pnl": 0.0}
        session_stats[sess]["trades"] += 1
        session_stats[sess]["wins"]   += 1 if won else 0
        session_stats[sess]["pnl"]    = round(session_stats[sess]["pnl"] + pnl, 2)

        # Stats by signal direction
        sig = analysis.signal
        if sig not in signal_stats:
            signal_stats[sig] = {"trades": 0, "wins": 0, "pnl": 0.0}
        signal_stats[sig]["trades"] += 1
        signal_stats[sig]["wins"]   += 1 if won else 0
        signal_stats[sig]["pnl"]    = round(signal_stats[sig]["pnl"] + pnl, 2)

        # Stats by pattern
        for pat in (analysis.patterns or []):
            if pat not in pattern_stats:
                pattern_stats[pat] = {"trades": 0, "wins": 0}
            pattern_stats[pat]["trades"] += 1
            pattern_stats[pat]["wins"]   += 1 if won else 0

    # ── Finalize metrics ─────────────────────────────────────────────────────
    total = result.wins + result.losses or 1
    result.win_rate       = round(result.wins / total * 100, 1)
    result.pnl            = round(equity, 2)
    result.max_drawdown   = round(max_dd, 2)
    result.profit_factor  = round(gross_wins / gross_losses, 2) if gross_losses > 0 else 0.0
    result.avg_confidence = round(conf_sum / result.total_trades, 1) if result.total_trades else 0.0

    # Simple Sharpe approximation: avg_pnl / std_pnl
    if result.trades:
        import statistics
        pnls = [t.pnl for t in result.trades]
        avg  = sum(pnls) / len(pnls)
        try:
            std = statistics.stdev(pnls)
            result.sharpe = round(avg / std, 2) if std > 0 else 0.0
        except Exception:
            result.sharpe = 0.0

    # Build by_session / by_signal / by_pattern with win_rate
    for key, d in session_stats.items():
        t = d["trades"] or 1
        result.by_session[key] = {**d, "win_rate": round(d["wins"] / t * 100, 1)}
    for key, d in signal_stats.items():
        t = d["trades"] or 1
        result.by_signal[key] = {**d, "win_rate": round(d["wins"] / t * 100, 1)}
    for key, d in pattern_stats.items():
        t = d["trades"] or 1
        result.by_pattern[key] = {**d, "win_rate": round(d["wins"] / t * 100, 1)}

    logger.info(
        f"Backtest complete: {result.total_trades} trades | "
        f"WR={result.win_rate}% | P&L={result.pnl:+.2f} | "
        f"Drawdown={result.max_drawdown:.2f} | PF={result.profit_factor}"
    )
    return result
