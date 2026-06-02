import os

# Cotação USD → BRL (atualize no .env ou reinicie após mudança)
DEFAULT_USD_BRL_RATE = float(os.getenv("USD_BRL_RATE", "5.85"))
DISPLAY_CURRENCY = "BRL"


def usd_brl_rate() -> float:
    rate = float(os.getenv("USD_BRL_RATE", str(DEFAULT_USD_BRL_RATE)))
    return rate if rate > 0 else DEFAULT_USD_BRL_RATE


def brl_to_usd(amount_brl: float) -> float:
    return round(amount_brl / usd_brl_rate(), 4)


def usd_to_brl(amount_usd: float) -> float:
    return round(amount_usd * usd_brl_rate(), 2)


def currency_config() -> dict:
    return {
        "display_currency": DISPLAY_CURRENCY,
        "account_currency": "USD",
        "usd_brl_rate":     usd_brl_rate(),
        "note": (
            "A conta DERIV opera em USD; limites e telas usam BRL "
            "com conversão automática."
        ),
    }
