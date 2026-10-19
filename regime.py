"""Bozor holati skaneri: bozor savdoga tayyormi yoki yo'qmi."""
import config as C


def classify(df):
    r = df.iloc[-1]
    up = r.ema20 > r.ema50 > r.ema200
    down = r.ema20 < r.ema50 < r.ema200
    trending = r.adx >= C.MIN_ADX
    healthy_vol = C.ATR_RANK_MIN <= r.atr_rank <= C.ATR_RANK_MAX

    if up and trending:
        regime = "TREND_UP"
    elif down and trending:
        regime = "TREND_DOWN"
    elif r.adx < 18:
        regime = "RANGE"
    else:
        regime = "MIXED"

    score = min(r.adx, 40) / 40 * 50 + (25 if (up or down) else 0) + (25 if healthy_vol else 0)
    tradeable = regime in ("TREND_UP", "TREND_DOWN") and healthy_vol
    extra_block = ""
    if tradeable and C.REQUIRE_ADX_RISING and not r.adx_chg > 0:
        tradeable, extra_block = False, "ADX pasayyapti (trend so'nmoqda)"
    if tradeable and C.HTF_FILTER:
        up_ok = r.htf_close > r.htf_ema and r.htf_ema_chg > 0
        dn_ok = r.htf_close < r.htf_ema and r.htf_ema_chg < 0
        if (regime == "TREND_UP" and not up_ok) or (regime == "TREND_DOWN" and not dn_ok):
            tradeable, extra_block = False, "4 soatlik trend mos emas"

    if extra_block:
        reason = extra_block
    elif tradeable:
        reason = "trend aniq, tebranish me'yorida"
    elif regime in ("RANGE", "MIXED"):
        reason = f"trend yo'q (ADX {r.adx:.0f}), kutamiz"
    elif r.atr_rank > C.ATR_RANK_MAX:
        reason = "tebranish juda yuqori, xavfli"
    else:
        reason = "bozor juda sust"
    return {"regime": regime, "score": round(float(score), 1), "tradeable": bool(tradeable), "reason": reason}
