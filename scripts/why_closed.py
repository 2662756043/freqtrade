import ccxt, json, os, sqlite3
from datetime import datetime, timezone

with open(r"d:\量化分析软件\freqtrade\user_data\config_okx_futures_local.json", encoding="utf-8") as f:
    cfg = json.load(f)
ex = cfg["exchange"]
okx = ccxt.okx({
    "apiKey": ex["key"], "secret": ex["secret"], "password": ex["password"],
    "enableRateLimit": True, "httpsProxy": ex["ccxt_config"]["httpsProxy"],
    "options": {"defaultType": "swap"},
})
okx.set_sandbox_mode(True)

# 1) 交易所真实持仓
bal = okx.fetch_balance({"type": "swap"})
print("USDT total:", round(bal.get("USDT", {}).get("total", 0), 4))
pos = okx.fetch_positions([p for p in ex["pair_whitelist"]])
op = [p for p in pos if float(p.get("contracts") or 0) != 0]
print("交易所真实持仓数:", len(op))
for p in op:
    print("  ", p["symbol"], p["side"], p["contracts"])

# 2) bot 数据库 trades (看 ETH id=1 是否还 open, 以及最近的 closed trade)
db = r"d:\量化分析软件\freqtrade\tradesv3.sqlite"
con = sqlite3.connect(db); cur = con.cursor()
cur.execute("SELECT id,pair,amount,is_short,leverage,open_rate,close_rate,open_date,close_date,is_open,exit_reason FROM trades ORDER BY id DESC LIMIT 5")
print("\n=== 最近 trades ===")
for r in cur.fetchall():
    print(f"  id={r[0]} {r[1]} amt={r[2]} short={r[3]} lev={r[4]} open={r[5]} close={r[6]} open_date={r[7]} close_date={r[8]} is_open={r[9]} exit={r[10]}")
con.close()

# 3) 日志里最近的 exit / close 关键字
log = r"d:\量化分析软件\freqtrade\user_data\logs\freqtrade_sim_2026-08-28.log"
lines = open(log, encoding="utf-8", errors="replace").readlines()
print("\n=== 日志中含 exit/close/ETH 的最近 25 行 ===")
hits = [l for l in lines if any(k in l for k in ["Exit", "exit", "close", "Close", "ETH/USDT", "sell", "Sell", "force", "Force"])]
for l in hits[-25:]:
    print(l.rstrip())
