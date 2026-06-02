import json
import time
import urllib.request

BASE = "http://127.0.0.1:8001"


def req(method: str, path: str, data: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


print("=== START + MONITOR ===")
print("health before:", req("GET", "/api/health").get("bot_running"))
print("start:", req("POST", "/api/bot/start", {"api_token": "", "account_id": ""}))

for i in range(18):
    time.sleep(10)
    if i % 3 == 0:
        try:
            req("POST", "/api/bot/analyze-now")
        except Exception as e:
            print("analyze err:", e)

    h = req("GET", "/api/health")
    s = req("GET", "/api/bot/status")
    sig = s.get("last_signal") or {}
    trades = s.get("trades_list") or []

    print(
        f"t+{(i+1)*10}s running={s.get('running')} health={h.get('bot_running')} "
        f"price={s.get('current_price')} signal={sig.get('signal')} conf={sig.get('confidence')} "
        f"buy={sig.get('buy_score')} sell={sig.get('sell_score')} trades={len(trades)}"
    )
    if sig.get("reason"):
        print(" ", sig["reason"][:90])

    open_tr = [t for t in trades if t.get("status") == "OPEN"]
    if open_tr:
        print("\n>>> OPERACAO ABERTA <<<")
        print(json.dumps(open_tr[0], indent=2, ensure_ascii=False))
        break
    if trades and trades[0].get("status") in ("WIN", "LOSS", "ERROR"):
        print("\n>>> TRADE <<<")
        print(json.dumps(trades[0], indent=2, ensure_ascii=False))
        break
    if not s.get("running") and i > 0:
        print("Bot parou inesperadamente.")
        break
else:
    print("\nNenhuma operacao aberta ainda — modo conservador aguardando confluencia >=78%.")
