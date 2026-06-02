"""Monitor bot until first OPEN trade or timeout."""
import json
import time
import urllib.request
from datetime import datetime

BASE = "http://127.0.0.1:8001"
MAX_CYCLES = 36  # ~3 min


def get(path: str) -> dict:
    return json.loads(urllib.request.urlopen(BASE + path, timeout=15).read())


def post(path: str, data: dict | None = None) -> dict:
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


print("=== MONITOR Rise/Fall DEMO ===")

# garante bot ativo
try:
    start = post("/api/bot/start", {"api_token": "", "account_id": ""})
    print("start:", start)
except Exception as e:
    print("start error:", e)

for i in range(MAX_CYCLES):
    try:
        post("/api/bot/analyze-now")
    except Exception as e:
        print("analyze error:", e)

    st = get("/api/bot/status")
    sig = st.get("last_signal") or {}
    trades = st.get("trades_list") or []
    open_tr = [t for t in trades if t.get("status") == "OPEN"]

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"preco={st.get('current_price')} "
        f"sinal={sig.get('signal')} conf={sig.get('confidence')}% "
        f"sobe={sig.get('buy_score')} desce={sig.get('sell_score')} adx={sig.get('adx')} "
        f"| {(sig.get('reason') or '')[:70]}"
    )

    if open_tr:
        print("\n>>> OPERACAO ABERTA <<<")
        print(json.dumps(open_tr[0], indent=2, ensure_ascii=False))
        break

    if trades and trades[0].get("status") in ("WIN", "LOSS", "ERROR"):
        print("\n>>> TRADE REGISTRADO <<<")
        print(json.dumps(trades[0], indent=2, ensure_ascii=False))
        break

    time.sleep(5)
else:
    print("\nTimeout: modo conservador ainda aguardando confluencia forte (conf >= 78%, gap >= 2).")
