"""Binance ochiq stakani va savdo oqimi (faqat kripto). MA'LUMOT UCHUN: tarixda sinab bo'lmaydi,
shuning uchun qaror qoidasi emas, tahlil xabarida ko'rsatiladi."""
import requests

BINANCE = {"BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT"}


def summary(symbol):
    s = BINANCE.get(symbol)
    if not s:
        return None
    try:
        d = requests.get("https://api.binance.com/api/v3/depth", params={"symbol": s, "limit": 50}, timeout=8).json()
        bids = sum(float(q) for _, q in d["bids"])
        asks = sum(float(q) for _, q in d["asks"])
        t = requests.get("https://api.binance.com/api/v3/trades", params={"symbol": s, "limit": 500}, timeout=8).json()
        sell_vol = sum(float(x["qty"]) for x in t if x["isBuyerMaker"])      # taker sotuvchi
        buy_vol = sum(float(x["qty"]) for x in t if not x["isBuyerMaker"])   # taker xaridor
    except Exception:
        return None
    tb, ta = bids / (bids + asks) * 100, asks / (bids + asks) * 100
    tot = buy_vol + sell_vol
    return (f"Binance stakan (50 daraja): xaridor {tb:.0f}% / sotuvchi {ta:.0f}%; "
            f"oxirgi 500 savdo: xarid {buy_vol / tot * 100:.0f}% / sotuv {sell_vol / tot * 100:.0f}% (faqat ma'lumot)")
