import config as C


def grade(sig):
    """'A' (ideal) yoki 'B' (oddiy). Razgon va boshqalar — 'B'."""
    return sig["ctx"].get("grade", "B")


def risk_fraction(sig):
    return C.RISK_A if grade(sig) == "A" else C.RISK_B


def position_size(equity, entry, sl, frac=None):
    dist = abs(entry - sl)
    if dist <= 0:
        return 0.0, 0.0
    risk_amount = equity * (frac if frac is not None else C.RISK_PER_TRADE)
    qty = risk_amount / dist
    max_qty = equity * C.MAX_LEVERAGE / entry
    if qty > max_qty:
        qty = max_qty
        risk_amount = qty * dist
    return qty, risk_amount


def allowed(journal, symbol, now_ts, base_equity=None, kind="swing", new_risk=0.0, grade_="B"):
    """(ruxsat, sabab). Bitimlar bir-biridan mustaqil. Cheklovlar: bir turdagi dublikat, vaziyat sifatiga qarab bir vaqtdagi
    bitimlar soni (A: 3 tagacha, B: 1 ta), umumiy son, jami risk, kunlik zarar."""
    base = base_equity or C.START_EQUITY
    if journal.open_position(symbol, kind):
        return False, f"bu simvolda {kind} bitimi allaqachon ochiq"
    if len(journal.open_positions()) >= C.MAX_OPEN_POSITIONS:
        return False, f"ochiq bitimlar limiti ({C.MAX_OPEN_POSITIONS})"
    if kind == "swing":
        n = len(journal.open_positions("swing"))
        if grade_ == "A" and n >= C.MAX_A_TRADES:
            return False, f"ideal vaziyatda ham bir vaqtda {C.MAX_A_TRADES} tadan ko'p oddiy bitim ochilmaydi"
        if grade_ != "A" and n >= C.MAX_B_TRADES:
            return False, "oddiy vaziyat (A emas): bir vaqtda faqat 1 ta bitim, ochiq bitim yopilishini kutamiz"
    if new_risk and journal.open_risk() + new_risk > C.MAX_TOTAL_RISK * base:
        return False, f"jami ochiq risk limiti ({C.MAX_TOTAL_RISK * 100:.0f}% hisob)"
    day = str(now_ts)[:10]
    if journal.pnl_on_day(day) <= -C.DAILY_LOSS_LIMIT * base:
        return False, "kunlik zarar limiti"
    return True, ""
