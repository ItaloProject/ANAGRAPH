"""
Walk-forward backtester for ANAGRAPH.

Modes:
  - Single run  (run_backtest): one parameter set, full metrics + breakdowns.
  - Grid search (run_grid):     sweeps score/adx/confidence combos, ranks the best.

Fidelity:
  - use_mtf=True runs the SAME analyze_mtf the live bot uses, with H1/H4 trend
    bias and DXY (USD/JPY) correlation, sliced to what was knowable at each candle.
  - Tick flow, news sentiment and the learning model are LIVE-only adaptive layers
    and are intentionally excluded — they cannot be reconstructed from history.

Entry/exit model (Rise/Fall, 15m contract):
  entry = open[i+1]   (next candle open — placed right after the signal)
  exit  = close[i+1]  (contract expires one candle later)
  win   = exit > entry (BUY) / exit < entry (SELL)
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services.analyzer import AnalyzerService

logger = logging.getLogger(__name__)

PAYOUT_RATIO = 0.85  # Deriv Rise/Fall typical payout (85% profit on win)


def _session_label(ts: int) -> str:
    """Rótulo de sessão limpo (London/NY/Asiática) a partir do timestamp UTC."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    hm = dt.hour * 60 + dt.minute
    in_london = 7 * 60 <= hm < 16 * 60
    in_ny     = 13 * 60 <= hm < 20 * 60 + 30
    if in_london and in_ny:
        return "London+NY"
    if in_london:
        return "London"
    if in_ny:
        return "New York"
    return "Asiática"


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
class CandidateSignal:
    """Sinal BUY/SELL emitido — guardado antes de aplicar o filtro de confiança."""
    index:      int
    time:       int
    signal:     str
    confidence: float
    entry:      float
    exit:       float
    won:        bool
    session:    str
    reason:     str
    patterns:   list[str]


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


# ── HTF slicing helper ─────────────────────────────────────────────────────────

def _sliced_upto(series: list[dict], ts: int, pointer: int) -> tuple[list[dict], int]:
    """
    Avança o ponteiro enquanto series[pointer].time <= ts (séries ordenadas).
    Retorna (fatia até o ponteiro, novo_pointer). O(n) amortizado no loop.
    """
    n = len(series)
    while pointer < n and series[pointer]["time"] <= ts:
        pointer += 1
    return series[:pointer], pointer


# ── Core walk-forward (coleta de sinais) ───────────────────────────────────────

def _collect_signals(
    candles:        list[dict],
    candles_h1:     list[dict] | None,
    candles_h4:     list[dict] | None,
    candles_usdjpy: list[dict] | None,
    min_score:      int,
    min_score_gap:  int,
    min_adx:        float,
    use_mtf:        bool,
    min_candles:    int = 60,
) -> tuple[list[CandidateSignal], int]:
    """
    Roda o walk-forward uma vez e devolve TODOS os sinais BUY/SELL emitidos
    (sem filtrar por confiança) + a contagem total de sinais.
    A confiança é aplicada depois — permite avaliar vários limiares sem re-rodar.
    """
    analyzer = AnalyzerService(
        min_score=min_score,
        min_score_gap=min_score_gap,
        min_adx=min_adx,
        session_mode="all",   # backtest avalia todos os horários; filtro vem do MTF/DXY
    )

    candidates: list[CandidateSignal] = []
    total_signals = 0

    h1_ptr = h4_ptr = jpy_ptr = 0
    has_htf = use_mtf and candles_h1 and candles_h4

    for i in range(min_candles, len(candles) - 1):
        window = candles[: i + 1]
        ts     = int(candles[i]["time"])

        try:
            if has_htf:
                h1_win, h1_ptr = _sliced_upto(candles_h1, ts, h1_ptr)
                h4_win, h4_ptr = _sliced_upto(candles_h4, ts, h4_ptr)
                if candles_usdjpy:
                    jpy_win, jpy_ptr = _sliced_upto(candles_usdjpy, ts, jpy_ptr)
                else:
                    jpy_win = None
                analysis = analyzer.analyze_mtf(
                    window, h1_win, h4_win,
                    tick_flow=None, candles_usdjpy=jpy_win,
                )
            else:
                analysis = analyzer.analyze(window)
        except Exception as e:
            logger.debug(f"Backtest analyze error at i={i}: {e}")
            continue

        if analysis.signal not in ("BUY", "SELL"):
            continue

        total_signals += 1

        entry = float(candles[i + 1]["open"])
        exit_ = float(candles[i + 1]["close"])
        won   = exit_ > entry if analysis.signal == "BUY" else exit_ < entry

        candidates.append(CandidateSignal(
            index=i, time=ts, signal=analysis.signal,
            confidence=analysis.confidence, entry=entry, exit=exit_,
            won=won, session=analysis.session, reason=analysis.reason,
            patterns=list(analysis.patterns or []),
        ))

    return candidates, total_signals


# ── Metric evaluation at a given confidence threshold ──────────────────────────

def _evaluate(
    candidates:     list[CandidateSignal],
    total_signals:  int,
    min_confidence: float,
    stake:          float,
    params:         dict,
) -> BacktestResult:
    result = BacktestResult(params=params)
    result.total_signals = total_signals

    equity = peak = max_dd = 0.0
    gross_wins = gross_losses = conf_sum = 0.0
    session_stats: dict[str, dict] = {}
    signal_stats:  dict[str, dict] = {}
    pattern_stats: dict[str, dict] = {}

    for c in candidates:
        if c.confidence < min_confidence:
            continue

        result.total_trades += 1
        pnl    = round(stake * PAYOUT_RATIO if c.won else -stake, 2)
        equity = round(equity + pnl, 2)

        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

        if pnl > 0:
            result.wins += 1; gross_wins  += pnl
        else:
            result.losses += 1; gross_losses += abs(pnl)
        conf_sum += c.confidence

        result.trades.append(BacktestTrade(
            index=c.index, time=c.time, signal=c.signal,
            confidence=c.confidence, entry=c.entry, exit=c.exit,
            stake=stake, pnl=pnl, won=c.won, session=c.session,
            reason=c.reason, patterns=c.patterns,
        ))
        result.equity_curve.append({"time": c.time, "equity": equity, "trade": result.total_trades})

        sess = _session_label(c.time)
        s = session_stats.setdefault(sess, {"trades": 0, "wins": 0, "pnl": 0.0})
        s["trades"] += 1; s["wins"] += int(c.won); s["pnl"] = round(s["pnl"] + pnl, 2)

        sg = signal_stats.setdefault(c.signal, {"trades": 0, "wins": 0, "pnl": 0.0})
        sg["trades"] += 1; sg["wins"] += int(c.won); sg["pnl"] = round(sg["pnl"] + pnl, 2)

        for pat in c.patterns:
            p = pattern_stats.setdefault(pat, {"trades": 0, "wins": 0})
            p["trades"] += 1; p["wins"] += int(c.won)

    total = result.wins + result.losses or 1
    result.win_rate       = round(result.wins / total * 100, 1)
    result.pnl            = round(equity, 2)
    result.max_drawdown   = round(max_dd, 2)
    result.profit_factor  = round(gross_wins / gross_losses, 2) if gross_losses > 0 else 0.0
    result.avg_confidence = round(conf_sum / result.total_trades, 1) if result.total_trades else 0.0

    if result.trades:
        pnls = [t.pnl for t in result.trades]
        avg  = sum(pnls) / len(pnls)
        try:
            std = statistics.stdev(pnls)
            result.sharpe = round(avg / std, 2) if std > 0 else 0.0
        except statistics.StatisticsError:
            result.sharpe = 0.0

    for key, d in session_stats.items():
        t = d["trades"] or 1
        result.by_session[key] = {**d, "win_rate": round(d["wins"] / t * 100, 1)}
    for key, d in signal_stats.items():
        t = d["trades"] or 1
        result.by_signal[key] = {**d, "win_rate": round(d["wins"] / t * 100, 1)}
    for key, d in pattern_stats.items():
        t = d["trades"] or 1
        result.by_pattern[key] = {**d, "win_rate": round(d["wins"] / t * 100, 1)}

    return result


# ── Public: single run ─────────────────────────────────────────────────────────

def run_backtest(
    candles:        list[dict],
    candles_h1:     list[dict] | None = None,
    candles_h4:     list[dict] | None = None,
    candles_usdjpy: list[dict] | None = None,
    min_confidence: float = 78.0,
    min_score:      int   = 5,
    min_score_gap:  int   = 2,
    min_adx:        float = 22.0,
    stake:          float = 6.0,
    use_mtf:        bool  = True,
    min_candles:    int   = 60,
) -> BacktestResult:
    candidates, total_signals = _collect_signals(
        candles, candles_h1, candles_h4, candles_usdjpy,
        min_score=min_score, min_score_gap=min_score_gap, min_adx=min_adx,
        use_mtf=use_mtf, min_candles=min_candles,
    )
    params = {
        "min_confidence": min_confidence, "min_score": min_score,
        "min_score_gap": min_score_gap, "min_adx": min_adx, "stake": stake,
        "candles_total": len(candles), "use_mtf": use_mtf,
    }
    result = _evaluate(candidates, total_signals, min_confidence, stake, params)

    logger.info(
        f"Backtest: {result.total_trades} trades | WR={result.win_rate}% | "
        f"P&L={result.pnl:+.2f} | DD={result.max_drawdown:.2f} | "
        f"PF={result.profit_factor} | MTF={use_mtf}"
    )
    return result


# ── Public: grid search ────────────────────────────────────────────────────────

def run_grid(
    candles:        list[dict],
    candles_h1:     list[dict] | None = None,
    candles_h4:     list[dict] | None = None,
    candles_usdjpy: list[dict] | None = None,
    score_values:   list[int]   | None = None,
    adx_values:     list[float] | None = None,
    conf_values:    list[float] | None = None,
    min_score_gap:  int   = 2,
    stake:          float = 6.0,
    use_mtf:        bool  = True,
) -> dict:
    """
    Varre combinações de (min_score × min_adx × min_confidence).
    Otimização: min_confidence é pós-filtro, então só re-roda o walk-forward
    para cada (score, adx) — depois avalia todos os confidence baratos.
    Ranqueia por P&L, com mínimo de 10 trades para a combinação contar.
    """
    score_values = score_values or [5, 6]
    adx_values   = adx_values   or [22.0, 25.0]
    conf_values  = conf_values  or [78.0, 82.0, 86.0]

    combos: list[dict] = []

    for score in score_values:
        for adx in adx_values:
            candidates, total_signals = _collect_signals(
                candles, candles_h1, candles_h4, candles_usdjpy,
                min_score=score, min_score_gap=min_score_gap, min_adx=adx,
                use_mtf=use_mtf,
            )
            for conf in conf_values:
                params = {
                    "min_confidence": conf, "min_score": score,
                    "min_score_gap": min_score_gap, "min_adx": adx, "stake": stake,
                }
                r = _evaluate(candidates, total_signals, conf, stake, params)
                combos.append({
                    "min_score":      score,
                    "min_adx":        adx,
                    "min_confidence": conf,
                    "trades":         r.total_trades,
                    "win_rate":       r.win_rate,
                    "pnl":            r.pnl,
                    "max_drawdown":   r.max_drawdown,
                    "profit_factor":  r.profit_factor,
                    "sharpe":         r.sharpe,
                })

    # Ranqueia: combos com >=10 trades primeiro, por P&L desc
    valid   = [c for c in combos if c["trades"] >= 10]
    invalid = [c for c in combos if c["trades"] < 10]
    valid.sort(key=lambda c: c["pnl"], reverse=True)
    invalid.sort(key=lambda c: c["pnl"], reverse=True)
    ranked = valid + invalid

    logger.info(
        f"Grid: {len(ranked)} combos | candles={len(candles)} | MTF={use_mtf} | "
        f"melhor P&L={ranked[0]['pnl'] if ranked else 0:+.2f}"
    )
    return {
        "combos":      ranked,
        "best":        ranked[0] if ranked else None,
        "total_combos": len(ranked),
        "candles_total": len(candles),
        "use_mtf":     use_mtf,
    }
