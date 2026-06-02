import asyncio
import logging
import time
from collections import deque
from datetime import date, datetime
from typing import Callable, Optional

from app.services.analyzer import AnalyzerService, AnalysisResult
from app.services.auto_adjuster import AdaptiveController
from app.services.deriv_client import DerivClient
from app.services.risk_manager import RiskManager, RiskConfig

logger = logging.getLogger(__name__)

SYMBOL_MAP = {
    "EUR/USD": "frxEURUSD",
    "GBP/USD": "frxGBPUSD",
    "USD/JPY": "frxUSDJPY",
    "BTC/USD": "cryBTCUSD",
    "Volatility 75": "R_75",
    "Boom 1000":    "BOOM1000",
}

# Rise/Fall on DERIV: CALL = Rise (Up), PUT = Fall (Down)
CONTRACT_TYPE = {"BUY": "CALL", "SELL": "PUT"}


class TradeRecord:
    def __init__(
        self,
        signal: str,
        asset: str,
        stake: float,
        confidence: float,
        reason: str,
        duration_minutes: int,
        contract_id: Optional[int] = None,
        entry_price: float = 0.0,
        expires_at: Optional[int] = None,
    ):
        self.id               = f"trade-{datetime.now().strftime('%H%M%S%f')}"
        self.signal           = signal
        self.asset            = asset
        self.stake            = stake
        self.confidence       = confidence
        self.reason           = reason
        self.duration_minutes = duration_minutes
        self.contract_id      = contract_id
        self.entry_price      = entry_price
        self.expires_at       = expires_at
        self.status           = "OPEN"
        self.pnl              = 0.0
        self.payout           = 0.0
        self.opened_at        = datetime.now().isoformat()
        self.closed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "signal":           self.signal,
            "asset":            self.asset,
            "stake":            self.stake,
            "confidence":       self.confidence,
            "reason":           self.reason,
            "status":           self.status,
            "pnl":              round(self.pnl, 2),
            "payout":           round(self.payout, 2),
            "entry_price":      round(self.entry_price, 5),
            "expires_at":       self.expires_at,
            "opened_at":        self.opened_at,
            "closed_at":        self.closed_at,
            "duration":         f"{self.duration_minutes}m",
            "contract_type":    "RISE" if self.signal == "BUY" else "FALL",
            "contract_id":      self.contract_id,
        }


class TradingBot:
    """
    Rise/Fall bot loop:
    1. Stream candles from DERIV
    2. Analyze every N ticks
    3. Place CALL (Rise) or PUT (Fall) with fixed duration
    4. Close at expiry (won/lost)
    """

    def __init__(
        self,
        api_token: str,
        app_id: str = "33qwHdRH3vY9cCAeAzIa7",
        account_id: str = "",
        asset: str = "EUR/USD",
        granularity: int = 60,
        contract_duration: int = 5,
        risk_config: Optional[RiskConfig] = None,
        analyzer_min_score: int = 5,
        analyzer_min_gap: int = 2,
        analyzer_min_adx: float = 22.0,
        on_signal: Optional[Callable] = None,
        on_trade: Optional[Callable] = None,
        on_tick: Optional[Callable] = None,
        on_stats: Optional[Callable] = None,
        analyze_every: int = 3,
        session_mode: str = "london_ny",
    ):
        self.api_token         = api_token
        self.app_id            = app_id
        self.account_id        = account_id
        self.asset             = asset
        self.symbol            = SYMBOL_MAP.get(asset, "frxEURUSD")
        self.granularity       = granularity
        self.contract_duration = contract_duration
        self.analyze_every     = analyze_every

        self.client   = DerivClient(app_id=app_id, api_token=api_token, account_id=account_id)
        self.analyzer = AnalyzerService(
            min_score=analyzer_min_score,
            min_score_gap=analyzer_min_gap,
            min_adx=analyzer_min_adx,
            session_mode=session_mode,
        )
        self.risk     = RiskManager(risk_config)
        self.adaptive = AdaptiveController(
            window=30,
            base_confidence=risk_config.min_confidence if risk_config else 78.0,
            base_score=analyzer_min_score,
            base_adx=analyzer_min_adx,
        )

        self.candles:     deque = deque(maxlen=300)
        self.candles_h1:  deque = deque(maxlen=200)
        self.candles_h4:  deque = deque(maxlen=150)
        self.trades:      list[TradeRecord] = []
        self.running      = False
        self._tick_count  = 0
        self._htf_counter = 0
        self._last_error_at: float = 0.0
        self._error_cooldown: int  = 120
        self._stop_reason: str     = ""     # razão do auto-stop

        self.on_signal = on_signal
        self.on_trade  = on_trade
        self.on_tick   = on_tick
        self.on_stats  = on_stats

        self.last_signal: dict = {}
        self._reconcile_counter = 0
        self._trade_lock = asyncio.Lock()

    def _rebuild_stats_from_trades(self):
        """Recalcula stats do dia a partir da lista de trades (sem duplicar contagem)."""
        closed = [
            (t.pnl, t.closed_at)
            for t in self.trades
            if t.status in ("WIN", "LOSS")
        ]
        self.risk.rebuild_from_closed_trades(closed)
        self.risk.stats.open_positions = sum(1 for t in self.trades if t.status == "OPEN")

    def _merge_trade_by_contract(self, trade: TradeRecord):
        """Insere ou atualiza trade pelo contract_id (evita duplicata local + DERIV)."""
        if trade.contract_id:
            for i, t in enumerate(self.trades):
                if t.contract_id == trade.contract_id:
                    if not t.id.startswith("deriv-") and trade.id.startswith("deriv-"):
                        return
                    self.trades[i] = trade
                    return
        self.trades.append(trade)

    async def reconcile_open_trades(self):
        """Fecha trades OPEN cujo contrato já venceu na DERIV."""
        for trade in list(self.trades):
            if trade.status != "OPEN" or not trade.contract_id:
                continue
            try:
                poc = await self.client.get_open_contract(trade.contract_id)
                await self._on_contract_update(trade, poc)
            except Exception as e:
                logger.warning(f"Reconcile contract {trade.contract_id}: {e}")

    async def sync_today_from_deriv(self):
        """Recupera trades Rise/Fall fechados hoje da DERIV (útil após restart)."""
        try:
            txs = await self.client.get_profit_table(limit=100)
        except Exception as e:
            logger.warning(f"sync_today_from_deriv: {e}")
            return

        today = date.today()
        known = {t.contract_id for t in self.trades if t.contract_id}
        restored: list[TradeRecord] = []

        for tx in txs:
            cid = tx.get("contract_id")
            ctype = tx.get("contract_type", "")
            symbol = tx.get("underlying_symbol", "")
            if not cid or cid in known:
                continue
            if ctype not in ("CALL", "PUT"):
                continue
            if symbol and symbol != self.symbol:
                continue

            purchase_time = int(tx.get("purchase_time") or 0)
            if not purchase_time or datetime.fromtimestamp(purchase_time).date() != today:
                continue

            stake = float(tx.get("buy_price") or self.risk.config.stake_amount)
            sell = float(tx.get("sell_price") or 0)
            pnl = round(sell - stake, 2)
            sell_time = int(tx.get("sell_time") or purchase_time)

            trade = TradeRecord(
                signal="BUY" if ctype == "CALL" else "SELL",
                asset=self.asset,
                stake=stake,
                confidence=0,
                reason="Sincronizado da DERIV",
                duration_minutes=self.contract_duration,
                contract_id=cid,
            )
            trade.id = f"deriv-{cid}"
            trade.status = "WIN" if pnl > 0 else "LOSS"
            trade.pnl = pnl
            trade.payout = float(tx.get("payout") or 0)
            trade.opened_at = datetime.fromtimestamp(purchase_time).isoformat()
            trade.closed_at = datetime.fromtimestamp(sell_time).isoformat()
            restored.append(trade)
            known.add(cid)

        if not restored:
            return

        for t in restored:
            self._merge_trade_by_contract(t)
        self._rebuild_stats_from_trades()
        logger.info(
            f"Restored {len(restored)} trade(s) from DERIV | "
            f"Day P&L: {self.risk.stats.pnl:+.2f} | "
            f"W/L: {self.risk.stats.wins}/{self.risk.stats.losses}"
        )
        if self.on_stats:
            asyncio.create_task(self.on_stats(self.risk.summary))

    async def start(self):
        self.running = True
        try:
            await self.client.connect()
            logger.info(
                f"Bot started | asset={self.asset} | "
                f"Rise/Fall {self.contract_duration}m | authorized={self.client.authorized}"
            )

            hist = await self.client.get_candles(self.symbol, self.granularity, 200)
            for c in hist:
                self.candles.append(c)
            logger.info(f"Loaded {len(self.candles)} candles (primary TF)")

            hist_h1 = await self.client.get_candles(self.symbol, 3600, 200)
            for c in hist_h1:
                self.candles_h1.append(c)
            logger.info(f"Loaded {len(self.candles_h1)} candles (H1)")

            hist_h4 = await self.client.get_candles(self.symbol, 14400, 150)
            for c in hist_h4:
                self.candles_h4.append(c)
            logger.info(f"Loaded {len(self.candles_h4)} candles (H4)")

            await self.client.subscribe_ticks(self.symbol, self._on_tick)
            logger.info(f"Subscribed to ticks for {self.symbol}")

            await self.sync_today_from_deriv()
            await self.reconcile_open_trades()

            while self.running:
                await asyncio.sleep(5)
                self._reconcile_counter += 1
                self._htf_counter += 1
                if self._reconcile_counter % 6 == 0:  # ~30s
                    await self.reconcile_open_trades()
                    if self.on_stats:
                        asyncio.create_task(self.on_stats(self.risk.summary))
                if self._htf_counter % 180 == 0:  # ~15min — refresh H1
                    await self._refresh_htf_candles(h4=False)
                if self._htf_counter % 720 == 0:  # ~60min — refresh H4
                    await self._refresh_htf_candles(h4=True)
                if self.client.authorized and self.client._trade_ws is not None:
                    try:
                        ws = self.client._trade_ws
                        if hasattr(ws, "open"):
                            is_closed = not ws.open
                        else:
                            state = getattr(ws, "state", None)
                            is_closed = state is not None and str(state).upper() not in ("OPEN", "STATE.OPEN")
                        if is_closed:
                            logger.info("Trade WS closed — reconnecting with new OTP...")
                            import websockets as _ws
                            ws_url = await self.client._get_ws_url_via_otp()
                            self.client._trade_ws = await _ws.connect(ws_url, ping_interval=20, ping_timeout=10)
                            asyncio.create_task(self.client._recv_from(self.client._trade_ws))
                            logger.info("Trade WS reconnected")
                    except Exception as e:
                        logger.error(f"Reconnect check failed: {e}")

        except Exception as e:
            logger.error(f"Bot FATAL ERROR: {type(e).__name__}: {e}", exc_info=True)
            self.running = False

    async def _refresh_htf_candles(self, h4: bool = False):
        try:
            hist_h1 = await self.client.get_candles(self.symbol, 3600, 200)
            self.candles_h1.clear()
            for c in hist_h1:
                self.candles_h1.append(c)
            logger.info(f"HTF refresh: {len(self.candles_h1)} H1 candles")
            if h4:
                hist_h4 = await self.client.get_candles(self.symbol, 14400, 150)
                self.candles_h4.clear()
                for c in hist_h4:
                    self.candles_h4.append(c)
                logger.info(f"HTF refresh: {len(self.candles_h4)} H4 candles")
        except Exception as e:
            logger.warning(f"HTF refresh failed: {e}")

    async def stop(self):
        self.running = False
        await self.client.disconnect()
        logger.info("Bot stopped")

    async def _on_tick(self, price: float, epoch: int):
        if not self.running:
            return
        self._tick_count += 1

        if self.candles:
            last = self.candles[-1]
            candle_start = (epoch // self.granularity) * self.granularity
            last_start   = (last["time"] // self.granularity) * self.granularity

            if candle_start == last_start:
                last["close"] = price
                last["high"]  = max(last["high"], price)
                last["low"]   = min(last["low"], price)
            else:
                self.candles.append({
                    "time":  candle_start,
                    "open":  last["close"],
                    "high":  price,
                    "low":   price,
                    "close": price,
                })
        else:
            candle_start = (epoch // self.granularity) * self.granularity
            self.candles.append({
                "time": candle_start, "open": price,
                "high": price, "low": price, "close": price,
            })

        if self.on_tick:
            asyncio.create_task(self.on_tick({"price": price, "epoch": epoch}))

        if self._tick_count % self.analyze_every == 0:
            await self._analyze_and_trade()

    async def _analyze_and_trade(self):
        candle_list = list(self.candles)
        if len(candle_list) < 30:
            return

        # ── Signal staleness guard ────────────────────────────────────────
        # Don't trade if the last candle is more than 2 periods old
        if candle_list:
            last_candle_ts  = candle_list[-1]["time"]
            signal_age_sec  = time.time() - last_candle_ts
            max_age_sec     = self.granularity * 2
            if signal_age_sec > max_age_sec:
                logger.info(
                    f"Sinal obsoleto ({signal_age_sec:.0f}s > {max_age_sec}s) — análise abortada"
                )
                return

        # Apply adaptive thresholds to analyzer before running
        adaptive = self.adaptive.state
        self.analyzer.min_score     = adaptive.min_score
        self.analyzer.min_score_gap = max(2, self.analyzer.min_score_gap)
        self.analyzer.min_adx       = adaptive.min_adx

        result = self.analyzer.analyze_mtf(
            candle_list,
            list(self.candles_h1),
            list(self.candles_h4),
        )

        if self.on_signal:
            signal_payload = {
                "signal":      result.signal,
                "confidence":  result.confidence,
                "reason":      result.reason,
                "asset":       self.asset,
                "rsi":         round(result.rsi, 2),
                "macd":        round(result.macd, 6),
                "macd_signal": round(result.macd_signal, 6),
                "bb_upper":    round(result.bb_upper, 5),
                "bb_lower":    round(result.bb_lower, 5),
                "ema9":        round(result.ema9, 5),
                "ema21":       round(result.ema21, 5),
                "buy_score":   result.buy_score,
                "sell_score":  result.sell_score,
                "adx":         round(result.adx, 1),
                "h1_bias":     result.h1_bias,
                "h4_bias":     result.h4_bias,
                "session":     result.session,
                "atr":         round(result.atr, 6),
                "atr_ratio":   round(result.atr_ratio, 2),
                "patterns":    result.patterns,
                "divergences": result.divergences,
                "price":       candle_list[-1]["close"] if candle_list else 0,
            }
            self.last_signal = signal_payload
            asyncio.create_task(self.on_signal(signal_payload))

        divs = ", ".join(result.divergences) if result.divergences else "—"
        logger.info(
            f"Analysis → {result.signal} | conf={result.confidence}% | "
            f"buy={result.buy_score} sell={result.sell_score} | "
            f"H1:{result.h1_bias} H4:{result.h4_bias} | "
            f"ATR×{result.atr_ratio:.1f} | diverg=[{divs}] | {result.reason}"
        )

        # Cooldown após ERRO de API
        if self._last_error_at > 0:
            elapsed = time.time() - self._last_error_at
            if elapsed < self._error_cooldown:
                remaining = int(self._error_cooldown - elapsed)
                logger.info(f"Cooldown pós-ERRO: {remaining}s restantes")
                return

        # Use adaptive confidence threshold (may be stricter than base)
        effective_conf = max(self.risk.config.min_confidence, self.adaptive.state.min_confidence)
        decision = self.risk.can_trade(result.confidence, result.signal)
        if not decision.allowed:
            pass
        elif result.confidence < effective_conf:
            logger.info(f"Trade blocked by adaptive threshold: {result.confidence:.1f}% < {effective_conf:.1f}%")
            decision.allowed = False
            decision.reason  = f"Confiança adaptativa exige {effective_conf:.1f}% (regime: {self.adaptive.state.regime})"
        if not decision.allowed:
            logger.info(f"Trade blocked: {decision.reason}")
            return

        async with self._trade_lock:
            if self.risk.stats.open_positions >= self.risk.config.max_open_positions:
                logger.info("Trade blocked: operação já aberta ou em abertura")
                return
            decision = self.risk.can_trade(result.confidence, result.signal)
            if not decision.allowed:
                logger.info(f"Trade blocked: {decision.reason}")
                return
            await self._place_trade(result, decision.stake)

    async def _place_trade(self, result: AnalysisResult, stake: float):
        contract_type = CONTRACT_TYPE[result.signal]
        entry_price   = float(list(self.candles)[-1]["close"]) if self.candles else 0.0

        trade = TradeRecord(
            signal=result.signal,
            asset=self.asset,
            stake=stake,
            confidence=result.confidence,
            reason=result.reason,
            duration_minutes=self.contract_duration,
            entry_price=entry_price,
        )

        self.risk.on_trade_opened()
        try:
            proposal = await self.client.get_proposal(
                symbol=self.symbol,
                contract_type=contract_type,
                stake=stake,
                duration=self.contract_duration,
                duration_unit="m",
            )

            buy_resp = await self.client.buy_contract(
                proposal_id=proposal["id"],
                price=proposal["ask_price"],
            )

            trade.contract_id = buy_resp["contract_id"]
            trade.payout      = float(proposal.get("payout") or 0)
            trade.entry_price = float(proposal.get("spot") or entry_price)
            trade.expires_at  = int(proposal.get("date_expiry") or 0)

            self._merge_trade_by_contract(trade)

            direction = "RISE" if result.signal == "BUY" else "FALL"
            logger.info(
                f"Trade OPENED | {direction} {self.asset} {self.contract_duration}m | "
                f"stake=${stake} | conf={result.confidence}% | id={trade.contract_id}"
            )

            if self.on_trade:
                asyncio.create_task(self.on_trade(trade.to_dict()))

            await self.client.subscribe_contract(
                trade.contract_id,
                lambda poc, t=trade: self._on_contract_update(t, poc),
            )

        except Exception as e:
            self.risk.stats.open_positions = max(0, self.risk.stats.open_positions - 1)
            self.risk.stats.trades = max(0, self.risk.stats.trades - 1)
            trade.status = "ERROR"
            trade.reason = f"Erro DERIV: {e}"
            trade.pnl    = 0.0
            self._last_error_at = time.time()   # ativa cooldown
            self._merge_trade_by_contract(trade)
            logger.error(f"Trade error: {e}", exc_info=True)
            if self.on_trade:
                asyncio.create_task(self.on_trade(trade.to_dict()))

    async def _on_contract_update(self, trade: TradeRecord, poc: dict):
        status = poc.get("status", "")
        profit = float(poc.get("profit") or 0)

        if status == "open":
            trade.pnl = profit
            if self.on_trade:
                asyncio.create_task(self.on_trade(trade.to_dict()))
            return

        if status not in ("won", "lost"):
            return

        if trade.status in ("WIN", "LOSS"):
            return

        won = status == "won" or profit > 0
        trade.status    = "WIN" if won else "LOSS"
        trade.pnl       = profit
        trade.closed_at = datetime.now().isoformat()

        self.risk.on_trade_closed(trade.pnl)
        self.adaptive.record(won)

        logger.info(
            f"Trade CLOSED | {trade.status} | "
            f"P&L=${trade.pnl:+.2f} | {trade.asset} {trade.duration_minutes}m"
        )

        if self.on_trade:
            asyncio.create_task(self.on_trade(trade.to_dict()))

        if self.on_stats:
            asyncio.create_task(self.on_stats(self.risk.summary))

        # ── Auto-stop ao atingir limites diários ─────────────────────────
        await self._check_daily_limits()

    async def _check_daily_limits(self):
        """
        Para o bot automaticamente quando limites diários são atingidos.
        Dispara broadcast antes de parar para o frontend atualizar.
        """
        pnl    = self.risk.stats.pnl
        streak = self.risk.stats.current_streak
        limit  = self.risk.config.daily_loss_limit
        target = self.risk.config.daily_profit_target
        max_consec = self.risk.config.max_consecutive_losses

        stop_reason: Optional[str] = None

        if pnl <= -abs(limit):
            stop_reason = (
                f"🛑 LIMITE DE PERDA DIÁRIA ATINGIDO — "
                f"P&L ${pnl:+.2f} (limite ${-abs(limit):.2f})"
            )
        elif pnl >= target:
            stop_reason = (
                f"🎯 META DIÁRIA ATINGIDA — "
                f"P&L ${pnl:+.2f} (meta ${target:.2f})"
            )
        elif streak <= -max_consec:
            stop_reason = (
                f"⛔ {max_consec} LOSSES CONSECUTIVOS — "
                f"Reinicie amanhã com o mercado mais favorável"
            )

        if stop_reason:
            self._stop_reason = stop_reason
            logger.warning(f"AUTO-STOP: {stop_reason}")
            # Notifica frontend antes de parar
            if self.on_stats:
                summary = {**self.risk.summary, "auto_stop_reason": stop_reason}
                asyncio.create_task(self.on_stats(summary))
            if self.on_signal:
                asyncio.create_task(self.on_signal({
                    "signal": "WAIT",
                    "confidence": 0.0,
                    "reason": stop_reason,
                    "auto_stopped": True,
                }))
            await asyncio.sleep(1)   # garante que broadcasts saíram
            await self.stop()

    @property
    def status(self) -> dict:
        return self.snapshot()

    def snapshot(self) -> dict:
        candle_list = list(self.candles)
        return {
            "running":           self.running,
            "asset":             self.asset,
            "contract_duration": self.contract_duration,
            "contract_mode":     "rise_fall",
            "trading_profile":   "conservative_precision",
            "candles":           len(candle_list),
            "trades":            len(self.trades),
            "stats":             self.risk.summary,
            "trades_list":       [t.to_dict() for t in reversed(self.trades)],
            "last_signal":       getattr(self, "last_signal", {}),
            "current_price":     float(candle_list[-1]["close"]) if candle_list else 0.0,
            "mtf": {
                "h1_bias":    self.last_signal.get("h1_bias", "NEUTRAL"),
                "h4_bias":    self.last_signal.get("h4_bias", "NEUTRAL"),
                "candles_h1": len(self.candles_h1),
                "candles_h4": len(self.candles_h4),
            },
            "adaptive":    self.adaptive.snapshot(),
            "stop_reason": self._stop_reason,
        }
