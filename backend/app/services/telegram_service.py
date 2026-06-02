"""
TelegramService — notificações em tempo real via Telegram Bot API.

Envia mensagem quando:
  - Trade aberto  (sinal, confiança, direção, stake)
  - Trade fechado (WIN/LOSS, P&L)
  - Auto-stop por limite diário ou streak
  - Evento econômico de alto impacto detectado

Configuração: defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env do servidor.
Para obter o chat_id: envie qualquer msg ao bot e acesse
  https://api.telegram.org/bot<TOKEN>/getUpdates
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, token: str, chat_id: str):
        self._token   = token
        self._chat_id = chat_id
        self._base    = f"https://api.telegram.org/bot{token}"

    # ── Core ──────────────────────────────────────────────────────────────────

    async def send(self, text: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._base}/sendMessage",
                    json={
                        "chat_id":    self._chat_id,
                        "text":       text,
                        "parse_mode": "HTML",
                    },
                )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[Telegram] Falha ao enviar: {e}")
            return False

    # ── Eventos ───────────────────────────────────────────────────────────────

    async def notify_trade_opened(
        self,
        signal: str,
        asset: str,
        stake_usd: float,
        confidence: float,
        reason: str,
        brl_rate: float = 5.85,
    ):
        direction = "📈 <b>COMPRA (RISE)</b>" if signal == "BUY" else "📉 <b>VENDA (FALL)</b>"
        stake_brl = stake_usd * brl_rate
        short_reason = reason[:180] + "…" if len(reason) > 180 else reason
        msg = (
            f"🤖 <b>ANAGRAPH — TRADE ABERTO</b>\n"
            f"{direction}\n"
            f"💰 Stake: R$ {stake_brl:.2f} (${stake_usd:.2f})\n"
            f"🎯 Confiança: {confidence:.1f}%\n"
            f"📊 {short_reason}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_trade_closed(
        self,
        signal: str,
        status: str,
        pnl_usd: float,
        brl_rate: float = 5.85,
    ):
        won     = status == "WIN"
        emoji   = "✅" if won else "❌"
        label   = "GANHOU" if won else "PERDEU"
        pnl_brl = pnl_usd * brl_rate
        sign    = "+" if pnl_usd >= 0 else ""
        direction = "RISE" if signal == "BUY" else "FALL"
        msg = (
            f"{emoji} <b>ANAGRAPH — {label}</b>\n"
            f"Direção: {direction}\n"
            f"P&amp;L: {sign}R$ {pnl_brl:.2f} ({sign}${pnl_usd:.2f})\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_auto_stop(self, reason: str):
        msg = (
            f"🛑 <b>ANAGRAPH — ROBÔ PARADO AUTOMATICAMENTE</b>\n"
            f"{reason}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_news_block(self, event: str, impact: str, minutes: int):
        msg = (
            f"📰 <b>ANAGRAPH — EVENTO ECONÔMICO</b>\n"
            f"⚠️ [{impact}] {event}\n"
            f"⏱ Em {minutes} minuto(s) — operações bloqueadas\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_daily_summary(
        self,
        wins: int,
        losses: int,
        pnl_usd: float,
        brl_rate: float = 5.85,
    ):
        total   = wins + losses or 1
        wr      = wins / total * 100
        pnl_brl = pnl_usd * brl_rate
        sign    = "+" if pnl_usd >= 0 else ""
        emoji   = "🟢" if pnl_usd >= 0 else "🔴"
        msg = (
            f"{emoji} <b>ANAGRAPH — RESUMO DO DIA</b>\n"
            f"W/L: {wins}W / {losses}L ({wr:.1f}% acerto)\n"
            f"P&amp;L: {sign}R$ {pnl_brl:.2f} ({sign}${pnl_usd:.2f})\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)
