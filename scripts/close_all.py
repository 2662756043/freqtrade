"""平掉 OKX 模拟盘全部持仓。

- freqtrade 管理的仓位：POST /api/v1/forceexit (市价)
- bot 未跟踪的仓位：直接调 OKX 私有接口下市价平仓单（绕开 load_markets）

用法：
    D:\\Python\\Python314\\python.exe -X utf8 -c "import glob,runpy; runpy.run_path(glob.glob('d:/*/freqtrade/scripts/close_all.py')[0], run_name='__main__')"
"""

import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8080/api/v1"
USERNAME = "admin"
PASSWORD = "guo15132080179"
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


def okx_positions(ex):
    """用私有接口查持仓，不依赖 load_markets。"""
    r = ex.privateGetAccountPositions({"instType": "SWAP"})
    out = {}
    for p in r.get("data", []):
        pos = float(p.get("pos") or 0)
        if pos != 0:
            out[p["instId"]] = p
    return out


def close_okx_position(ex, inst_id: str, pos_data: dict):
    """下市价平仓单。"""
    pos_side = pos_data.get("posSide", "long")
    sz = pos_data.get("pos")
    side = "sell" if pos_side == "long" else "buy"
    return ex.privatePostTradeOrder(
        {
            "instId": inst_id,
            "tdMode": "isolated",
            "side": side,
            "posSide": pos_side,
            "ordType": "market",
            "sz": sz,
        }
    )


def main() -> None:
    fh = _OUT.open("w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, fh)
    sys.stderr = _Tee(sys.__stderr__, fh)

    print("=" * 80)
    print("平掉 OKX 模拟盘全部持仓")
    print("=" * 80)

    # ---- 1. bot 管理的仓位 ----
    print("\n[1] freqtrade 管理的仓位 -> forceexit (市价)")
    code, resp = req("POST", "/token/login", basic=True)
    if code != 200 or not isinstance(resp, dict) or "access_token" not in resp:
        print("   登录失败: %s %s" % (code, resp))
        return
    token = resp["access_token"]

    code, trades = req("GET", "/status", token=token)
    if code != 200:
        print("   获取持仓失败: %s %s" % (code, trades))
        return
    open_trades = [t for t in trades if t.get("is_open")]
    if not open_trades:
        print("   (bot 无持仓)")
    for t in open_trades:
        tid, pair = t["trade_id"], t["pair"]
        print("   -> trade #%s (%s) 市价平仓..." % (tid, pair), end=" ")
        code, res = req(
            "POST", "/forceexit", {"tradeid": str(tid), "ordertype": "market"}, token=token
        )
        if code == 200:
            print("OK: %s" % res)
        else:
            print("FAIL %s: %s" % (code, res))

    # ---- 2. bot 未跟踪的仓位 ----
    print("\n[2] 交易所剩余持仓 (bot 未跟踪的) -> 直接 OKX 市价平仓")
    ex = build_client()
    remaining = okx_positions(ex)
    if not remaining:
        print("   (交易所无剩余持仓)")
    for inst_id, p in sorted(remaining.items()):
        print(
            "   -> %s  %s %s 张  市价平仓..."
            % (inst_id, p.get("posSide"), p.get("pos")),
            end=" ",
        )
        try:
            res = close_okx_position(ex, inst_id, p)
            ok = res.get("code") == "0"
            print("OK" if ok else "resp=%s" % json.dumps(res, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            print("FAIL: %s: %s" % (type(e).__name__, e))

    # ---- 3. 等待成交，验证 ----
    print("\n[3] 等待 3 秒后验证...")
    time.sleep(3)
    remaining = okx_positions(ex)
    if remaining:
        print("   仍有持仓:")
        for inst_id, p in sorted(remaining.items()):
            print("      %s  %s %s 张" % (inst_id, p.get("posSide"), p.get("pos")))
    else:
        print("   全部平仓完成，交易所无持仓")

    code, trades = req("GET", "/status", token=token)
    if code == 200:
        open_trades = [t for t in trades if t.get("is_open")]
        if open_trades:
            print("   bot 仍有 open trades:")
            for t in open_trades:
                print("      #%s %s" % (t["trade_id"], t["pair"]))
        else:
            print("   bot 无 open trades")

    usdt = ex.fetch_balance({"type": "swap"}).get("USDT", {})
    print("   USDT free=%s total=%s" % (usdt.get("free"), usdt.get("total")))
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
