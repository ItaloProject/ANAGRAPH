import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.api import signals, market, backtest
from app.services.trader import TradingBot
from app.services.risk_manager import RiskConfig
from app.services.deriv_client import DerivClient
from app.config.currency import brl_to_usd, currency_config, usd_to_brl

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_API_TOKEN   = os.getenv("DERIV_API_TOKEN", "").strip()
DEFAULT_ACCOUNT_ID  = os.getenv("DERIV_ACCOUNT_ID", "").strip()
DEFAULT_APP_ID      = os.getenv("DERIV_APP_ID", "33qwHdRH3vY9cCAeAzIa7").strip()
BOT_AUTOSTART       = os.getenv("BOT_AUTOSTART", "true").lower() in ("1", "true", "yes")

_bot: Optional["TradingBot"] = None
_ws_clients: list[WebSocket] = []
_autostart_lock = asyncio.Lock()
_watchdog_task: Optional[asyncio.Task] = None


async def _watchdog_loop():
    """Reativa o bot no servidor se parar inesperadamente (modo 24/7)."""
    while True:
        await asyncio.sleep(90)
        if not BOT_AUTOSTART:
            continue
        try:
            await _ensure_bot_running()
        except Exception as e:
            logger.error(f"Watchdog error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _watchdog_task
    _watchdog_task = asyncio.create_task(_watchdog_loop())
    await asyncio.sleep(1.5)
    if BOT_AUTOSTART:
        asyncio.create_task(_ensure_bot_running())
    yield
    if _watchdog_task:
        _watchdog_task.cancel()
    global _bot
    if _bot and _bot.running:
        await _bot.stop()
        _bot = None


app = FastAPI(title="ANAGRAPH API", version="1.1.0", lifespan=lifespan)

ALLOWED_ORIGINS = [
    "http://localhost:9000",          # dev Quasar
    "http://localhost:5173",          # dev Vite
    os.getenv("FRONTEND_URL", ""),    # ex: https://anagraph.vercel.app
    os.getenv("FRONTEND_URL_2", ""),  # domínio customizado opcional
]
# Remove vazios e mantém * em dev
_origins = [o for o in ALLOWED_ORIGINS if o] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # qualquer deploy do Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router,  prefix="/api/signals",  tags=["signals"])
app.include_router(market.router,   prefix="/api/market",   tags=["market"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])

async def _broadcast(event: str, data: dict):
    payload = json.dumps({"event": event, "data": data})
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


class BotStartRequest(BaseModel):
    api_token: str = ""
    app_id: str = DEFAULT_APP_ID
    account_id: str = ""
    asset: str = "EUR/USD"
    granularity: int = 900
    contract_duration: int = Field(default=15, ge=15, le=60, description="Rise/Fall duration in minutes (min 15 for forex)")
    stake_amount: float = 6.0
    max_stake: float = 60.0
    daily_loss_limit: float = 100.0
    daily_profit_target: float = 150.0
    min_confidence: float = 78.0
    max_consecutive_losses: int = Field(default=3, ge=1, le=10)
    cooldown_after_loss_sec: int = Field(default=300, ge=0, le=3600)
    analyzer_min_score: int = Field(default=5, ge=3, le=10)
    analyzer_min_gap: int = Field(default=2, ge=1, le=5)
    analyzer_min_adx: float = Field(default=22.0, ge=15.0, le=40.0)
    analyze_every: int = 15
    session_mode: str = "london_ny"  # "all"|"london_ny"|"london"|"new_york"|"asian"


def _enforce_conservative(req: BotStartRequest) -> BotStartRequest:
    """Garante piso do perfil conservador oficial — qualidade sobre quantidade."""
    req.asset = "EUR/USD"
    req.granularity = 900
    req.contract_duration = max(req.contract_duration, 15)
    req.min_confidence = max(req.min_confidence, 78.0)
    req.max_consecutive_losses = min(req.max_consecutive_losses, 3)
    req.cooldown_after_loss_sec = max(req.cooldown_after_loss_sec, 300)
    req.analyzer_min_score = max(req.analyzer_min_score, 5)
    req.analyzer_min_gap = max(req.analyzer_min_gap, 2)
    req.analyzer_min_adx = max(req.analyzer_min_adx, 22.0)
    req.analyze_every = max(req.analyze_every, 15)
    return req


def _build_risk_config(req: BotStartRequest) -> RiskConfig:
    return RiskConfig(
        stake_amount=brl_to_usd(req.stake_amount),
        max_stake=brl_to_usd(req.max_stake),
        daily_loss_limit=brl_to_usd(req.daily_loss_limit),
        daily_profit_target=brl_to_usd(req.daily_profit_target),
        min_confidence=req.min_confidence,
        max_consecutive_losses=req.max_consecutive_losses,
        cooldown_after_loss_sec=req.cooldown_after_loss_sec,
    )


async def _launch_bot(req: BotStartRequest) -> dict:
    global _bot
    if _bot and _bot.running:
        return {"status": "already_running", "bot_running": True}

    req = _enforce_conservative(req)
    api_token  = (req.api_token or DEFAULT_API_TOKEN).strip()
    account_id = (req.account_id or DEFAULT_ACCOUNT_ID).strip()
    app_id     = (req.app_id or DEFAULT_APP_ID).strip()

    if not api_token:
        raise HTTPException(400, "Token DERIV não configurado. Defina DERIV_API_TOKEN no backend/.env")
    if not account_id:
        raise HTTPException(400, "Account ID não configurado. Defina DERIV_ACCOUNT_ID no backend/.env")

    _bot = TradingBot(
        api_token=api_token,
        app_id=app_id,
        account_id=account_id,
        asset=req.asset,
        granularity=req.granularity,
        contract_duration=req.contract_duration,
        risk_config=_build_risk_config(req),
        analyzer_min_score=req.analyzer_min_score,
        analyzer_min_gap=req.analyzer_min_gap,
        analyzer_min_adx=req.analyzer_min_adx,
        analyze_every=req.analyze_every,
        session_mode=req.session_mode,
        on_signal=lambda d: _broadcast("signal", d),
        on_trade=lambda d: _broadcast("trade", d),
        on_tick=lambda d: _broadcast("tick", d),
        on_stats=lambda d: _broadcast("stats", d),
    )

    asyncio.create_task(_bot.start())
    return {
        "status": "started",
        "bot_running": True,
        "mode": "conservative_precision",
        "profile": "conservative",
        "duration_minutes": req.contract_duration,
        "background_mode": True,
    }


async def _ensure_bot_running() -> bool:
    """Garante bot ativo no servidor — independe do browser/celular."""
    if not BOT_AUTOSTART or not DEFAULT_API_TOKEN or not DEFAULT_ACCOUNT_ID:
        return bool(_bot and _bot.running)

    async with _autostart_lock:
        if _bot and _bot.running:
            return True
        try:
            await _launch_bot(BotStartRequest())
            logger.info("Bot autostarted on server (background mode)")
            return True
        except HTTPException:
            return False
        except Exception as e:
            logger.error(f"Autostart failed: {e}")
            return False


@app.post("/api/bot/start")
async def start_bot(req: BotStartRequest):
    return await _launch_bot(req)


@app.post("/api/bot/ensure-running")
async def ensure_bot_running():
    """Reativa o bot no servidor — usado pelo keep-alive e após reinício do Render."""
    if not DEFAULT_API_TOKEN or not DEFAULT_ACCOUNT_ID:
        raise HTTPException(400, "Credenciais DERIV não configuradas")
    ok = await _ensure_bot_running()
    return {
        "status": "running" if ok else "failed",
        "bot_running": bool(_bot and _bot.running),
        "background_mode": True,
    }


@app.post("/api/bot/stop")
async def stop_bot():
    global _bot
    if _bot:
        await _bot.stop()
        _bot = None
    return {"status": "stopped"}


@app.get("/api/bot/status")
async def bot_status():
    if not _bot:
        return {"running": False}
    return _bot.snapshot()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    logger.info(f"WS client connected. Total: {len(_ws_clients)}")

    if _bot:
        await ws.send_text(json.dumps({"event": "status", "data": _bot.snapshot()}))

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            if data.get("type") == "ping":
                await ws.send_text(json.dumps({"event": "pong"}))

    except WebSocketDisconnect:
        _ws_clients.remove(ws)
        logger.info(f"WS client disconnected. Total: {len(_ws_clients)}")


@app.get("/api/health")
async def health():
    """Leve — não consulta DERIV (evita travar o servidor)."""
    if BOT_AUTOSTART and DEFAULT_API_TOKEN and DEFAULT_ACCOUNT_ID:
        if not _bot or not _bot.running:
            asyncio.create_task(_ensure_bot_running())
    return {
        "status": "ok",
        "bot_running": _bot.running if _bot else False,
        "ws_clients": len(_ws_clients),
        "credentials_configured": bool(DEFAULT_API_TOKEN and DEFAULT_ACCOUNT_ID),
        "autostart_enabled": BOT_AUTOSTART,
        "background_mode": True,
    }


@app.get("/api/account/status")
async def account_status():
    """Saldo da conta DERIV. Usa a conexão do bot se ele estiver rodando."""
    if not DEFAULT_API_TOKEN or not DEFAULT_ACCOUNT_ID:
        raise HTTPException(400, "Credenciais DERIV não configuradas")

    # Usa conexão já aberta do bot (evita criar nova conexão WebSocket)
    if _bot and _bot.running and _bot.client.authorized:
        try:
            info = await asyncio.wait_for(_bot.client.get_account_info(), timeout=15.0)
            return info
        except Exception as e:
            logger.warning(f"account_status via bot failed: {e}")

    # Fallback: cria conexão temporária com timeout
    client = DerivClient(
        app_id=DEFAULT_APP_ID,
        api_token=DEFAULT_API_TOKEN,
        account_id=DEFAULT_ACCOUNT_ID,
    )
    try:
        await asyncio.wait_for(client.connect(), timeout=20.0)
        info = await asyncio.wait_for(client.get_account_info(), timeout=10.0)
        return info
    except asyncio.TimeoutError:
        raise HTTPException(504, "Timeout ao conectar à DERIV. Tente novamente.")
    except Exception as e:
        logger.error(f"account_status error: {e}")
        raise HTTPException(502, f"Falha ao consultar DERIV: {e}")
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), timeout=5.0)
        except Exception:
            pass


@app.get("/api/bot/credentials")
async def credentials_status():
    aid = DEFAULT_ACCOUNT_ID
    return {
        "token_configured":   bool(DEFAULT_API_TOKEN),
        "account_configured": bool(aid),
        "app_id":             DEFAULT_APP_ID,
        "account_id":         aid,
        "account_id_hint":    aid[:3] + "..." + aid[-2:] if len(aid) > 5 else aid,
        "is_demo":            aid.upper().startswith(("VRT", "DOT")),
    }


@app.get("/api/auth/session")
async def auth_session():
    """Indica se o backend já tem credenciais DERIV — frontend entra sem OAuth."""
    if not DEFAULT_API_TOKEN or not DEFAULT_ACCOUNT_ID:
        return {"available": False}

    aid = DEFAULT_ACCOUNT_ID.upper()
    is_demo = aid.startswith("VRT") or aid.startswith("VRW") or aid.startswith("DOT")

    return {
        "available":     True,
        "app_id":        DEFAULT_APP_ID,
        "account_id":    DEFAULT_ACCOUNT_ID,
        "account_hint":  DEFAULT_ACCOUNT_ID[:3] + "..." + DEFAULT_ACCOUNT_ID[-2:],
        "is_demo":       is_demo,
        "currency":      "USD",
    }


@app.get("/api/config/currency")
async def get_currency_config():
    """Moeda de exibição (BRL) e cotação USD/BRL para conversão na UI."""
    return currency_config()


@app.get("/api/bot/daily-stats")
async def daily_stats_from_deriv():
    """Stats do dia direto da DERIV — funciona mesmo com bot parado."""
    if not DEFAULT_API_TOKEN or not DEFAULT_ACCOUNT_ID:
        raise HTTPException(400, "Credenciais DERIV não configuradas")

    from datetime import date, datetime

    # Usa conexão do bot se disponível
    if _bot and _bot.running and _bot.client.authorized:
        try:
            txs = await asyncio.wait_for(_bot.client.get_profit_table(limit=100), timeout=15.0)
        except Exception as e:
            logger.warning(f"daily_stats via bot failed: {e}")
            txs = []
    else:
        client = DerivClient(
            app_id=DEFAULT_APP_ID,
            api_token=DEFAULT_API_TOKEN,
            account_id=DEFAULT_ACCOUNT_ID,
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=20.0)
            txs = await asyncio.wait_for(client.get_profit_table(limit=100), timeout=10.0)
        except asyncio.TimeoutError:
            raise HTTPException(504, "Timeout ao conectar à DERIV. Tente novamente.")
        except Exception as e:
            logger.error(f"daily_stats error: {e}")
            raise HTTPException(502, f"Falha ao consultar DERIV: {e}")
        finally:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=5.0)
            except Exception:
                pass

    today = date.today()
    symbol = "frxEURUSD"
    wins = losses = 0
    pnl = 0.0
    trades_list = []

    for tx in txs:
        ctype = tx.get("contract_type", "")
        sym = tx.get("underlying_symbol", "")
        if ctype not in ("CALL", "PUT") or sym != symbol:
            continue
        pt = int(tx.get("purchase_time") or 0)
        if not pt or datetime.fromtimestamp(pt).date() != today:
            continue
        stake = float(tx.get("buy_price") or 1)
        sell = float(tx.get("sell_price") or 0)
        trade_pnl = round(sell - stake, 2)
        pnl += trade_pnl
        if trade_pnl > 0:
            wins += 1
        else:
            losses += 1
        trades_list.append({
            "id": f"deriv-{tx.get('contract_id')}",
            "signal": "BUY" if ctype == "CALL" else "SELL",
            "asset": "EUR/USD",
            "stake": stake,
            "confidence": 0,
            "reason": "Histórico DERIV",
            "status": "WIN" if trade_pnl > 0 else "LOSS",
            "pnl": trade_pnl,
            "payout": float(tx.get("payout") or 0),
            "entry_price": 0,
            "expires_at": None,
            "opened_at": datetime.fromtimestamp(pt).isoformat(),
            "closed_at": datetime.fromtimestamp(int(tx.get("sell_time") or pt)).isoformat(),
            "duration": "15m",
            "contract_type": "RISE" if ctype == "CALL" else "FALL",
        })

    total = wins + losses or 1
    daily_loss_limit_usd = brl_to_usd(float(os.getenv("DAILY_LOSS_LIMIT_BRL", "100")))
    pnl_brl = usd_to_brl(pnl)
    return {
        "stats": {
            "date": str(today),
            "pnl": round(pnl, 2),
            "pnl_brl": pnl_brl,
            "wins": wins,
            "losses": losses,
            "trades": wins + losses,
            "accuracy": round(wins / total * 100, 1),
            "open_positions": 0,
            "current_streak": 0,
            "daily_limit_used": round(abs(pnl) / daily_loss_limit_usd * 100, 1) if pnl < 0 else 0,
            "display_currency": "BRL",
        },
        "trades_list": trades_list,
    }


@app.post("/api/bot/reconcile")
async def reconcile_trades():
    """Sincroniza trades abertas com status real na DERIV."""
    if not _bot or not _bot.running:
        return {"error": "Bot não iniciado"}
    await _bot.sync_today_from_deriv()
    await _bot.reconcile_open_trades()
    if _bot.on_stats:
        await _bot.on_stats(_bot.risk.summary)
    return _bot.snapshot()


@app.get("/api/bot/adaptive")
async def adaptive_state():
    """Estado atual do auto-ajuste adaptativo de parâmetros."""
    if not _bot:
        return {"error": "Bot não iniciado"}
    return _bot.adaptive.snapshot()


@app.post("/api/bot/analyze-now")
async def force_analyze():
    if not _bot:
        return {"error": "Bot não iniciado"}
    await _bot._analyze_and_trade()
    return {"status": "analysis triggered"}


@app.get("/api/bot/diagnose")
async def diagnose():
    if not _bot:
        return {"error": "Bot não iniciado"}

    trade_ws = _bot.client._trade_ws
    public_ws = _bot.client._public_ws

    result = {
        "running":           _bot.running,
        "authorized":        _bot.client.authorized,
        "contract_mode":     "rise_fall",
        "contract_duration": _bot.contract_duration,
        "candles":           len(_bot.candles),
        "asset":             _bot.asset,
        "symbol":            _bot.symbol,
        "has_token":         bool(_bot.client.api_token),
        "app_id":            _bot.client.app_id,
        "trade_ws_open":     trade_ws is not None and getattr(trade_ws, "open", True),
        "public_ws_open":    public_ws is not None and getattr(public_ws, "open", True),
        "open_trades":       sum(1 for t in _bot.trades if t.status == "OPEN"),
    }

    return result
