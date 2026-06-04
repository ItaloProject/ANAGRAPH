"""
NewsService — lê notícias e calendário econômico, usa Claude para análise de sentimento.

Fluxo:
  1. Busca calendário da semana (ForexFactory mirror — gratuito)
  2. Busca manchetes de forex via RSS (ForexLive)
  3. Envia ambos ao Claude Haiku para análise de impacto no EUR/USD
  4. Retorna sentimento, nível de risco e recomendação (OK / CAUTION / AVOID)
  5. Cache de 5 minutos para não sobrecarregar APIs
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import anthropic

logger = logging.getLogger(__name__)

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NEWS_RSS_URL  = "https://www.forexlive.com/feed/news"
CACHE_TTL_SEC = 300   # 5 min


class NewsService:
    """
    Analisa notícias e eventos macroeconômicos para filtrar operações de alto risco.
    Usa Claude Haiku (rápido e barato) para análise de sentimento contextual.
    """

    def __init__(self, api_key: str):
        self._claude  = anthropic.Anthropic(api_key=api_key)
        self._cache: Optional[dict] = None
        self._cached_at: float = 0.0
        self._lock = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_market_context(self) -> dict:
        """
        Retorna contexto de mercado com sentimento e nível de risco.
        Resultado em cache por CACHE_TTL_SEC segundos.
        """
        async with self._lock:
            if self._cache and (time.time() - self._cached_at) < CACHE_TTL_SEC:
                return self._cache

            events    = await self._fetch_calendar()
            headlines = await self._fetch_headlines()
            analysis  = await self._analyze(events, headlines)

            self._cache     = analysis
            self._cached_at = time.time()
            return analysis

    def invalidate_cache(self):
        self._cached_at = 0.0

    # ── Calendar ──────────────────────────────────────────────────────────────

    async def _fetch_calendar(self) -> list[dict]:
        now        = datetime.now(timezone.utc)
        window_end = now + timedelta(hours=4)

        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(CALENDAR_URL)
                raw  = resp.json()
        except Exception as e:
            logger.warning(f"[News] Calendar fetch failed: {e}")
            return []

        relevant: list[dict] = []
        for ev in raw:
            if ev.get("currency") not in ("EUR", "USD"):
                continue
            if ev.get("impact") not in ("High", "Medium"):
                continue
            try:
                # ForexFactory usa formato "YYYY-MM-DDTHH:MM:SS-HH:MM"
                dt_str = ev.get("date", "")
                # Normaliza timezone
                dt_str = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", dt_str)
                event_dt = datetime.fromisoformat(dt_str).astimezone(timezone.utc)
            except (ValueError, TypeError):
                continue

            if not (now - timedelta(hours=1) <= event_dt <= window_end):
                continue

            mins = int((event_dt - now).total_seconds() / 60)
            relevant.append({
                "time":        event_dt.strftime("%H:%M UTC"),
                "currency":    ev.get("currency", ""),
                "event":       ev.get("title", ""),
                "impact":      ev.get("impact", ""),
                "forecast":    ev.get("forecast", ""),
                "previous":    ev.get("previous", ""),
                "minutes_away": mins,
            })

        relevant.sort(key=lambda x: x["minutes_away"])
        return relevant[:10]

    # ── Headlines ─────────────────────────────────────────────────────────────

    async def _fetch_headlines(self) -> list[str]:
        try:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=True,
                headers={"User-Agent": "ANAGRAPH-Bot/1.0"},
            ) as client:
                resp = await client.get(NEWS_RSS_URL)
                text = resp.text

            # Extrai <title> do RSS (CDATA ou texto puro)
            titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", text, re.DOTALL)
            if not titles:
                titles = re.findall(r"<title>(.*?)</title>", text)

            # Remove o título do canal (primeiro item) e limpa HTML
            titles = titles[1:16]
            clean  = [re.sub(r"<[^>]+>", "", t).strip() for t in titles]
            return [t for t in clean if len(t) > 10][:12]

        except Exception as e:
            logger.warning(f"[News] Headlines fetch failed: {e}")
            return []

    # ── Claude analysis ───────────────────────────────────────────────────────

    async def _analyze(self, events: list[dict], headlines: list[str]) -> dict:
        default = {
            "sentiment_score": 0,
            "sentiment":       "neutral",
            "risk_level":      "low",
            "recommendation":  "OK",
            "reason":          "Sem dados de notícias disponíveis",
            "high_impact_soon": False,
            "key_factor":      "",
            "events":          events,
            "headlines_count": len(headlines),
        }

        if not events and not headlines:
            return default

        events_txt = "\n".join(
            f"- [{e['impact']}] {e['currency']} {e['event']} em {e['time']} ({e['minutes_away']}min)"
            + (f" | forecast={e['forecast']}" if e.get("forecast") else "")
            for e in events
        ) or "Nenhum evento relevante no período"

        headlines_txt = "\n".join(f"- {h}" for h in headlines) or "Sem manchetes recentes"

        prompt = f"""Você é um analista sênior de forex especializado em EUR/USD com 15 anos de experiência.
Analise os dados abaixo e determine o impacto nas próximas 1-2 horas de trading:

CALENDÁRIO ECONÔMICO (próximas 4h):
{events_txt}

MANCHETES RECENTES:
{headlines_txt}

Retorne SOMENTE um JSON válido (sem texto extra):
{{
  "sentiment_score": <inteiro -100 a +100; positivo = bullish EUR/USD>,
  "sentiment": "<bullish|bearish|neutral>",
  "risk_level": "<low|medium|high|extreme>",
  "recommendation": "<OK|CAUTION|AVOID>",
  "reason": "<frase curta em português explicando o principal fator>",
  "high_impact_soon": <true se evento de alto impacto em ≤30min>,
  "key_factor": "<principal evento ou notícia identificada>"
}}"""

        try:
            loop = asyncio.get_event_loop()
            msg  = await loop.run_in_executor(
                None,
                lambda: self._claude.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                ),
            )
            raw = msg.content[0].text.strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
                result["events"]          = events
                result["headlines_count"] = len(headlines)
                logger.info(
                    f"[News] sentiment={result.get('sentiment')} "
                    f"risk={result.get('risk_level')} "
                    f"rec={result.get('recommendation')}"
                )
                return result
        except Exception as e:
            logger.error(f"[News] Claude analysis failed: {e}")

        default["events"] = events
        return default

    # ── Score helper ──────────────────────────────────────────────────────────

    def news_score_adjustment(self, context: dict, signal: str) -> tuple[float, str]:
        """
        Retorna (confidence_multiplier, reason).
        AVOID → 0.0 (bloqueia), CAUTION → 0.7, OK → 1.0.
        Sentimento alinhado com o sinal recebe bônus.
        """
        rec   = context.get("recommendation", "OK")
        score = context.get("sentiment_score", 0)
        reason = context.get("reason", "")

        if rec == "AVOID":
            return 0.0, f"[NEWS AVOID] {reason}"

        # Multiplicador único por cenário — sem empilhamento de descontos.
        # CAUTION base + penalidade separada causava 0.88×0.80=0.68 (32% off).
        if rec == "CAUTION":
            if   signal == "BUY"  and score >  30:
                mult = 1.05   # CAUTION mas sentimento bullish — leve bônus
            elif signal == "SELL" and score < -30:
                mult = 1.05   # CAUTION mas sentimento bearish — leve bônus
            elif signal == "BUY"  and score < -30:
                mult = 0.88   # CAUTION + BUY contra EUR bearish — penalidade moderada
            elif signal == "SELL" and score >  30:
                mult = 0.88   # CAUTION + SELL contra EUR bullish — penalidade moderada
            else:
                mult = 0.95   # CAUTION neutro — penalidade mínima
        else:
            mult = 1.0

        label = f"[NEWS {rec}] {reason}" if rec != "OK" or abs(score) > 30 else ""
        return mult, label
