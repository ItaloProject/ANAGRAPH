import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.backtester import run_backtest, BacktestResult
from app.services.deriv_client import DerivClient

logger = logging.getLogger(__name__)
router = APIRouter()

APP_ID = "33qwHdRH3vY9cCAeAzIa7"


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


@router.get("/run", response_model=BacktestResponse)
async def backtest_run(
    symbol:         str   = Query("frxEURUSD"),
    granularity:    int   = Query(900,  ge=60,  le=86400),
    count:          int   = Query(500,  ge=100, le=2000),
    min_confidence: float = Query(78.0, ge=50.0, le=99.0),
    min_score:      int   = Query(5,    ge=3,   le=10),
    min_score_gap:  int   = Query(2,    ge=1,   le=5),
    min_adx:        float = Query(22.0, ge=10.0, le=40.0),
    stake:          float = Query(6.0,  ge=1.0,  le=100.0),
):
    """
    Walk-forward backtest on historical candles fetched from Deriv.
    CPU-bound work runs in a thread pool to avoid blocking the event loop.
    """
    client = DerivClient(app_id=APP_ID)
    try:
        await client.connect()
        candles = await client.get_candles(symbol, granularity, count)
    except Exception as e:
        raise HTTPException(502, f"Falha ao buscar candles da Deriv: {e}")
    finally:
        await client.disconnect()

    if len(candles) < 70:
        raise HTTPException(422, "Candles insuficientes para backtest (mín. 70)")

    logger.info(
        f"Backtest request: {len(candles)} candles | sym={symbol} | "
        f"gran={granularity}s | conf>={min_confidence}"
    )

    loop   = asyncio.get_event_loop()
    result: BacktestResult = await loop.run_in_executor(
        None,
        lambda: run_backtest(
            candles=candles,
            min_confidence=min_confidence,
            min_score=min_score,
            min_score_gap=min_score_gap,
            min_adx=min_adx,
            stake=stake,
        ),
    )

    return BacktestResponse(
        total_signals  = result.total_signals,
        total_trades   = result.total_trades,
        wins           = result.wins,
        losses         = result.losses,
        win_rate       = result.win_rate,
        pnl            = result.pnl,
        max_drawdown   = result.max_drawdown,
        profit_factor  = result.profit_factor,
        sharpe         = result.sharpe,
        avg_confidence = result.avg_confidence,
        equity_curve   = result.equity_curve,
        by_session     = result.by_session,
        by_signal      = result.by_signal,
        by_pattern     = result.by_pattern,
        params         = result.params,
    )
