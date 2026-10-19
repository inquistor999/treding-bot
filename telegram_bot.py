"""Telegram bot (long polling, qo'shimcha kutubxonasiz).
- /start va begona xabarlarga JIM turadi.
- "login:<TG_LOGIN>" yozilsa (faqat TELEGRAM_OWNER_ID chatidan) tanib oladi va top-5 bozorni beradi.
- "Tahlil qilish" tugmasi: signal bo'lsa 1–2 ta eng yaxshisiga demo hisobda kiradi va tafsilotini yozadi."""
import threading
import time

import requests

import bridge_broker as B
import config as C
import live_xm as L
import scalp
import tg_store
from journal import Journal

API = f"https://api.telegram.org/bot{C.TELEGRAM_TOKEN}/"
MAX_TRADES_PER_ANALYSIS = 2
MENU = [[{"text": "🔍 Tahlil qilish", "callback_data": "analyze"},
         {"text": "🔄 Yangilash", "callback_data": "refresh"}],
        [{"text": "📂 Ochiq bitimlar", "callback_data": "open"}]]
# yaxshi pozitsiya topilmaganda: qo'shimcha "razgon" tugmasi
MENU_NO_SIGNAL = MENU + [[{"text": "⚡ Hozir zdelka ochish", "callback_data": "scalp"}]]


def call(method, **params):
    try:
        r = requests.post(API + method, json=params, timeout=40)
        return r.json()
    except Exception as e:
        print("telegram xato:", type(e).__name__, flush=True)
        return {}


def send(chat, text, buttons=None):
    p = {"chat_id": chat, "text": text[:4000]}
    if buttons:
        p["reply_markup"] = {"inline_keyboard": buttons}
    return call("sendMessage", **p)


# ---------------- bozorlar reytingi ----------------
def market_rows():
    rows = []
    n = C.MOMO_N
    for sym, m in B.resolve_symbols():
        df, fresh = L.load_symbol(sym)
        if df is None:
            continue
        last = df.iloc[-1]
        move = float((last.close - df.close.iloc[-1 - n]) / (last.atr * n ** 0.5))
        sp = B.spread_pct(sym) or 0.0
        momo = min(abs(move) / C.MOMO_THR, 1.5) / 1.5 * 50
        trend = min(float(last.adx), 40) / 40 * 30
        vol = 20 if 0.2 <= float(last.atr_rank) <= 0.85 else 0
        score = momo + trend + vol - min(15, sp * 1000)
        aligned = (move > 0 and last.close > last.ema200) or (move < 0 and last.close < last.ema200)
        if m not in C.ENABLED_MARKETS:
            state = "strategiya bu bozorda savdo qilmaydi"
        elif not fresh:
            state = "bozor yopiq"
        elif abs(move) >= C.MOMO_THR and aligned:
            state = "SIGNAL ✅"
        else:
            state = f"kutilmoqda (impuls {abs(move):.2f}/{C.MOMO_THR})"
        rows.append({"sym": sym, "m": m, "move": move, "adx": float(last.adx), "sp": sp,
                     "score": score, "state": state, "enabled": m in C.ENABLED_MARKETS})
    return sorted(rows, key=lambda r: -r["score"])


def top5_text():
    rows = market_rows()[:5]
    if not rows:
        return "Ma'lumot yo'q: MT5 va BridgeEA ishlayaptimi?"
    lines = ["📊 Hozir eng yaxshi yurayotgan 5 bozor (ball bo'yicha):", ""]
    for i, r in enumerate(rows, 1):
        arrow = "↑" if r["move"] > 0 else "↓"
        lines.append(f"{i}. {r['sym']} {arrow}  ball {r['score']:.0f} | ADX {r['adx']:.0f} | spread {r['sp'] * 100:.3f}%\n    {r['state']}")
    lines += ["", "Ball = impuls kuchi + trend (ADX) + tebranish me'yori − spread.",
              "Strategiya faqat " + ", ".join(sorted({s for m in C.ENABLED_MARKETS for s in C.XM_SYMBOLS[m]})) + " da savdo qiladi."]
    return "\n".join(lines)


# ---------------- tahlil va kirish ----------------
def analyze_and_trade(chat):
    try:
        acc = B.connect("demo")  # faqat DEMO hisobda: real hisobda bu tugma ishlamaydi
    except B.MT5Error as e:
        send(chat, f"⛔ Savdo qilib bo'lmaydi: {e}")
        return
    j = Journal(L.journal_path("demo"))
    ready, report_lines = [], []
    for sym, m in B.resolve_symbols():
        if m not in C.ENABLED_MARKETS:
            continue
        df, fresh = L.load_symbol(sym)
        if df is None:
            report_lines.append(f"• {sym}: ma'lumot yo'q")
            continue
        sig, status, why = L.check_entry(j, sym, m, df, fresh)
        if sig:
            ready.append((abs(sig["ctx"].get("move", 0)), sym, m, df, sig))
            report_lines.append(f"• {sym}: SIGNAL ✅ ({sig['side']}, impuls {sig['ctx'].get('move')})")
        else:
            report_lines.append(f"• {sym}: {why}")
    send(chat, "🔍 Tahlil natijasi:\n" + "\n".join(report_lines))
    if not ready:
        send(chat, "Hozir kirish uchun yaxshi pozitsiya yo'q. Strategiya sifatsiz signalga kirmaydi, "
                   "shuning uchun bitim ochilmadi. Soat shamlari yopilganda bot o'zi tekshirib turadi.\n\n"
                   "⚡ \"Hozir zdelka ochish\": majburan qisqa muddatli (razgon, ~40 pip) bitim ochadi. "
                   "Boshqa ochiq bitimlardan mustaqil. Tarixiy testda kutilgan natija manfiy (tajriba uchun).",
             MENU_NO_SIGNAL)
        return
    ready.sort(reverse=True)
    for _, sym, m, df, sig in ready[:MAX_TRADES_PER_ANALYSIS]:
        try:
            fill = L.open_position(j, sym, m, df, sig, "demo")
        except B.MT5Error as e:
            send(chat, f"⚠️ {sym}: kirib bo'lmadi: {e}")
            continue
        send(chat, L.open_message("demo", sym, sig, fill))
    send(chat, "Bitim(lar) ochildi. Yopilganda natija va sabab tahlili yuboriladi.", MENU)


def open_trades_text():
    """Botning har bir ochiq bitimi alohida: tur, chipta, hozirgi foyda/zarar. Qo'lda ochilganlar alohida aytiladi."""
    j = Journal(L.journal_path("demo"))
    trades = j.open_positions()
    profit = {r[0]: r[7] for r in B._rows("positions.csv") if len(r) >= 8}
    lines = []
    for t in trades:
        kind = "⚡ razgon" if t.get("kind") == "scalp" else "📈 oddiy"
        pl = profit.get(str(t["ticket"]))
        now = f"{float(pl):+.2f} USD" if pl is not None else "ma'lumot yo'q"
        lines.append(f"{kind} | {t['symbol']} {t['side'].upper()} {t['qty']} lot | chipta {t['ticket']}\n"
                     f"   kirish {t['entry']:.5g} | SL {t['sl']:.5g} | TP {t['tp']:.5g} | hozir {now}\n"
                     f"   ochilgan: {t['entry_time']} (server vaqti)")
    try:
        manual = max(0, B.all_positions_count() - sum(1 for t in trades if str(t["ticket"]) in profit))
    except B.MT5Error:
        manual = 0
    head = f"📂 Botning ochiq bitimlari: {len(trades)} ta (limit {C.MAX_OPEN_POSITIONS})" if trades else "📂 Botning ochiq bitimi yo'q."
    tail = f"\n\nQo'lda ochilgan pozitsiyalar: {manual} ta, bot ularga tegmaydi." if manual else ""
    return head + ("\n\n" + "\n\n".join(lines) if lines else "") + tail


def do_scalp(chat):
    try:
        B.connect("demo")  # faqat DEMO
    except B.MT5Error as e:
        send(chat, f"⛔ Savdo qilib bo'lmaydi: {e}")
        return
    send(chat, "⚡ Razgon tahlil qilinmoqda (15 daqiqalik shamlar)...")
    j = Journal(L.journal_path("demo"))
    text, _ = scalp.open_scalp(j, "demo")
    send(chat, text, MENU)


# ---------------- xabarlarni qayta ishlash ----------------
def handle_message(msg):
    chat = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    if tg_store.is_authorized(chat):
        send(chat, top5_text(), MENU)
        return
    # login: faqat egasining chatidan, aniq so'z bilan. Boshqa hamma narsaga jim.
    if C.TG_LOGIN and chat == C.TELEGRAM_OWNER_ID and text.lower() == f"login:{C.TG_LOGIN}".lower():
        tg_store.add(chat)
        call("deleteMessage", chat_id=chat, message_id=msg["message_id"])  # login so'zi chatda qolmasin
        send(chat, top5_text(), MENU)


def handle_callback(cb):
    chat = cb["message"]["chat"]["id"]
    call("answerCallbackQuery", callback_query_id=cb["id"])
    if not tg_store.is_authorized(chat):
        return
    if cb.get("data") == "analyze":
        analyze_and_trade(chat)
    elif cb.get("data") == "scalp":
        do_scalp(chat)
    elif cb.get("data") == "open":
        send(chat, open_trades_text(), MENU)
    elif cb.get("data") == "refresh":
        send(chat, top5_text(), MENU)


def run_polling():
    if not C.TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN yo'q (.env), telegram bot ishga tushmadi.", flush=True)
        return
    me = call("getMe").get("result", {})
    print(f"Telegram bot ishga tushdi: @{me.get('username')}", flush=True)
    offset = None
    while True:
        try:
            upd = call("getUpdates", offset=offset, timeout=30, allowed_updates=["message", "callback_query"])
            for u in upd.get("result", []):
                offset = u["update_id"] + 1
                if "message" in u:
                    handle_message(u["message"])
                elif "callback_query" in u:
                    handle_callback(u["callback_query"])
        except Exception as e:
            print("telegram sikl xatosi:", type(e).__name__, e, flush=True)
            time.sleep(5)


def start_thread():
    t = threading.Thread(target=run_polling, daemon=True)
    t.start()
    return t
