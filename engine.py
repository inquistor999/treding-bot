"""Bitta shamni qayta ishlash: ochiq pozitsiyani yuritish + yangi signal. Jonli va backtest uchun umumiy."""
import pandas as pd
import config as C
import regime as R
import strategy as S
import risk
import postmortem


def _manage(journal, pos, df):
    last = df.iloc[-1]
    ts = df.index[-1]
    sgn = 1 if pos["side"] == "long" else -1
    price, reason = None, None
    if (sgn == 1 and last.low <= pos["sl"]) or (sgn == -1 and last.high >= pos["sl"]):
        price, reason = pos["sl"], "SL"  # ikkalasi bir shamda bo'lsa — konservativ: SL
    elif (sgn == 1 and last.high >= pos["tp"]) or (sgn == -1 and last.low <= pos["tp"]):
        price, reason = pos["tp"], "TP"
    elif len(df) - 1 - df.index.searchsorted(pd.Timestamp(pos["entry_time"])) >= C.MAX_HOLD_BARS:
        price, reason = float(last.close), "TIME"
    if price is None:
        # Breakeven: yetarli foyda bo'lgach, SL ni kirish narxiga ko'chiramiz (keyingi shamdan kuchga kiradi)
        if C.BE_AT_R and pos["sl"] != pos["entry"]:
            r_dist = abs(pos["entry"] - pos["sl"])
            fav = (last.high - pos["entry"]) if sgn == 1 else (pos["entry"] - last.low)
            if fav >= C.BE_AT_R * r_dist:
                journal.update_sl(pos["id"], pos["entry"])
        return None
    if reason == "SL" and pos["sl"] == pos["entry"]:
        reason = "BE"

    market = pos["market"]
    fees = (pos["entry"] + price) * pos["qty"] * C.FEE_PCT[market]
    pnl = (price - pos["entry"]) * pos["qty"] * sgn - fees
    pos = dict(pos, pnl=pnl)
    text = postmortem.analyze(pos, df.iloc[df.index.searchsorted(pd.Timestamp(pos["entry_time"])):], reason)
    journal.close_trade(pos["id"], ts, price, pnl, fees, reason, text)
    return {"event": "close", "symbol": pos["symbol"], "pnl": pnl, "reason": reason, "text": text}


def on_candle(journal, symbol, market, df, allow_open=True):
    """df — indikatorli, faqat YOPILGAN shamlar. Hodisalar ro'yxatini qaytaradi."""
    events = []
    pos = journal.open_position(symbol)
    if pos:
        ev = _manage(journal, pos, df)
        if ev:
            events.append(ev)
        return events
    if not allow_open or market not in C.ENABLED_MARKETS:
        return events

    reg = R.classify(df)
    sig = S.signal(df, reg, market)
    if not sig:
        return events
    eq = journal.equity()
    qty, risk_amount = risk.position_size(eq, sig["entry"], sig["sl"], risk.risk_fraction(sig))
    if qty <= 0:
        return events
    ok, why = risk.allowed(journal, symbol, df.index[-1], base_equity=eq, kind="swing",
                           new_risk=risk_amount, grade_=risk.grade(sig))
    if not ok:
        return events
    journal.open_trade(symbol, market, sig, df.index[-1], qty, risk_amount)
    events.append({"event": "open", "symbol": symbol, "side": sig["side"], "entry": sig["entry"],
                   "sl": sig["sl"], "tp": sig["tp"], "risk": risk_amount, "ctx": sig["ctx"]})
    return events
