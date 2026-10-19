"""Strategiya tadqiqoti. Ma'lumot bir marta yuklanib keshlanadi; variantlar parallel sinaladi.
Ishlatish:
  python research.py baseline          — hozirgi strategiya + zarar tahlili
  python research.py variants          — variantlarni train/test bo'yicha solishtirish
"""
import json
import os
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import pandas as pd

import config as C

CACHE = os.path.join(os.path.dirname(__file__), "research_cache")
DAYS = 700


def symbols():
    return [(s, m) for m, lst in C.WATCHLIST.items() for s in lst]


def load_raw():
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"raw_{DAYS}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    import data
    raw = {}
    for sym, m in symbols():
        try:
            df = data.fetch(sym, m, C.TIMEFRAME, DAYS)
            if len(df) > 500:
                raw[(sym, m)] = df
                print(f"{sym}: {len(df)} sham, {df.index[0]:%Y-%m-%d} .. {df.index[-1]:%Y-%m-%d}", flush=True)
        except Exception as e:
            print(f"{sym}: xato {e}", flush=True)
    with open(path, "wb") as f:
        pickle.dump(raw, f)
    return raw


def prepare(raw):
    import indicators
    return {k: indicators.add_all(df) for k, df in raw.items()}


def simulate(frames, overrides=None, start=None, end=None):
    """Barcha simvollar birga, vaqt bo'yicha. start/end — sana oralig'i (bitimlar shu oraliqda ochiladi)."""
    import engine
    from journal import Journal
    for k, v in (overrides or {}).items():
        setattr(C, k, v)
    j = Journal(":memory:")
    frames = {k: df for k, df in frames.items() if k[1] in C.ENABLED_MARKETS}
    timeline = sorted(set().union(*[set(d.index) for d in frames.values()]))
    if start is not None:
        timeline = [t for t in timeline if t >= start]
    if end is not None:
        timeline = [t for t in timeline if t < end]
    for ts in timeline:
        for (sym, m), df in frames.items():
            i = df.index.searchsorted(ts)
            if i >= len(df) or df.index[i] != ts or i < 5:
                continue
            engine.on_candle(j, sym, m, df.iloc[: i + 1])
    return j.closed()


def stats(trades):
    if not trades:
        return dict(n=0, wr=0, net=0, pf=0, avg_r=0, mdd=0)
    pnls = [t["pnl"] for t in trades]
    w = sum(p for p in pnls if p > 0)
    l = -sum(p for p in pnls if p <= 0)
    eq = peak = C.START_EQUITY
    mdd = 0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
    rs = [t["pnl"] / t["risk_amount"] for t in trades if t["risk_amount"]]
    return dict(n=len(trades), wr=100 * sum(p > 0 for p in pnls) / len(pnls), net=sum(pnls),
                pf=(w / l if l else 9.99), avg_r=sum(rs) / len(rs), mdd=100 * mdd)


def fmt(s):
    return f"n={s['n']:4d}  wr={s['wr']:5.1f}%  PF={s['pf']:.2f}  avgR={s['avg_r']:+.2f}  net={s['net']:+8.1f}  mdd={s['mdd']:4.1f}%"


def _worker(args):
    import importlib
    name, overrides, split = args
    importlib.reload(C)  # worker qayta ishlatiladi: oldingi variant sozlamalari qolib ketmasin
    overrides = dict(overrides)
    markets = overrides.pop("_markets", None)
    frames = prepare(load_raw())
    if markets:
        frames = {k: v for k, v in frames.items() if k[1] in markets}
    res = {}
    for part, (a, b) in {"train": (None, split), "test": (split, None)}.items():
        res[part] = stats(simulate(frames, overrides, a, b))
    return name, res


def split_date(raw):
    lo = min(df.index[0] for df in raw.values())
    hi = max(df.index[-1] for df in raw.values())
    return lo + (hi - lo) * 0.6


def cmd_baseline():
    raw = load_raw()
    frames = prepare(raw)
    split = split_date(raw)
    print("Bo'linish sanasi (train | test):", split)
    trades = simulate(frames)
    print("\nUMUMIY ", fmt(stats(trades)))
    for m in ("crypto", "forex", "gold"):
        print(f"{m:7s}", fmt(stats([t for t in trades if t["market"] == m])))

    df = pd.DataFrame(trades)
    ctx = df["ctx"].apply(json.loads).apply(pd.Series)
    df = pd.concat([df.drop(columns=["ctx"]), ctx], axis=1)
    df["win"] = df["pnl"] > 0
    df["hour"] = pd.to_datetime(df["entry_time"]).dt.hour
    df["R"] = df["pnl"] / df["risk_amount"]

    def table(col, bins=None, labels=None):
        key = pd.cut(df[col], bins, labels=labels) if bins is not None else df[col]
        t = df.groupby(key, observed=True).agg(n=("win", "size"), wr=("win", "mean"), avgR=("R", "mean"))
        t["wr"] = (t["wr"] * 100).round(1)
        t["avgR"] = t["avgR"].round(2)
        print(f"\n-- {col}")
        print(t.to_string())

    table("adx", [0, 25, 30, 35, 45, 100])
    table("atr_rank", [0, 0.35, 0.5, 0.65, 0.75, 1.0])
    table("rsi_pullback", [0, 30, 35, 40, 45, 50, 55, 60, 70, 100])
    table("hour", [-1, 3, 7, 11, 15, 19, 23])
    table("side")
    table("exit_reason")
    df.to_csv(os.path.join(CACHE, "baseline_trades.csv"), index=False)


VARIANTS = {
    "baza": {},
}


def cmd_variants():
    raw = load_raw()
    split = split_date(raw)
    try:
        extra = json.load(open(os.path.join(CACHE, "variants.json")))
    except OSError:
        extra = {}
    allv = {**VARIANTS, **extra}
    print("Bo'linish:", split)
    with ProcessPoolExecutor(max_workers=min(10, len(allv))) as ex:
        results = dict(ex.map(_worker, [(n, o, split) for n, o in allv.items()]))
    for n in allv:
        r = results[n]
        print(f"\n{n}  {allv[n]}")
        print("  train", fmt(r["train"]))
        print("  test ", fmt(r["test"]))


if __name__ == "__main__":
    {"baseline": cmd_baseline, "variants": cmd_variants}[sys.argv[1]]()
