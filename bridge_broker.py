"""MT5 bilan fayl-ko'prik orqali aloqa (BridgeEA). Parol yo'q, MetaTrader5 Python paketi kerak emas."""
import os
import time
import uuid
from types import SimpleNamespace

import pandas as pd

import config as C


class MT5Error(RuntimeError):
    pass


def _p(name):
    return os.path.join(C.BRIDGE_DIR, name)


def _read_kv(name):
    try:
        with open(_p(name), encoding="utf-8", errors="ignore") as f:
            return dict(line.strip().split("=", 1) for line in f if "=" in line)
    except OSError:
        return None


def _account():
    a = None
    for _ in range(8):  # EA fayli yangilanayotgan lahzada vaqtincha yo'q bo'lishi mumkin
        a = _read_kv("account.txt")
        if a and "gmt" in a:
            break
        time.sleep(0.25)
    if not a:
        raise MT5Error(f"EA fayllari topilmadi ({C.BRIDGE_DIR}). BridgeEA MT5 grafigida ishlayaptimi?")
    if abs(time.time() - float(a.get("gmt", "0"))) > 120:
        raise MT5Error("EA 2 daqiqadan beri yangilanmayapti: MT5 yopiq yoki robot o'chgan.")
    return a


def connect(expect_mode):
    a = _account()
    if a["mode"] != expect_mode:
        raise MT5Error(f"Rejim '{expect_mode}' so'ralgan, lekin MT5 da '{a['mode']}' hisob ochiq. To'xtadim.")
    if a.get("allowed_mode") != expect_mode:
        raise MT5Error(f"EA sozlamasida AllowedMode='{a.get('allowed_mode')}', '{expect_mode}' kerak.")
    if a.get("trading_allowed") != "1":
        raise MT5Error("EA savdo qila olmaydi: yuqoridagi Algo Trading tugmasi yoqilganmi? Hisobda savdo ruxsat etilganmi?")
    return SimpleNamespace(login=a["login"], balance=float(a["balance"]), currency=a["currency"], server=a["server"])


def balance():
    return float(_account()["balance"])


def server_now(symbol=None):
    return pd.to_datetime(int(_account()["server_time"]), unit="s")


def resolve_symbols():
    out = []
    for market, lst in C.XM_SYMBOLS.items():
        for s in lst:
            if os.path.exists(_p(f"bars_{s}.csv")):
                out.append((s, market))
            else:
                print(f"  {s}: EA shamlarni eksport qilmagan (XM da yo'q yoki EA ro'yxatida yo'q), o'tkazildi")
    return out


def all_positions_count():
    """Hisobdagi BARCHA ochiq pozitsiyalar soni (qo'lda ochilganlar ham)."""
    return int(_account().get("open_positions_all", "0"))


def candles(symbol, tf="1h", n=500):
    files = {"1h": f"bars_{symbol}.csv", "15m": f"bars15_{symbol}.csv"}
    if tf not in files:
        raise MT5Error("faqat 1h va 15m")
    try:
        df = pd.read_csv(_p(files[tf]), header=None,
                         names=["time", "open", "high", "low", "close", "volume"])
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()
    df["ts"] = pd.to_datetime(df["time"], unit="s")  # server vaqti
    return df.set_index("ts").sort_index()[["open", "high", "low", "close", "volume"]].tail(n)


def _send(cmd, timeout=25):
    cid = uuid.uuid4().hex[:12]
    body = "".join(f"{k}={v}\n" for k, v in {**cmd, "id": cid, "ts": int(time.time())}.items())
    tmp, final = _p(f"cmd_{cid}.tmp"), _p(f"cmd_{cid}.txt")
    os.makedirs(C.BRIDGE_DIR, exist_ok=True)
    with open(tmp, "w", encoding="ascii") as f:
        f.write(body)
    os.replace(tmp, final)
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = _read_kv(f"res_{cid}.txt")
        if r and "status" in r:
            try:
                os.remove(_p(f"res_{cid}.txt"))
            except OSError:
                pass
            return r
        time.sleep(0.5)
    try:
        os.remove(final)  # EA olmagan bo'lsa, keyin kutilmaganda bajarilib ketmasin
    except OSError:
        pass
    raise MT5Error(f"EA buyruqqa {timeout} s ichida javob bermadi.")


def open_market(symbol, side, risk_amount, sl_dist, tp_dist, comment="bot"):
    r = _send({"action": "open", "symbol": symbol, "side": side, "risk_amount": f"{risk_amount:.2f}",
               "sl_dist": f"{sl_dist:.10g}", "tp_dist": f"{tp_dist:.10g}", "comment": comment})
    if r["status"] != "ok":
        raise MT5Error(r.get("message", "noma'lum xato"))
    return {"position": int(r["position"]), "price": float(r["price"]), "lots": float(r["lots"]),
            "sl": float(r["sl"]), "tp": float(r["tp"]), "risk": float(r["risk"])}


def close_position(position_id):
    r = _send({"action": "close", "position": int(position_id)})
    return r["status"] == "ok"


def spread_pct(symbol):
    """To'liq spread, narxning ulushi (ask-bid)/mid. Narx yo'q bo'lsa None."""
    for r in _rows("symbols.csv"):
        if len(r) >= 3 and r[0] == symbol:
            bid, ask = float(r[1]), float(r[2])
            return (ask - bid) / ((ask + bid) / 2) if bid > 0 and ask > 0 else None
    return None


def _rows(name):
    try:
        with open(_p(name), encoding="utf-8", errors="ignore") as f:
            return [line.strip().split(",") for line in f if line.strip()]
    except OSError:
        return []


def is_open(position_id):
    return any(r and r[0] == str(position_id) for r in _rows("positions.csv"))


def closing_deal(position_id):
    """(vaqt, narx, sof_pnl, komissiya+swap, sabab) yoki None."""
    deals = [r for r in _rows("deals.csv") if len(r) >= 10 and r[0] == str(position_id)]
    outs = [r for r in deals if r[1] in ("1", "2", "3")]
    if not outs:
        return None
    pnl = sum(float(r[5]) + float(r[6]) + float(r[7]) + float(r[8]) for r in deals)
    fees = -sum(float(r[6]) + float(r[7]) + float(r[8]) for r in deals)
    d = outs[-1]
    reason = {"SL": "SL", "TP": "TP", "EXPERT": "TIME"}.get(d[9], "MANUAL")
    return pd.to_datetime(int(d[3]), unit="s"), float(d[4]), pnl, fees, reason
