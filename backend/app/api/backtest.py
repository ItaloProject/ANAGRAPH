import asyncio
import logging

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
    """Walk-forward backtest com candles históricos da Deriv (MTF opcional)."""
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

    logger.info(
        f"Backtest request: {len(primary)} candles | sym={symbol} | "
        f"gran={granularity}s | conf>={min_confidence} | MTF={use_mtf}"
    )

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

    return BacktestResponse(
        total_signals=result.total_signals, total_trades=result.total_trades,
        wins=result.wins, losses=result.losses, win_rate=result.win_rate,
        pnl=result.pnl, max_drawdown=result.max_drawdown,
        profit_factor=result.profit_factor, sharpe=result.sharpe,
        avg_confidence=result.avg_confidence, equity_curve=result.equity_curve,
        by_session=result.by_session, by_signal=result.by_signal,
        by_pattern=result.by_pattern, params=result.params,
    )


@router.get("/grid")
async def backtest_grid(
    symbol:        str  = Query("frxEURUSD"),
    granularity:   int  = Query(900,  ge=60,   le=86400),
    count:         int  = Query(1000, ge=200,  le=2000),
    stake:         float = Query(6.0, ge=1.0,  le=100.0),
    min_score_gap: int  = Query(2,    ge=1,    le=5),
    use_mtf:       bool = Query(True),
):
    """
    Grid search: varre score × adx × confiança e ranqueia as melhores combinações.
    Pesado — roda em thread pool. Use para descobrir os parâmetros ótimos no histórico.
    """
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

    logger.info(f"Grid request: {len(primary)} candles | sym={symbol} | MTF={use_mtf}")

    loop = asyncio.get_event_loop()
    grid = await loop.run_in_executor(
        None,
        lambda: run_grid(
            candles=primary, candles_h1=h1, candles_h4=h4, candles_usdjpy=jpy,
            stake=stake, min_score_gap=min_score_gap, use_mtf=use_mtf,
        ),
    )
    return grid
