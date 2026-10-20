"""
启动 OKX NostalgiaForInfinityX8 (NFI X8) —— 跨平台后台启动器
(参照 start_nfix7_demo.py 风格, 并适配 Linux 后台启动)
- 放在 freqtrade 根目录, 用装了 freqtrade 的 python 运行
- 支持两个策略变体, 用 -s/--strategy 切换:
      x8   : NostalgiaForInfinityX8            (原版)
      x84  : NostalgiaForInfinityX8_4        (NostalgiaForInfinityX8_4.py;
             官方 X8 + 每仓 80% 仓位, 留 20% 给 DCA 补仓, 固定 4x 杠杆, 默认)
- 飞书卡片由 config 的 add_config_files 引入 (feishu_cards.json), 启动前连通性检查随 config 的 sandbox / 模拟盘头
- 启动卡片只由 freqtrade 发送: rpc/webhook.py 已合并多条 startup 为 1 条, 脚本不再另发(否则会收 2 张)
- 启动前检测 OKX 连通性 (跟随 config 的 sandbox 开关)
- Linux 后台: 用 start_new_session (setsid) 真正脱离终端, 关掉 SSH 后 bot 继续运行
- Windows 后台: 用 pythonw + DETACHED_PROCESS 无窗口
- 日志按日期写 user_data/logs/, pid 写 user_data/configs/okx/NFlX8/nfi-x8-config/.nfix8_*.pid

用法:
      python  start_nfix8_ghz.py                 # 默认后台启动 x84(NostalgiaForInfinityX8_4)
      python  start_nfix8_ghz.py start  -s x84
      python  start_nfix8_ghz.py stop   -s x84
      python  start_nfix8_ghz.py status -s x84
  (Linux 用 python3; -s 也可直接跟在脚本后无需子命令: python3 start_nfix8_demo.py -s x8)

注意: 原版与 8020 子类共用同一 OKX 账户余额, 同时跑两个进程会相互竞争可用资金,
      建议二选一实盘, 或分别用小资金隔离验证。
"""
import argparse
import subprocess
import datetime
import json
import os
import sys
import shutil
import time
import signal

# 脚本位于 freqtrade/start/ 下, 故 BASE 取上一级即为 freqtrade 根目录
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 实际配置目录 (账户1 = 模拟盘)
CONFIG_DIR = os.path.join(BASE, "user_data", "configs", "okx", "NFlX8", "nfi-x8-config")
CONFIG = os.path.join(CONFIG_DIR, "NostalgiaForInfinityX8.json")
LOG_DIR = os.path.join(BASE, "user_data", "logs")
PID_DIR = CONFIG_DIR
# 策略文件放在 user_data/strategies/NFlX8 子目录, 显式指定避免子目录不被搜索
STRATEGY_DIR = os.path.join(BASE, "user_data", "strategies", "NFlX8")

# -s/--strategy 接受的别名 -> 真实策略类名
# 注意: resolve_strategy 会先把参数转小写再查表, 故这里全部用小写键
STRATEGY_MAP = {
    # 原版: NFlX8/NostalgiaForInfinityX8.py (父类杠杆 3.0)
    "x8": "NostalgiaForInfinityX8",
    "original": "NostalgiaForInfinityX8",
    "nfix8": "NostalgiaForInfinityX8",
    "nostalgiaforinfinityx8": "NostalgiaForInfinityX8",
    # 80/20 子类: NFlX8/NostalgiaForInfinityX8_4.py, 类名 NostalgiaForInfinityX8_4
    # (每仓 80% 留 20% 给 DCA 补仓, 固定 4 倍杠杆) —— 默认启动这个
    "8020": "NostalgiaForInfinityX8_4",
    "nfix8_8020": "NostalgiaForInfinityX8_4",
    "nostalgiaforinfinityx8_8020": "NostalgiaForInfinityX8_4",
    "x84": "NostalgiaForInfinityX8_4",
    "x8_4": "NostalgiaForInfinityX8_4",
    "nostalgiaforinfinityx8_4": "NostalgiaForInfinityX8_4",
}

# 真实策略类名 -> 简短标识(用于 pid 文件名与日志名)
# freqtrade 按"类名"加载, NostalgiaForInfinityX8_4.py 里的类名就是 NostalgiaForInfinityX8_4
SHORT_MAP = {
    "NostalgiaForInfinityX8": "nfix8",
    "NostalgiaForInfinityX8_4": "nfix8_4",
}
# 数据库文件名直接采用 config 中 db_url 的配置(见 start_bot), 不再在此硬编码


def pid_path(short):
    return os.path.join(PID_DIR, f".nfix8_{short}.pid")


def find_pythonw():
    """跨平台取 venv 内的解释器; 等价于在 shell 里先激活项目虚拟环境后再启动:
        Linux  : source .venv/bin/activate  -> 用 .venv/bin/python (或 python3)
        Windows: .venv\\Scripts\\activate    -> 用 .venv\\Scripts\\pythonw.exe (无窗口, 优先) / python.exe
    优先使用 BASE/.venv 下的解释器; 找不到时退回 sys.executable 并打印警告。"""
    if os.name == "nt":
        candidates = [
            os.path.join(BASE, ".venv", "Scripts", "pythonw.exe"),
            os.path.join(BASE, ".venv", "Scripts", "python.exe"),
            os.path.join(os.path.dirname(sys.executable), "pythonw.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        found = shutil.which("pythonw.exe")
        if found:
            return found
        print("[start_nfix8] 未找到 .venv\\Scripts, 退回用当前 python 启动 (会显示窗口)")
        return sys.executable
    # Linux / POSIX
    candidates = [
        os.path.join(BASE, ".venv", "bin", "python"),
        os.path.join(BASE, ".venv", "bin", "python3"),
        os.path.join(os.path.dirname(sys.executable), "python"),
        os.path.join(os.path.dirname(sys.executable), "python3"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    print("[start_nfix8] 未找到 .venv/bin, 退回用当前 python 启动")
    return sys.executable


def build_config(cfg, out_path):
    """读 config, 把外部卡片文件 (feishu_cards.json) 注入 webhook 段, 写出临时 config 供 freqtrade 使用。"""
    cards_file = cfg.get("webhook", {}).get("_cards_file")
    if cards_file:
        cards_path = os.path.join(BASE, cards_file)
        with open(cards_path, encoding="utf-8") as f:
            cards = json.load(f)
        cfg["webhook"].pop("_cards_file", None)
        for k, v in cards.items():
            cfg["webhook"][k] = v
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return out_path


def ensure_db_dir(cfg):
    """sqlite 不会自动创建父目录, 启动前需确保 db 文件所在目录存在, 否则报 unable to open database file。
    db_url 形如 sqlite:///user_data/sqlite/nfi-x7-config/xxx.sqlite -> 相对项目根目录(启动时的 cwd)解析。"""
    db_url = cfg.get("db_url", "")
    prefix = "sqlite:///"
    if not db_url.startswith(prefix):
        return
    rel = db_url[len(prefix):]
    if not rel:
        return
    # 绝对路径: 以 / 开头, 或 Windows 盘符(如 d:/)开头 -> 直接按绝对路径使用
    if rel.startswith("/") or (len(rel) >= 2 and rel[1] == ":"):
        db_path = rel
    else:
        db_path = os.path.join(BASE, *rel.split("/"))
    db_dir = os.path.dirname(db_path)
    os.makedirs(db_dir, exist_ok=True)
    print(f"[start_nfix8] 已确保数据库目录存在: {db_dir}")


def _retry(fn, times=3, what=""):
    """对瞬时网络抖动(代理超时等)做简单重试, 返回 (是否成功, 结果或最后的异常)"""
    last = None
    for i in range(times):
        try:
            return True, fn()
        except Exception as e:
            last = e
            if i < times - 1:
                print(f"[start_nfix8] {what}第 {i + 1} 次失败({type(e).__name__}), 2 秒后重试...")
                time.sleep(2)
    return False, last


def check_okx(cfg):
    """启动前检测 OKX 连通性, 密钥/代理/模拟盘开关全部跟随 config"""
    ex = cfg.get("exchange", {})
    if not ex.get("key"):
        print("[start_nfix8] config 中未填写 exchange.key, 无法连通性检查")
        return False
    ccfg = ex.get("ccxt_config", {})
    headers = dict(ccfg.get("headers", {}))
    try:
        import ccxt
        okx = ccxt.okx({
            "apiKey": ex.get("key", ""),
            "secret": ex.get("secret", ""),
            "password": ex.get("password", ""),
            "enableRateLimit": True,
            "httpsProxy": ccfg.get("httpsProxy", ""),
            "headers": headers,
            "options": {"defaultType": "swap"},
        })
        if ccfg.get("sandbox", False):
            okx.set_sandbox_mode(True)
        is_demo = headers.get("x-simulated-trading") == "1" or ccfg.get("sandbox", False)
        mode = "模拟盘" if is_demo else "实盘"

        # 1) 主连通性证明: 查询余额(模拟盘下真实有效且信息量最大的信号), 重试抗抖动
        ok, res = _retry(lambda: okx.fetch_balance({"type": "swap"}), times=3, what="余额查询")
        if ok:
            usdt = res.get("USDT", {}).get("total", 0)
            print(f"[start_nfix8] OKX {mode}连通正常, 余额 = {usdt} USDT")
            return True
        print(f"[start_nfix8] 余额查询失败: {res}")

        # 2) 兜底: 用公共接口 fetch_time 证明代理连通(模拟盘余额接口可能返回 50038)
        ok2, res2 = _retry(okx.fetch_time, times=3, what="连通性探测")
        if ok2:
            print("[start_nfix8] 代理连通正常, 但余额接口不可用(模拟盘已知限制)。")
            if is_demo:
                print("[start_nfix8] 请到 OKX 网页 -> 模拟交易 -> 给模拟账户划转虚拟 USDT 后再试;")
                print("[start_nfix8] 若 freqtrade 启动仍报余额错误, 机器人将无法正常开仓。")
                return True
            return False

        print(f"[start_nfix8] 连通性检查失败: {res2}")
        proxy = ccfg.get("httpsProxy", "无")
        print(f"[start_nfix8] 请确认: 1) 代理({proxy})是否可用  2) config 中是否为模拟盘 Key")
        return False
    except Exception as e:
        print(f"[start_nfix8] 连通性检查失败: {e}")
        proxy = ccfg.get("httpsProxy", "无")
        print(f"[start_nfix8] 请确认: 1) 代理({proxy})是否可用  2) config 中是否为模拟盘 Key")
        return False


def resolve_strategy(arg):
    key = (arg or "x84").strip().lower()
    if key in STRATEGY_MAP:
        return STRATEGY_MAP[key]
    # 允许直接用实例 short(nfix8 / nfix8_4) 作 -s 来 stop/status, 此时策略类无关紧要
    if key in {v.lower() for v in SHORT_MAP.values()}:
        return STRATEGY_MAP["x84"]
    print(f"[start_nfix8] 未知 --strategy 值: {arg}, 可选: x84(默认,NostalgiaForInfinityX8_4) / x8(原版) / nfix8 / nfix8_4(实例标识)")
    sys.exit(2)


def is_pid_alive(pid):
    """跨平台判断进程存活。
    注意: Windows 上 os.kill(pid, 0) 不可靠 —— 信号 0 对 Windows 是非法参数,
    会抛 OSError(WinError 87 参数错误), 导致活着的进程也被误判为"不存在"
    (进而 status 误报未运行, 并把 pid 文件删掉)。故 Windows 改用 tasklist 检测。"""
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/fi", f"PID eq {pid}"],
                capture_output=True,
            )
            # 用 bytes 比较, 避免中文 Windows 下 gbk 解码问题
            return str(pid).encode() in out.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True   # 进程存在, 只是无权发信号
    except OSError:
        return False  # 进程不存在
    except Exception:
        return False
    return True


def read_pid(short):
    p = pid_path(short)
    if os.path.exists(p):
        try:
            return int(open(p, encoding="utf-8").read().strip())
        except Exception:
            return None
    return None


def write_pid(short, pid):
    with open(pid_path(short), "w", encoding="utf-8") as f:
        f.write(str(pid))


def remove_pid(short):
    try:
        os.remove(pid_path(short))
    except FileNotFoundError:
        pass


def start_bot(strategy, short):
    pid = read_pid(short)
    if pid and is_pid_alive(pid):
        print(f"[start_nfix8] {short} 已在运行 (PID={pid}), 无需重复启动。先 stop 再 start。")
        return
    remove_pid(short)

    os.makedirs(LOG_DIR, exist_ok=True)
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)

    # 数据库路径直接使用 config 中配置的 db_url, 写入配置指定的 sqlite 文件
    print(f"[start_nfix8] 数据库: {cfg.get('db_url', '')}")

    ensure_db_dir(cfg)
    if not check_okx(cfg):
        print("[start_nfix8] 未通过连通性检查, 已退出。请修复后重试。")
        sys.exit(1)

    # 生成注入了飞书卡片样式的临时 config
    cards_out = os.path.join(CONFIG_DIR, f"_config_with_cards_{short}.json")
    cfg_to_use = build_config(cfg, cards_out)

    today = datetime.date.today().strftime("%Y-%m-%d")
    logfile = os.path.join(LOG_DIR, f"freqtrade_{short}_{today}.log")

    py = find_pythonw()
    cmd = [
        py, "-m", "freqtrade", "trade",
        "--config", cfg_to_use,
        "--strategy", strategy,
        "--strategy-path", STRATEGY_DIR,
        "--logfile", logfile,
    ]
    print(f"[start_nfix8] 启动解释器(venv): {py}")

    # PYTHONUTF8=1: 让 freqtrade 以 UTF-8 读取配置 (Windows 默认 GBK 会导致含中文/emoji 的 config 启动崩溃)
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    # 只写一行启动分隔线; 日志本体由 freqtrade 的 --logfile 负责写入
    # (若把 stdout 也重定向到同一个 logfile, 会与 freqtrade 的 file handler 形成两个独立
    #  文件句柄、各自维护偏移量, 导致日志交错/重复甚至互相覆盖)
    with open(logfile, "a", encoding="utf-8") as lf:
        lf.write(f"\n===== NFI X8({short}) 后台启动 {datetime.datetime.now()} =====\n")
    if os.name == "nt":
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            env=env,
            cwd=BASE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    else:
        # Linux: start_new_session=True 相当于 setsid, 让 bot 脱离终端, 关掉 SSH 后继续运行
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            env=env,
            cwd=BASE,
            start_new_session=True,
        )
    write_pid(short, proc.pid)
    print(f"[start_nfix8] 已后台启动 -> 策略={strategy}  PID={proc.pid}")
    print(f"[start_nfix8] 日志: {logfile}")
    # 启动卡片由 freqtrade 自己发: rpc/webhook.py 已把多条 startup 合并成 1 条,
    # 故脚本不再重复发送, 否则飞书会收到 2 张启动卡
    if os.name == "nt":
        print(f"[start_nfix8] 停止: python start_nfix8_demo.py stop -s {short}")
    else:
        print(f"[start_nfix8] 停止: python3 start_nfix8_demo.py stop -s {short}   (或 kill -INT {proc.pid})")


def stop_bot(short):
    pid = read_pid(short)
    if not pid or not is_pid_alive(pid):
        print(f"[start_nfix8] {short} 未在运行。")
        remove_pid(short)
        return
    print(f"[start_nfix8] 正在停止 {short} (PID={pid}) ...")
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/pid", str(pid), "/f"], check=False)
        else:
            os.kill(pid, signal.SIGINT)  # freqtrade 捕获 SIGINT 优雅停机
    except Exception as e:
        print(f"[start_nfix8] 发送停止信号失败: {e}")
    # 等待优雅退出
    for _ in range(30):
        if not is_pid_alive(pid):
            break
        time.sleep(1)
    else:
        print("[start_nfix8] 30s 内未退出, 强制终止...")
        try:
            if os.name != "nt":
                os.kill(pid, signal.SIGKILL)
            else:
                subprocess.run(["taskkill", "/pid", str(pid), "/f"], check=False)
        except Exception:
            pass
    remove_pid(short)
    print(f"[start_nfix8] {short} 已停止。")


def status_bot(short):
    pid = read_pid(short)
    if pid and is_pid_alive(pid):
        print(f"[start_nfix8] {short} 运行中  PID={pid}")
    else:
        print(f"[start_nfix8] {short} 未运行。")
        remove_pid(short)


def main():
    parser = argparse.ArgumentParser(description="启动 OKX NostalgiaForInfinityX8 (X8 原版 / 8020 子类) —— 跨平台后台启动器")
    sub = parser.add_subparsers(dest="cmd")

    def add_s(p):
        p.add_argument("-s", "--strategy", default="x84",
                       help="策略变体: x84(默认, NostalgiaForInfinityX8_4.py / 80-20 补仓子类) 或 x8(原版)")

    add_s(parser)  # 默认 start 也能直接跟 -s (无需写 start 子命令)
    p_start = sub.add_parser("start", help="后台启动 (默认)")
    add_s(p_start)
    p_stop = sub.add_parser("stop", help="停止")
    add_s(p_stop)
    p_status = sub.add_parser("status", help="查看运行状态")
    add_s(p_status)

    args = parser.parse_args()
    cmd = args.cmd or "start"
    strategy = resolve_strategy(args.strategy)
    short = SHORT_MAP[strategy]

    if cmd == "start":
        start_bot(strategy, short)
    elif cmd == "stop":
        stop_bot(short)
    elif cmd == "status":
        status_bot(short)


if __name__ == "__main__":
    main()
