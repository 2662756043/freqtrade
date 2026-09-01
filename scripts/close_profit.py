import ccxt, json

with open(r"d:\量化分析软件\freqtrade\user_data\config_okx_futures_local.json", encoding="utf-8") as f:
    cfg = json.load(f)
ex = cfg["exchange"]

okx = ccxt.okx({
    "apiKey": ex["key"],
    "secret": ex["secret"],
    "password": ex["password"],
    "enableRateLimit": True,
    "httpsProxy": ex["ccxt_config"]["httpsProxy"],
    "options": {"defaultType": "swap"},
})
okx.set_sandbox_mode(True)

# 先查当前持仓, 找出盈利超的 (这里: SOL 收益率 9.46% 视为超, ETH 1.63% 不超)
pos = okx.fetch_positions([p for p in ex["pair_whitelist"]])
open_pos = [p for p in pos if float(p.get("contracts") or 0) != 0]

THRESHOLD = 5.0  # 盈利超阈值: 收益率>5% 视为"盈利超"
to_close = []
for p in open_pos:
    notional = float(p["notional"])
    upl = float(p.get("unrealizedPnl") or 0)
    ratio = (upl / notional * 100) if notional else 0
    if ratio > THRESHOLD:
        to_close.append((p["symbol"], ratio, float(p["contracts"])))

if not to_close:
    print("没有盈利超的持仓, 无需平仓。")
else:
    for sym, ratio, contracts in to_close:
        print(f"平仓 {sym} 收益率={ratio:.2f}% 张数={contracts}")
        # 反向市价平掉全部
        side = "sell" if contracts > 0 else "buy"
        okx.create_order(
            symbol=sym,
            type="market",
            side=side,
            amount=abs(contracts),
            params={"reduceOnly": True, "tdMode": "isolated"},
        )
        print(f"  -> 已提交平仓单 {sym} {side} {abs(contracts)}")
    print("平仓完成。")
