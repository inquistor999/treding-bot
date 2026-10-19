"""Ishlatish:
  python main.py scan                 — hozir qaysi bozor savdoga tayyor
  python main.py backtest --days 180  — tarixiy sinov
  python main.py run                  — jonli PAPER rejim (soxta pul)
  python main.py report               — hisobot
  python main.py xm --mode demo       — XM demo hisobda savdo (MT5 terminal ochiq va login qilingan bo'lsin)
  python main.py xm --mode real       — XM real (faqat demo'da yetarli natija bo'lsa ochiladi)
"""
import argparse
import os
import tempfile
import time
from datetime import datetime

import pandas as pd

import config as C
import data
import engine
import indicators
import regime
import report
from journal import Journal


def symbols():
    return [(s, m) for m, lst in C.WATCHLIST.items() for s in lst]


def load(sym, market, days):
    try:
        df = data.fetch(sym, market, C.TIMEFRAME, days)
        return indicators.add_all(df) if len(df) > 250 else None
    except Exception as e:
        print(f"  {sym}: ma'lumot xatosi {e}")
        return None


def cmd_scan(_):
    rows = []
    for sym, m in symbols():
        df = load(sym, m, 60)
        if df is None:
            continue
        df = df.iloc[:-1]
        age_h = (pd.Timestamp.utcnow().tz_localize(None) - df.index[-1]).total_seconds() / 3600
        reg = regime.classify(df)
        status = "YOPIQ" if age_h > C.MAX_CANDLE_AGE_H else ("TAYYOR" if reg["tradeable"] else "kutish")
        rows.append((reg["score"], sym, m, reg["regime"], status, reg["reason"]))
    for r in sorted(rows, reverse=True):
        print(f"{r[0]:5.1f}  {r[1]:10s} {r[2]:7s} {r[3]:10s} {r[4]:7s} {r[5]}")


def cmd_backtest(a):
    path = os.path.join(tempfile.gettempdir(), "bt_journal.db")
    if os.path.exists(path):
        os.remove(path)
    j = Journal(path)
    frames = {}
    for sym, m in symbols():
        df = load(sym, m, a.days)
        if df is not None:
            frames[(sym, m)] = df
            print(f"{sym}: {len(df)} sham")
    # barcha simvollarni vaqt bo'yicha birga yuritamiz (risk limitlari umumiy bo'lishi uchun)
    timeline = sorted(set().union(*[set(d.index) for d in frames.values()]))
    pos = {k: 0 for k in frames}
    for ts in timeline:
        for (sym, m), df in frames.items():
            i = df.index.searchsorted(ts)
            if i >= len(df) or df.index[i] != ts or i < 5:
                continue
            engine.on_candle(j, sym, m, df.iloc[: i + 1])
    text = report.build(j, last_n=20)
    print(text)
    print("\nSaqlandi:", report.save(text, "backtest"))


def cmd_run(_):
    j = Journal()
    last_seen = {}
    print("Paper rejim ishga tushdi. To'xtatish: Ctrl+C")
    while True:
        cands = []
        for sym, m in symbols():
            df = load(sym, m, 60)
            if df is None:
                continue
            df = df.iloc[:-1]  # shakllanayotgan shamni tashlaymiz
            ts = df.index[-1]
            if last_seen.get(sym) == ts:
                continue
            last_seen[sym] = ts
            age_h = (pd.Timestamp.utcnow().tz_localize(None) - ts).total_seconds() / 3600
            cands.append((regime.classify(df)["score"], sym, m, df, age_h <= C.MAX_CANDLE_AGE_H))
        for _, sym, m, df, fresh in sorted(cands, key=lambda x: -x[0]):  # eng yaxshi bozor birinchi
            for ev in engine.on_candle(j, sym, m, df, allow_open=fresh):
                if ev["event"] == "open":
                    msg = (f"🟢 OCHILDI {ev['symbol']} {ev['side']} @ {ev['entry']:.5g}\n"
                           f"SL {ev['sl']:.5g} | TP {ev['tp']:.5g} | risk {ev['risk']:.2f}$\n"
                           f"Sabab: {ev['ctx']['regime']}, ADX {ev['ctx']['adx']}, RSI {ev['ctx']['rsi']}")
                else:
                    msg = (f"{'✅' if ev['pnl'] > 0 else '🔴'} YOPILDI {ev['symbol']} {ev['reason']} {ev['pnl']:+.2f}$\n{ev['text']}")
                print(datetime.utcnow().strftime("%H:%M"), msg)
                report.telegram(msg)
        if datetime.utcnow().hour == 20 and datetime.utcnow().minute < C.LOOP_SECONDS // 60 + 1:
            report.telegram(report.build(j))
        time.sleep(C.LOOP_SECONDS)


def cmd_tg(_):
    import telegram_bot
    telegram_bot.run_polling()


def cmd_xm(a):
    import live_xm
    if a.mode == "demo":  # demo'da telegram bot ham birga ishlaydi (tugma orqali tahlil/kirish)
        import telegram_bot
        telegram_bot.start_thread()
    try:
        live_xm.run(a.mode)
    except live_xm.B.MT5Error as e:
        print("TO'XTADI:", e)


def cmd_report(_):
    text = report.build(Journal())
    print(text)
    print("\nSaqlandi:", report.save(text))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("scan").set_defaults(f=cmd_scan)
    b = sp.add_parser("backtest")
    b.add_argument("--days", type=int, default=180)
    b.set_defaults(f=cmd_backtest)
    sp.add_parser("run").set_defaults(f=cmd_run)
    sp.add_parser("report").set_defaults(f=cmd_report)
    sp.add_parser("tg", help="faqat telegram bot").set_defaults(f=cmd_tg)
    x = sp.add_parser("xm", help="XM (MT5) orqali savdo")
    x.add_argument("--mode", choices=["demo", "real"], default="demo")
    x.set_defaults(f=cmd_xm)
    a = p.parse_args()
    a.f(a)
