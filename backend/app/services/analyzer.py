import numpy as np
import pandas as pd
import ta
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


@dataclass
class AnalysisResult:
    signal: Literal["BUY", "SELL", "WAIT"]
    confidence: float
    rsi: float
    macd: float
    macd_signal: float
    bb_upper: float
    bb_lower: float
    bb_mid: float
    ema9: float
    ema21: float
    reason: str
    buy_score: int
    sell_score: int
    adx: float = 0.0
    atr: float = 0.0
    atr_ratio: float = 1.0
    h1_bias: str = "NEUTRAL"
    h4_bias: str = "NEUTRAL"
    session: str = ""
    patterns: list = None
    divergences: list = None

    def __post_init__(self):
        if self.patterns is None:
            self.patterns = []
        if self.divergences is None:
            self.divergences = []


class AnalyzerService:
    """
    Multi-indicator confluence engine with trend, volatility, and MTF filters.
    Indicators: RSI + Stochastic + MACD + Bollinger Bands + EMA + ADX
    MTF: H4 macro trend → H1 confirmation → primary TF entry
    session_mode: "london_ny" (default), "all" (24h), "london", "new_york", "asian"
    """

    def __init__(
        self,
        min_score: int = 5,
        min_score_gap: int = 2,
        min_adx: float = 22.0,
        session_mode: str = "london_ny",
    ):
        self.min_score     = min_score
        self.min_score_gap = min_score_gap
        self.min_adx       = min_adx
        self.session_mode  = session_mode

    # ── Public API ────────────────────────────────────────────────────────────

    def _detect_patterns(
        self,
        df: pd.DataFrame,
    ) -> tuple[int, int, list[str]]:
        """
        Detects candlestick patterns on the last 3 candles.
        Returns (buy_score_delta, sell_score_delta, pattern_names).

        Patterns detected:
          Bullish: Pin Bar, Hammer, Bullish Engulfing, Bullish Marubozu, Morning Doji Star
          Bearish: Pin Bar, Shooting Star, Bearish Engulfing, Bearish Marubozu, Evening Doji Star
          Neutral: Doji / Inside Bar (penalizes weak confluence)
        """
        buy_pts  = 0
        sell_pts = 0
        found: list[str] = []

        o = df["open"].values
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values

        # Need at least 3 candles for engulfing/star patterns
        if len(df) < 3:
            return 0, 0, []

        # Last candle (index -1), previous (-2), before that (-3)
        o1, h1, l1, c1 = o[-1], h[-1], l[-1], c[-1]   # current
        o2, h2, l2, c2 = o[-2], h[-2], l[-2], c[-2]   # previous
        o3, h3, l3, c3 = o[-3], h[-3], l[-3], c[-3]   # 2 candles ago

        body1     = abs(c1 - o1)
        body2     = abs(c2 - o2)
        body3     = abs(c3 - o3)
        candle1   = h1 - l1
        candle2   = h2 - l2
        upper_wick1 = h1 - max(o1, c1)
        lower_wick1 = min(o1, c1) - l1
        upper_wick2 = h2 - max(o2, c2)
        lower_wick2 = min(o2, c2) - l2

        if candle1 == 0 or candle2 == 0:
            return 0, 0, []

        body_pct1 = body1 / candle1
        body_pct2 = body2 / candle2

        # ── Doji (last candle — indecision) ──────────────────────────────
        if body_pct1 < 0.1:
            found.append("Doji")
            # Doji after trending candle signals reversal potential
            if c2 > o2:       sell_pts += 1
            elif c2 < o2:     buy_pts  += 1
            # No extra penalty — just mark it

        # ── Inside Bar (last inside previous) ────────────────────────────
        elif h1 <= h2 and l1 >= l2:
            found.append("Inside Bar")
            # Compression — slight bias toward continuation of prior candle
            if c2 > o2:   buy_pts  += 1
            else:         sell_pts += 1

        else:
            # ── Bullish Pin Bar / Hammer ──────────────────────────────────
            # Long lower wick (≥ 2× body), small upper wick, body in upper third
            if (lower_wick1 >= 2 * body1 and
                    upper_wick1 <= body1 * 0.5 and
                    body_pct1 > 0.05):
                buy_pts += 2
                found.append("Hammer/Pin Bar Alta")

            # ── Bearish Pin Bar / Shooting Star ──────────────────────────
            # Long upper wick (≥ 2× body), small lower wick, body in lower third
            elif (upper_wick1 >= 2 * body1 and
                    lower_wick1 <= body1 * 0.5 and
                    body_pct1 > 0.05):
                sell_pts += 2
                found.append("Shooting Star/Pin Bar Baixa")

            # ── Bullish Marubozu (strong bull candle, no significant wicks) ─
            if (c1 > o1 and
                    body_pct1 >= 0.8 and
                    upper_wick1 <= body1 * 0.1 and
                    lower_wick1 <= body1 * 0.1):
                buy_pts += 1
                found.append("Marubozu Alta")

            # ── Bearish Marubozu ─────────────────────────────────────────
            elif (c1 < o1 and
                    body_pct1 >= 0.8 and
                    upper_wick1 <= body1 * 0.1 and
                    lower_wick1 <= body1 * 0.1):
                sell_pts += 1
                found.append("Marubozu Baixa")

        # ── Bullish Engulfing (current bull candle engulfs prior bear) ───
        if (c1 > o1 and c2 < o2 and
                o1 <= c2 and c1 >= o2 and
                body1 > body2 * 1.1):
            buy_pts += 2
            found.append("Engolfo de Alta")

        # ── Bearish Engulfing (current bear candle engulfs prior bull) ───
        elif (c1 < o1 and c2 > o2 and
                o1 >= c2 and c1 <= o2 and
                body1 > body2 * 1.1):
            sell_pts += 2
            found.append("Engolfo de Baixa")

        # ── Morning Doji Star (3-candle bullish reversal) ────────────────
        # Bear candle → Doji/small body → Bull candle with gap
        if (c3 < o3 and                          # prior bear
                body2 / candle2 < 0.2 and        # doji/star in middle
                c1 > o1 and                       # current bull
                c1 > (o3 + c3) / 2):             # closes above midpoint of first candle
            buy_pts += 2
            found.append("Morning Star")

        # ── Evening Doji Star (3-candle bearish reversal) ────────────────
        elif (c3 > o3 and
                body2 / candle2 < 0.2 and
                c1 < o1 and
                c1 < (o3 + c3) / 2):
            sell_pts += 2
            found.append("Evening Star")

        return buy_pts, sell_pts, found

    def _session_filter(self, ts: int | None = None) -> tuple[bool, str]:
        """
        Returns (allowed, session_name).
        Behaviour is controlled by self.session_mode:
          "all"      — opera 24h, sem restrição
          "london_ny"— London 07:00–16:00 + NY 13:00–20:30 (default)
          "london"   — apenas London 07:00–16:00
          "new_york" — apenas New York 13:00–20:30
          "asian"    — apenas Asian 21:00–07:00
        `ts` is a Unix timestamp; uses current time when None.
        """
        if self.session_mode == "all":
            dt   = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
            hour = dt.hour
            minute = dt.minute
            return True, f"24h (UTC {hour:02d}:{minute:02d})"

        dt      = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
        hour    = dt.hour
        minute  = dt.minute
        hm      = hour * 60 + minute

        LONDON_OPEN  = 7  * 60
        LONDON_CLOSE = 16 * 60
        NY_OPEN      = 13 * 60
        NY_CLOSE     = 20 * 60 + 30

        in_london = LONDON_OPEN <= hm < LONDON_CLOSE
        in_ny     = NY_OPEN     <= hm < NY_CLOSE
        # Asian = fora de London e NY (inclui noite e madrugada)
        in_asian  = not in_london and not in_ny

        if self.session_mode == "london":
            if in_london:
                return True, "London"
            return False, f"Fora da sessão London (UTC {hour:02d}:{minute:02d})"

        if self.session_mode == "new_york":
            if in_ny:
                return True, "New York"
            return False, f"Fora da sessão New York (UTC {hour:02d}:{minute:02d})"

        if self.session_mode == "asian":
            if in_asian:
                return True, f"Asian (UTC {hour:02d}:{minute:02d})"
            return False, f"Fora da sessão Asiática (UTC {hour:02d}:{minute:02d})"

        # default: london_ny
        if in_london and in_ny:
            return True, "London+NY (sessão premium)"
        if in_london:
            return True, "London"
        if in_ny:
            return True, "New York"
        return False, f"Sessão asiática/fora de horário (UTC {hour:02d}:{minute:02d})"

    def _market_structure(
        self,
        df: pd.DataFrame,
        lookback: int = 20,
    ) -> tuple[int, int, list[str]]:
        """
        Detects market structure context:
          - Swing highs / swing lows (pivot points)
          - Price proximity to support or resistance zones
          - Broken structure (BoS) — bullish or bearish
          - Liquidity sweep (wick beyond prior swing then reversal)

        Returns (buy_score_delta, sell_score_delta, reasons).
        """
        buy_pts  = 0
        sell_pts = 0
        reasons: list[str] = []

        if len(df) < lookback + 5:
            return 0, 0, []

        high  = df["high"].values
        low   = df["low"].values
        close = df["close"].values
        n     = len(close)
        price = close[-1]
        swing = 5  # bars each side to confirm a pivot

        # ── Find swing highs and lows in the lookback window ─────────────
        swing_highs: list[float] = []
        swing_lows:  list[float] = []

        for i in range(swing, n - swing - 1):
            if all(high[i] >= high[i - j] for j in range(1, swing + 1)) and \
               all(high[i] >= high[i + j] for j in range(1, swing + 1)):
                swing_highs.append(high[i])
            if all(low[i] <= low[i - j] for j in range(1, swing + 1)) and \
               all(low[i] <= low[i + j] for j in range(1, swing + 1)):
                swing_lows.append(low[i])

        if not swing_highs or not swing_lows:
            return 0, 0, []

        last_swing_high = max(swing_highs[-3:]) if len(swing_highs) >= 3 else swing_highs[-1]
        last_swing_low  = min(swing_lows[-3:])  if len(swing_lows)  >= 3 else swing_lows[-1]

        # Tolerance band (0.05% of price) for "near" level
        tol = price * 0.0005

        # ── Price near support (last swing low) ──────────────────────────
        if abs(price - last_swing_low) <= tol * 3:
            buy_pts += 2
            reasons.append(f"Preço no suporte ({last_swing_low:.5f})")

        # ── Price near resistance (last swing high) ───────────────────────
        elif abs(price - last_swing_high) <= tol * 3:
            sell_pts += 2
            reasons.append(f"Preço na resistência ({last_swing_high:.5f})")

        # ── Break of Structure (BoS) ─────────────────────────────────────
        # Bullish BoS: close above the last swing high → structure flipped bullish
        prev_close = close[-2]
        if prev_close < last_swing_high and price > last_swing_high:
            buy_pts += 2
            reasons.append(f"BoS Alta — rompeu {last_swing_high:.5f}")

        # Bearish BoS: close below the last swing low
        elif prev_close > last_swing_low and price < last_swing_low:
            sell_pts += 2
            reasons.append(f"BoS Baixa — rompeu {last_swing_low:.5f}")

        # ── Liquidity Sweep + Reversal ───────────────────────────────────
        # Price swept below swing low but closed above it (stop hunt then reversal)
        curr_low  = df["low"].values[-1]
        curr_high = df["high"].values[-1]

        if curr_low < last_swing_low and price > last_swing_low:
            buy_pts += 2
            reasons.append(f"Sweep de liquidez baixa + reversão")

        elif curr_high > last_swing_high and price < last_swing_high:
            sell_pts += 2
            reasons.append(f"Sweep de liquidez alta + reversão")

        # ── Higher Highs / Lower Lows trend confirmation ─────────────────
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            hh = swing_highs[-1] > swing_highs[-2]  # higher high
            hl = swing_lows[-1]  > swing_lows[-2]   # higher low
            lh = swing_highs[-1] < swing_highs[-2]  # lower high
            ll = swing_lows[-1]  < swing_lows[-2]   # lower low

            if hh and hl:
                buy_pts += 1
                reasons.append("Estrutura HH+HL (tendência de alta)")
            elif lh and ll:
                sell_pts += 1
                reasons.append("Estrutura LH+LL (tendência de baixa)")

        return buy_pts, sell_pts, reasons

    def _atr_filter(
        self,
        df: pd.DataFrame,
        spike_ratio: float = 2.5,
        dead_ratio: float  = 0.3,
        window: int        = 14,
        avg_window: int    = 50,
    ) -> tuple[bool, str, float, float]:
        """
        ATR-based volatility filter.
        Returns (allowed, reason, current_atr, atr_ratio).

        Blocks:
          - Extreme volatility (ATR > spike_ratio × avg) → news spike, avoid
          - Dead market     (ATR < dead_ratio × avg)     → no movement, avoid
        """
        if len(df) < avg_window:
            return True, "", 0.0, 1.0

        atr_series = ta.volatility.AverageTrueRange(
            df["high"], df["low"], df["close"], window=window
        ).average_true_range()

        current_atr = float(atr_series.iloc[-1])
        avg_atr     = float(atr_series.iloc[-avg_window:].mean())

        if avg_atr == 0:
            return True, "", current_atr, 1.0

        ratio = current_atr / avg_atr

        if ratio > spike_ratio:
            return (
                False,
                f"Volatilidade extrema (ATR {ratio:.1f}× acima da média — possível notícia)",
                current_atr, ratio,
            )
        if ratio < dead_ratio:
            return (
                False,
                f"Mercado sem volatilidade (ATR {ratio:.2f}× da média)",
                current_atr, ratio,
            )

        return True, "", current_atr, ratio

    def _detect_divergence(
        self,
        df: pd.DataFrame,
        rsi_series: pd.Series,
        macd_hist: pd.Series,
    ) -> tuple[int, int, list[str]]:
        """
        Detects RSI and MACD divergence using two non-overlapping price windows.

        Bullish divergence: price makes lower low  → indicator makes higher low  → BUY
        Bearish divergence: price makes higher high → indicator makes lower high  → SELL

        Window A: candles[-30:-10]  (previous swing)
        Window B: candles[-10:]     (recent swing)
        """
        n = len(df)
        if n < 35:
            return 0, 0, []

        low  = df["low"].values
        high = df["high"].values

        rsi = rsi_series.values
        mh  = macd_hist.values

        # ── Two non-overlapping windows ──────────────────────────────────
        wA_s, wA_e = n - 30, n - 10   # previous
        wB_s, wB_e = n - 10, n        # recent

        # Price extremes
        pA_low_i  = wA_s + int(np.argmin(low[wA_s:wA_e]))
        pA_high_i = wA_s + int(np.argmax(high[wA_s:wA_e]))
        pB_low_i  = wB_s + int(np.argmin(low[wB_s:wB_e]))
        pB_high_i = wB_s + int(np.argmax(high[wB_s:wB_e]))

        pA_low  = low[pA_low_i];   rA_low  = rsi[pA_low_i];  mA_low  = mh[pA_low_i]
        pA_high = high[pA_high_i]; rA_high = rsi[pA_high_i]; mA_high = mh[pA_high_i]
        pB_low  = low[pB_low_i];   rB_low  = rsi[pB_low_i];  mB_low  = mh[pB_low_i]
        pB_high = high[pB_high_i]; rB_high = rsi[pB_high_i]; mB_high = mh[pB_high_i]

        buy_pts = sell_pts = 0
        reasons: list[str] = []

        # ── Bullish RSI divergence ───────────────────────────────────────
        # Price: lower low  |  RSI: higher low  |  RSI still below 55
        if pB_low < pA_low and rB_low > rA_low + 2 and rB_low < 55:
            buy_pts += 3
            reasons.append(f"Divergência RSI Alta (RSI {rA_low:.0f}→{rB_low:.0f})")

        # ── Bearish RSI divergence ───────────────────────────────────────
        # Price: higher high  |  RSI: lower high  |  RSI still above 45
        if pB_high > pA_high and rB_high < rA_high - 2 and rB_high > 45:
            sell_pts += 3
            reasons.append(f"Divergência RSI Baixa (RSI {rA_high:.0f}→{rB_high:.0f})")

        # ── Bullish MACD histogram divergence ────────────────────────────
        # Price: lower low  |  MACD hist: less negative (momentum slowing)
        if pB_low < pA_low and mB_low > mA_low + 1e-6 and mB_low < 0:
            buy_pts += 2
            reasons.append("Divergência MACD Alta")

        # ── Bearish MACD histogram divergence ────────────────────────────
        # Price: higher high  |  MACD hist: less positive
        if pB_high > pA_high and mB_high < mA_high - 1e-6 and mB_high > 0:
            sell_pts += 2
            reasons.append("Divergência MACD Baixa")

        return buy_pts, sell_pts, reasons

    def _detect_fvg_ob(
        self,
        df: pd.DataFrame,
        lookback: int = 30,
    ) -> tuple[int, int, list[str]]:
        """
        Fair Value Gap (FVG) and Order Block detection.

        FVG: 3-candle gap where price left an imbalance zone.
          Bullish FVG: high[i-2] < low[i]  (gap upward — price may retrace down to fill)
          Bearish FVG: low[i-2] > high[i]  (gap downward)
          Score if current price is inside the gap.

        Order Block (OB): last opposing candle before an impulsive move.
          Bullish OB: bearish candle → strong bull impulse (≥2× OB body)
          Bearish OB: bullish candle → strong bear impulse
          Score if current price is back in the OB zone.
        """
        n = len(df)
        if n < lookback + 5:
            return 0, 0, []

        o = df["open"].values
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values
        price = c[-1]

        buy_pts = sell_pts = 0
        reasons: list[str] = []

        scan_start = max(2, n - lookback)

        # ── FVG scan ─────────────────────────────────────────────────────
        for i in range(scan_start, n - 1):
            # Bullish FVG: gap between [i-2].high and [i].low
            if h[i - 2] < l[i]:
                gap_lo, gap_hi = h[i - 2], l[i]
                if gap_lo <= price <= gap_hi:
                    buy_pts += 2
                    reasons.append(f"FVG Alta ({gap_lo:.5f}–{gap_hi:.5f})")
                    break  # closest FVG wins

            # Bearish FVG: gap between [i-2].low and [i].high
            elif l[i - 2] > h[i]:
                gap_lo, gap_hi = h[i], l[i - 2]
                if gap_lo <= price <= gap_hi:
                    sell_pts += 2
                    reasons.append(f"FVG Baixa ({gap_lo:.5f}–{gap_hi:.5f})")
                    break

        # ── Order Block scan ─────────────────────────────────────────────
        ob_start = max(1, n - lookback)
        for i in range(ob_start, n - 4):
            body = abs(c[i] - o[i])
            if body < 0.00005:          # skip micro-candles
                continue

            next_range = max(h[i + 1:i + 4]) - min(l[i + 1:i + 4])

            # Bullish OB: bearish candle followed by impulse ≥ 2× body
            if c[i] < o[i] and next_range >= body * 2.0:
                ob_lo = min(o[i], c[i])
                ob_hi = max(o[i], c[i])
                if ob_lo <= price <= ob_hi:
                    buy_pts += 2
                    reasons.append(f"Order Block Alta ({ob_lo:.5f}–{ob_hi:.5f})")
                    break

            # Bearish OB: bullish candle followed by impulse ≥ 2× body
            elif c[i] > o[i] and next_range >= body * 2.0:
                ob_lo = min(o[i], c[i])
                ob_hi = max(o[i], c[i])
                if ob_lo <= price <= ob_hi:
                    sell_pts += 2
                    reasons.append(f"Order Block Baixa ({ob_lo:.5f}–{ob_hi:.5f})")
                    break

        return buy_pts, sell_pts, reasons

    def analyze(self, candles: list[dict]) -> AnalysisResult:
        """Single-timeframe confluence analysis."""
        df = pd.DataFrame(candles)
        df.columns = [c.lower() for c in df.columns]

        if len(df) < 50:
            return self._wait(0.0, "Dados insuficientes (mín. 50 candles)", 0, 0)

        last_ts = int(df["time"].iloc[-1]) if "time" in df.columns else None
        session_ok, session_name = self._session_filter(ts=last_ts)
        if not session_ok:
            r = self._wait(0.0, f"Fora de horário: {session_name}", 0, 0)
            r.session = session_name
            return r

        # ── ATR volatility filter ─────────────────────────────────────
        atr_ok, atr_reason, current_atr, atr_ratio = self._atr_filter(df)
        if not atr_ok:
            r = self._wait(0.0, atr_reason, 0, 0)
            r.session = session_name
            r.atr = current_atr
            r.atr_ratio = atr_ratio
            return r

        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        # ── Indicators ───────────────────────────────────────────────────────
        rsi_ind   = ta.momentum.RSIIndicator(close, window=14)
        stoch_ind = ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
        macd_ind  = ta.trend.MACD(close, window_fast=12, window_slow=26, window_sign=9)
        bb_ind    = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        ema9_ind  = ta.trend.EMAIndicator(close, window=9)
        ema21_ind = ta.trend.EMAIndicator(close, window=21)
        ema50_ind = ta.trend.EMAIndicator(close, window=50)
        adx_ind   = ta.trend.ADXIndicator(high, low, close, window=14)

        rsi    = float(rsi_ind.rsi().iloc[-1])
        stoch  = float(stoch_ind.stoch().iloc[-1])
        macd   = float(macd_ind.macd().iloc[-1])
        macd_s = float(macd_ind.macd_signal().iloc[-1])
        macd_h = float(macd_ind.macd_diff().iloc[-1])
        bb_u   = float(bb_ind.bollinger_hband().iloc[-1])
        bb_l   = float(bb_ind.bollinger_lband().iloc[-1])
        bb_m   = float(bb_ind.bollinger_mavg().iloc[-1])
        e9     = float(ema9_ind.ema_indicator().iloc[-1])
        e21    = float(ema21_ind.ema_indicator().iloc[-1])
        e50    = float(ema50_ind.ema_indicator().iloc[-1])
        adx    = float(adx_ind.adx().iloc[-1])
        plus_di  = float(adx_ind.adx_pos().iloc[-1])
        minus_di = float(adx_ind.adx_neg().iloc[-1])
        price  = float(close.iloc[-1])

        prev_macd = float(macd_ind.macd().iloc[-2])
        prev_sig  = float(macd_ind.macd_signal().iloc[-2])
        prev_e9   = float(ema9_ind.ema_indicator().iloc[-2])
        prev_e21  = float(ema21_ind.ema_indicator().iloc[-2])

        # ── Volatility / trend filter ─────────────────────────────────────
        if adx < self.min_adx:
            # Retorna indicadores REAIS (não zeros) para a UI mostrar análise viva
            r = AnalysisResult(
                "WAIT", 0.0, rsi, macd, macd_s, bb_u, bb_l, bb_m,
                e9, e21,
                f"Mercado lateral (ADX {adx:.1f} < {self.min_adx:.0f}) — aguardando tendência",
                0, 0, adx,
            )
            r.atr        = current_atr
            r.atr_ratio  = atr_ratio
            r.session    = session_name
            return r

        buy_score  = 0
        sell_score = 0
        reasons: list[str] = []

        # RSI (max 3)
        if rsi < 25:
            buy_score += 3; reasons.append(f"RSI sobrevenda extrema ({rsi:.1f})")
        elif rsi < 35:
            buy_score += 2; reasons.append(f"RSI sobrevenda ({rsi:.1f})")
        elif rsi < 45:
            buy_score += 1
        elif rsi > 75:
            sell_score += 3; reasons.append(f"RSI sobrecompra extrema ({rsi:.1f})")
        elif rsi > 65:
            sell_score += 2; reasons.append(f"RSI sobrecompra ({rsi:.1f})")
        elif rsi > 55:
            sell_score += 1

        # Stochastic (max 2)
        if stoch < 20:
            buy_score += 2; reasons.append(f"Stoch sobrevenda ({stoch:.1f})")
        elif stoch < 35:
            buy_score += 1
        elif stoch > 80:
            sell_score += 2; reasons.append(f"Stoch sobrecompra ({stoch:.1f})")
        elif stoch > 65:
            sell_score += 1

        # MACD crossover (max 3)
        if prev_macd <= prev_sig and macd > macd_s:
            buy_score += 3; reasons.append("MACD cruzamento alta")
        elif prev_macd >= prev_sig and macd < macd_s:
            sell_score += 3; reasons.append("MACD cruzamento baixa")
        elif macd > macd_s and macd_h > 0:
            buy_score += 2; reasons.append("MACD histograma positivo")
        elif macd < macd_s and macd_h < 0:
            sell_score += 2; reasons.append("MACD histograma negativo")
        elif macd > macd_s:
            buy_score += 1
        else:
            sell_score += 1

        # Bollinger Bands (max 2)
        bb_width = bb_u - bb_l
        bb_pos   = (price - bb_l) / bb_width if bb_width > 0 else 0.5
        if bb_pos <= 0.1:
            buy_score += 2; reasons.append("Preço na banda inferior BB")
        elif bb_pos <= 0.3:
            buy_score += 1
        elif bb_pos >= 0.9:
            sell_score += 2; reasons.append("Preço na banda superior BB")
        elif bb_pos >= 0.7:
            sell_score += 1

        # EMA crossover (max 2)
        if prev_e9 <= prev_e21 and e9 > e21:
            buy_score += 2; reasons.append("EMA9 cruzou acima EMA21")
        elif prev_e9 >= prev_e21 and e9 < e21:
            sell_score += 2; reasons.append("EMA9 cruzou abaixo EMA21")
        elif e9 > e21:
            buy_score += 1
        else:
            sell_score += 1

        # EMA50 + DI trend alignment (max 2)
        if price > e50 and plus_di > minus_di:
            buy_score += 2; reasons.append("Tendência de alta (EMA50 + DI+)")
        elif price < e50 and minus_di > plus_di:
            sell_score += 2; reasons.append("Tendência de baixa (EMA50 + DI-)")
        elif price > e50:
            buy_score += 1
            sell_score = max(0, sell_score - 1)
        elif price < e50:
            sell_score += 1
            buy_score = max(0, buy_score - 1)

        # Price momentum last 5 candles (max 1)
        momentum = (price - float(close.iloc[-5])) / float(close.iloc[-5]) * 100
        if momentum > 0.05:
            buy_score += 1
        elif momentum < -0.05:
            sell_score += 1

        # ── Candlestick patterns (max +2 each side) ───────────────────────
        pat_buy, pat_sell, patterns = self._detect_patterns(df)
        buy_score  += pat_buy
        sell_score += pat_sell
        if patterns:
            reasons.append(" + ".join(patterns))

        # ── Market structure (max +2 each side) ───────────────────────────
        ms_buy, ms_sell, ms_reasons = self._market_structure(df)
        buy_score  += ms_buy
        sell_score += ms_sell
        reasons.extend(ms_reasons)

        # ── RSI / MACD Divergence (max +3 each side) ──────────────────────
        div_buy, div_sell, divergences = self._detect_divergence(
            df, rsi_ind.rsi(), macd_ind.macd_diff()
        )
        buy_score  += div_buy
        sell_score += div_sell
        reasons.extend(divergences)

        # ── Fair Value Gap + Order Blocks (max +2 each side) ──────────────
        fvg_buy, fvg_sell, fvg_reasons = self._detect_fvg_ob(df)
        buy_score  += fvg_buy
        sell_score += fvg_sell
        reasons.extend(fvg_reasons)

        # ── Decision ─────────────────────────────────────────────────────────
        total = buy_score + sell_score or 1
        gap   = abs(buy_score - sell_score)

        if (
            buy_score >= self.min_score
            and buy_score > sell_score
            and gap >= self.min_score_gap
            and price >= e50 * 0.9995
        ):
            conf = min(97.0, round((buy_score / total) * 100 + gap * 2, 1))
            result = AnalysisResult(
                "BUY", conf, rsi, macd, macd_s, bb_u, bb_l, bb_m,
                e9, e21, " | ".join(reasons), buy_score, sell_score, adx,
            )
            result.atr        = current_atr
            result.atr_ratio  = atr_ratio
            result.patterns   = patterns
            result.divergences = divergences
            result.session    = session_name
            return result

        if (
            sell_score >= self.min_score
            and sell_score > buy_score
            and gap >= self.min_score_gap
            and price <= e50 * 1.0005
        ):
            conf = min(97.0, round((sell_score / total) * 100 + gap * 2, 1))
            result = AnalysisResult(
                "SELL", conf, rsi, macd, macd_s, bb_u, bb_l, bb_m,
                e9, e21, " | ".join(reasons), buy_score, sell_score, adx,
            )
            result.atr        = current_atr
            result.atr_ratio  = atr_ratio
            result.patterns   = patterns
            result.divergences = divergences
            result.session    = session_name
            return result

        conf = round(max(buy_score, sell_score) / total * 100, 1)
        reason = " | ".join(reasons) if reasons else "Sem confluência clara"
        if gap < self.min_score_gap and max(buy_score, sell_score) >= self.min_score:
            reason = f"Confluência fraca (gap {gap} < {self.min_score_gap}) — {reason}"
        wait = self._wait(conf, reason, buy_score, sell_score, adx)
        wait.atr        = current_atr
        wait.atr_ratio  = atr_ratio
        wait.patterns   = patterns
        wait.divergences = divergences
        wait.session    = session_name
        return wait

    def trend_bias(self, candles: list[dict]) -> str:
        """
        Reads macro trend from a higher timeframe.
        Returns BULL, BEAR, or NEUTRAL.
        Scoring: price vs EMA50 (2pt), EMA9>EMA21 (1pt), EMA21>EMA50 (1pt), MACD bias (1pt).
        Requires ADX >= 18 to declare a trend; otherwise NEUTRAL.
        """
        if len(candles) < 50:
            return "NEUTRAL"

        df = pd.DataFrame(candles)
        df.columns = [c.lower() for c in df.columns]
        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        ema9   = float(ta.trend.EMAIndicator(close, window=9).ema_indicator().iloc[-1])
        ema21  = float(ta.trend.EMAIndicator(close, window=21).ema_indicator().iloc[-1])
        ema50  = float(ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1])
        adx    = float(ta.trend.ADXIndicator(high, low, close, window=14).adx().iloc[-1])
        macd_i = ta.trend.MACD(close)
        macd   = float(macd_i.macd().iloc[-1])
        macd_s = float(macd_i.macd_signal().iloc[-1])
        price  = float(close.iloc[-1])

        if adx < 18:
            return "NEUTRAL"

        bull = bear = 0

        if price > ema50: bull += 2
        else: bear += 2

        if ema9 > ema21: bull += 1
        else: bear += 1

        if ema21 > ema50: bull += 1
        else: bear += 1

        if macd > macd_s: bull += 1
        else: bear += 1

        if bull >= 4: return "BULL"
        if bear >= 4: return "BEAR"
        return "NEUTRAL"

    def analyze_mtf(
        self,
        candles_primary: list[dict],
        candles_h1: list[dict],
        candles_h4: list[dict],
    ) -> AnalysisResult:
        """
        Multi-timeframe analysis:
          1. Runs full confluence on the primary (entry) timeframe.
          2. Reads H1 and H4 bias.
          3. Blocks trades that go against H4 or H1 trend.
          4. Boosts confidence when all three align.
        """
        result = self.analyze(candles_primary)

        h1_bias = self.trend_bias(candles_h1) if len(candles_h1) >= 50 else "NEUTRAL"
        h4_bias = self.trend_bias(candles_h4) if len(candles_h4) >= 50 else "NEUTRAL"
        result.h1_bias = h1_bias
        result.h4_bias = h4_bias

        if result.signal == "WAIT":
            return result

        # ── H4 hard block (macro trend contra-sinal) ─────────────────────
        if result.signal == "BUY" and h4_bias == "BEAR":
            result.signal     = "WAIT"
            result.confidence = round(result.confidence * 0.4, 1)
            result.reason     = f"MTF BLOQUEADO — H4 em baixa | {result.reason}"
            return result

        if result.signal == "SELL" and h4_bias == "BULL":
            result.signal     = "WAIT"
            result.confidence = round(result.confidence * 0.4, 1)
            result.reason     = f"MTF BLOQUEADO — H4 em alta | {result.reason}"
            return result

        # ── H1 secondary filter ───────────────────────────────────────────
        if result.signal == "BUY" and h1_bias == "BEAR":
            result.signal     = "WAIT"
            result.confidence = round(result.confidence * 0.6, 1)
            result.reason     = f"MTF BLOQUEADO — H1 em baixa | {result.reason}"
            return result

        if result.signal == "SELL" and h1_bias == "BULL":
            result.signal     = "WAIT"
            result.confidence = round(result.confidence * 0.6, 1)
            result.reason     = f"MTF BLOQUEADO — H1 em alta | {result.reason}"
            return result

        # ── Alignment bonus ───────────────────────────────────────────────
        full_align = (
            (result.signal == "BUY"  and h1_bias == "BULL" and h4_bias == "BULL") or
            (result.signal == "SELL" and h1_bias == "BEAR" and h4_bias == "BEAR")
        )

        if full_align:
            result.confidence = min(97.0, round(result.confidence + 6.0, 1))
            result.reason     = f"[MTF✓ H1:{h1_bias} H4:{h4_bias}] {result.reason}"
        else:
            # Partial: H4 neutral or H1 neutral — still allowed, no bonus
            result.reason = f"[MTF~ H1:{h1_bias} H4:{h4_bias}] {result.reason}"

        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _wait(
        self,
        confidence: float,
        reason: str,
        bs: int = 0,
        ss: int = 0,
        adx: float = 0.0,
    ) -> AnalysisResult:
        return AnalysisResult(
            "WAIT", confidence, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, reason, bs, ss, adx,
        )
