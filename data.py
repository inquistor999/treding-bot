"""Ma'lumot olish: kripto — Binance (ccxt, kalitsiz), forex/oltin — yfinance."""
import time
import pandas as pd


def _crypto(symbol, tf, days):
    import ccxt
    ex = ccxt.binance({"enableRateLimit": True})
    ms_bar = ex.parse_timeframe(tf) * 1000
    since = ex.milliseconds() - days * 86400 * 1000
    rows = []
    while True:
        batch = ex.fetch_ohlcv(symbol, tf, since=since, limit=1000)
        if not batch:
            break
        rows += batch
        since = batch[-1][0] + ms_bar
        if len(batch) < 1000:
            break
        time.sleep(0.2)
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.drop_duplicates("ts").set_index("ts")


def _yf(symbol, tf, days):
    import yfinance as yf
    days = min(days, 700)  # yfinance 1h uchun ~730 kun chegara
    df = yf.download(symbol, period=f"{days}d", interval=tf, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    idx = pd.to_datetime(df.index)
    df.index = (idx.tz_convert("UTC") if idx.tz is not None else idx).tz_localize(None)
    df.index.name = "ts"
    return df[["open", "high", "low", "close", "volume"]]


def fetch(symbol, market, tf="1h", days=60):
    df = _crypto(symbol, tf, days) if market == "crypto" else _yf(symbol, tf, days)
    return df.sort_index()
