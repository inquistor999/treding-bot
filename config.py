"""Robot sozlamalari. Hamma narsa shu yerda."""
import os


def _load_env():
    """.env fayli (token va parollar shu yerda, kodda emas). Tashqi kutubxona kerak emas."""
    path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


_load_env()

# Bozor -> simvollar. crypto: ccxt/Binance (ochiq ma'lumot), forex/gold: yfinance
WATCHLIST = {
    "crypto": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"],
    "forex": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"],
    "gold": ["GC=F"],
}

TIMEFRAME = "1h"

START_EQUITY = 1000.0          # paper hisob (USD)
# Risk sifatga qarab o'zgaradi: ideal vaziyat (A) — katta risk va ko'proq bitim, oddiy (B) — kichikroq risk va 1 ta bitim
RISK_A = 0.025                 # A (ideal): bitimga hisobning 2.5% i
RISK_B = 0.015                 # B (oddiy): 1.5%
RISK_PER_TRADE = RISK_B        # umumiy standart (eski kod uchun)
GRADE_A_MOVE = 1.3             # A: impuls kuchi chegaradan kamida 1.3 baravar katta
GRADE_A_ADX = 25               # A: trend kuchli
GRADE_A_VOL = (0.2, 0.8)       # A: tebranish me'yorida (ATR rank oralig'i)
MAX_A_TRADES = 3               # ideal vaziyatda bir vaqtda ochiq oddiy bitimlar soni
MAX_B_TRADES = 3               # oddiy vaziyatda ham 3 tagacha (1 ta qilinsa, tarixiy natija yomonlashdi: PF 1.16 -> 0.96)
DAILY_LOSS_LIMIT = 0.06        # kunlik zarar 6% ga yetsa, shu kuni yangi bitim yo'q
MAX_OPEN_POSITIONS = 4         # botning bir vaqtdagi ochiq bitimlari (qo'lda ochilganlar hisobga olinmaydi)
MAX_TOTAL_RISK = 0.08          # barcha ochiq bitimlar jami riski: hisobning 8% idan oshmasin
MAX_LEVERAGE = 5.0             # bitim hajmi / equity chegarasi
ALLOW_SHORT = {"crypto": True, "forex": True, "gold": True}   # XM CFD da short ruxsat etilgan

# Komissiya/spread (bir tomonga, notional ulushi) — XM CFD uchun taxmin; EA spread eksporti bilan tasdiqlanadi
FEE_PCT = {"crypto": 0.0003, "forex": 0.00006, "gold": 0.00008}
# Jonli savdoda spread shundan katta bo'lsa (taxmin buzilgan), bitim ochilmaydi (notional ulushi, to'liq spread)
MAX_SPREAD_PCT = {"crypto": 0.0015, "forex": 0.0004, "gold": 0.0004}

# "Razgon" (qisqa muddatli majburiy kirish, telegramdagi ⚡ tugma). Tarixiy test: kutilgan natija manfiy, faqat demo.
SCALP_TARGET_PCT = 0.0035      # maqsad: narxning 0.35% i (~40 pip EURUSD da), kamida 1 ATR(M15)
SCALP_SL_MULT = 1.5            # SL = 1.5 x TP masofa (yutuq darajasi yuqori, tarixda eng kam zararli)
SCALP_HOLD_MIN = 240           # shuncha daqiqadan keyin vaqt bo'yicha yopiladi
SCALP_RISK = 0.01              # razgon: hisobning 1% i (majburiy kirish, ustunlik isbotlanmagan, shuning uchun A dan kichik)
SCALP_MAX_COST_RATIO = 0.20    # spread / maqsad shundan katta bo'lsa (masalan ETH), kirmaymiz

# Qaysi bozorlarda savdo qilinadi. Tadqiqot: forexda ustunlik topilmadi, oltin va kriptoda bor.
ENABLED_MARKETS = ("crypto", "gold")

# Strategiya turi: "momentum" (tadqiqotda tasdiqlangan) yoki "pullback" (eski, zararli)
STRATEGY = "momentum"
MOMO_N = 24                    # impuls oynasi (soat)
MOMO_THR = 1.5                 # harakat > THR * ATR * sqrt(N) bo'lsa — impuls (portfel backtestida eng barqaror)

# Bozor holati filtri
MIN_ADX = 22
ATR_RANK_MIN = 0.20            # juda "o'lik" bozor emas
ATR_RANK_MAX = 0.85            # juda og'ir tebranish emas

# Qo'shimcha filtrlar (tadqiqot natijasiga ko'ra yoqiladi; False/0 = o'chiq)
REQUIRE_ADX_RISING = False     # ADX 3 shamdan beri o'sib borayotgan bo'lsin
HTF_FILTER = False             # 4 soatlik trend (EMA50) yo'nalishi mos bo'lsin
PULLBACK_RSI_LONG = 45         # long: oldingi 8 shamda RSI shu darajadan pastga tushgan bo'lsin
PULLBACK_RSI_SHORT = 55        # short: yuqoriga chiqqan bo'lsin
MAX_EXT_ATR = 0.0              # >0: narx EMA20 dan ATR ning shuncha ulushidan uzoq bo'lsa, kirmaymiz
BLOCK_HOURS = ()               # forex/oltinda kirish taqiqlangan UTC soatlari
BE_AT_R = 0.0                  # >0: narx shuncha R foyda bergach, SL kirish narxiga ko'chiriladi

# Strategiya
SL_ATR = 2.0
TP_ATR = 4.0
MAX_HOLD_BARS = 96             # shuncha soatdan keyin bitim yopiladi

LOOP_SECONDS = 300             # jonli rejimda skaner chastotasi
MAX_CANDLE_AGE_H = 2           # eski shamda yangi bitim ochilmaydi (bozor yopiq)

# --- XM (MetaTrader 5) ---
# Simvol nomlari XM hisob turiga qarab farq qilishi mumkin (EURUSD, EURUSD#, GOLD ...).
# MT5 terminalida "Market Watch" dan aniq nomni tekshiring. Topilmagan simvol o'tkazib yuboriladi.
XM_SYMBOLS = {
    "forex": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
    "gold": ["GOLD"],
    # Altkoin CFD spreadi juda katta (LTC/XRP/SOL ~0.7%, DOGE ~1.4%): ular backtest foydasini yeb qo'yadi
    "crypto": ["BTCUSD", "ETHUSD"],
}
# Yangilik filtri (MT5 iqtisodiy kalendari, faqat yuqori ahamiyatli: FOMC, CPI, NFP, foiz stavkalari ...)
NEWS_FILTER = True
NEWS_MIN_IMPORTANCE = 3        # 3 = yuqori
NEWS_BLOCK_BEFORE_MIN = 30     # yangilikdan oldin yangi bitim yo'q
NEWS_BLOCK_AFTER_MIN = 45      # yangilikdan keyin ham (tebranish pasayguncha)
NEWS_STALE_SEC = 36 * 3600     # kalendar fayli shundan eski bo'lsa, xavfsizlik uchun savdo to'xtaydi (EA 6 soatda yangilaydi)

# Python <-> MT5 fayl-ko'prik papkasi (BridgeEA shu yerga yozadi)
BRIDGE_DIR = os.path.join(os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files", "bridge")
JOURNAL_DEMO = os.path.join(os.path.dirname(__file__), "journal_xm_demo.db")
JOURNAL_REAL = os.path.join(os.path.dirname(__file__), "journal_xm_real.db")

DB_PATH =os.path.join(os.path.dirname(__file__), "journal.db")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", "0") or 0)   # faqat shu chat botni ishga tushira oladi
TG_LOGIN = os.getenv("TG_LOGIN", "")                                 # "login:<shu>" yozilganda bot tanib oladi
TG_AUTH_FILE = os.path.join(os.path.dirname(__file__), "tg_auth.json")
