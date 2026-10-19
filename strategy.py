"""Trend ichida pullback tugagach, trend yo'nalishida kirish."""
import config as C


def _momentum(df, market):
    """Kuchli impuls (n soatda > THR*ATR*sqrt(n)) va EMA200 yo'nalishi mos bo'lsa, impuls tomoniga kirish."""
    n = C.MOMO_N
    if len(df) < n + 2:
        return None
    last = df.iloc[-1]
    move = (last.close - df.close.iloc[-1 - n]) / (last.atr * n ** 0.5)
    if move > C.MOMO_THR and last.close > last.ema200:
        side = "long"
    elif move < -C.MOMO_THR and last.close < last.ema200 and C.ALLOW_SHORT.get(market, False):
        side = "short"
    else:
        return None
    entry, a = float(last.close), float(last.atr)
    sgn = 1 if side == "long" else -1
    lo, hi = C.GRADE_A_VOL
    ideal = (abs(float(move)) >= C.GRADE_A_MOVE * C.MOMO_THR and float(last.adx) >= C.GRADE_A_ADX
             and lo <= float(last.atr_rank) <= hi)
    return {
        "side": side,
        "entry": entry,
        "sl": entry - sgn * C.SL_ATR * a,
        "tp": entry + sgn * C.TP_ATR * a,
        "ctx": {
            "grade": "A" if ideal else "B",
            "regime": "MOMENTUM", "score": round(abs(float(move)), 2), "adx": round(float(last.adx), 1),
            "rsi": round(float(last.rsi), 1), "atr_pct": round(float(last.atr_pct) * 100, 3),
            "atr_rank": round(float(last.atr_rank), 2), "atr": a,
            "rsi_pullback": round(float(last.rsi), 1), "move": round(float(move), 2),
        },
    }


def signal(df, reg, market):
    if C.STRATEGY == "momentum":
        return _momentum(df, market)
    if not reg["tradeable"] or len(df) < 12:
        return None
    last, prev = df.iloc[-1], df.iloc[-2]
    if C.BLOCK_HOURS and market != "crypto" and df.index[-1].hour in C.BLOCK_HOURS:
        return None
    if C.MAX_EXT_ATR and abs(last.close - last.ema20) > C.MAX_EXT_ATR * last.atr:
        return None
    window = df["rsi"].iloc[-9:-1]
    side = None
    if reg["regime"] == "TREND_UP":
        if window.min() < C.PULLBACK_RSI_LONG and prev.rsi < 50 <= last.rsi and last.close > last.ema20:
            side = "long"
    elif reg["regime"] == "TREND_DOWN" and C.ALLOW_SHORT.get(market, False):
        if window.max() > C.PULLBACK_RSI_SHORT and prev.rsi > 50 >= last.rsi and last.close < last.ema20:
            side = "short"
    if side is None:
        return None

    entry, a = float(last.close), float(last.atr)
    sgn = 1 if side == "long" else -1
    return {
        "side": side,
        "entry": entry,
        "sl": entry - sgn * C.SL_ATR * a,
        "tp": entry + sgn * C.TP_ATR * a,
        "ctx": {
            "regime": reg["regime"], "score": reg["score"], "adx": round(float(last.adx), 1),
            "rsi": round(float(last.rsi), 1), "atr_pct": round(float(last.atr_pct) * 100, 3),
            "atr_rank": round(float(last.atr_rank), 2), "atr": a,
            "rsi_pullback": round(float(window.min() if side == "long" else window.max()), 1),
        },
    }
