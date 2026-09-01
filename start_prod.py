"""
启动 OKX 模拟盘滚仓交易 (NfiDcaX7ProMaxV4) —— 便携版 (路径不写死)
- 放在 freqtrade 根目录, 用装了 freqtrade 的 python 运行: `python start_prod.py`
- pythonw 自动探测: 优先取当前 python 同目录的 pythonw.exe, 其次 PATH, 无需改代码
- OKX 密钥/代理全部从 config 读取, 脚本里不出现任何密钥或绝对路径
- 启动前自动检测 OKX 连通性 (sandbox 与否跟随 config)
- 用 pythonw 后台拉起 freqtrade, 无控制台窗口, 日志按日期写 user_data/logs/
- 如需停止: 命令行 `taskkill /pid <PID> /f`
"""
import subprocess
import datetime
import json
import os
import sys
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "user_data", "config_okx_futures_local.json")
STRATEGY = "NfiDcaX7ProMaxV4"
LOG_DIR = os.path.join(BASE, "user_data", "logs")
CARDS_OUT = os.path.join(BASE, "user_data", "_config_with_cards.json")


def find_pythonw():
    """自动找 pythonw: 当前解释器同目录 -> PATH -> 退回当前解释器 (会有窗口但能跑)"""
    cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if os.path.exists(cand):
        return cand
    found = shutil.which("pythonw.exe")
    if found:
        return found
    print("[start_prod] 未找到 pythonw.exe, 退回用当前 python 启动 (会显示窗口)")
    return sys.executable


def build_config():
    """读 config, 把外部卡片文件 (feishu_cards.json) 注入 webhook 段, 写出临时 config 供 freqtrade 使用。"""
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    cards_file = cfg.get("webhook", {}).get("_cards_file")
    if cards_file:
        cards_path = os.path.join(BASE, cards_file)
        with open(cards_path, encoding="utf-8") as f:
            cards = json.load(f)
        cfg["webhook"].pop("_cards_file", None)
        for k, v in cards.items():
            cfg["webhook"][k] = v
    with open(CARDS_OUT, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return CARDS_OUT


def check_okx(cfg):
    """启动前检测 OKX 连通性, 密钥/代理/sandbox 全部跟随 config"""
    ex = cfg.get("exchange", {})
    if not ex.get("key"):
        print("[start_prod] config 中未填写 exchange.key, 无法连通性检查")
        return False
    ccfg = ex.get("ccxt_config", {})
    try:
        import ccxt
        okx = ccxt.okx({
            "apiKey": ex.get("key", ""),
            "secret": ex.get("secret", ""),
            "password": ex.get("password", ""),
            "enableRateLimit": True,
            "httpsProxy": ccfg.get("httpsProxy", ""),
            "options": {"defaultType": "swap"},
        })
        if ccfg.get("sandbox", False):
            okx.set_sandbox_mode(True)
        r = okx.fetch_balance({"type": "swap"})
        usdt = r.get("USDT", {}).get("total", 0)
        mode = "模拟盘" if ccfg.get("sandbox", False) else "实盘"
        print(f"[start_prod] OKX {mode}连通, 余额 = {usdt} USDT")
        return True
    except Exception as e:
        print(f"[start_prod] 连通性检查失败: {e}")
        proxy = ccfg.get("httpsProxy", "无")
        print(f"[start_prod] 请确认: 1) 代理({proxy})是否可用  2) config 中 OKX key 是否有效")
        return False


def main():
    os.makedirs(LOG_DIR, exist_ok=True)

    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    if not check_okx(cfg):
        print("[start_prod] 未通过连通性检查, 已退出。请修复后重试。")
        sys.exit(1)

    # 生成注入了飞书卡片样式的临时 config
    cfg_to_use = build_config()

    today = datetime.date.today().strftime("%Y-%m-%d")
    logfile = os.path.join(LOG_DIR, f"freqtrade_sim_{today}.log")

    cmd = [
        find_pythonw(), "-m", "freqtrade", "trade",
        "--config", cfg_to_use,
        "--strategy", STRATEGY,
        "--logfile", logfile,
    ]

    # PYTHONUTF8=1: 让 freqtrade 以 UTF-8 读取配置 (Windows 默认 GBK 会导致含中文/emoji 的 config 启动崩溃)
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    with open(logfile, "a", encoding="utf-8") as lf:
        lf.write(f"\n===== 后台启动(无窗口) {datetime.datetime.now()} =====\n")
        proc = subprocess.Popen(
            cmd,
            stdout=lf,
            stderr=subprocess.STDOUT,
            close_fds=True,
            env=env,
            cwd=BASE,
        )
    print(f"[start_prod] 已后台启动(无窗口) -> 策略={STRATEGY}  PID={proc.pid}")
    print(f"[start_prod] 日志: {logfile}")
    print(f"[start_prod] 停止: taskkill /pid {proc.pid} /f")


if __name__ == "__main__":
    main()
