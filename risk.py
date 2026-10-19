import config as C


def position_size(equity, entry, sl):
    dist = abs(entry - sl)
    if dist <= 0:
        return 0.0, 0.0
    risk_amount = equity * C.RISK_PER_TRADE
    qty = risk_amount / dist
    max_qty = equity * C.MAX_LEVERAGE / entry
    if qty > max_qty:
        qty = max_qty
        risk_amount = qty * dist
    return qty, risk_amount


def allowed(journal, symbol, now_ts, base_equity=None, kind="swing", new_risk=0.0):
    """(ruxsat, sabab). Bitimlar bir-biridan mustaqil: faqat bir turdagi dublikat, umumiy soni va umumiy risk cheklanadi."""
    base = base_equity or C.START_EQUITY
    if journal.open_position(symbol, kind):
        return False, f"bu simvolda {kind} bitimi allaqachon ochiq"
    if len(journal.open_positions()) >= C.MAX_OPEN_POSITIONS:
        return False, f"ochiq bitimlar limiti ({C.MAX_OPEN_POSITIONS})"
    if new_risk and journal.open_risk() + new_risk > C.MAX_TOTAL_RISK * base:
        return False, f"jami ochiq risk limiti ({C.MAX_TOTAL_RISK * 100:.0f}% hisob)"
    day = str(now_ts)[:10]
    if journal.pnl_on_day(day) <= -C.DAILY_LOSS_LIMIT * base:
        return False, "kunlik zarar limiti"
    return True, ""
