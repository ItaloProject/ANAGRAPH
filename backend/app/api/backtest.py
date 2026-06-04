import asyncio
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.backtester import run_backtest, run_grid, BacktestResult
from app.services.deriv_client import DerivClient

logger = logging.getLogger(__name__)
router = APIRouter()

APP_ID = "33qwHdRH3vY9cCAeAzIa7"

# HTF (higher timeframe) por granularidade primária — mesmo esquema do bot ao vivo.
HTF_MAP = {
    900:  (3600, 14400),   # M15 → H1, H4
    3600: (14400, 86400),  # H1  → H4, D1
}

# ── Job store em memória ─────────────────────────────────────────────────────
# Chave: job_id (8 chars)
# Valor: {"status": "running"|"done"|"error", "result": dict|None, "error": str|None,
#          "started_at": str, "type": "backtest"|"grid"}
_jobs: dict[str, dict] = {}


def _cleanup_jobs() -> None:
    """Mantém no máximo 30 jobs — descarta os mais antigos."""
    if len(_jobs) > 30:
        oldest = sorted(_jobs.keys(), key=lambda k: _jobs[k].get("started_at", ""))
        for k in oldest[:-30]:
            del _jobs[k]


class BacktestResponse(BaseModel):
    total_signals:  int
    total_trades:   int
    wins:           int
    losses:         int
    win_rate:       float
    pnl:            float
    max_drawdown:   float
    profit_factor:  float
    sharpe:         float
    avg_confidence: float
    equity_curve:   list[dict]
    by_session:     dict
    by_signal:      dict
    by_pattern:     dict
    params:         dict


async def _fetch_all(
    client: DerivClient, symbol: str, granularity: int, count: int, use_mtf: bool,
) -> tuple[list, list | None, list | None, list | None]:
    """Busca candles primários + (se MTF) H1/H4 e USD/JPY como proxy DXY."""
    primary = await client.get_candles(symbol, granularity, count)
    if not use_mtf:
        return primary, None, None, None

    h1g, h4g = HTF_MAP.get(granularity, (granularity * 4, granularity * 16))
    h1 = h4 = jpy = None
    try:
        h1 = await client.get_candles(symbol, h1g, 720)
    except Exception as e:
        logger.warning(f"Backtest H1 fetch failed: {e}")
    try:
        h4 = await client.get_candles(symbol, h4g, 400)
    except Exception as e:
        logger.warning(f"Backtest H4 fetch failed: {e}")
    if "JPY" not in symbol:   # DXY proxy só para pares não-JPY
        try:
            jpy = await client.get_candles("frxUSDJPY", granularity, count)
        except Exception as e:
            logger.warning(f"Backtest USD/JPY fetch failed: {e}")
    return primary, h1, h4, jpy


def _make_backtest_response(result: BacktestResult) -> dict:
    return BacktestResponse(
        total_signals=result.total_signals, total_trades=result.total_trades,
        wins=result.wins, losses=result.losses, win_rate=result.win_rate,
        pnl=result.pnl, max_drawdown=result.max_drawdown,
        profit_factor=result.profit_factor, sharpe=result.sharpe,
        avg_confidence=result.avg_confidence, equity_curve=result.equity_curve,
        by_session=result.by_session, by_signal=result.by_signal,
        by_pattern=result.by_pattern, params=result.params,
    ).model_dump()


# ── Background job runner — não vinculado ao request HTTP ───────────────────

async def _run_backtest_job(job_id: str, p: dict) -> None:
    """Roda backtest em background. Não cancela se o cliente desconectar."""
    try:
        client = DerivClient(app_id=APP_ID)
        try:
            await client.connect()
            primary, h1, h4, jpy = await _fetch_all(
                client, p["symbol"], p["granularity"], p["count"], p["use_mtf"]
            )
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"]  = f"Falha ao buscar candles da Deriv: {e}"
            return
        finally:
            await client.disconnect()

        if len(primary) < 70:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"]  = "Candles insuficientes para backtest (mín. 70)"
            return

        logger.info(
            f"[Job {job_id}] Backtest: {len(primary)} candles | sym={p['symbol']} | "
            f"gran={p['granularity']}s | conf>={p['min_confidence']} | MTF={p['use_mtf']}"
        )

        loop = asyncio.get_event_loop()
        result: BacktestResult = await loop.run_in_executor(
            None,
            lambda: run_backtest(
                candles=primary, candles_h1=h1, candles_h4=h4, candles_usdjpy=jpy,
                min_confidence=p["min_confidence"], min_score=p["min_score"],
                min_score_gap=p["min_score_gap"], min_adx=p["min_adx"],
                stake=p["stake"], use_mtf=p["use_mtf"],
            ),
        )

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = _make_backtest_response(result)
        logger.info(f"[Job {job_id}] Backtest concluído — {result.total_trades} trades")

    except Exception as e:
        logger.error(f"[Job {job_id}] Backtest falhou: {e}")
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"]  = str(e)


async def _run_grid_job(job_id: str, p: dict) -> None:
    """Roda grid search em background. Não cancela se o cliente desconectar."""
    try:
        client = DerivClient(app_id=APP_ID)
        try:
            await client.connect()
            primary, h1, h4, jpy = await _fetch_all(
                client, p["symbol"], p["granularity"], p["count"], p["use_mtf"]
            )
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"]  = f"Falha ao buscar candles da Deriv: {e}"
            return
        finally:
            await client.disconnect()

        if len(primary) < 100:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"]  = "Candles insuficientes para grid (mín. 100)"
            return

        logger.info(f"[Job {job_id}] Grid: {len(primary)} candles | sym={p['symbol']} | MTF={p['use_mtf']}")

        loop = asyncio.get_event_loop()
        grid = await loop.run_in_executor(
            None,
            lambda: run_grid(
                candles=primary, candles_h1=h1, candles_h4=h4, candles_usdjpy=jpy,
                stake=p["stake"], min_score_gap=p["min_score_gap"], use_mtf=p["use_mtf"],
            ),
        )

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = grid
        logger.info(f"[Job {job_id}] Grid concluído")

    except Exception as e:
        logger.error(f"[Job {job_id}] Grid falhou: {e}")
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"]  = str(e)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/start")
async def backtest_start(
    symbol:         str   = Query("frxEURUSD"),
    granularity:    int   = Query(900,  ge=60,   le=86400),
    count:          int   = Query(500,  ge=100,  le=2000),
    min_confidence: float = Query(78.0, ge=50.0, le=99.0),
    min_score:      int   = Query(5,    ge=3,    le=10),
    min_score_gap:  int   = Query(2,    ge=1,    le=5),
    min_adx:        float = Query(20.0, ge=10.0, le=40.0),
    stake:          float = Query(6.0,  ge=1.0,  le=100.0),
    use_mtf:        bool  = Query(True),
):
    """Inicia backtest em background. Retorna job_id para polling via /status/{job_id}."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "status":     "running",
        "type":       "backtest",
        "result":     None,
        "error":      None,
        "started_at": datetime.utcnow().isoformat(),
    }
    _cleanup_jobs()

    asyncio.create_task(_run_backtest_job(job_id, {
        "symbol": symbol, "granularity": granularity, "count": count,
        "min_confidence": min_confidence, "min_score": min_score,
        "min_score_gap": min_score_gap, "min_adx": min_adx,
        "stake": stake, "use_mtf": use_mtf,
    }))

    logger.info(f"[Job {job_id}] Backtest agendado")
    return {"job_id": job_id}


@router.get("/grid/start")
async def grid_start(
    symbol:        str   = Query("frxEURUSD"),
    granularity:   int   = Query(900,  ge=60,   le=86400),
    count:         int   = Query(1000, ge=200,  le=2000),
    stake:         float = Query(6.0,  ge=1.0,  le=100.0),
    min_score_gap: int   = Query(2,    ge=1,    le=5),
    use_mtf:       bool  = Query(True),
):
    """Inicia grid search em background. Retorna job_id para polling via /status/{job_id}."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "status":     "running",
        "type":       "grid",
        "result":     None,
        "error":      None,
        "started_at": datetime.utcnow().isoformat(),
    }
    _cleanup_jobs()

    asyncio.create_task(_run_grid_job(job_id, {
        "symbol": symbol, "granularity": granularity, "count": count,
        "stake": stake, "min_score_gap": min_score_gap, "use_mtf": use_mtf,
    }))

    logger.info(f"[Job {job_id}] Grid agendado")
    return {"job_id": job_id}


@router.get("/status/{job_id}")
async def backtest_job_status(job_id: str):
    """Consulta status/resultado de um job de backtest ou grid."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado — pode ter expirado")
    return job


# ── Endpoints legados (mantidos para compatibilidade) ────────────────────────

@router.get("/run", response_model=BacktestResponse)
async def backtest_run(
    symbol:         str   = Query("frxEURUSD"),
    granularity:    int   = Query(900,  ge=60,   le=86400),
    count:          int   = Query(500,  ge=100,  le=2000),
    min_confidence: float = Query(78.0, ge=50.0, le=99.0),
    min_score:      int   = Query(5,    ge=3,    le=10),
    min_score_gap:  int   = Query(2,    ge=1,    le=5),
    min_adx:        float = Query(22.0, ge=10.0, le=40.0),
    stake:          float = Query(6.0,  ge=1.0,  le=100.0),
    use_mtf:        bool  = Query(True),
):
    """Walk-forward backtest síncrono (legado). Prefira /start + /status/{id}."""
    client = DerivClient(app_id=APP_ID)
    try:
        await client.connect()
        primary, h1, h4, jpy = await _fetch_all(client, symbol, granularity, count, use_mtf)
    except Exception as e:
        raise HTTPException(502, f"Falha ao buscar candles da Deriv: {e}")
    finally:
        await client.disconnect()

    if len(primary) < 70:
        raise HTTPException(422, "Candles insuficientes para backtest (mín. 70)")

    loop = asyncio.get_event_loop()
    result: BacktestResult = await loop.run_in_executor(
        None,
        lambda: run_backtest(
            candles=primary, candles_h1=h1, candles_h4=h4, candles_usdjpy=jpy,
            min_confidence=min_confidence, min_score=min_score,
            min_score_gap=min_score_gap, min_adx=min_adx, stake=stake,
            use_mtf=use_mtf,
        ),
    )

    return BacktestResponse(**_make_backtest_response(result))


@router.get("/grid")
async def backtest_grid(
    symbol:        str  = Query("frxEURUSD"),
    granularity:   int  = Query(900,  ge=60,   le=86400),
    count:         int  = Query(1000, ge=200,  le=2000),
    stake:         float = Query(6.0, ge=1.0,  le=100.0),
    min_score_gap: int  = Query(2,    ge=1,    le=5),
    use_mtf:       bool = Query(True),
):
    """Grid search síncrono (legado). Prefira /grid/start + /status/{id}."""
    client = DerivClient(app_id=APP_ID)
    try:
        await client.connect()
        primary, h1, h4, jpy = await _fetch_all(client, symbol, granularity, count, use_mtf)
    except Exception as e:
        raise HTTPException(502, f"Falha ao buscar candles da Deriv: {e}")
    finally:
        await client.disconnect()

    if len(primary) < 100:
        raise HTTPException(422, "Candles insuficientes para grid (mín. 100)")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: run_grid(
            candles=primary, candles_h1=h1, candles_h4=h4, candles_usdjpy=jpy,
            stake=stake, min_score_gap=min_score_gap, use_mtf=use_mtf,
        ),
    )
