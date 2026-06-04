import asyncio
import logging
import time
from collections import deque
from datetime import date, datetime, timezone
from typing import Callable, Optional

from app.services.analyzer import AnalyzerService, AnalysisResult
from app.services.auto_adjuster import AdaptiveController
from app.services.deriv_client import DerivClient
from app.services.risk_manager import RiskManager, RiskConfig
from app.services.tick_flow import TickFlowAnalyzer
from app.services.learning_engine import LearningEngine
from app.services.news_service import NewsService
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

SYMBOL_MAP = {
    "EUR/USD": "frxEURUSD",
    "GBP/USD": "frxGBPUSD",
    "USD/JPY": "frxUSDJPY",
    "BTC/USD": "cryBTCUSD",
    "Volatility 75": "R_75",
    "Boom 1000":    "BOOM1000",
}

# Timeframes HTF por granularidade primária
# (htf1_gran, htf2_gran, htf1_label, htf2_label)
HTF_MAP: dict[int, tuple[int, int, str, str]] = {
    900:  (3600,  14400, "H1", "H4"),   # M15 → H1, H4
    3600: (14400, 86400, "H4", "D1"),   # H1  → H4, D1
}

# Ativo ideal por sessão (modo multi-ativo / auto_asset).
# London/NY: pares EUR têm volume institucional.
# Asiático:  USD/JPY tem volume real (sessão de Tóquio).
SESSION_PRIMARY_ASSET = {
    "london_ny": "EUR/USD",
    "asian":     "USD/JPY",
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
        anthropic_api_key: str = "",
        telegram_token: str = "",
        telegram_chat_id: str = "",
        auto_asset: bool = False,
    ):
        self.api_token         = api_token
        self.app_id            = app_id
        self.account_id        = account_id
        self.asset             = asset
        self.symbol            = SYMBOL_MAP.get(asset, "frxEURUSD")
        self.granularity       = granularity
        self.contract_duration = contract_duration
        self.analyze_every     = analyze_every

        self.auto_asset = auto_asset
        self._switching = False

        self.client   = DerivClient(app_id=app_id, api_token=api_token, account_id=account_id)
        self.analyzer = AnalyzerService(
            min_score=analyzer_min_score,
            min_score_gap=analyzer_min_gap,
            min_adx=analyzer_min_adx,
            # Em modo multi-ativo o filtro de sessão é desligado: o ativo já é
            # escolhido para a sessão atual, então pode operar 24h.
            session_mode="all" if auto_asset else session_mode,
        )
        self.risk     = RiskManager(risk_config)
        self.adaptive = AdaptiveController(
            window=30,
            base_confidence=risk_config.min_confidence if risk_config else 78.0,
            base_score=analyzer_min_score,
            base_adx=analyzer_min_adx,
        )

        self.candles:        deque = deque(maxlen=300)
        self.candles_h1:     deque = deque(maxlen=200)
        self.candles_h4:     deque = deque(maxlen=150)
        self.candles_usdjpy: deque = deque(maxlen=200)
        self.trades:      list[TradeRecord] = []
        self.running      = False
        self._tick_count  = 0
        self._htf_counter = 0
        self._last_error_at: float = 0.0
        self._error_cooldown: int  = 120
        self._stop_reason: str     = ""

        self.on_signal = on_signal
        self.on_trade  = on_trade
        self.on_tick   = on_tick
        self.on_stats  = on_stats

        self.last_signal: dict = {}
        self._reconcile_counter = 0
        self._trade_lock = asyncio.Lock()

        # ── Inteligência avançada ─────────────────────────────────────────
        self.tick_flow = TickFlowAnalyzer(buffer_size=300)
        self.learning  = LearningEngine()
        self.news: Optional[NewsService] = (
            NewsService(api_key=anthropic_api_key) if anthropic_api_key else None
        )
        self.telegram: Optional[TelegramService] = (
            TelegramService(token=telegram_token, chat_id=telegram_chat_id)
            if telegram_token and telegram_chat_id else None
        )
        self._news_context: dict = {}
        self._news_refresh_counter = 0
        self._brl_rate: float = 5.85
        self._daily_report_sent_date: str = ""
        self._last_tick_at: float = 0.0          # timestamp do último tick recebido

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

            # Modo multi-ativo: escolhe o ativo ideal para a sessão atual
            if self.auto_asset:
                self.asset  = self._select_asset_for_now()
                self.symbol = SYMBOL_MAP.get(self.asset, "frxEURUSD")

            logger.info(
                f"Bot started | asset={self.asset} | auto_asset={self.auto_asset} | "
                f"Rise/Fall {self.contract_duration}m | authorized={self.client.authorized}"
            )

            hist = await self.client.get_candles(self.symbol, self.granularity, 200)
            for c in hist:
                self.candles.append(c)
            logger.info(f"Loaded {len(self.candles)} candles (primary TF)")

            htf1g, htf2g, htf1_lbl, htf2_lbl = HTF_MAP.get(self.granularity, HTF_MAP[900])

            hist_h1 = await self.client.get_candles(self.symbol, htf1g, 200)
            for c in hist_h1:
                self.candles_h1.append(c)
            logger.info(f"Loaded {len(self.candles_h1)} candles ({htf1_lbl})")

            hist_h4 = await self.client.get_candles(self.symbol, htf2g, 150)
            for c in hist_h4:
                self.candles_h4.append(c)
            logger.info(f"Loaded {len(self.candles_h4)} candles ({htf2_lbl})")

            # DXY proxy só para pares não-JPY (se operar USD/JPY, seria circular)
            if not self._is_jpy_pair():
                try:
                    hist_usdjpy = await self.client.get_candles("frxUSDJPY", 900, 200)
                    for c in hist_usdjpy:
                        self.candles_usdjpy.append(c)
                    logger.info(f"Loaded {len(self.candles_usdjpy)} candles (USD/JPY — DXY proxy)")
                except Exception as e:
                    logger.warning(f"USD/JPY fetch failed: {e}")

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
                if self.auto_asset and self._htf_counter % 12 == 0:  # ~60s — checa sessão
                    await self._switch_asset(self._select_asset_for_now())
                if self._htf_counter % 180 == 0:  # ~15min — refresh H1 + USDJPY
                    await self._refresh_htf_candles(h4=False)
                    if not self._is_jpy_pair():
                        await self._refresh_usdjpy()
                if self._htf_counter % 720 == 0:  # ~60min — refresh H4
                    await self._refresh_htf_candles(h4=True)
                await self._check_daily_report()
                # ── Reconexão Trade WS ───────────────────────────────────────
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
                        logger.error(f"Trade WS reconnect failed: {e}")

                # ── Reconexão Public WS (ticks) ──────────────────────────────
                # Se o WS público cair, os ticks param silenciosamente.
                # Detecta pelo tempo desde o último tick recebido.
                tick_silence_sec = time.time() - self._last_tick_at
                max_silence      = self.granularity * 3   # 3× o candle period
                if self._last_tick_at > 0 and tick_silence_sec > max_silence:
                    logger.warning(
                        f"Sem ticks há {tick_silence_sec:.0f}s — reconectando Public WS..."
                    )
                    try:
                        import websockets as _ws
                        if self.client._public_ws:
                            try: await self.client._public_ws.close()
                            except Exception: pass
                        self.client._public_ws = await _ws.connect(
                            self.client.WS_PUBLIC, ping_interval=30
                        )
                        asyncio.create_task(self.client._recv_from(self.client._public_ws))
                        await self.client.subscribe_ticks(self.symbol, self._on_tick)
                        self._last_tick_at = time.time()
                        logger.info("Public WS reconectado — ticks reinscritos")
                    except Exception as e:
                        logger.error(f"Public WS reconnect failed: {e}")

                # ── Reset periódico de contadores ────────────────────────────
                # Evita inteiros muito grandes após dias de operação
                if self._htf_counter >= 100_000:
                    self._htf_counter = 0
                if self._reconcile_counter >= 100_000:
                    self._reconcile_counter = 0

        except Exception as e:
            logger.error(f"Bot FATAL ERROR: {type(e).__name__}: {e}", exc_info=True)
            self.running = False

    # ── Multi-ativo por sessão (auto_asset) ───────────────────────────────────

    def _current_session(self) -> str:
        """Retorna 'london_ny' (07:00–20:30 UTC) ou 'asian' (resto)."""
        now = datetime.now(timezone.utc)
        hm  = now.hour * 60 + now.minute
        in_london = 7  * 60 <= hm < 16 * 60
        in_ny     = 13 * 60 <= hm < 20 * 60 + 30
        return "london_ny" if (in_london or in_ny) else "asian"

    def _select_asset_for_now(self) -> str:
        return SESSION_PRIMARY_ASSET.get(self._current_session(), "EUR/USD")

    def _is_jpy_pair(self) -> bool:
        return "JPY" in self.asset

    async def _switch_asset(self, new_asset: str):
        """Troca o ativo operado de forma limpa (re-inscrição de ticks + candles)."""
        if new_asset == self.asset or new_asset not in SYMBOL_MAP:
            return
        # Nunca troca com posição aberta — o contrato é do ativo antigo
        if any(t.status == "OPEN" for t in self.trades) or self.risk.stats.open_positions > 0:
            return

        old = self.asset
        self._switching = True
        try:
            await self.client.unsubscribe_ticks()

            self.asset  = new_asset
            self.symbol = SYMBOL_MAP[new_asset]
            self.candles.clear()
            self.candles_h1.clear()
            self.candles_h4.clear()
            self.tick_flow = TickFlowAnalyzer(buffer_size=300)

            hist = await self.client.get_candles(self.symbol, self.granularity, 200)
            for c in hist:
                self.candles.append(c)
            htf1g, htf2g, _, _ = HTF_MAP.get(self.granularity, HTF_MAP[900])
            h1 = await self.client.get_candles(self.symbol, htf1g, 200)
            for c in h1:
                self.candles_h1.append(c)
            h4 = await self.client.get_candles(self.symbol, htf2g, 150)
            for c in h4:
                self.candles_h4.append(c)

            # DXY proxy (USD/JPY) só faz sentido para pares não-JPY
            if self._is_jpy_pair():
                self.candles_usdjpy.clear()
            else:
                await self._refresh_usdjpy()

            await self.client.subscribe_ticks(self.symbol, self._on_tick)

            logger.info(
                f"Ativo trocado: {old} → {new_asset} "
                f"(sessão {self._current_session()})"
            )
            if self.telegram:
                asyncio.create_task(self.telegram.send(
                    f"🔄 <b>ANAGRAPH — TROCA DE ATIVO</b>\n"
                    f"{old} → {new_asset}\n"
                    f"Sessão: {self._current_session()}"
                ))
        except Exception as e:
            logger.error(f"Falha ao trocar de ativo: {e}", exc_info=True)
            # Reverte para o ativo antigo em caso de erro
            self.asset  = old
            self.symbol = SYMBOL_MAP.get(old, "frxEURUSD")
        finally:
            self._switching = False

    async def _refresh_usdjpy(self):
        try:
            hist = await self.client.get_candles("frxUSDJPY", 900, 200)
            self.candles_usdjpy.clear()
            for c in hist:
                self.candles_usdjpy.append(c)
        except Exception as e:
            logger.warning(f"USD/JPY refresh failed: {e}")

    async def _check_daily_report(self):
        """Envia relatório diário via Telegram após o fechamento da sessão NY (20:30 UTC)."""
        if not self.telegram:
            return
        from datetime import timezone as _tz
        now = datetime.now(_tz.utc)
        today_str = now.strftime("%Y-%m-%d")
        if today_str == self._daily_report_sent_date:
            return
        if now.hour == 20 and now.minute >= 30:
            stats = self.risk.summary
            await self.telegram.notify_daily_summary(
                wins=stats["wins"],
                losses=stats["losses"],
                pnl_usd=stats["pnl"],
                brl_rate=self._brl_rate,
            )
            self._daily_report_sent_date = today_str
            logger.info("Daily report sent via Telegram")

    async def _refresh_htf_candles(self, h4: bool = False):
        try:
            htf1g, htf2g, htf1_lbl, htf2_lbl = HTF_MAP.get(self.granularity, HTF_MAP[900])
            hist_h1 = await self.client.get_candles(self.symbol, htf1g, 200)
            self.candles_h1.clear()
            for c in hist_h1:
                self.candles_h1.append(c)
            logger.info(f"HTF refresh: {len(self.candles_h1)} {htf1_lbl} candles")
            if h4:
                hist_h4 = await self.client.get_candles(self.symbol, htf2g, 150)
                self.candles_h4.clear()
                for c in hist_h4:
                    self.candles_h4.append(c)
                logger.info(f"HTF refresh: {len(self.candles_h4)} {htf2_lbl} candles")
        except Exception as e:
            logger.warning(f"HTF refresh failed: {e}")

    async def stop(self):
        self.running = False
        await self.client.disconnect()
        logger.info("Bot stopped")

    async def _on_tick(self, price: float, epoch: int):
        if not self.running or self._switching:
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

        self.tick_flow.push(price, float(epoch))
        self._last_tick_at = time.time()

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

        # ── Tick flow ─────────────────────────────────────────────────────
        flow = self.tick_flow.analyze(window=80)

        result = self.analyzer.analyze_mtf(
            candle_list,
            list(self.candles_h1),
            list(self.candles_h4),
            tick_flow=flow,
            candles_usdjpy=list(self.candles_usdjpy),
        )

        # ── Notícias + sentimento (refresh a cada ~25 análises ≈ 5min) ────
        self._news_refresh_counter += 1
        if self.news and self._news_refresh_counter % 25 == 1:
            try:
                self._news_context = await self.news.get_market_context()
            except Exception as e:
                logger.warning(f"News refresh failed: {e}")

        # ── Ajuste de confiança por notícias ──────────────────────────────
        news_mult, news_label = 1.0, ""
        if self._news_context and result.signal != "WAIT":
            news_mult, news_label = self.news.news_score_adjustment(
                self._news_context, result.signal
            )
            if news_mult == 0.0:
                result.signal     = "WAIT"
                result.confidence = 0.0
                result.reason     = f"{news_label} | {result.reason}"
            elif news_mult != 1.0:
                result.confidence = round(result.confidence * news_mult, 1)
                if news_label:
                    result.reason = f"{news_label} | {result.reason}"

        # ── Ajuste de confiança por aprendizado ───────────────────────────
        learning_label = ""
        if result.signal != "WAIT":
            base_payload = {
                "signal":      result.signal,
                "confidence":  result.confidence,
                "rsi":         result.rsi,
                "macd":        result.macd,
                "macd_signal": result.macd_signal,
                "bb_upper":    result.bb_upper,
                "bb_lower":    result.bb_lower,
                "adx":         result.adx,
                "atr_ratio":   result.atr_ratio,
                "buy_score":   result.buy_score,
                "sell_score":  result.sell_score,
                "patterns":    result.patterns,
                "divergences": result.divergences,
                "price":       candle_list[-1]["close"] if candle_list else 0,
                "h1_bias":     result.h1_bias,
                "h4_bias":     result.h4_bias,
                "session":     result.session,
            }
            result.confidence, learning_label = self.learning.adjust_confidence(
                base_payload, result.confidence
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
                # ── Novas inteligências ────────────────────────────────────
                "tick_flow": {
                    "velocity":   flow.velocity,
                    "momentum":   flow.momentum,
                    "imbalance":  flow.imbalance,
                    "smoothness": flow.smoothness,
                    "buy_pts":    flow.buy_pts,
                    "sell_pts":   flow.sell_pts,
                },
                "news": self._news_context,
                "learning_label": learning_label,
                "learning": self.learning.stats(),
                "vwap":        round(result.vwap, 5),
                "fib_level":   result.fib_level,
                "usd_strength": self.analyzer._usd_strength(list(self.candles_usdjpy)) if self.candles_usdjpy else "NEUTRAL",
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

        # ── Determina motivo de bloqueio (exibido na UI via last_signal) ────────
        block_reason: str = ""

        # Cooldown após ERRO de API
        if self._last_error_at > 0:
            elapsed = time.time() - self._last_error_at
            if elapsed < self._error_cooldown:
                remaining = int(self._error_cooldown - elapsed)
                block_reason = f"Cooldown pós-erro: {remaining}s restantes"
                logger.info(block_reason)

        # WS de trading não autenticada
        if not block_reason and (not self.client.authorized or not self.client._trade_ws):
            block_reason = "WS de trading não autenticada — reconectando"

        # Risk manager (limite de perda, cooldown de loss, posição aberta, etc.)
        if not block_reason:
            effective_conf = max(self.risk.config.min_confidence, self.adaptive.state.min_confidence)
            win_rate = self.learning.stats().get("win_rate", 0.0) / 100.0
            decision = self.risk.can_trade(result.confidence, result.signal, win_rate)
            if not decision.allowed:
                block_reason = decision.reason
            elif result.confidence < effective_conf:
                block_reason = f"Confiança {result.confidence:.1f}% < mínimo adaptativo {effective_conf:.1f}%"

        if block_reason:
            logger.info(f"Trade blocked: {block_reason}")
            # Propaga o motivo para a UI via last_signal
            if self.last_signal:
                self.last_signal["block_reason"] = block_reason
            if self.on_signal and self.last_signal:
                asyncio.create_task(self.on_signal({**self.last_signal, "block_reason": block_reason}))
            return

        async with self._trade_lock:
            if self.risk.stats.open_positions >= self.risk.config.max_open_positions:
                logger.info("Trade blocked: operação já aberta ou em abertura")
                return
            decision = self.risk.can_trade(result.confidence, result.signal, win_rate)
            if not decision.allowed:
                logger.info(f"Trade blocked: {decision.reason}")
                return
            await self._place_trade(result, decision.stake)

    async def _place_trade(self, result: AnalysisResult, stake: float):
        contract_type = CONTRACT_TYPE[result.signal]
        entry_price   = float(list(self.candles)[-1]["close"]) if self.candles else 0.0

        # ── Verifica WS ANTES de criar o TradeRecord ─────────────────────────
        # Erros de WS (conexão) não devem criar entradas "ERRO" no histórico
        # nem ativar cooldown — o bot simplesmente aguarda a reconexão.
        try:
            self.client._require_trade_ws()
        except RuntimeError as ws_err:
            logger.warning(f"Trade adiado (WS indisponível): {ws_err}")
            return   # sem TradeRecord, sem cooldown, sem erro no histórico

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
            # ── Fallback automático de duração ────────────────────────────────
            # A nova API Deriv (api.derivws.com) não suporta minutos para todos
            # os ativos. Tenta durações em ordem até encontrar uma aceita.
            proposal = None
            durations_to_try: list[tuple[int, str]] = [
                (self.contract_duration, "m"),   # preferido: minutos
                (5, "m"), (2, "m"), (1, "m"),    # minutos menores
                (10, "t"), (5, "t"),             # ticks como último recurso
            ]
            last_duration_error: Exception | None = None
            for _dur, _unit in durations_to_try:
                try:
                    proposal = await self.client.get_proposal(
                        symbol=self.symbol,
                        contract_type=contract_type,
                        stake=stake,
                        duration=_dur,
                        duration_unit=_unit,
                    )
                    if (_dur, _unit) != (self.contract_duration, "m"):
                        logger.warning(
                            f"Duration fallback: {self.contract_duration}m não suportado "
                            f"→ usando {_dur}{_unit} para {self.symbol}"
                        )
                    break   # encontrou uma duração válida
                except RuntimeError as _de:
                    if "TradingDurationNotAllowed" in str(_de):
                        last_duration_error = _de
                        continue   # tenta próxima duração
                    raise          # erro diferente — propaga normalmente
            if proposal is None:
                raise last_duration_error or RuntimeError(
                    f"Nenhuma duração válida encontrada para {self.symbol}"
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

            # Registra sinal no learning engine para aprendizado futuro
            self.learning.record_signal(self.last_signal, contract_id=trade.contract_id)

            # Notificação Telegram
            if self.telegram:
                asyncio.create_task(self.telegram.notify_trade_opened(
                    signal=result.signal,
                    asset=self.asset,
                    stake_usd=stake,
                    confidence=result.confidence,
                    reason=result.reason,
                    brl_rate=self._brl_rate,
                ))

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

            err_str = str(e).lower()
            is_ws_error = any(kw in err_str for kw in (
                "ws", "connection", "websocket", "closed", "não conectada",
                "estado", "timeout", "não aberta",
            ))

            if is_ws_error:
                # Erro de conexão: não cria histórico de ERRO, não ativa cooldown.
                # O bot vai tentar novamente na próxima janela de análise.
                logger.warning(f"Trade adiado (conexão instável): {e}")
            else:
                # Erro real da API Deriv (TradingDurationNotAllowed, saldo insuf., etc.)
                trade.status = "ERROR"
                trade.reason = f"Erro DERIV: {e}"
                trade.pnl    = 0.0
                self._last_error_at = time.time()   # ativa cooldown apenas para erros reais
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

        # Registra outcome para o learning engine aprender
        if trade.contract_id:
            self.learning.record_outcome(trade.contract_id, trade.status)

        # Notificação Telegram
        if self.telegram:
            asyncio.create_task(self.telegram.notify_trade_closed(
                signal=trade.signal,
                status=trade.status,
                pnl_usd=trade.pnl,
                brl_rate=self._brl_rate,
            ))

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
            if self.telegram:
                asyncio.create_task(self.telegram.notify_auto_stop(stop_reason))
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
            "auto_asset":        self.auto_asset,
            "session":           self._current_session() if self.auto_asset else "",
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
