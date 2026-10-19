import numpy as np
import pandas as pd


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(df, n=14):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df, n=14):
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def add_all(df):
    """Barcha indikatorlar sababiy (kelajakni ko'rmaydi), shuning uchun
    backtestda bir marta hisoblab, keyin kesib ishlatish mumkin."""
    df = df.copy()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi"] = rsi(df["close"])
    df["atr"] = atr(df)
    df["adx"] = adx(df)
    df["atr_pct"] = df["atr"] / df["close"]
    df["atr_rank"] = df["atr_pct"].rolling(100).apply(lambda x: (x <= x[-1]).mean(), raw=True)
    df["adx_chg"] = df["adx"] - df["adx"].shift(3)

    # 4 soatlik trend: faqat TUGAGAN 4h shamlar ishlatiladi (indeks 4 soatga suriladi — kelajakni ko'rmaydi)
    h4 = df["close"].resample("4h").last().dropna()
    h4e = ema(h4, 50)
    h4echg = h4e - h4e.shift(3)
    shift = pd.Timedelta(hours=4)
    for name, s in (("htf_close", h4), ("htf_ema", h4e), ("htf_ema_chg", h4echg)):
        s = s.copy()
        s.index = s.index + shift
        df[name] = s.reindex(df.index, method="ffill")
    return df.dropna()
