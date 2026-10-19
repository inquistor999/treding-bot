"""Yangilik filtri: muhim iqtisodiy yangilik atrofida yangi bitim ochilmaydi."""
import os
import time

import config as C

_CRYPTO = ("BTC", "ETH", "LTC", "XRP", "SOL", "DOGE")
_cache = {"mtime": None, "rows": []}


def currencies_for(symbol):
    s = symbol.upper()
    if s.startswith(_CRYPTO) or s.startswith(("XAU", "GOLD", "XAG", "SILVER")):
        return {"USD"}
    cur = {s[:3], s[3:6]} if len(s) >= 6 else set()
    return {"CNY" if c == "CNH" else c for c in cur}


def _decode(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:  # MQL5 FILE_ANSI: tizim kodirovkasi (rus Windows — cp1251)
        return raw.decode("cp1251", errors="replace")


def _load():
    path = os.path.join(C.BRIDGE_DIR, "calendar.csv")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None, None
    if _cache["mtime"] != mtime:
        with open(path, "rb") as f:
            text = _decode(f.read())
        rows = []
        for line in text.splitlines():
            p = line.strip().split(",", 3)
            if len(p) == 4 and p[0].isdigit():
                rows.append((int(p[0]), p[1], int(p[2]), p[3]))
        _cache.update(mtime=mtime, rows=rows)
    return _cache["rows"], mtime


def blocked(symbol, now_epoch):
    """(bloklandimi, sabab). now_epoch — MT5 server vaqti (sekund)."""
    if not C.NEWS_FILTER:
        return False, ""
    rows, mtime = _load()
    if rows is None:
        return True, "yangilik kalendari yo'q (EA yangi versiyasi grafikka qo'yilganmi?)"
    if time.time() - mtime > C.NEWS_STALE_SEC:
        return True, "yangilik kalendari eskirgan"
    cur = currencies_for(symbol)
    before, after = C.NEWS_BLOCK_BEFORE_MIN * 60, C.NEWS_BLOCK_AFTER_MIN * 60
    for ts, c, imp, name in rows:
        if c in cur and imp >= C.NEWS_MIN_IMPORTANCE and ts - before <= now_epoch <= ts + after:
            mins = (ts - now_epoch) // 60
            when = f"{mins} daqiqadan keyin" if mins >= 0 else f"{-mins} daqiqa oldin"
            return True, f"{c} {name} ({when})"
    return False, ""
