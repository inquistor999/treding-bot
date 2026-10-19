//+------------------------------------------------------------------+
//| BridgeEA: Python bilan fayl orqali ishlaydigan ijrochi robot.      |
//| Tahlil Pythonda, bu robot faqat: shamlarni eksport qiladi,         |
//| buyruq bo'yicha bitim ochadi/yopadi va natijani qaytaradi.         |
//| Fayllar: Common\Files\bridge\                                      |
//+------------------------------------------------------------------+
#property copyright "trading_bot"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

input string AllowedMode  = "demo";   // faqat shu turdagi hisobda savdo qiladi: demo yoki real
input string SymbolsList  = "EURUSD,GBPUSD,USDJPY,AUDUSD,GOLD,BTCUSD,ETHUSD";
input long   MagicNumber  = 770077;
input double MaxRiskPct   = 2.0;      // bitimga ruxsat etilgan eng katta risk (balansning %)
input int    DeviationPts = 20;
input int    BarsExport   = 500;
input int    HistoryDays  = 30;
input int    MaxCmdAgeSec = 120;      // eski buyruqlar bajarilmaydi
input int    CalendarMinImportance = 2; // kalendar: 2 = o'rta va yuqori, 3 = faqat yuqori

const string DIR = "bridge\\";

CTrade   trade;
string   g_syms[];
datetime g_lastBar[];
datetime g_lastBar15[];
int      g_tick = 0;

//--- yordamchilar -------------------------------------------------
string ModeStr()
{
   long m = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(m == ACCOUNT_TRADE_MODE_DEMO) return "demo";
   if(m == ACCOUNT_TRADE_MODE_REAL) return "real";
   return "contest";
}

bool TradingAllowed()
{
   return ModeStr() == AllowedMode
       && (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)
       && (bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)
       && (bool)MQLInfoInteger(MQL_TRADE_ALLOWED);
}

bool WriteAtomic(const string name, const string text)
{
   string tmp = DIR + name + ".tmp";
   int h = FileOpen(tmp, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return false;
   FileWriteString(h, text);
   FileClose(h);
   return FileMove(tmp, FILE_COMMON, DIR + name, FILE_COMMON | FILE_REWRITE);
}

int ReadLines(const string name, string &lines[])
{
   ArrayResize(lines, 0);
   int h = FileOpen(DIR + name, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if(h == INVALID_HANDLE) return 0;
   int n = 0;
   while(!FileIsEnding(h))
   {
      string s = FileReadString(h);
      StringTrimLeft(s);
      StringTrimRight(s);
      if(StringLen(s) == 0) continue;
      ArrayResize(lines, n + 1);
      lines[n++] = s;
   }
   FileClose(h);
   return n;
}

string Get(const string &L[], const string key)
{
   string p = key + "=";
   for(int i = 0; i < ArraySize(L); i++)
      if(StringFind(L[i], p) == 0) return StringSubstr(L[i], StringLen(p));
   return "";
}

bool IsListed(const string sym)
{
   for(int i = 0; i < ArraySize(g_syms); i++)
      if(g_syms[i] == sym) return true;
   return false;
}

// Robotning shu simvoldagi pozitsiyasi (tanlangan holatda qoladi). 0 — yo'q.
ulong FindPos(const string sym)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == sym && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         return t;
   }
   return 0;
}

// Robotning shu simvoldagi ENG YANGI pozitsiyasi (tanlangan holatda qoladi). 0 — yo'q.
ulong NewestPos(const string sym)
{
   ulong best = 0;
   long bestT = -1;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != sym || PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      long tm = PositionGetInteger(POSITION_TIME_MSC);
      if(tm > bestT) { bestT = tm; best = t; }
   }
   if(best != 0) PositionSelectByTicket(best);
   return best;
}

string ReasonStr(const long r)
{
   switch((int)r)
   {
      case DEAL_REASON_CLIENT:   return "CLIENT";
      case DEAL_REASON_MOBILE:   return "MOBILE";
      case DEAL_REASON_WEB:      return "WEB";
      case DEAL_REASON_EXPERT:   return "EXPERT";
      case DEAL_REASON_SL:       return "SL";
      case DEAL_REASON_TP:       return "TP";
      case DEAL_REASON_SO:       return "SO";
   }
   return "OTHER";
}

string Err(const string msg) { return "status=error\nmessage=" + msg + "\n"; }

//--- buyruqlar ----------------------------------------------------
string DoOpen(const string &L[])
{
   string sym   = Get(L, "symbol");
   string side  = Get(L, "side");
   double risk  = StringToDouble(Get(L, "risk_amount"));
   double slD   = StringToDouble(Get(L, "sl_dist"));
   double tpD   = StringToDouble(Get(L, "tp_dist"));

   if(!TradingAllowed())  return Err("savdo ruxsat etilmagan (hisob turi/algo tugmasi)");
   if(!IsListed(sym))     return Err("simvol ro'yxatda yo'q: " + sym);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   if(risk <= 0 || risk > bal * MaxRiskPct / 100.0 * 1.001) return Err("risk limitdan oshdi");
   // Bir simvolda bir nechta bitim mumkin (hedge hisob): har biri o'z chiptasi bilan mustaqil. Dublikatni Python nazorat qiladi.
   if((ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(sym, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL)
      return Err("bozor yopiq yoki savdo cheklangan");

   MqlTick tick;
   if(!SymbolInfoTick(sym, tick) || tick.ask <= 0 || tick.bid <= 0) return Err("narx yo'q");
   bool   isBuy  = (side == "long");
   double price  = isBuy ? tick.ask : tick.bid;
   int    digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double pt     = SymbolInfoDouble(sym, SYMBOL_POINT);
   double minD   = (SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) + SymbolInfoInteger(sym, SYMBOL_SPREAD)) * pt;
   if(slD <= minD || tpD <= minD) return Err("SL/TP masofasi broker minimumidan kichik");

   double sl = NormalizeDouble(isBuy ? price - slD : price + slD, digits);
   double tp = NormalizeDouble(isBuy ? price + tpD : price - tpD, digits);

   double profit = 0;
   if(!OrderCalcProfit(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, sym, 1.0, price, sl, profit) || profit == 0)
      return Err("lot hisoblab bo'lmadi");
   double lossPerLot = MathAbs(profit);

   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double lots = MathFloor(risk / lossPerLot / step + 1e-9) * step;
   if(lots > vmax) lots = vmax;
   if(lots < vmin) return Err("minimal lot riskdan oshadi");
   lots = NormalizeDouble(lots, 8);

   // Marja tekshiruvi: kerakli marja bo'sh marjaning 80% idan oshsa, bitim ochilmaydi (hisob "yonib ketmasin")
   double margin = 0;
   if(OrderCalcMargin(isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, sym, lots, price, margin)
      && margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.8)
      return Err("marja yetarli emas: kerak " + DoubleToString(margin, 2) + ", bo'sh " +
                 DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2));

   trade.SetTypeFillingBySymbol(sym);
   string cmt = Get(L, "comment");              // MT5 ro'yxatida ko'rinadi: bot-swing / bot-scalp
   if(cmt == "") cmt = "bot";
   if(StringLen(cmt) > 25) cmt = StringSubstr(cmt, 0, 25);
   bool ok = isBuy ? trade.Buy(lots, sym, 0.0, sl, tp, cmt) : trade.Sell(lots, sym, 0.0, sl, tp, cmt);
   uint rc = trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
      return Err("order rad etildi: " + IntegerToString(rc) + " " + trade.ResultRetcodeDescription());

   ulong ot = trade.ResultOrder();
   ulong t = 0;
   if(ot > 0 && PositionSelectByTicket(ot)) t = ot;   // hedge: pozitsiya chiptasi = ochgan order chiptasi
   else t = NewestPos(sym);
   if(t == 0) return Err("order bajarildi, lekin pozitsiya topilmadi");
   long   pid   = PositionGetInteger(POSITION_IDENTIFIER);
   double popen = PositionGetDouble(POSITION_PRICE_OPEN);
   double psl   = PositionGetDouble(POSITION_SL);
   double ptp   = PositionGetDouble(POSITION_TP);
   double plots = PositionGetDouble(POSITION_VOLUME);
   return "status=ok\nposition=" + IntegerToString(pid)
        + "\nprice=" + DoubleToString(popen, digits)
        + "\nlots=" + DoubleToString(plots, 8)
        + "\nsl=" + DoubleToString(psl, digits)
        + "\ntp=" + DoubleToString(ptp, digits)
        + "\nrisk=" + DoubleToString(plots * lossPerLot, 2) + "\n";
}

string DoClose(const string &L[])
{
   long pid = StringToInteger(Get(L, "position"));
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_IDENTIFIER) == pid && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
      {
         trade.SetTypeFillingBySymbol(PositionGetString(POSITION_SYMBOL));
         bool ok = trade.PositionClose(t, DeviationPts);
         uint rc = trade.ResultRetcode();
         if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
            return Err("yopilmadi: " + IntegerToString(rc) + " " + trade.ResultRetcodeDescription());
         return "status=ok\n";
      }
   }
   return Err("pozitsiya topilmadi");
}

void HandleCommand(const string fname)
{
   string L[];
   int n = ReadLines(fname, L);
   FileDelete(DIR + fname, FILE_COMMON);
   if(n == 0) return;

   string id = Get(L, "id");
   if(id == "") return;
   long ts = StringToInteger(Get(L, "ts"));
   string res;
   if(MathAbs((long)TimeGMT() - ts) > MaxCmdAgeSec)
      res = Err("buyruq eskirgan");
   else
   {
      string act = Get(L, "action");
      if(act == "open")       res = DoOpen(L);
      else if(act == "close") res = DoClose(L);
      else                    res = Err("noma'lum action");
   }
   WriteAtomic("res_" + id + ".txt", res);
}

void ProcessCommands()
{
   string fname;
   long h = FileFindFirst(DIR + "cmd_*.txt", fname, FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   string names[];
   int n = 0;
   do { ArrayResize(names, n + 1); names[n++] = fname; } while(FileFindNext(h, fname));
   FileFindClose(h);
   for(int i = 0; i < n; i++) HandleCommand(names[i]);
}

//--- eksport ------------------------------------------------------
void WriteAccount()
{
   string s = "login=" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))
            + "\nserver=" + AccountInfoString(ACCOUNT_SERVER)
            + "\nmode=" + ModeStr()
            + "\ncurrency=" + AccountInfoString(ACCOUNT_CURRENCY)
            + "\nbalance=" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2)
            + "\nequity=" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2)
            + "\nserver_time=" + IntegerToString((long)TimeCurrent())
            + "\ngmt=" + IntegerToString((long)TimeGMT())
            + "\nconnected=" + IntegerToString((int)TerminalInfoInteger(TERMINAL_CONNECTED))
            + "\nopen_positions_all=" + IntegerToString(PositionsTotal())
            + "\ntrading_allowed=" + (TradingAllowed() ? "1" : "0")
            + "\nallowed_mode=" + AllowedMode + "\n";
   WriteAtomic("account.txt", s);
}

void WritePositions()
{
   string s = "";
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      s += IntegerToString(PositionGetInteger(POSITION_IDENTIFIER)) + ","
         + PositionGetString(POSITION_SYMBOL) + ","
         + IntegerToString(PositionGetInteger(POSITION_TYPE)) + ","
         + DoubleToString(PositionGetDouble(POSITION_VOLUME), 8) + ","
         + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), 8) + ","
         + DoubleToString(PositionGetDouble(POSITION_SL), 8) + ","
         + DoubleToString(PositionGetDouble(POSITION_TP), 8) + ","
         + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + "\n";
   }
   WriteAtomic("positions.csv", s);
}

void WriteDeals()
{
   datetime to   = TimeCurrent() + 86400;
   datetime from = to - (datetime)(HistoryDays * 86400);
   if(!HistorySelect(from, to)) return;
   int total = HistoryDealsTotal();
   string s = "";
   for(int i = 0; i < total; i++)
   {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0) continue;
      long type = HistoryDealGetInteger(t, DEAL_TYPE);
      if(type != DEAL_TYPE_BUY && type != DEAL_TYPE_SELL) continue;
      s += IntegerToString(HistoryDealGetInteger(t, DEAL_POSITION_ID)) + ","
         + IntegerToString(HistoryDealGetInteger(t, DEAL_ENTRY)) + ","
         + HistoryDealGetString(t, DEAL_SYMBOL) + ","
         + IntegerToString(HistoryDealGetInteger(t, DEAL_TIME)) + ","
         + DoubleToString(HistoryDealGetDouble(t, DEAL_PRICE), 8) + ","
         + DoubleToString(HistoryDealGetDouble(t, DEAL_PROFIT), 2) + ","
         + DoubleToString(HistoryDealGetDouble(t, DEAL_COMMISSION), 2) + ","
         + DoubleToString(HistoryDealGetDouble(t, DEAL_SWAP), 2) + ","
         + DoubleToString(HistoryDealGetDouble(t, DEAL_FEE), 2) + ","
         + ReasonStr(HistoryDealGetInteger(t, DEAL_REASON)) + "\n";
   }
   WriteAtomic("deals.csv", s);
}

void ExportBars()
{
   for(int i = 0; i < ArraySize(g_syms); i++)
   {
      string sym = g_syms[i];
      datetime bt = (datetime)SeriesInfoInteger(sym, PERIOD_H1, SERIES_LASTBAR_DATE);
      if(bt == 0 || bt == g_lastBar[i]) continue;
      MqlRates r[];
      int got = CopyRates(sym, PERIOD_H1, 0, BarsExport, r);
      if(got <= 0) continue;
      int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
      string s = "";
      for(int k = 0; k < got; k++)
         s += IntegerToString((long)r[k].time) + "," + DoubleToString(r[k].open, digits) + ","
            + DoubleToString(r[k].high, digits) + "," + DoubleToString(r[k].low, digits) + ","
            + DoubleToString(r[k].close, digits) + "," + IntegerToString(r[k].tick_volume) + "\n";
      if(WriteAtomic("bars_" + sym + ".csv", s) && got >= BarsExport / 2)
         g_lastBar[i] = bt;   // tarix yetarli yuklanmagan bo'lsa, keyingi siklda qayta urinadi
   }
}

// Joriy narxlar (spread hisoblash uchun): simvol,bid,ask
void WriteSymbols()
{
   string s = "";
   for(int i = 0; i < ArraySize(g_syms); i++)
   {
      MqlTick t;
      if(!SymbolInfoTick(g_syms[i], t) || t.bid <= 0 || t.ask <= 0) continue;
      s += g_syms[i] + "," + DoubleToString(t.bid, 8) + "," + DoubleToString(t.ask, 8) + "\n";
   }
   WriteAtomic("symbols.csv", s);
}

// MT5 iqtisodiy kalendari: kecha + keyingi 7 kun. Vaqt — server vaqti (TimeCurrent bilan bir xil).
void WriteCalendar()
{
   MqlCalendarValue vals[];
   datetime from = TimeCurrent() - 86400;
   datetime to   = TimeCurrent() + 7 * 86400;
   if(CalendarValueHistory(vals, from, to) <= 0) return;   // hamma davlatlar
   string s = "";
   for(int i = 0; i < ArraySize(vals); i++)
   {
      MqlCalendarEvent ev;
      if(!CalendarEventById(vals[i].event_id, ev)) continue;
      if((int)ev.importance < CalendarMinImportance) continue;
      MqlCalendarCountry c;
      if(!CalendarCountryById(ev.country_id, c)) continue;
      string name = ev.name;
      StringReplace(name, ",", " ");
      s += IntegerToString((long)vals[i].time) + "," + c.currency + ","
         + IntegerToString((int)ev.importance) + "," + name + "\n";
   }
   WriteAtomic("calendar.csv", s);
}

// 15 daqiqalik shamlar (qisqa muddatli "razgon" tahlili uchun)
void ExportBars15()
{
   for(int i = 0; i < ArraySize(g_syms); i++)
   {
      string sym = g_syms[i];
      datetime bt = (datetime)SeriesInfoInteger(sym, PERIOD_M15, SERIES_LASTBAR_DATE);
      if(bt == 0 || bt == g_lastBar15[i]) continue;
      MqlRates r[];
      int got = CopyRates(sym, PERIOD_M15, 0, 400, r);
      if(got <= 0) continue;
      int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
      string s = "";
      for(int k = 0; k < got; k++)
         s += IntegerToString((long)r[k].time) + "," + DoubleToString(r[k].open, digits) + ","
            + DoubleToString(r[k].high, digits) + "," + DoubleToString(r[k].low, digits) + ","
            + DoubleToString(r[k].close, digits) + "," + IntegerToString(r[k].tick_volume) + "\n";
      if(WriteAtomic("bars15_" + sym + ".csv", s) && got >= 200)
         g_lastBar15[i] = bt;
   }
}

//--- hayot sikli --------------------------------------------------
int OnInit()
{
   string raw[];
   int n = StringSplit(SymbolsList, ',', raw);
   ArrayResize(g_syms, n);
   ArrayResize(g_lastBar, n);
   ArrayResize(g_lastBar15, n);
   for(int i = 0; i < n; i++)
   {
      StringTrimLeft(raw[i]);
      StringTrimRight(raw[i]);
      g_syms[i] = raw[i];
      g_lastBar[i] = 0;
      g_lastBar15[i] = 0;
      SymbolSelect(g_syms[i], true);
   }
   FolderCreate("bridge", FILE_COMMON);
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(DeviationPts);
   EventSetTimer(1);
   Print("BridgeEA ishga tushdi. Hisob turi: ", ModeStr(), " | ruxsat etilgan: ", AllowedMode);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
{
   g_tick++;
   WriteAccount();
   ProcessCommands();
   WritePositions();
   if(g_tick % 5 == 0)  WriteDeals();
   if(g_tick % 2 == 0)  WriteSymbols();
   if(g_tick % 3 == 0)  { ExportBars(); ExportBars15(); }
   // Kalendar so'rovi MT5 serveriga murojaat qiladi va qotib qolishi mumkin: faqat boshida va 6 soatda bir marta
   if(g_tick == 4 || g_tick % 21600 == 0) WriteCalendar();
}
