"""Nomzod momentum strategiyasi diagnostikasi: long/short, simvol va chorak bo'yicha barqarorlik."""
import numpy as np
import pandas as pd

import config as C
import edge_scan as E
import research

C.FEE_PCT = {"crypto": 0.0003, "forex": 0.00006, "gold": 0.00008}
CANDS = [(36, 1.0, 2.0, 4.0, 96), (48, 1.0, 2.0, 4.0, 96), (24, 1.5, 2.0, 4.0, 96)]


def main():
    raw = research.load_raw()
    frames = {k: v for k, v in research.prepare(raw).items() if k[1] in ("crypto", "gold")}
    split = research.split_date(raw)
    for n, thr, sl, tp, hold in CANDS:
        print(f"\n=== momo n={n} thr={thr} SL{sl} TP{tp} h{hold} ===")
        rows = []
        for (sym, m), df in frames.items():
            side = np.asarray(E.sig_momo(df, m, n, thr))
            for label, s in (("long", np.where(side > 0, 1, 0)), ("short", np.where(side < 0, -1, 0))):
                for ts, r in E.evaluate(df, s, sl, tp, hold, C.FEE_PCT[m]):
                    rows.append((sym, m, label, ts, r))
        d = pd.DataFrame(rows, columns=["sym", "market", "side", "ts", "R"])
        d["part"] = np.where(d.ts < split, "train", "test")
        g = d.groupby(["side", "part"]).R.agg(["count", "mean"]).round(3)
        print(g.to_string())
        print("\nsimvol bo'yicha (butun davr):")
        print(d.groupby("sym").R.agg(["count", "mean"]).round(3).T.to_string())
        d["q"] = d.ts.dt.to_period("Q")
        q = d.groupby("q").R.agg(["count", "sum", "mean"]).round(2)
        print("\nchorak bo'yicha (jami R):")
        print(q.T.to_string())
        print(f"musbat choraklar: {(q['sum'] > 0).sum()} / {len(q)}")


if __name__ == "__main__":
    main()
