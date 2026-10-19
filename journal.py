"""SQLite jurnal: har bir bitim va uning tahlili. Har bitim alohida qator: o'z chiptasi (ticket) va turi (swing/scalp)."""
import json
import sqlite3
import config as C

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT, market TEXT, side TEXT,
  entry_time TEXT, entry REAL, sl REAL, tp REAL, qty REAL, risk_amount REAL,
  status TEXT DEFAULT 'open',
  exit_time TEXT, exit REAL, pnl REAL, fees REAL, exit_reason TEXT,
  ctx TEXT, postmortem TEXT
);
"""


class Journal:
    def __init__(self, path=None):
        self.db = sqlite3.connect(path or C.DB_PATH, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(trades)")]
        if "ticket" not in cols:
            self.db.execute("ALTER TABLE trades ADD COLUMN ticket INTEGER")
        if "kind" not in cols:
            self.db.execute("ALTER TABLE trades ADD COLUMN kind TEXT DEFAULT 'swing'")
        self.db.commit()

    def open_position(self, symbol, kind=None):
        """Shu simvoldagi ochiq bitim (kind berilsa — faqat shu turdagisi)."""
        q, a = "SELECT * FROM trades WHERE status='open' AND symbol=?", [symbol]
        if kind:
            q, a = q + " AND COALESCE(kind,'swing')=?", a + [kind]
        r = self.db.execute(q, a).fetchone()
        return dict(r) if r else None

    def open_positions(self, kind=None):
        q, a = "SELECT * FROM trades WHERE status='open'", []
        if kind:
            q, a = q + " AND COALESCE(kind,'swing')=?", [kind]
        return [dict(r) for r in self.db.execute(q, a)]

    def open_risk(self):
        """Hozir ochiq bitimlarning jami riski (USD)."""
        r = self.db.execute("SELECT COALESCE(SUM(risk_amount),0) FROM trades WHERE status='open'").fetchone()
        return r[0]

    def open_trade(self, symbol, market, sig, ts, qty, risk_amount, ticket=None):
        kind = sig["ctx"].get("kind", "swing")
        self.db.execute(
            "INSERT INTO trades(symbol,market,side,entry_time,entry,sl,tp,qty,risk_amount,ctx,ticket,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (symbol, market, sig["side"], str(ts), sig["entry"], sig["sl"], sig["tp"], qty, risk_amount, json.dumps(sig["ctx"]), ticket, kind),
        )
        self.db.commit()

    def update_sl(self, trade_id, sl):
        self.db.execute("UPDATE trades SET sl=? WHERE id=?", (sl, trade_id))
        self.db.commit()

    def close_trade(self, trade_id, ts, price, pnl, fees, reason, postmortem):
        self.db.execute(
            "UPDATE trades SET status='closed',exit_time=?,exit=?,pnl=?,fees=?,exit_reason=?,postmortem=? WHERE id=?",
            (str(ts), price, pnl, fees, reason, postmortem, trade_id),
        )
        self.db.commit()

    def closed(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM trades WHERE status='closed' ORDER BY exit_time")]

    def pnl_on_day(self, day):
        r = self.db.execute("SELECT COALESCE(SUM(pnl),0) FROM trades WHERE status='closed' AND substr(exit_time,1,10)=?", (day,)).fetchone()
        return r[0]

    def equity(self):
        r = self.db.execute("SELECT COALESCE(SUM(pnl),0) FROM trades WHERE status='closed'").fetchone()
        return C.START_EQUITY + r[0]
