"""Hisobot: statistika + har bir bitim post-mortemi."""
import os
from datetime import datetime
import requests
import config as C


def stats(trades):
    if not trades:
        return None
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    eq, peak, mdd = C.START_EQUITY, C.START_EQUITY, 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
    rs = [t["pnl"] / t["risk_amount"] for t in trades if t["risk_amount"]]
    return {
        "n": len(trades), "wins": len(wins), "losses": len(losses),
        "winrate": len(wins) / len(trades) * 100,
        "net": sum(pnls), "gross_win": sum(wins), "gross_loss": sum(losses),
        "pf": (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float("inf"),
        "avg_r": sum(rs) / len(rs) if rs else 0, "mdd": mdd * 100, "equity": eq,
    }


def build(journal, last_n=15):
    trades = journal.closed()
    s = stats(trades)
    out = [f"# Savdo hisoboti — {datetime.utcnow():%Y-%m-%d %H:%M} UTC", ""]
    if not s:
        out.append("Hali yopilgan bitim yo'q.")
    else:
        out += [
            f"Bitimlar: {s['n']}  (yutuq {s['wins']} / zarar {s['losses']}, winrate {s['winrate']:.1f}%)",
            f"Sof natija: {s['net']:+.2f} USD  | Equity: {s['equity']:.2f} (start {C.START_EQUITY:.0f})",
            f"Profit factor: {s['pf']:.2f}  | O'rtacha R: {s['avg_r']:+.2f}  | Max drawdown: {s['mdd']:.1f}%",
            "", "## Bozorlar bo'yicha",
        ]
        for m in sorted({t["market"] for t in trades}):
            ms = stats([t for t in trades if t["market"] == m])
            out.append(f"- {m}: {ms['n']} ta, winrate {ms['winrate']:.0f}%, natija {ms['net']:+.2f}")
        out += ["", f"## Oxirgi {last_n} ta bitim va tahlil"]
        for t in trades[-last_n:]:
            mark = "✅" if t["pnl"] > 0 else "❌"
            out.append(f"{mark} {t['symbol']} {t['side']} {t['entry_time'][:16]} → {t['exit_reason']}  {t['pnl']:+.2f}")
            out.append(f"    {t['postmortem']}")
    openp = journal.open_positions()
    if openp:
        out += ["", "## Ochiq pozitsiyalar"]
        for p in openp:
            out.append(f"- {p['symbol']} {p['side']} @ {p['entry']:.5g}  SL {p['sl']:.5g}  TP {p['tp']:.5g}")
    return "\n".join(out)


def save(text, name="report"):
    os.makedirs(C.REPORT_DIR, exist_ok=True)
    path = os.path.join(C.REPORT_DIR, f"{name}_{datetime.utcnow():%Y%m%d_%H%M}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def telegram(text):
    """Faqat bot'da login qilgan chatlarga yuboradi (login'gacha bot jim turadi)."""
    if not C.TELEGRAM_TOKEN:
        return
    import tg_store
    for chat in tg_store.authorized():
        try:
            requests.post(f"https://api.telegram.org/bot{C.TELEGRAM_TOKEN}/sendMessage",
                          json={"chat_id": chat, "text": text[:4000]}, timeout=15)
        except Exception as e:
            print("telegram xato:", type(e).__name__)
