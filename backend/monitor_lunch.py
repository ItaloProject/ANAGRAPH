"""Monitor ANAGRAPH bot — avisa quando abrir/fechar trade Rise/Fall."""
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

BASE = "http://127.0.0.1:8001"
POLL_SEC = 20
MAX_MINUTES = 120


def req(method: str, path: str, data: dict | None = None) -> dict | None:
    try:
        body = json.dumps(data).encode() if data is not None else None
        headers = {"Content-Type": "application/json"} if body else {}
        r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
        return json.loads(urllib.request.urlopen(r, timeout=30).read())
    except Exception as e:
        print(f"[{ts()}] ERRO API {path}: {e}", flush=True)
        return None


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def ensure_bot_running() -> bool:
    st = req("GET", "/api/bot/status")
    if st and st.get("running"):
        return True
    print(f"[{ts()}] Bot parado — reiniciando...", flush=True)
    r = req("POST", "/api/bot/start", {"api_token": "", "account_id": ""})
    print(f"[{ts()}] start: {r}", flush=True)
    time.sleep(8)
    st = req("GET", "/api/bot/status")
    return bool(st and st.get("running"))


def main():
    print(f"=== MONITOR ALMOCO — ate {MAX_MINUTES} min ===", flush=True)
    print(f"[{ts()}] Aguardando primeira operacao Rise/Fall (conf >=78%)...", flush=True)

    seen_ids: set[str] = set()
    cycles = (MAX_MINUTES * 60) // POLL_SEC

    for n in range(cycles):
        if not ensure_bot_running():
            time.sleep(POLL_SEC)
            continue

        st = req("GET", "/api/bot/status") or {}
        sig = st.get("last_signal") or {}
        trades = st.get("trades_list") or []

        # nova operacao aberta
        for t in trades:
            tid = t.get("id", "")
            if t.get("status") == "OPEN" and tid not in seen_ids:
                seen_ids.add(tid)
                direction = "SOBE" if t.get("signal") == "BUY" else "DESCE"
                msg = (
                    f"\n*** OPERACAO ABERTA ***\n"
                    f"Direcao: {direction} | Stake: ${t.get('stake')} | "
                    f"Conf: {t.get('confidence')}% | Duracao: {t.get('duration')}\n"
                    f"Entrada: {t.get('entry_price')} | Motivo: {t.get('reason', '')[:120]}\n"
                    f"Contrato: {json.dumps(t, ensure_ascii=False)}\n"
                )
                print(msg, flush=True)
                print("TRADE_OPEN", flush=True)

        # trade fechado
        for t in trades:
            tid = t.get("id", "")
            key = f"{tid}-{t.get('status')}"
            if t.get("status") in ("WIN", "LOSS", "ERROR") and key not in seen_ids:
                seen_ids.add(key)
                result = t.get("status")
                pnl = t.get("pnl", 0)
                msg = (
                    f"\n*** OPERACAO FECHADA: {result} ***\n"
                    f"P&L: ${pnl:+.2f} | {t.get('contract_type')} {t.get('duration')}\n"
                )
                print(msg, flush=True)
                print(f"TRADE_{result}", flush=True)

        if n % 9 == 0:  # ~3 min heartbeat
            print(
                f"[{ts()}] heartbeat | preco={st.get('current_price')} "
                f"sinal={sig.get('signal')} conf={sig.get('confidence')}% "
                f"sobe={sig.get('buy_score')} desce={sig.get('sell_score')} "
                f"trades={len(trades)} abertas={sum(1 for x in trades if x.get('status')=='OPEN')}",
                flush=True,
            )

        time.sleep(POLL_SEC)

    print(f"[{ts()}] Monitor encerrado apos {MAX_MINUTES} min.", flush=True)


if __name__ == "__main__":
    main()
