"""'Razgon': qisqa muddatli majburiy kirish (telegramdagi ⚡ tugma).
Qoidalar: faqat DEMO; xarajat/maqsad nisbati chegaradan past bozorlardan eng kuchli impulsliga impuls tomoniga kiradi.
Boshqa bitimlar ochiq bo'lsa ham ochiladi, lekin ulardan mustaqil (alohida chipta, tur va izoh bilan)."""
import numpy as np

import bridge_broker as B
import config as C
import indicators as I
import news
import risk


def _load15(sym):
    df = B.candles(sym, "15m", 400)
    if len(df) < 120:
        return None, False
    df = df.copy()
    df["atr"] = I.atr(df)
    df["adx"] = I.adx(df)
    df["ema20"] = I.ema(df.close, 20)
    df["ema50"] = I.ema(df.close, 50)
    df["rsi"] = I.rsi(df.close)
    df["mv8"] = (df.close - df.close.shift(8)) / (df.atr * np.sqrt(8))
    df = df.dropna().iloc[:-1]  # shakllanayotgan shamni tashlaymiz
    now = B.server_now(sym)
    fresh = now is not None and (now - df.index[-1]).total_seconds() / 60 <= 30
    return df, fresh


def market_of(sym):
    for m, lst in C.XM_SYMBOLS.items():
        if sym in lst:
            return m
    return "forex"


def pick():
    """(tanlov|None, qatorlar). tanlov — eng yaxshi nomzod (dict)."""
    cands, lines = [], []
    for sym, m in B.resolve_symbols():
        df, fresh = _load15(sym)
        if df is None:
            continue
        if not fresh:
            lines.append(f"• {sym}: bozor yopiq")
            continue
        last = df.iloc[-1]
        price, atr = float(last.close), float(last.atr)
        sp = B.spread_pct(sym)
        if sp is None:
            lines.append(f"• {sym}: spread noma'lum")
            continue
        tp_dist = max(C.SCALP_TARGET_PCT * price, atr)
        cost_ratio = sp * price / tp_dist
        mv = float(last.mv8)
        if cost_ratio > C.SCALP_MAX_COST_RATIO:
            lines.append(f"• {sym}: xarajat maqsadning {cost_ratio * 100:.0f}% i (chegara {C.SCALP_MAX_COST_RATIO * 100:.0f}%) — o'tkazildi")
            continue
        side = "long" if mv > 0 else "short"
        aligned = (last.ema20 > last.ema50) == (mv > 0)
        score = abs(mv) + (0.5 if aligned else 0) + min(float(last.adx), 40) / 40 * 0.5 - cost_ratio
        lines.append(f"• {sym}: impuls {mv:+.2f}, ADX {last.adx:.0f}, xarajat {cost_ratio * 100:.0f}%, ball {score:.2f}")
        cands.append({"sym": sym, "m": m, "side": side, "price": price, "atr": atr, "tp_dist": tp_dist,
                      "sl_dist": C.SCALP_SL_MULT * tp_dist, "mv": mv, "adx": float(last.adx), "rsi": float(last.rsi),
                      "score": score, "ts": df.index[-1], "cost_ratio": cost_ratio})
    if not cands:
        return None, lines
    return max(cands, key=lambda c: c["score"]), lines


def open_scalp(j, mode="demo"):
    """(matn, fill|None). Razgon boshqa bitimlardan mustaqil: o'z chiptasi, o'z turi ('scalp'). Oddiy bitimlar va
    qo'lda ochilganlarga tegmaydi; umumiy bitim soni va jami risk limitlari saqlanadi."""
    best, lines = pick()
    if best is None:
        return "⛔ Razgon uchun mos bozor topilmadi:\n" + "\n".join(lines), None
    bal = B.balance()
    ok, why = risk.allowed(j, best["sym"], best["ts"], base_equity=bal, kind="scalp", new_risk=bal * C.SCALP_RISK)
    if not ok:
        return f"⛔ {best['sym']}: razgon ochilmadi — {why}.", None
    stop, why = news.blocked(best["sym"], int(B.server_now().timestamp()))
    if stop:
        return f"⛔ {best['sym']}: yangilik filtri — {why}. Razgon ochilmadi.", None
    try:
        fill = B.open_market(best["sym"], best["side"], bal * C.SCALP_RISK, best["sl_dist"], best["tp_dist"],
                             comment="bot-scalp")
    except B.MT5Error as e:
        return f"⚠️ {best['sym']}: kirib bo'lmadi: {e}", None
    sig = {"side": best["side"], "entry": fill["price"], "sl": fill["sl"], "tp": fill["tp"],
           "ctx": {"regime": "SCALP", "kind": "scalp", "score": round(best["score"], 2), "adx": round(best["adx"], 1),
                   "rsi": round(best["rsi"], 1), "atr_pct": 0, "atr_rank": 0, "atr": best["atr"],
                   "rsi_pullback": round(best["rsi"], 1), "move": round(best["mv"], 2)}}
    j.open_trade(best["sym"], best["m"], sig, best["ts"], fill["lots"], fill["risk"], ticket=fill["position"])
    arrow = "📈 LONG (sotib olish)" if best["side"] == "long" else "📉 SHORT (sotish)"
    text = (f"⚡ RAZGON OCHILDI [{mode}] {best['sym']}\n{arrow}\n"
            f"Lot: {fill['lots']} | Kirish: {fill['price']}\n"
            f"TP: {fill['tp']:.5g} (maqsad ~{best['tp_dist'] / best['price'] * 100:.2f}%) | SL: {fill['sl']:.5g}\n"
            f"Risk: {fill['risk']:.2f} USD ({C.SCALP_RISK * 100:.1f}% hisob) | vaqt chegarasi: {C.SCALP_HOLD_MIN // 60} soat\n"
            f"Sabab: eng kuchli impuls ({best['mv']:+.2f}), ADX {best['adx']:.0f}, xarajat maqsadning {best['cost_ratio'] * 100:.0f}% i.\n"
            f"⚠️ Majburiy kirish: tarixiy testda bunday kirishlarning o'rtacha natijasi manfiy edi (taxminan −0.05R…−0.15R). Bu tajriba.")
    try:
        import orderflow
        extra = orderflow.summary(best["sym"])
        if extra:
            text += "\n" + extra
    except Exception:
        pass
    return text, fill
