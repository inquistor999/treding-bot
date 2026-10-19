"""Qisqa muddatli 'razgon' tugmasi uchun tarixiy sinov (M15).
Savol: tugma bosilganda (istalgan payt) eng kuchli impulsli bozorni tanlab kirsak, kutilgan natija qancha?
Kripto: Binance klines (taker delta bilan), oltin/forex: yfinance 15m (so'nggi ~59 kun)."""
import os
import pickle
import time

import numpy as np
import pandas as pd
import requests

import indicators as I

CACHE = os.path.join(os.path.dirname(__file__), "research_cache")
# XM bo'yicha o'lchangan spread (to'liq, narx ulushi): BTC 0.048%, ETH 0.123%, oltin ~0.011%, forex ~0.02%
SPREAD = {"BTC": 0.00048, "ETH": 0.00123, "GC": 0.00011, "EURUSD": 0.0002, "GBPUSD": 0.0002, "USDJPY": 0.0002, "AUDUSD": 0.0003}
TARGET_PCT = 0.0035       # ~40 pip (EURUSD); hamma bozorda narxning shu ulushi
HOLD = 16                 # 16 ta M15 sham = 4 soat


def binance(symbol, days=365):
    end = int(time.time() * 1000)
    start = end - days * 86400000
    rows = []
    while start < end:
        r = requests.get("https://api.binance.com/api/v3/klines",
                         params=dict(symbol=symbol, interval="15m", startTime=start, limit=1000), timeout=30).json()
        if not r:
            break
        rows += r
        start = r[-1][0] + 900000
        if len(r) < 1000:
            break
    df = pd.DataFrame(rows).iloc[:, :11]
    df.columns = ["t", "open", "high", "low", "close", "volume", "ct", "qv", "n", "tbb", "tbq"]
    df = df.astype({c: float for c in ["open", "high", "low", "close", "volume", "tbb"]})
    df.index = pd.to_datetime(df["t"], unit="ms")
    df["delta"] = (2 * df["tbb"] - df["volume"]) / df["volume"].replace(0, np.nan)   # -1..+1
    return df[["open", "high", "low", "close", "volume", "delta"]]


def yf15(symbol):
    import yfinance as yf
    df = yf.download(symbol, period="59d", interval="15m", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    idx = pd.to_datetime(df.index)
    df.index = (idx.tz_convert("UTC") if idx.tz is not None else idx).tz_localize(None)
    df["delta"] = 0.0
    return df[["open", "high", "low", "close", "volume", "delta"]]


def load():
    path = os.path.join(CACHE, "scalp_raw.pkl")
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    raw = {"BTC": binance("BTCUSDT"), "ETH": binance("ETHUSDT")}
    for k, s in {"GC": "GC=F", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X"}.items():
        try:
            raw[k] = yf15(s)
        except Exception as e:
            print(k, "xato", e)
    pickle.dump(raw, open(path, "wb"))
    return raw


def prep(df):
    df = df.copy()
    df["atr"] = I.atr(df)
    df["adx"] = I.adx(df)
    for k in (4, 8):
        df[f"mv{k}"] = (df.close - df.close.shift(k)) / (df.atr * np.sqrt(k))
    df["dl8"] = df["delta"].rolling(8).mean()
    return df.dropna()


def trade(df, i, d, sl_k, spread):
    hi, lo, cl, at = df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(), df.atr.to_numpy()
    entry = cl[i]
    tp_dist = max(TARGET_PCT * entry, at[i])
    sl_dist = sl_k * tp_dist
    tp, sl = entry + d * tp_dist, entry - d * sl_dist
    end = min(i + HOLD, len(df) - 1)
    for j in range(i + 1, end + 1):
        if (d == 1 and lo[j] <= sl) or (d == -1 and hi[j] >= sl):
            return -1.0 - spread * entry / sl_dist
        if (d == 1 and hi[j] >= tp) or (d == -1 and lo[j] <= tp):
            return tp_dist / sl_dist - spread * entry / sl_dist
    return d * (cl[end] - entry) / sl_dist - spread * entry / sl_dist


def summarize(rs):
    if not rs:
        return "n=   0"
    a = np.array(rs)
    w, l = a[a > 0].sum(), -a[a <= 0].sum()
    return f"n={len(a):4d} avgR={a.mean():+.3f} PF={(w / l if l else 9.99):.2f} wr={100 * (a > 0).mean():4.1f}%"


def main():
    raw = load()
    frames = {k: prep(v) for k, v in raw.items()}
    for k, v in frames.items():
        print(f"{k}: {len(v)} sham, {v.index[0]:%Y-%m-%d} .. {v.index[-1]:%Y-%m-%d}")
    clock = frames["BTC"].index[::HOLD]
    half = clock[len(clock) // 2]
    modes = {"davom (impuls tomoniga)": 1, "teskari (impulsga qarshi)": -1}
    for sl_k in (0.6, 1.0, 1.5):
        for gated in (False, True):
            for delta_req in (False, True):
                if delta_req and not gated and False:
                    continue
                for mname, sgn in modes.items():
                    res = {"BTC/ETH": {"A": [], "B": []}, "oltin/forex": {"A": [], "B": []}}
                    for t in clock:
                        best = None
                        for k, df in frames.items():
                            if t not in df.index:
                                continue
                            i = df.index.get_loc(t)
                            mv = df["mv8"].iat[i]
                            if gated and abs(mv) < 1.5:
                                continue
                            d = int(np.sign(mv)) * sgn
                            if d == 0:
                                continue
                            if delta_req and k in ("BTC", "ETH"):
                                if np.sign(df["dl8"].iat[i]) != np.sign(mv):   # sotib olish/sotish oqimi impulsni tasdiqlasin
                                    continue
                            if best is None or abs(mv) > best[0]:
                                best = (abs(mv), k, df, i, d)
                        if best:
                            _, k, df, i, d = best
                            r = trade(df, i, d, sl_k, SPREAD[k])
                            grp = "BTC/ETH" if k in ("BTC", "ETH") else "oltin/forex"
                            res[grp]["A" if t < half else "B"].append(r)
                    tag = f"SL={sl_k}xTP {'tanlab' if gated else 'MAJBURIY'}{' +delta' if delta_req else ''}"
                    if delta_req and not gated:
                        continue
                    print(f"{tag:28s} {mname:27s} | BTC/ETH 1-yarim {summarize(res['BTC/ETH']['A'])} | 2-yarim {summarize(res['BTC/ETH']['B'])}", flush=True)
                    if res["oltin/forex"]["A"] or res["oltin/forex"]["B"]:
                        allg = res["oltin/forex"]["A"] + res["oltin/forex"]["B"]
                        print(f"{'':28s} {'':27s} | oltin/forex (59 kun) {summarize(allg)}", flush=True)


if __name__ == "__main__":
    main()
