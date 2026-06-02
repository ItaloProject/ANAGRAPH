from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.analyzer import AnalyzerService

router = APIRouter()
analyzer = AnalyzerService()


class CandleIn(BaseModel):
    time:  int
    open:  float
    high:  float
    low:   float
    close: float


class AnalyzeRequest(BaseModel):
    candles: list[CandleIn]


@router.post("/analyze")
async def analyze(req: AnalyzeRequest):
    if len(req.candles) < 30:
        raise HTTPException(422, "Mínimo de 30 candles necessários")
    data = [c.model_dump() for c in req.candles]
    result = analyzer.analyze(data)
    return {
        "signal":      result.signal,
        "confidence":  result.confidence,
        "reason":      result.reason,
        "indicators": {
            "rsi":         result.rsi,
            "macd":        result.macd,
            "macd_signal": result.macd_signal,
            "bb_upper":    result.bb_upper,
            "bb_lower":    result.bb_lower,
            "bb_mid":      result.bb_mid,
            "ema9":        result.ema9,
            "ema21":       result.ema21,
        },
    }
