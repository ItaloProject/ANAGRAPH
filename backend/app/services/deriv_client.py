import asyncio
import json
import logging
import os
from typing import Callable, Optional

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

REST_BASE = "https://api.derivws.com"
WS_PUBLIC = "wss://api.derivws.com/trading/v1/options/ws/public"
APP_ID    = os.getenv("DERIV_APP_ID", "33qwHdRH3vY9cCAeAzIa7")


class DerivClient:
    WS_PUBLIC = WS_PUBLIC   # expõe a constante para reconexão externa
    """
    DERIV REST + WebSocket API client.
    Uses api.derivws.com (new Deriv platform):
      - Public WS for market data (ticks, candles)
      - Authenticated WS (via OTP) for trading
    """

    def __init__(
        self,
        app_id:     str = APP_ID,
        api_token:  str = "",
        account_id: str = "",
    ):
        self.app_id     = app_id
        self.api_token  = api_token
        self.account_id = account_id

        self._trade_ws        = None
        self._public_ws       = None
        self._req_id          = 0
        self._pending:       dict[int, asyncio.Future] = {}
        self._tick_cbs:      list[Callable] = []
        self._contract_cbs:  dict[int, list[Callable]] = {}
        self._recv_task:     Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None
        self._active_tick_symbol: Optional[str] = None
        self.authorized = False

    async def connect(self):
        if self.api_token and self.account_id:
            ws_url = await self._get_ws_url_via_otp()
            self._trade_ws = await websockets.connect(
                ws_url, ping_interval=20, ping_timeout=10
            )
            self.authorized = True
            logger.info(f"Connected authenticated WS for account {self.account_id}")
        else:
            logger.warning("No token/account_id — using public WS only")

        self._public_ws = await websockets.connect(WS_PUBLIC, ping_interval=30)
        logger.info("Connected public WS for market data")

        self._recv_task      = asyncio.create_task(self._recv_loop())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _get_ws_url_via_otp(self, max_retries: int = 3) -> str:
        url = f"{REST_BASE}/trading/v1/options/accounts/{self.account_id}/otp"
        headers = {
            "Deriv-App-ID":  self.app_id,
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type":  "application/json",
        }
        last_err: Exception = RuntimeError("OTP: sem tentativas")
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, headers=headers)
                if resp.status_code != 200:
                    raise ValueError(
                        f"OTP request failed ({resp.status_code}): {resp.text}"
                    )
                data   = resp.json()
                ws_url = data["data"]["url"]
                logger.info(f"Got authenticated WS URL: {ws_url[:60]}...")
                return ws_url
            except Exception as e:
                last_err = e
                logger.warning(f"OTP attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(5 * attempt)   # backoff: 5s, 10s
        raise last_err

    async def disconnect(self):
        if self._keepalive_task:
            self._keepalive_task.cancel()
        if self._recv_task:
            self._recv_task.cancel()
        if self._trade_ws:
            await self._trade_ws.close()
        if self._public_ws:
            await self._public_ws.close()
        logger.info("Disconnected from DERIV API")

    async def get_candles(
        self,
        symbol:      str = "frxEURUSD",
        granularity: int = 60,
        count:       int = 200,
    ) -> list[dict]:
        resp = await self._request_public({
            "ticks_history": symbol,
            "style":         "candles",
            "granularity":   granularity,
            "count":         count,
            "end":           "latest",
        })
        if resp.get("error"):
            raise RuntimeError(f"get_candles error: {resp['error']['message']}")
        return [
            {
                "time":  c["epoch"],
                "open":  float(c["open"]),
                "high":  float(c["high"]),
                "low":   float(c["low"]),
                "close": float(c["close"]),
            }
            for c in resp.get("candles", [])
        ]

    async def subscribe_ticks(self, symbol: str, callback: Callable):
        self._tick_cbs.append(callback)
        self._active_tick_symbol = symbol
        await self._send_public({
            "ticks":     symbol,
            "subscribe": 1,
            "req_id":    self._next_id(),
        })

    async def unsubscribe_ticks(self):
        """Cancela todas as inscrições de ticks (usado ao trocar de ativo)."""
        try:
            await self._send_public({"forget_all": "ticks"})
        except Exception as e:
            logger.warning(f"unsubscribe_ticks: {e}")
        self._tick_cbs.clear()
        self._active_tick_symbol = None

    async def get_proposal(
        self,
        symbol:        str,
        contract_type: str,
        stake:         float,
        duration:      int = 5,
        duration_unit: str = "m",
        currency:      str = "USD",
    ) -> dict:
        """Rise/Fall proposal: CALL = Rise, PUT = Fall."""
        ws = self._trade_ws or self._public_ws
        payload = {
            "proposal":          1,
            "amount":            round(stake, 2),
            "basis":             "stake",
            "contract_type":     contract_type,
            "currency":          currency,
            "duration":          duration,
            "duration_unit":     duration_unit,
            "underlying_symbol": symbol,
        }
        resp = await self._request_ws(ws, payload)
        if resp.get("error"):
            err = resp["error"]
            logger.error(
                f"Proposal ERRO | code={err.get('code','?')} | "
                f"msg={err.get('message')} | payload={payload}"
            )
            raise RuntimeError(
                f"proposal error [{err.get('code','?')}]: {err.get('message')}"
            )
        return resp["proposal"]

    async def buy_contract(self, proposal_id: str, price: float) -> dict:
        ws = self._trade_ws or self._public_ws
        resp = await self._request_ws(ws, {
            "buy":   proposal_id,
            "price": price,
        })
        if resp.get("error"):
            raise RuntimeError(f"buy error: {resp['error']['message']}")
        return resp["buy"]

    async def get_balance(self) -> float:
        info = await self.get_account_info()
        return info["balance"]

    async def get_account_info(self) -> dict:
        ws = self._trade_ws
        if not ws:
            return {"balance": 0.0, "currency": "USD", "loginid": "", "is_demo": True, "open_contracts": 0}

        auth = await self._request_ws(ws, {"authorize": self.api_token})
        if auth.get("error"):
            raise RuntimeError(auth["error"]["message"])

        a = auth.get("authorize", {})
        port = await self._request_ws(ws, {"portfolio": 1})
        contracts = (
            port.get("portfolio", {}).get("contracts", [])
            if not port.get("error") else []
        )
        return {
            "loginid":        a.get("loginid", self.account_id),
            "balance":        float(a.get("balance") or 0),
            "currency":       a.get("currency", "USD"),
            "is_demo":        bool(a.get("is_virtual")),
            "open_contracts": len(contracts),
        }

    async def get_open_contract(self, contract_id: int) -> dict:
        ws = self._trade_ws or self._public_ws
        resp = await self._request_ws(ws, {
            "proposal_open_contract": 1,
            "contract_id":            contract_id,
        })
        if resp.get("error"):
            raise RuntimeError(resp["error"]["message"])
        return resp["proposal_open_contract"]

    async def get_profit_table(self, limit: int = 50, offset: int = 0) -> list[dict]:
        ws = self._trade_ws or self._public_ws
        resp = await self._request_ws(ws, {
            "profit_table": 1,
            "description":  1,
            "sort":         "DESC",
            "limit":        limit,
            "offset":       offset,
        })
        if resp.get("error"):
            raise RuntimeError(resp["error"]["message"])
        return resp.get("profit_table", {}).get("transactions", [])

    async def subscribe_contract(self, contract_id: int, callback: Callable):
        self._contract_cbs.setdefault(contract_id, []).append(callback)
        ws = self._trade_ws or self._public_ws
        await self._send_ws(ws, {
            "proposal_open_contract": 1,
            "contract_id":            contract_id,
            "subscribe":              1,
            "req_id":                 self._next_id(),
        })

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def _request_public(self, payload: dict) -> dict:
        return await self._request_ws(self._public_ws, payload)

    async def _request_ws(self, ws, payload: dict) -> dict:
        req_id = self._next_id()
        payload["req_id"] = req_id
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        await ws.send(json.dumps(payload))
        return await asyncio.wait_for(fut, timeout=20.0)

    async def _send_public(self, payload: dict):
        await self._public_ws.send(json.dumps(payload))

    async def _send_ws(self, ws, payload: dict):
        await ws.send(json.dumps(payload))

    async def _keepalive_loop(self):
        while True:
            await asyncio.sleep(20)
            for ws in [self._trade_ws, self._public_ws]:
                if ws is None:
                    continue
                try:
                    if getattr(ws, "open", None) is False:
                        continue
                    await ws.send(json.dumps({"ping": 1}))
                except Exception:
                    pass

    async def _recv_loop(self):
        tasks = []
        if self._public_ws:
            tasks.append(asyncio.create_task(self._recv_from(self._public_ws)))
        if self._trade_ws:
            tasks.append(asyncio.create_task(self._recv_from(self._trade_ws)))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _recv_from(self, ws):
        try:
            async for raw in ws:
                msg = json.loads(raw)
                req_id = msg.get("req_id")

                if req_id and req_id in self._pending:
                    fut = self._pending.pop(req_id)
                    if not fut.done():
                        fut.set_result(msg)
                    continue

                if "tick" in msg:
                    tick = msg["tick"]
                    # Filtro defensivo: ignora ticks de símbolo diferente do ativo
                    # (evita corromper candles durante troca de ativo por sessão)
                    sym = tick.get("symbol")
                    if self._active_tick_symbol and sym and sym != self._active_tick_symbol:
                        continue
                    for cb in self._tick_cbs:
                        asyncio.create_task(cb(float(tick["quote"]), tick["epoch"]))
                    continue

                if "proposal_open_contract" in msg:
                    poc = msg["proposal_open_contract"]
                    cid = poc.get("contract_id")
                    status = poc.get("status")
                    logger.info(f"Contract update: {cid} → {status}")
                    for cb in self._contract_cbs.get(cid, []):
                        asyncio.create_task(cb(poc))

        except ConnectionClosed as e:
            logger.warning(f"WebSocket closed: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"recv_from error: {e}")
