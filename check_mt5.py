"""Ko'prik tekshiruvi (BridgeEA ishlayaptimi). Hech qanday bitim ochmaydi."""
import bridge_broker as B

try:
    a = B._account()
except B.MT5Error as e:
    print("XATO:", e)
    raise SystemExit(1)

print(f"hisob: {a['login']} | rejim: {a['mode']} | server: {a['server']} | balans: {a['balance']} {a['currency']}")
print(f"MT5 serverga ulangan: {a['connected']} | EA savdo qila oladi: {a['trading_allowed']} | EA rejimi: {a['allowed_mode']}")
print("Simvollar (shamlar eksport qilinganlari):")
for s, m in B.resolve_symbols():
    df = B.candles(s)
    print(f"  {m:7s} {s:8s} {len(df)} sham, oxirgisi {df.index[-1] if len(df) else '-'}")
