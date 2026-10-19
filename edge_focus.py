"""Oltin + kripto momentum/breakout: parametr qo'shnilarida mustahkamlik tekshiruvi (real xarajat)."""
import numpy as np

import config as C
import edge_scan as E
import research

C.FEE_PCT = {"crypto": 0.0003, "forex": 0.00006, "gold": 0.00008}
MARKETS = ("crypto", "gold")


def run(frames, split, fn, sl, tp, hold, markets=MARKETS):
    res = {"train": [], "test": []}
    per = {}
    for (sym, m), df in frames.items():
        if m not in markets:
            continue
        for ts, r in E.evaluate(df, np.asarray(fn(df, m)), sl, tp, hold, C.FEE_PCT[m]):
            res["train" if ts < split else "test"].append(r)
            per.setdefault((m, "train" if ts < split else "test"), []).append(r)
    return res, per


def main():
    raw = research.load_raw()
    frames = research.prepare(raw)
    split = research.split_date(raw)
    exits = [(2.0, 4.0, 96), (2.5, 5.0, 120), (2.0, 3.0, 96)]
    cases = []
    for n in (24, 36, 48, 72):
        for thr in (1.0, 1.5, 2.0):
            cases.append((f"momo n={n} thr={thr}", lambda d, m, n=n, thr=thr: E.sig_momo(d, m, n, thr)))
    for n in (72, 96, 144):
        cases.append((f"donchian n={n}", lambda d, m, n=n: E.sig_donchian(d, m, n)))
    for name, fn in cases:
        for sl, tp, hold in exits:
            res, per = run(frames, split, fn, sl, tp, hold)
            print(f"{name:20s} SL{sl} TP{tp} h{hold:3d} | train {E.summarize(res['train'])} | test {E.summarize(res['test'])}", flush=True)
            print("    " + " ".join(f"{m}/{p}: {E.summarize(per.get((m, p), []))}" for m in MARKETS for p in ("train", "test")), flush=True)


if __name__ == "__main__":
    main()
