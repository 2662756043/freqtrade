"""
启动 OKX 模拟盘滚仓交易 (NfiDcaX7ProMaxV4) —— 后台版
- 放在 freqtrade 根目录, 双击或 `python start_v3.py` 即可
- 启动前自动检测代理 + OKX 模拟盘连通性
- 用 pythonw 后台拉起 freqtrade, 完全无控制台窗口, 不阻塞终端, 父进程打印 PID 后退出
- 日志按日期写入 user_data/logs/freqtrade_sim_YYYY-MM-DD.log
- 如需停止: 任务管理器结束 python.exe (命令行行 `taskkill /pid <PID> /f`)
"""
import subprocess
import datetime
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
# 用 pythonw 启动 -> 完全无控制台窗口 (不会弹出 cmd)
# 注意: 原 .venv 为空, 改用系统 Python314 的 pythonw (已安装 freqtrade)
PYTHONW = r"D:\Python\Python314\pythonw.exe"
CONFIG = os.path.join(BASE, "user_data", "config_okx_futures_local.json")
STRATEGY = "NfiDcaX7ProMaxV4"
LOG_DIR = os.path.join(BASE, "user_data", "logs")


def build_config():
    """读 config, 把外部卡片文件 (feishu_cards.json) 注入 webhook 段, 写出临时 config 供 freqtrade 使用。
    这样卡片样式维护在独立文件, 不必把大段 JSON 塞进 config。"""
    import json
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
    out = os.path.join(BASE, "user_data", "_config_with_cards.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return out


def check_okx():
    """启动前检测代理 + OKX 模拟盘连通性"""
    try:
        import ccxt
        okx = ccxt.okx({
            "apiKey": "c4c79c8a-4566-4a21-b07f-d8d072e3a231",
            "secret": "8BB6D5F46196CEAF28C0FCB33484E7E7",
            "password": "Guo15132080179@",
            "enableRateLimit": True,
            "httpsProxy": "http://127.0.0.1:7890",
            "options": {"defaultType": "swap"},
        })
        okx.set_sandbox_mode(True)
        r = okx.fetch_balance({"type": "swap"})
        usdt = r.get("USDT", {}).get("total", 0)
        print(f"[start_v3] OKX 模拟盘连通, 余额 = {usdt} USDT")
        return True
    except Exception as e:
        print(f"[start_v3] 连通性检查失败: {e}")
        print("[start_v3] 请确认: 1) 代理(127.0.0.1:7890) 是否运行  2) OKX 模拟盘 key 是否有效")
        return False


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    if not check_okx():
        print("[start_v3] 未通过连通性检查, 已退出。请修复后重试。")
        sys.exit(1)

    # 生成注入了飞书卡片样式的临时 config
    cfg_to_use = build_config()

    today = datetime.date.today().strftime("%Y-%m-%d")
    logfile = os.path.join(LOG_DIR, f"freqtrade_sim_{today}.log")

    cmd = [
        PYTHONW, "-m", "freqtrade", "trade",
        "--config", cfg_to_use,
        "--strategy", STRATEGY,
        "--logfile", logfile,
    ]

    # PYTHONUTF8=1: 让 freqtrade 以 UTF-8 读取配置 (Windows 默认 GBK 会导致含中文/emoji 的 config 启动崩溃)
    # pythonw 本身无控制台窗口, 且独立于父进程运行, 不会弹 cmd
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
        )
    print(f"[start_v3] 已后台启动(无窗口) -> 策略={STRATEGY}  PID={proc.pid}")
    print(f"[start_v3] 日志: {logfile}")
    print(f"[start_v3] 停止: taskkill /pid {proc.pid} /f")


if __name__ == "__main__":
    main()
