"""Yopilgan bitim tahlili: nega foyda / zarar bo'ldi (o'zbekcha)."""
import json
import config as C


def analyze(trade, path_df, exit_reason):
    """path_df — bitim ochilgandan yopilgunga qadar shamlar (indikatorlari bilan)."""
    ctx = json.loads(trade["ctx"])
    sgn = 1 if trade["side"] == "long" else -1
    entry, sl = trade["entry"], trade["sl"]
    r_dist = abs(entry - sl)
    after = path_df.iloc[1:] if len(path_df) > 1 else path_df
    if after.empty or r_dist <= 0:
        return "Ma'lumot yetarli emas."

    fav = (after["high"].max() - entry) if sgn == 1 else (entry - after["low"].min())
    adv = (entry - after["low"].min()) if sgn == 1 else (after["high"].max() - entry)
    mfe_r, mae_r = fav / r_dist, adv / r_dist
    bars = len(after)
    win = (trade.get("pnl") or 0) > 0

    head = f"MFE {mfe_r:.2f}R, MAE {mae_r:.2f}R, {bars} soat. "
    momentum = ctx.get("regime") == "MOMENTUM"
    notes = []

    if ctx.get("regime") == "SCALP":  # razgon: qisqa muddatli majburiy kirish
        head = f"MFE {mfe_r:.2f}R, MAE {mae_r:.2f}R, {bars} sham (M15). "
        if win:
            notes.append("Foyda: impuls davom etib, maqsadga yetdi." if exit_reason == "TP" else "Foyda: vaqt chegarasida ijobiy yopildi.")
        elif exit_reason in ("SL", "BE"):
            if bars <= 3 and mfe_r < 0.3:
                notes.append("Kirishdan keyin narx darhol qaytdi: impuls allaqachon tugagan edi (majburiy kirishning asosiy xavfi).")
            elif mfe_r >= 0.6:
                notes.append(f"Narx {mfe_r:.1f}R maqsad tomon yurdi, lekin to'liq yetmay qaytib SL urdi.")
            else:
                notes.append("Impuls davom etmadi: narx qaytib SL ga tushdi.")
        elif exit_reason == "TIME":
            notes.append("Vaqt chegarasi tugadi: narx na TP, na SL ga yetdi, impuls so'ndi.")
        notes.append("Eslatma: majburiy kirish signal sifatiga qaramaydi, tarixiy testda kutilgan natija manfiy edi.")
        return head + " ".join(notes)

    if win:
        if momentum:
            notes.append(f"Foyda: impuls (kuch {ctx.get('move')}) davom etdi" + (", TP ga yetdi." if exit_reason == "TP" else ", vaqt chegarasida ijobiy yopildi."))
        else:
            notes.append("Foyda: trend yo'nalishida kirildi" if exit_reason == "TP" else "Foyda: vaqt chegarasida ijobiy yopildi")
            notes.append(f"kirishda ADX {ctx['adx']}, RSI pullback {ctx['rsi_pullback']} edi — signal sifatli.")
        return head + " ".join(notes)

    if momentum:
        if exit_reason in ("SL", "BE"):
            if bars <= 3 and mfe_r < 0.3:
                notes.append("Impuls kirgan zahoti qaytdi: harakat allaqachon tugagan yoki likvidlik tozalash (stop-hunt) bo'lgan.")
            elif mfe_r >= 1.0:
                notes.append(f"Narx avval {mfe_r:.1f}R foyda berdi, keyin impuls so'nib SL urdi — qisman foyda olish/trailing yo'q edi.")
            else:
                notes.append("Impuls davom etmadi: kirishdan keyin narx qaytib, stopgacha tushdi.")
            if abs(ctx.get("move", 9)) < 1.3:
                notes.append(f"Impuls chegaraga yaqin edi (kuch {ctx.get('move')}) — signal kuchsizroq edi.")
            if ctx["atr_rank"] > 0.8:
                notes.append(f"Tebranish juda yuqori edi (ATR rank {ctx['atr_rank']}) — stop shovqinda urilishi osonroq.")
        elif exit_reason == "TIME":
            notes.append(f"{C.MAX_HOLD_BARS} soat ichida narx na TP ga, na SL ga yetdi: momentum so'ndi, bozor yon tomonga o'tdi.")
        notes.append("Eslatma: bu strategiya ~38% yutuq darajasiga mo'ljallangan, uchta bitimdan ikkitasi zarar bo'lishi me'yoriy.")
        return head + " ".join(notes)

    if exit_reason == "SL":
        if bars <= 3 and mfe_r < 0.3:
            notes.append("Kirish vaqti yomon: narx darhol qarshi yurdi (qalbaki signal / pullback hali tugamagan edi).")
        elif mfe_r >= 1.0:
            notes.append(f"Narx avval {mfe_r:.1f}R foyda tomon yurdi, keyin qaytib SL urdi — foydani himoya qiladigan trailing stop/qisman yopish yo'q edi.")
        else:
            notes.append("Trend davom etmadi: narx pullbackdan keyin qayta qarshi tomonga burildi.")
        if ctx["adx"] < 26:
            notes.append(f"Trend kuchsiz edi (ADX {ctx['adx']}) — chegara yaqinida kirilgan.")
        if ctx["atr_rank"] > 0.7:
            notes.append(f"Tebranish yuqori edi (ATR rank {ctx['atr_rank']}) — shovqin stopni urishi osonroq.")
        if (trade["side"] == "long" and ctx["rsi_pullback"] > 40) or (trade["side"] == "short" and ctx["rsi_pullback"] < 60):
            notes.append("Pullback sayoz edi — kirish nuqtasi uncha qulay bo'lmagan.")
    elif exit_reason == "TIME":
        notes.append(f"{C.MAX_HOLD_BARS} soat ichida narx na TP ga, na SL ga yetdi: bozor yon tomonga o'tib ketdi, momentum so'ndi.")
    if len(notes) == 0:
        notes.append("Oddiy statistik zarar: strategiya bu risk (1R) ni oldindan hisoblagan.")
    return head + " ".join(notes)
