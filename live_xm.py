"""XM (MT5) jonli savdo. Demo yoki real. SL/TP serverda turadi — bot o'chib qolsa ham himoya saqlanadi.
Funksiyalar telegram bot tomonidan ham ishlatiladi."""
import json
import time
import pandas as pd

import config as C
import indicators
import news
import bridge_broker as B
import postmortem
import regime
import report
import risk
import strategy
from journal import Journal

REAL_MIN_DEMO_TRADES = 30
REAL_MIN_DEMO_PF = 1.2


def real_gate():
    """Real hisobga o'tish sharti: demo'da yetarli bitim va profit factor."""
    s = report.stats(Journal(C.JOURNAL_DEMO).closed())
    if not s or s["n"] < REAL_MIN_DEMO_TRADES or s["pf"] < REAL_MIN_DEMO_PF or s["net"] <= 0:
        got = "demo bitimi yo'q" if not s else f"{s['n']} bitim, PF {s['pf']:.2f}, natija {s['net']:+.2f}"
        raise B.MT5Error(
            f"REAL rejim yopiq: demo'da kamida {REAL_MIN_DEMO_TRADES} bitim, PF >= {REAL_MIN_DEMO_PF} va plyus natija kerak. Hozir: {got}."
        )


def notify(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)
    report.telegram(msg)


def journal_path(mode):
    return C.JOURNAL_DEMO if mode == "demo" else C.JOURNAL_REAL


def sync_closed(j):
    for t in j.open_positions():
        ticket = t["ticket"]
        if ticket is None:
            continue
        scalp = json.loads(t["ctx"]).get("kind") == "scalp"
        if B.is_open(ticket):
            if scalp:  # razgon: vaqt chegarasi daqiqalarda
                mins = (B.server_now() - pd.Timestamp(t["entry_time"])).total_seconds() / 60
                if mins >= C.SCALP_HOLD_MIN:
                    B.close_position(ticket)
            else:
                df = B.candles(t["symbol"], C.TIMEFRAME, 500)
                held = len(df) - 1 - df.index.searchsorted(pd.Timestamp(t["entry_time"]))
                if held >= C.MAX_HOLD_BARS:
                    B.close_position(ticket)
            continue
        res = B.closing_deal(ticket)
        if res is None:
            continue
        ts, price, pnl, fees, reason = res
        if scalp:
            df = B.candles(t["symbol"], "15m", 400)
        else:
            df = indicators.add_all(B.candles(t["symbol"], C.TIMEFRAME, 500))
        path = df.iloc[df.index.searchsorted(pd.Timestamp(t["entry_time"])):]
        text = postmortem.analyze(dict(t, pnl=pnl), path, reason)
        j.close_trade(t["id"], ts, price, pnl, fees, reason, text)
        notify(f"{'✅' if pnl > 0 else '🔴'} YOPILDI {t['symbol']} {reason} {pnl:+.2f}\n{text}")


def load_symbol(sym):
    """(df, fresh): indikatorli, faqat YOPILGAN shamlar. Ma'lumot yetarli bo'lmasa (None, False)."""
    df = B.candles(sym, C.TIMEFRAME, 500)
    if len(df) < 300:
        return None, False
    df = indicators.add_all(df).iloc[:-1]
    now = B.server_now(sym)
    fresh = now is not None and (now - df.index[-1]).total_seconds() / 3600 <= C.MAX_CANDLE_AGE_H
    return df, fresh


def check_entry(j, sym, m, df, fresh):
    """Signal va barcha filtrlarni tekshiradi. (sig|None, holat, sabab). sig bo'lsa kirishga tayyor."""
    if m not in C.ENABLED_MARKETS:
        return None, "o'chiq", "bu bozorda strategiya savdo qilmaydi"
    if not fresh:
        return None, "yopiq", "bozor yopiq yoki ma'lumot eski"
    if j.open_position(sym, "swing"):
        return None, "ochiq", "bu simvolda oddiy bitim allaqachon ochiq"
    reg = regime.classify(df)
    sig = strategy.signal(df, reg, m)
    if not sig:
        return None, "kutish", "impuls yetarli emas"
    stop, why = news.blocked(sym, int(B.server_now().timestamp()))
    if stop:
        return None, "yangilik", f"signal bor ({sig['side']}), lekin yangilik filtri: {why}"
    sp = B.spread_pct(sym)
    if sp is None or sp > C.MAX_SPREAD_PCT[m]:
        shown = "noma'lum" if sp is None else f"{sp * 100:.3f}%"
        return None, "spread", f"signal bor ({sig['side']}), lekin spread {shown} (chegara {C.MAX_SPREAD_PCT[m] * 100:.3f}%)"
    bal = B.balance()
    ok, why = risk.allowed(j, sym, df.index[-1], base_equity=bal, kind="swing", new_risk=bal * C.RISK_PER_TRADE)
    if not ok:
        return None, "limit", f"signal bor ({sig['side']}), lekin xavf limiti: {why}"
    return sig, "signal", ""


def open_position(j, sym, m, df, sig, mode):
    """Bitim ochadi (lotni EA risk summasi va SL masofasidan hisoblaydi). fill qaytaradi yoki MT5Error."""
    bal = B.balance()
    fill = B.open_market(sym, sig["side"], bal * C.RISK_PER_TRADE,
                         abs(sig["entry"] - sig["sl"]), abs(sig["tp"] - sig["entry"]), comment="bot-swing")
    sig.update(entry=fill["price"], sl=fill["sl"], tp=fill["tp"])
    j.open_trade(sym, m, sig, df.index[-1], fill["lots"], fill["risk"], ticket=fill["position"])
    return fill


def open_message(mode, sym, sig, fill):
    arrow = "📈 LONG (sotib olish)" if sig["side"] == "long" else "📉 SHORT (sotish)"
    return (f"🟢 BITIM OCHILDI [{mode}] {sym}\n{arrow}\n"
            f"Lot: {fill['lots']} | Kirish: {fill['price']}\n"
            f"SL: {sig['sl']:.5g} | TP: {sig['tp']:.5g}\n"
            f"Risk: {fill['risk']:.2f} USD ({C.RISK_PER_TRADE * 100:.0f}% hisob)\n"
            f"Sabab: impuls kuchi {sig['ctx'].get('move')} (chegara {C.MOMO_THR}), ADX {sig['ctx']['adx']}, RSI {sig['ctx']['rsi']}")


def run(mode):
    if mode == "real":
        real_gate()
    acc = B.connect(mode)
    notify(f"XM {mode.upper()} ulandi: hisob {acc.login}, balans {acc.balance:.2f} {acc.currency}")
    syms = [(s, m) for s, m in B.resolve_symbols() if m in C.ENABLED_MARKETS]
    for s, m in syms:  # xarajat taxmini (FEE_PCT bir tomonga = spreadning yarmi) bilan solishtirish uchun
        sp = B.spread_pct(s)
        print(f"  {s:8s} {m:6s} spread: {'?' if sp is None else f'{sp * 100:.4f}%'}  (taxmin: {2 * C.FEE_PCT[m] * 100:.4f}%)", flush=True)
    j = Journal(journal_path(mode))
    last_seen = {}
    while True:
        try:
            sync_closed(j)
            for sym, m in syms:
                df, fresh = load_symbol(sym)
                if df is None or last_seen.get(sym) == df.index[-1]:
                    continue
                last_seen[sym] = df.index[-1]
                sig, status, why = check_entry(j, sym, m, df, fresh)
                if sig is None:
                    if status in ("yangilik", "spread", "limit"):
                        notify(f"⏸ {sym}: {why} — o'tkazildi")
                    continue
                try:
                    fill = open_position(j, sym, m, df, sig, mode)
                except B.MT5Error as e:
                    notify(f"⚠️ {sym}: {e}")
                    continue
                notify(open_message(mode, sym, sig, fill))
        except Exception as e:  # sikl o'lib qolmasin
            notify(f"⚠️ xato: {e}")
        time.sleep(C.LOOP_SECONDS)
