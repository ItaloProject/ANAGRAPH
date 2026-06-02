from fastapi import APIRouter
from app.services.deriv_client import DerivClient

router = APIRouter()


@router.get("/candles")
async def get_candles(symbol: str = "frxEURUSD", granularity: int = 60, count: int = 200):
    client = DerivClient()
    try:
        await client.connect()
        candles = await client.get_candles(symbol, granularity, count)
        return {"candles": candles, "symbol": symbol}
    finally:
        await client.disconnect()
