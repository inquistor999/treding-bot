"""Tezkor 'edge skaner': turli strategiya oilalarini ATR-stop/TP bilan bir xil sharoitda solishtiradi.
Natija: o'rtacha R (komissiya ayirilgan), PF, bitimlar soni — train va test bo'yicha alohida.
Portfel limitlari hisobga olinmaydi (maqsad — signalda ustunlik bor-yo'qligini topish)."""
import sys

import numpy as np
import pandas as pd

import config as C
import research

SPLIT = None


def evaluate(df, side, sl_atr, tp_atr, hold, fee):
    """side: +1/-1/0 massiv. Kirish — signal shami yopilishida. Bir vaqtda bitta pozitsiya. [(vaqt, R_net)]"""
    hi, lo, cl, at = (df[c].to_numpy() for c in ("high", "low", "close", "atr"))
    idx = df.index
    out, busy = [], -1
    for i in np.flatnonzero(side != 0):
        if i <= busy or i + 1 >= len(df):
            continue
        s = side[i]
        entry, risk = cl[i], sl_atr * at[i]
        sl, tp = entry - s * risk, entry + s * tp_atr * at[i]
        R, end = None, min(i + hold, len(df) - 1)
        busy = end
        for j in range(i + 1, end + 1):
            if (s == 1 and lo[j] <= sl) or (s == -1 and hi[j] >= sl):
                R, busy = -1.0, j
                break
            if (s == 1 and hi[j] >= tp) or (s == -1 and lo[j] <= tp):
                R, busy = tp_atr / sl_atr, j
                break
        if R is None:
            R = s * (cl[end] - entry) / risk
        cost = 2 * fee * entry / risk
        out.append((idx[i], R - cost))
    return out


# ---------------- signal oilalari ----------------
def sig_baseline(df, market, fade=False):
    up = (df.ema20 > df.ema50) & (df.ema50 > df.ema200) & (df.adx >= C.MIN_ADX)
    dn = (df.ema20 < df.ema50) & (df.ema50 < df.ema200) & (df.adx >= C.MIN_ADX)
    rmin = df.rsi.shift(1).rolling(8).min()
    rmax = df.rsi.shift(1).rolling(8).max()
    long_ = up & (rmin < 45) & (df.rsi.shift(1) < 50) & (df.rsi >= 50) & (df.close > df.ema20)
    short_ = dn & (rmax > 55) & (df.rsi.shift(1) > 50) & (df.rsi <= 50) & (df.close < df.ema20)
    s = np.where(long_, 1, 0) + np.where(short_, -1, 0)
    return -s if fade else s


def sig_donchian(df, market, n=48, adx_min=20):
    hh = df.high.shift(1).rolling(n).max()
    ll = df.low.shift(1).rolling(n).min()
    long_ = (df.close > hh) & (df.close > df.ema200) & (df.adx >= adx_min)
    short_ = (df.close < ll) & (df.close < df.ema200) & (df.adx >= adx_min)
    return np.where(long_, 1, 0) + np.where(short_, -1, 0)


def sig_meanrev(df, market, lo_rsi=25, hi_rsi=75, adx_max=22):
    mid = df.close.rolling(20).mean()
    sd = df.close.rolling(20).std()
    long_ = (df.close < mid - 2 * sd) & (df.rsi < lo_rsi) & (df.adx < adx_max)
    short_ = (df.close > mid + 2 * sd) & (df.rsi > hi_rsi) & (df.adx < adx_max)
    return np.where(long_, 1, 0) + np.where(short_, -1, 0)


def sig_session(df, market, start=0, end=7, trade_to=11):
    """Osiyo sessiyasi diapazoni (UTC start..end) London/NY da buzilsa, buzilish tomoniga kirish."""
    if market == "crypto":
        return np.zeros(len(df), dtype=int)
    d = df.copy()
    d["date"] = d.index.date
    d["h"] = d.index.hour
    asia = d[(d.h >= start) & (d.h < end)].groupby("date").agg(ah=("high", "max"), al=("low", "min"))
    d = d.join(asia, on="date")
    live = (d.h >= end) & (d.h < trade_to)
    # kunning birinchi buzilishi
    long_ = live & (d.close > d.ah)
    short_ = live & (d.close < d.al)
    first_l = long_ & ~long_.groupby(d.date).cumsum().shift(1).fillna(0).astype(bool)
    first_s = short_ & ~short_.groupby(d.date).cumsum().shift(1).fillna(0).astype(bool)
    return np.where(first_l, 1, 0) + np.where(first_s, -1, 0)


def sig_momo(df, market, n=24, thr=1.5):
    """Kuchli impuls: n shamda >thr*ATR*sqrt(n) harakat va trend yo'nalishi bilan mos."""
    move = (df.close - df.close.shift(n)) / (df.atr * np.sqrt(n))
    long_ = (move > thr) & (df.close > df.ema200)
    short_ = (move < -thr) & (df.close < df.ema200)
    return np.where(long_, 1, 0) + np.where(short_, -1, 0)


FAMILIES = {
    "baza": lambda d, m: sig_baseline(d, m),
    "baza TESKARISI": lambda d, m: sig_baseline(d, m, fade=True),
    "donchian48": lambda d, m: sig_donchian(d, m, 48),
    "donchian96": lambda d, m: sig_donchian(d, m, 96),
    "meanrev": lambda d, m: sig_meanrev(d, m),
    "session-breakout": lambda d, m: sig_session(d, m),
    "momo24": lambda d, m: sig_momo(d, m, 24, 1.5),
    "momo48": lambda d, m: sig_momo(d, m, 48, 1.5),
}
EXITS = [(1.5, 2.5, 48), (2.0, 4.0, 96), (1.5, 1.5, 48)]


def summarize(rs):
    if not rs:
        return "n=   0"
    a = np.array(rs)
    w, l = a[a > 0].sum(), -a[a <= 0].sum()
    return f"n={len(a):4d} avgR={a.mean():+.3f} PF={(w / l if l else 9.99):.2f} wr={100 * (a > 0).mean():4.1f}%"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--real" in sys.argv:  # XM CFD spreadiga yaqinroq (bir tomonga): taxminiy, EA orqali tasdiqlanishi kerak
        C.FEE_PCT = {"crypto": 0.0003, "forex": 0.00006, "gold": 0.00008}
        print("xarajat (bir tomonga):", C.FEE_PCT)
    raw = research.load_raw()
    frames = research.prepare(raw)
    split = research.split_date(raw)
    print("split:", split)
    fam = args or list(FAMILIES)
    for name in fam:
        fn = FAMILIES[name]
        for sl, tp, hold in EXITS:
            tr, te, per = [], [], {}
            for (sym, m), df in frames.items():
                side = np.asarray(fn(df, m))
                res = evaluate(df, side, sl, tp, hold, C.FEE_PCT[m])
                for ts, r in res:
                    (tr if ts < split else te).append(r)
                    per.setdefault(m, []).append(r)
            print(f"{name:18s} SL{sl} TP{tp} h{hold:3d} | train {summarize(tr)} | test {summarize(te)}")
            print("   " + "  ".join(f"{m}: {summarize(v)}" for m, v in per.items()), flush=True)


if __name__ == "__main__":
    main()
