"""查询 OKX 模拟盘持仓，并通过 freqtrade REST API 调整保证金。

对比「交易所实际持仓」与「freqtrade 管理的持仓」；bot 未跟踪的仓位直接走
交易所私有接口处理（freqtrade 不会接管交易所上已存在的仓位）。

用法：
    D:\\Python\\Python314\\python.exe -X utf8 -c "import glob,runpy; runpy.run_path(glob.glob('d:/*/freqtrade/scripts/margin_api_test.py')[0], run_name='__main__')" [amount]
    amount > 0 加保证金, amount < 0 减保证金, 0 = 只查询, 缺省 20
"""

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8080/api/v1"
USERNAME = "admin"
PASSWORD = "guo15132080179"
AMOUNT = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0

CONFIG = Path(__file__).resolve().parents[1] / "user_data/config_okx_futures_local.json"
_OUT = Path(__file__).resolve().with_suffix(".out.txt")


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def req(method, path, data=None, token=None, basic=False):
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(BASE + path, data=body, method=method)
    request.add_header("Content-Type", "application/json")
    if basic:
        creds = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
        request.add_header("Authorization", f"Basic {creds}")
    elif token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def build_client():
    import ccxt

    conf = json.loads(CONFIG.read_text(encoding="utf-8"))["exchange"]
    c = conf.get("ccxt_config", {})
    ex = ccxt.okx(
        {
            "apiKey": conf["key"],
            "secret": conf["secret"],
            "password": conf["password"],
            "enableRateLimit": True,
            "httpsProxy": c.get("httpsProxy"),
            "wssProxy": c.get("wssProxy"),
            "options": c.get("options", {"defaultType": "swap"}),
        }
    )
    ex.set_sandbox_mode(bool(c.get("sandbox", False)))
    return ex


def open_positions(ex):
    return {
        p["symbol"]: p
        for p in ex.fetch_positions()
        if float(p.get("contracts") or 0) != 0
    }


def raw_adjust_margin(ex, symbol: str, amount: float):
    """绕过 freqtrade/bot，直接调交易所私有接口（用于 bot 未跟踪的仓位）。"""
    market_id = ex.market(symbol)["id"]
    # fetch_positions expects a list of symbols - passing a plain string would be
    # iterated char by char ("ETH/USDT:USDT" -> "E").
    pos = next(
        (
            p
            for p in ex.fetch_positions([symbol])
            if float(p.get("contracts") or 0) != 0
        ),
        None,
    )
    pos_side = "long" if (pos is None or pos.get("side") == "long") else "short"
    return ex.privatePostAccountPositionMarginBalance(
        {
            "instId": market_id,
            "amt": str(abs(amount)),
            "type": "add" if amount > 0 else "reduce",
            "posSide": pos_side,
        }
    )


def fmt_ex(symbol: str, p: dict) -> str:
    return (
        "   %-16s %-5s 张数=%-8s 名义=%-12.2f 杠杆=%sx 保证金=%-18s 强平价=%s"
        % (
            symbol,
            p.get("side"),
            p.get("contracts"),
            float(p.get("notional") or 0),
            p.get("leverage"),
            p.get("collateral"),
            p.get("liquidationPrice"),
        )
    )


def report_change(symbol: str, before: dict, after: dict, label: str) -> None:
    b_col, a_col = before.get("collateral"), after.get("collateral")
    b_liq, a_liq = before.get("liquidationPrice"), after.get("liquidationPrice")
    print("      %s: 保证金 %s -> %s" % (label, b_col, a_col))
    if b_col and a_col and b_liq and a_liq:
        print(
            "      保证金变化 %+.4f | 强平价 %.4f -> %.4f (%+.4f)"
            % (
                float(a_col) - float(b_col),
                float(b_liq),
                float(a_liq),
                float(a_liq) - float(b_liq),
            )
        )
    else:
        print("      强平价 %s -> %s" % (b_liq, a_liq))


def main() -> None:
    fh = _OUT.open("w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, fh)
    sys.stderr = _Tee(sys.__stderr__, fh)

    print("=" * 84)
    print("OKX 模拟盘 持仓 / 保证金   调整金额 = %s USDT" % AMOUNT)
    print("=" * 84)

    ex = build_client()

    print("\n[1] 交易所实际持仓 (直接查 OKX)")
    ex_pos = open_positions(ex)
    usdt = ex.fetch_balance({"type": "swap"}).get("USDT", {})
    for sym, p in sorted(ex_pos.items()):
        print(fmt_ex(sym, p))
    print("   USDT free=%s used=%s total=%s" % (usdt.get("free"), usdt.get("used"), usdt.get("total")))

    code, resp = req("POST", "/token/login", basic=True)
    if code != 200 or not isinstance(resp, dict) or "access_token" not in resp:
        print("登录失败: %s %s" % (code, resp))
        return
    token = resp["access_token"]

    code, trades = req("GET", "/status", token=token)
    if code != 200:
        print("获取持仓失败: %s %s" % (code, trades))
        return
    open_trades = [t for t in trades if t.get("is_open")]

    print("\n[2] freqtrade 管理的持仓 (bot 数据库)")
    for t in open_trades:
        print(
            "   id=%-4s %-16s %-5s 杠杆=%-4s 保证金=%-12s 强平价=%-20s 名义=%s"
            % (
                t.get("trade_id"),
                t.get("pair"),
                "short" if t.get("is_short") else "long",
                t.get("leverage"),
                t.get("stake_amount"),
                t.get("liquidation_price"),
                t.get("open_trade_value"),
            )
        )

    ft_pairs = {t["pair"] for t in open_trades}
    missing = [s for s in ex_pos if s not in ft_pairs]
    print("\n[3] 差异")
    if missing:
        print("    交易所有、bot 未跟踪: %s" % ", ".join(missing))
        print("    -> 这些仓位不在 freqtrade 数据库，只能通过交易所接口直接调整。")
    else:
        print("    无差异，交易所持仓与 bot 持仓一致")

    if AMOUNT == 0:
        print("\n(amount=0，只查询不调整)")
        return

    print("\n[4] 通过 freqtrade API 调整 (bot 跟踪的仓位)")
    for t in open_trades:
        trade_id, pair = t["trade_id"], t["pair"]
        before = ex_pos.get(pair, {})
        print("\n   -> trade #%s (%s)" % (trade_id, pair))
        code, res = req("POST", f"/trades/{trade_id}/margin", {"amount": AMOUNT}, token=token)
        if code != 200:
            print("      失败 HTTP %s: %s" % (code, res))
            continue
        after = open_positions(ex).get(pair, {})
        report_change(pair, before, after, "交易所侧")
        print("      bot 记录强平价: %s -> %s" % (t.get("liquidation_price"), res.get("liquidation_price")))

    if missing:
        print("\n[5] 直接调交易所接口调整 (bot 未跟踪的仓位)")
        for sym in missing:
            before = ex_pos.get(sym, {})
            print("\n   -> %s" % sym)
            try:
                res = raw_adjust_margin(ex, sym, AMOUNT)
                print("      响应: %s" % json.dumps(res, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001
                print("      失败: %s: %s" % (type(e).__name__, e))
                continue
            report_change(sym, before, open_positions(ex).get(sym, {}), "交易所侧")

    print("\n" + "=" * 84)


if __name__ == "__main__":
    main()
