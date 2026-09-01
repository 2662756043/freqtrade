# NfiDcaX7ProMaxV4 策略修复方案清单

> 策略文件：`user_data/strategies/NfiDcaX7ProMaxV4.py`
> 回测数据：`回测数据文档/主数据/OKX NfiDcaX7ProMaxV4.md` + `回测数据文档/明细/OKX NfiDcaX7ProMaxV4每月回测明细.md`
> 生成日期：2026-08-29

---

## 问题总览（按严重程度排序）

| 编号 | 问题 | 严重程度 | 类型 | 影响范围 |
|------|------|----------|------|----------|
| P1 | 未来函数（Look-ahead bias） | 致命 | 代码缺陷 | 入场/方向清零/DCA补仓 |
| P2 | 止损过宽（-95%/-90%） | 致命 | 参数缺陷 | 单笔最大亏损-47U |
| P3 | s1信号盈亏比严重不对称 | 严重 | 逻辑缺陷 | 361笔净亏-144U |
| P4 | 最大回撤过大（70%） | 严重 | 风控缺陷 | 多月回撤>65% |
| P5 | 资金费率数据缺失 | 严重 | 数据缺陷 | 做空利润高估 |
| P6 | 回测方法不真实（每月独立） | 中等 | 方法缺陷 | 无法评估连续回撤 |
| P7 | 信号结构单一（过度依赖s3） | 中等 | 结构缺陷 | s3失效即整体亏损 |
| P8 | 缺少KDJ指标 | 增强 | 功能缺失 | 少一种超买超卖入场信号 |
| P9 | 缺少MA多周期排列过滤 | 增强 | 功能缺失 | 趋势判定依赖未来函数 |
| P10 | 缺少支撑/阻力位 | 增强 | 功能缺失 | 无区域过滤 |
| P11 | 止盈门槛4%偏保守 | 优化 | 参数调优 | 可能让利润跑更多 |
| P12 | max_open_trades=3偏大 | 优化 | 参数调优 | 同时亏损时回撤叠加 |

---

## P1：未来函数（Look-ahead bias）

### 问题描述

`_majority_trend_direction()` 方法（第219-240行）对**整个 dataframe**（包含未来K线）做"多数投票"来判断趋势方向。在回测中，freqtrade 把整个回测窗口的数据传进函数，导致策略在月初就能"知道"整月是多头还是空头。

### 影响位置（3处调用）

| 位置 | 行号 | 用途 | 后果 |
|------|------|------|------|
| `populate_entry_trend()` | 第325行 | s4入场过滤 | 回测中s4能精准顺势，实盘不能 |
| `populate_entry_trend()` | 第370-375行 | 方向清零 | 回测中整月只做空/做多，实盘不能 |
| `_is_with_trend_for_trade()` | 第500行 | DCA补仓判定 | 回测中只给顺势单加仓，实盘不能 |

### 当前代码

```python
# 第219-240行
def _majority_trend_direction(self, dataframe: DataFrame) -> str:
    ema_trend = dataframe.get("EMA_TREND_1h")
    macd = dataframe.get("MACD_1h")
    if ema_trend is None or macd is None:
        return "neutral"
    valid = ema_trend.notna() & macd.notna()
    if valid.sum() < 10:
        return "neutral"
    above = dataframe["close"] > ema_trend
    macd_up = macd > 0
    macd_dn = macd < 0
    long_conf = (above & macd_up).sum()
    short_conf = ((~above) & macd_dn).sum()
    n = valid.sum()
    if long_conf >= 0.6 * n:
        return "long"
    if short_conf >= 0.6 * n:
        return "short"
    return "neutral"
```

### 修复方案

改为用**滚动窗口**（最近200根bar ≈ 16小时），只用当前bar及之前的数据：

```python
def _majority_trend_direction(self, dataframe: DataFrame) -> str:
    """用最近 lookback 根 bar 判定趋势（无未来函数）"""
    lookback = 200  # 5m×200 ≈ 16小时窗口
    ema_trend = dataframe.get("EMA_TREND_1h")
    macd = dataframe.get("MACD_1h")
    if ema_trend is None or macd is None:
        return "neutral"
    tail = dataframe.tail(lookback)
    valid_mask = tail[ema_trend.name].notna() & tail[macd.name].notna()
    valid = tail[valid_mask]
    if len(valid) < 10:
        return "neutral"
    above = valid["close"] > valid[ema_trend.name]
    macd_up = valid[macd.name] > 0
    macd_dn = valid[macd.name] < 0
    long_conf = (above & macd_up).sum()
    short_conf = ((~above) & macd_dn).sum()
    n = len(valid)
    if long_conf >= 0.6 * n:
        return "long"
    if short_conf >= 0.6 * n:
        return "short"
    return "neutral"
```

### 验证方法

修复后重新回测，对比月度收益。预期：2025-02月（整月BTC -17.7%）的 +1783U 会大幅下降，因为策略不再"提前知道"整月是空头。

---

## P2：止损过宽

### 问题描述

当前止损参数在4x杠杆下，允许价格反向波动22.5%~24%才止损。SOL/BTC在极端行情中单日波动可达20-40%，导致大量-95%止损单。

### 当前参数

| 参数 | 行号 | 当前值 | 4x杠杆对应价格波动 | 问题 |
|------|------|--------|-------------------|------|
| `stoploss` | 第76行 | -0.95 | ~24% | 几乎等于爆仓 |
| `hard_exit_counter_trend` | 第123行 | -0.90 | ~22.5% | SOL/BTC波动22%很常见 |
| `hard_exit_with_trend` | 第122行 | -0.25 | ~6.25% | 相对合理但可收紧 |
| `neutral_hard_exit` | 第120行 | -0.60 | ~15% | 仍偏宽 |

### 回测数据支撑

- 150笔stop_loss，平均亏损 **-60.68%**，合计 **-4882.30 USDT**
- 2笔liquidation，平均亏损 -93.37%
- 大量SOL闪崩型止损：持仓0.0~0.3小时，亏损-95%
- BTC逆势扛单型：持仓10~18天，亏损-27%~-49%

### 修复方案

```python
# 第76行
stoploss = -0.30  # 4x杠杆下价格反向7.5%即止损（原-0.95）

# 第119-123行
neutral_hard_exit = -0.15        # 震荡市：4x下价格反向3.75%（原-0.60）
hard_exit_with_trend = -0.10    # 顺势：4x下价格反向2.5%（原-0.25）
hard_exit_counter_trend = -0.20 # 逆势：4x下价格反向5%（原-0.90）
```

### 预期效果

```
当前：150笔止损 × 平均-60.68% = -4882U
修复后：150笔止损 × 平均-15% = -1200U
差额：+3682U 直接转为利润
最大回撤从70%降至~25%
```

---

## P3：s1信号盈亏比严重不对称

### 问题描述

s1信号（RSI3<15做多 / >85做空）胜率高达83-89%，但总盈亏为负。原因是止盈+4%、止损-95%，盈亏比1:24，赢24次才能补1次亏。

### 回测数据

| 信号 | 笔数 | 胜率 | 总盈亏 | 盈利单均赚 | 亏损单均亏 | 盈亏比 |
|------|------|------|--------|-----------|-----------|--------|
| long_s1 | 221 | 83.3% | **-251.45** | ~+4% | -95% | 1:24 |
| short_s1 | 140 | 88.6% | +107.22 | ~+4% | -95% | 1:24 |
| **s1合计** | **361** | 85.3% | **-144.22** | - | - | - |

### 当前代码

```python
# 第319行
long_s1 = (rsi3 < 15) & (close > ema26)
# 第339行
short_s1 = (rsi3 > 85) & (close < ema26)
```

### 修复方案：给s1单独设止损（不删信号）

在类属性中添加：

```python
# s1 专用止损：亏损 -15%（4x杠杆下价格反向3.75%）
s1_hard_exit = -0.15
```

在 `custom_exit()` 中（约第411行后）添加 s1 分支：

```python
# s1 信号专用止损（比全局更紧，避免-95%大亏）
if trade.enter_tag and trade.enter_tag.endswith("_s1"):
    if current_profit <= self.s1_hard_exit:
        return "stop_loss"
```

### 预期效果

```
修复前：long_s1 = 221笔 × (184×+4% - 37×-95%) = -251U
修复后：long_s1 = 221笔 × (184×+4% - 37×-15%) = +148U
s1整体从 -144U 变为 +255U
```

---

## P4：最大回撤过大

### 问题描述

多个月份最大回撤超过50%，最高达70.5%（2025-04）。主要原因是止损过宽 + 3个交易对同时持仓。

### 回测数据

| 月份 | 回撤 | 交易数 | 止损数 | 原因 |
|------|------|--------|--------|------|
| 2025-04 | 70.5% | 25 | 5(含3笔-95%) | SOL/ETH闪崩止损 |
| 2025-06 | 66.2% | 54 | 8 | 横盘期连续止损 |
| 2026-01 | 65.7% | 88 | 7 | BTC空单扛18天 |

### 修复方案（多管齐下）

1. **收紧止损**（见P2）：单笔最大亏损从-47U降到-15U
2. **max_open_trades 3→2**：在config文件中修改，降低同时持仓风险
3. **加入波动率过滤**：在极端波动时不开仓

```python
# populate_indicators 中添加（约第179行后）
dataframe["ATR_14"] = ta.ATR(dataframe, timeperiod=14)
dataframe["ATR_pct"] = dataframe["ATR_14"] / dataframe["close"]  # 波动率占比

# populate_entry_trend 中添加全局过滤
vol_ok = dataframe["ATR_pct"] < 0.03  # 5m ATR < 3%时才入场
# 所有信号与 vol_ok 取交集
```

---

## P5：资金费率数据缺失

### 问题描述

V3文档明确提到："2025-02~2026-05 期间本地缺 funding_rate 历史数据，该段资金费按 0 计"。V4基于V3代码，同样的数据缺口存在。策略用4x杠杆做合约，且空头占比更高（1034空单 vs 890多单），做空在资金费率上通常收取方，但回测里这段时间资金费=0。

### 影响

- 做空利润被高估
- 实盘做空需要持续支付/收取资金费，成本结构不同
- 特别是2025-02月（+1783U），如果算上资金费成本，利润可能减少10-20%

### 修复方案

数据下载已在执行中：
```bash
freqtrade download-data \
  --config user_data/configs/okx/proxy-okx.json \
  --exchange okx \
  --trading-mode futures \
  --pairs "BTC/USDT:USDT" "SOL/USDT:USDT" "ETH/USDT:USDT" \
  --datadir user_data/data/okx \
  --timerange 20250101-20260727 \
  --timeframes 5m 15m 1h 4h 1d \
  --candle-types futures mark funding_rate \
  --no-parallel-download
```

下载完成后重新回测，对比有无资金费的结果差异。

---

## P6：回测方法不真实

### 问题描述

每月独立起200U回测，不是连续权益曲线。总利润6487.89U是各月简单相加，不代表真实复利。最大回撤是单月级别，实际连续运行的回撤可能远超单月70%。

### 修复方案

修复P1（未来函数）后，用整段timerange一次回测：

```bash
freqtrade backtesting \
  --config user_data/configs/okx/proxy-okx.json \
  --strategy NfiDcaX7ProMaxV4 \
  --timerange 20250101-20260727 \
  --datadir user_data/data/okx \
  --timeframe 5m \
  --candle-types futures mark funding_rate \
  --stake-amount 50 \
  --starting-balance 200
```

---

## P7：信号结构单一

### 问题描述

策略几乎完全依赖s3信号盈利，s3占1391/1924 = 72%的交易量，贡献6365U利润（占总利润98%）。一旦s3在某段行情中失效，整体会快速亏损。

### 回测数据

| 信号 | 笔数 | 占比 | 总盈亏 | 利润占比 |
|------|------|------|--------|----------|
| s1 | 361 | 19% | -144U | -2.2% |
| s2 | 106 | 6% | +114U | 1.8% |
| **s3** | **1391** | **72%** | **+6366U** | **98%** |
| s4 | 66 | 3% | +152U | 2.3% |

### 修复方案：加入新信号s5/s6

见下方P8/P9/P10。

---

## P8：加入KDJ指标 + 新信号s5

### 问题描述

当前策略有STOCHRSI但没有KDJ。KDJ的J线在极端值（>100或<0）时反转，是经典抄底摸顶信号，比RSI3更灵敏。

### 修复方案

#### Step 1：populate_indicators 中添加KDJ（约第178行后）

```python
# KDJ 随机指标
stoch = ta.STOCH(dataframe, fastk_period=9, slowk_period=3, slowd_period=3)
dataframe["K"] = stoch["slowk"]
dataframe["D"] = stoch["slowd"]
dataframe["J"] = 3 * stoch["slowk"] - 2 * stoch["slowd"]
```

#### Step 2：populate_entry_trend 中添加s5信号

```python
# ================= 新增 s5：KDJ J线极端反转 =================
# J<0 超卖拐头向上做多 / J>100 超买拐头向下做空
long_s5 = (dataframe["J"] < 0) & (dataframe["J"].shift(1) < dataframe["J"])
short_s5 = (dataframe["J"] > 100) & (dataframe["J"].shift(1) > dataframe["J"])

dataframe.loc[long_s5, "enter_long"] = 1
dataframe.loc[long_s5, "enter_tag"] = "long_s5"
dataframe.loc[short_s5, "enter_short"] = 1
dataframe.loc[short_s5, "enter_tag"] = "short_s5"
```

---

## P9：加入MA多周期排列 + 替代未来函数

### 问题描述

当前趋势判定依赖`_majority_trend_direction`（未来函数）。MA5/10/30多周期排列可以提供无未来函数的趋势判定。

### 修复方案

#### Step 1：populate_indicators 中添加MA（约第178行后）

```python
# MA 多周期
dataframe["MA5"] = ta.SMA(dataframe, timeperiod=5)
dataframe["MA10"] = ta.SMA(dataframe, timeperiod=10)
dataframe["MA30"] = ta.SMA(dataframe, timeperiod=30)

# 趋势排列
dataframe["ma_bull_align"] = (
    (dataframe["MA5"] > dataframe["MA10"]) &
    (dataframe["MA10"] > dataframe["MA30"])
)
dataframe["ma_bear_align"] = (
    (dataframe["MA5"] < dataframe["MA10"]) &
    (dataframe["MA10"] < dataframe["MA30"])
)
```

#### Step 2：在populate_entry_trend的方向清零部分替换未来函数

将第370-375行的 `_majority_trend_direction` 方向清零逻辑替换为：

```python
# 方向清零：用MA排列替代未来函数
# 多头排列时禁止做空，空头排列时禁止做多
dataframe.loc[dataframe["ma_bear_align"], "enter_long"] = 0
dataframe.loc[dataframe["ma_bull_align"], "enter_short"] = 0
```

---

## P10：加入支撑/阻力位 + 布林带入场信号s6

### 问题描述

当前策略只在止盈时用布林带，没有在入场时用。支撑/阻力位完全缺失。

### 修复方案

#### Step 1：populate_indicators 中添加支撑/阻力

```python
# 支撑/阻力位（最近50根bar的高低点）
lookback_sr = 50
dataframe["support"] = dataframe["low"].rolling(lookback_sr).min()
dataframe["resistance"] = dataframe["high"].rolling(lookback_sr).max()
```

#### Step 2：添加s6信号（布林带破轨+RSI确认）

```python
# ================= 新增 s6：布林带极值回归 =================
# 价格跌破下轨 + RSI超卖 = 超跌反弹做多
long_s6 = (dataframe["close"] < dataframe["BBL_20_2.0"]) & (dataframe["RSI_14"] < 30)
# 价格突破上轨 + RSI超买 = 超买回落做空
short_s6 = (dataframe["close"] > dataframe["BBU_20_2.0"]) & (dataframe["RSI_14"] > 70)

dataframe.loc[long_s6, "enter_long"] = 1
dataframe.loc[long_s6, "enter_tag"] = "long_s6"
dataframe.loc[short_s6, "enter_short"] = 1
dataframe.loc[short_s6, "enter_tag"] = "short_s6"
```

#### Step 3（可选）：支撑/阻力作为入场区域过滤

```python
# 接近支撑不做空，接近阻力不做多
near_support = (dataframe["close"] - dataframe["support"]) / dataframe["close"] < 0.01
near_resistance = (dataframe["resistance"] - dataframe["close"]) / dataframe["close"] < 0.01
dataframe.loc[near_support, "enter_short"] = 0
dataframe.loc[near_resistance, "enter_long"] = 0
```

---

## P11：止盈门槛4%→5%

### 问题描述

`grind_exit_profit = 0.04`（第110-111行），止盈门槛偏保守，可能让利润跑更多。

### 当前代码

```python
# 第110-111行
long_grind_exit_profit = 0.04
short_grind_exit_profit = 0.04
```

### 修复方案

```python
# 第110-111行
long_grind_exit_profit = 0.05   # 4% → 5%
short_grind_exit_profit = 0.05  # 4% → 5%
```

### 预期影响

| 指标 | 当前(4%) | 改后(5%) | 说明 |
|------|----------|----------|------|
| 止盈单均赚 | +4% | +5% | 每笔多赚1% |
| 止盈单数 | 1728笔 | 可能减少~10% | 部分单子因没到5%而回撤 |
| 止盈胜率 | 100% | 可能降到95%+ | 少量单子错过止盈 |
| 总利润 | +6488U | 可能持平或略增 | 需回测验证 |

---

## P12：max_open_trades 3→2

### 问题描述

当前config中`max_open_trades=3`，3个交易对（BTC/ETH/SOL）同时持仓时，如果行情闪崩，三单同时止损，回撤叠加。

### 修复方案

在config文件中修改：
```json
"max_open_trades": 2
```

### 预期效果

- 同时持仓从3降到2，极端行情下最大同时亏损减少1/3
- 回撤从70%可能降到~50%（配合止损收紧可进一步降到~25%）
- 交易频率略降，但单笔风控更好

---

## P13：市场状态判定（不拟合）

### 问题描述

当前策略用 `_majority_trend_direction()` 判断市场方向，但该方法看整个回测窗口（含未来数据），属于拟合。需要在不用未来函数的前提下判断当前市场是趋势上涨、趋势下跌还是震荡。

### 策略已有的无未来函数工具

| 方法 | 代码位置 | 判定什么 | 有未来函数吗 |
|------|----------|----------|-------------|
| `_is_trending(last)` | 第212-217行 | ADX≥30=趋势市，<30=震荡市 | 无（只看当前bar） |
| `_trend_direction(last)` | 第185-203行 | EMA+MACD双确认=多/空/中性 | 无（只看当前bar） |

**结论**：`_is_trending` 和 `_trend_direction` 本身没有未来函数，实盘能用。问题只出在 `_majority_trend_direction` 上。

### 四种市场状态判定方法

用 `_is_trending` + `_trend_direction` + MA排列 三重确认：

```python
def _market_state(self, last, dataframe) -> str:
    """无未来函数的市场状态判定"""
    # 第一层：ADX 判断趋势/震荡
    is_trending = self._is_trending(last)

    if not is_trending:
        # ADX < 30 → 震荡市
        return "ranging"

    # 第二层：EMA+MACD 判断方向
    direction = self._trend_direction(last)
    if direction == "long":
        # 第三层：MA排列二次确认
        if dataframe["ma_bull_align"].iloc[-1]:
            return "trend_up"       # 趋势上涨
        return "trend_up_weak"     # 弱趋势上涨
    if direction == "short":
        if dataframe["ma_bear_align"].iloc[-1]:
            return "trend_down"    # 趋势下跌
        return "trend_down_weak"  # 弱趋势下跌
    return "neutral"               # 趋势不明
```

### 四种状态对应的策略行为

| 市场状态 | ADX | 方向 | MA排列 | 策略应做什么 | 适合信号 |
|----------|-----|------|--------|-------------|----------|
| 趋势上涨 | ≥30 | long | 多头排列 | 只做多，紧止损(-10%) | s4/s7做多 |
| 趋势下跌 | ≥30 | short | 空头排列 | 只做空，紧止损(-10%) | s4/s7做空 |
| 趋势不明 | ≥30 | neutral | 混乱 | 双向都可，中等止损(-15%) | s3/s5 |
| 震荡市 | <30 | - | 混乱 | 做反转（抄底摸顶），中等止损(-15%) | s1/s2/s3/s5/s6 |

### 为什么不拟合

- ADX 只看当前bar的值（`last.get("ADX_1h")`），实盘实时可得
- EMA200 是滚动计算的，当前bar的EMA只用到当前及之前的价格
- MACD 同理，当前bar的MACD只用到当前及之前的价格
- MA5/MA10/MA30 是 SMA，滚动计算，无未来数据
- 支撑/阻力 = `.rolling(50).min/max()`，只用当前及之前数据

**所有判定都基于当前bar及之前的数据，实盘完全可复现。**

---

## P14：支撑/阻力破位信号 s7

### 问题描述

当前策略在 BTC 单边上涨月表现差（2025-04 -119U、2026-04 -5.7U、2026-07 -9.6U），因为现有信号都是反转类（抄底摸顶），缺少**顺势破位**信号。支撑/阻力破位正好弥补这个弱点。

### 四种支撑/阻力入场逻辑

| 场景 | 条件 | 方向 | 说明 |
|------|------|------|------|
| 阻力破位 | close突破resistance + RSI>50 | 做多 | 突破上方阻力=多头力量强 |
| 支撑破位 | close跌破support + RSI<50 | 做空 | 跌破下方支撑=空头力量强 |
| 支撑反弹 | close接近support + RSI超卖 | 做多 | 触支撑反弹=抄底（可选） |
| 阻力回落 | close接近resistance + RSI超买 | 做空 | 触阻力回落=摸顶（可选） |

### 修复方案

#### Step 1：populate_indicators 中添加支撑/阻力（P10中已定义）

```python
# 支撑/阻力位（最近50根bar的高低点）
lookback_sr = 50
dataframe["support"] = dataframe["low"].rolling(lookback_sr).min()
dataframe["resistance"] = dataframe["high"].rolling(lookback_sr).max()
```

#### Step 2：添加 s7 破位信号

```python
# ================= 新增 s7：支撑/阻力破位信号 =================
# 判断"刚破位"：当前bar收盘价穿越支撑/阻力，上一根bar还没穿越
break_support = (
    (dataframe["close"] < dataframe["support"]) &
    (dataframe["close"].shift(1) >= dataframe["support"].shift(1))
)
break_resistance = (
    (dataframe["close"] > dataframe["resistance"]) &
    (dataframe["close"].shift(1) <= dataframe["resistance"].shift(1))
)

# 阻力破位做多（突破上方阻力=多头力量强，RSI>50确认非超买区假突破）
dataframe.loc[break_resistance & (dataframe["RSI_14"] > 50), "enter_long"] = 1
dataframe.loc[break_resistance & (dataframe["RSI_14"] > 50), "enter_tag"] = "long_s7"

# 支撑破位做空（跌破下方支撑=空头力量强，RSI<50确认非超卖区假突破）
dataframe.loc[break_support & (dataframe["RSI_14"] < 50), "enter_short"] = 1
dataframe.loc[break_support & (dataframe["RSI_14"] < 50), "enter_tag"] = "short_s7"
```

#### Step 3（可选）：支撑/阻力反弹信号

```python
# ================= 新增 s7b：支撑/阻力反弹信号（可选） =================
# 接近支撑 + RSI超卖 = 反弹做多
near_support = (dataframe["close"] - dataframe["support"]) / dataframe["close"] < 0.005  # 0.5%以内
bounce_support = near_support & (dataframe["RSI_14"] < 35) & (dataframe["close"] > dataframe["close"].shift(1))

# 接近阻力 + RSI超买 = 回落做空
near_resistance = (dataframe["resistance"] - dataframe["close"]) / dataframe["close"] < 0.005
bounce_resistance = near_resistance & (dataframe["RSI_14"] > 65) & (dataframe["close"] < dataframe["close"].shift(1))

dataframe.loc[bounce_support, "enter_long"] = 1
dataframe.loc[bounce_support, "enter_tag"] = "long_s7b"
dataframe.loc[bounce_resistance, "enter_short"] = 1
dataframe.loc[bounce_resistance, "enter_tag"] = "short_s7b"
```

### 为什么这个信号没有未来函数

| 数据 | 计算方式 | 是否有未来函数 |
|------|----------|---------------|
| support | `.rolling(50).min()` 最近50根最低价 | 无 |
| resistance | `.rolling(50).max()` 最近50根最高价 | 无 |
| close.shift(1) | 上一根bar的收盘价 | 无 |
| RSI_14 | 当前bar的RSI值 | 无 |

### 预期效果

- **弥补趋势行情弱点**：当前策略在BTC单边上涨月亏损，s7破位信号可以在这些月份捕捉趋势
- **与s3互补**：s3在震荡市赚钱（反转逻辑），s7在趋势市赚钱（破位逻辑）
- s7信号频率预期较低（每月10-20笔），但单笔利润可能较高（趋势行情空间大）

### 完整信号体系（修复后）

| 信号 | 定位 | 适合行情 | 逻辑 | 止损 |
|------|------|----------|------|------|
| s1 | 抄底摸顶 | 震荡市 | RSI3极端反转 | -15%（专用） |
| s2 | 中周期反转 | 震荡市 | 15m RSI极端 | -10%（顺势） |
| s3 | 利润引擎 | 震荡市 | WILLR+AROON反转 | -10%/-20% |
| s4 | 趋势跟踪 | 趋势市 | MACD金叉+ADX确认 | -10%/-20% |
| s5 | KDJ反转 | 震荡市 | J线极端拐头 | -10%/-20% |
| s6 | 布林极值回归 | 震荡市 | 破轨+RSI确认 | -10%/-20% |
| **s7** | **支撑阻力破位** | **趋势市** | **破位+RSI方向确认** | **-10%/-20%** |
| s7b | 支撑阻力反弹（可选） | 震荡市 | 触位+RSI反转 | -15% |

**震荡市信号**：s1/s2/s3/s5/s6/s7b — 在ADX<30时活跃
**趋势市信号**：s4/s7 — 在ADX≥30时活跃

---

## 修复执行顺序

建议按以下顺序逐项修复，每步修复后重新回测验证：

| 步骤 | 编号 | 改动 | 验证方法 |
|------|------|------|----------|
| 1 | P1 | 修复未来函数 | 对比月度收益，预期大幅下降 |
| 2 | P2 | 收紧止损 | 检查stop_loss笔数和平均亏损 |
| 3 | P3 | s1专用止损 | 检查s1信号总盈亏转正 |
| 4 | P9 | 加入MA排列替代方向清零 | 确认无未来函数后方向清零生效 |
| 5 | P13 | 市场状态判定方法 | 验证ADX+EMA+MA三重确认可用 |
| 6 | P8 | 加入KDJ + s5信号 | 检查s5信号独立盈亏 |
| 7 | P10 | 加入布林带s6 + 支撑阻力 | 检查s6信号独立盈亏 |
| 8 | P14 | 加入支撑阻力破位s7 | 检查趋势月是否扭亏 |
| 9 | P11 | 止盈4%→5% | 对比止盈单数和总利润 |
| 10 | P12 | max_open_trades 3→2 | 对比最大回撤 |
| 11 | P4 | 波动率过滤(ATR) | 检查闪崩型止损是否减少 |
| 12 | P5 | 补全funding_rate数据 | 下载完成后重新回测 |
| 13 | P6 | 连续回测验证 | 整段timerange一次回测 |

---

## 当前策略已有指标清单

| 指标 | 周期 | 代码位置 | 用途 |
|------|------|----------|------|
| EMA26 | 5m | 第166行 | 入场条件 |
| RSI3 | 5m | 第167行 | s1/s2信号 |
| RSI14 | 5m | 第168行 | 备用 |
| WILLR14 | 5m | 第169行 | s3信号 |
| AROON14 | 5m | 第170-172行 | s3信号 |
| BBANDS(20,2) | 5m | 第173-175行 | 止盈条件 |
| STOCHRSI | 5m | 第176-178行 | 未使用（冗余） |
| RSI14 | 15m | 第137行 | s2信号 |
| RSI3 | 15m | 第138行 | s2信号 |
| AROON14 | 15m | 第139-141行 | 补仓过滤 |
| MACD | 15m | 第142-144行 | s4信号 |
| EMA200 | 1h | 第152行 | 趋势方向 |
| ADX14 | 1h | 第153行 | 趋势/震荡判定 |
| MACD | 1h | 第154-156行 | 趋势方向 |

## 待新增指标清单

| 指标 | 周期 | 用途 | 添加位置 | 有未来函数 |
|------|------|------|----------|-----------|
| KDJ(K,D,J) | 5m | s5入场信号 | populate_indicators | 无 |
| MA5/MA10/MA30 | 5m | 趋势排列过滤 | populate_indicators | 无 |
| ATR14 | 5m | 波动率过滤 | populate_indicators | 无 |
| 支撑/阻力 | 5m | s7破位信号 + 区域过滤 | populate_indicators | 无 |
