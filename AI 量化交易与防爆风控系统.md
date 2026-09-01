# AI 马丁量化交易与防爆风控系统

## 技术设计说明书 V1.0

| 项目属性 | 说明 |
|---------|------|
| 文档版本 | V1.0 |
| 项目类型 | AI 辅助自适应量化交易系统 |
| 第一阶段基线 | Freqtrade + FreqAI + LightGBM + OKX |
| 主要交易品种 | BTC、ETH、SOL 等高流动性永续合约 |
| 文档状态 | 需求确认中，待开发 |
| 编写日期 | 2026-08-20 |

---

## 文档变更记录

| 版本 | 日期 | 修改人 | 修改内容 |
|------|------|--------|----------|
| V1.0 | 2026-08-20 | - | 初始版本，整理系统架构、模块设计、开发计划 |

---

## 术语表与缩略语

| 术语/缩略语 | 全称/说明 |
|------------|-----------|
| DCA | Dollar Cost Averaging，成本平均法，即马丁补仓 |
| Martingale | 马丁策略，亏损后加倍补仓摊低成本 |
| ATR | Average True Range，平均真实波幅，波动率指标 |
| RSI | Relative Strength Index，相对强弱指数 |
| MACD | Moving Average Convergence Divergence，指数平滑异同移动平均线 |
| ADX | Average Directional Index，平均趋向指数，衡量趋势强度 |
| EMA | Exponential Moving Average，指数移动平均线 |
| ROI | Return on Investment，止盈目标 |
| FreqAI | Freqtrade 内置的机器学习框架 |
| LightGBM | 微软开源的梯度提升决策树框架 |
| Regime | 市场状态/行情体制 |
| RANGE | 震荡行情状态 |
| TREND_UP | 上涨趋势状态 |
| TREND_DOWN | 下跌趋势状态 |
| OKX | 欧易交易所 |
| Dry Run | 模拟交易（不真实下单） |
| Demo Trading | 交易所模拟盘（使用交易所沙箱环境，真实下单逻辑） |
| Drawdown | 回撤，从峰值到谷值的跌幅 |
| Sharpe Ratio | 夏普比率，风险调整后收益指标 |
| Sortino Ratio | 索提诺比率，仅考虑下行波动的风险调整收益 |
| Profit Factor | 盈利因子，总盈利/总亏损 |
| slippage | 滑点，预期价格与实际成交价格的偏差 |

---

## 参考资料

1. Freqtrade 官方文档：https://www.freqtrade.io/
2. FreqAI 文档：https://www.freqtrade.io/en/latest/freqai/
3. LightGBM 文档：https://lightgbm.readthedocs.io/
4. OKX API 文档：https://www.okx.com/docs-v5/
5. TA-Lib 技术指标库：https://ta-lib.org/

---

# 第一部分：项目概述

## 1. 项目背景

### 1.1 传统马丁策略的优势与困境

传统马丁（Martingale/DCA）策略在震荡行情中具有较高的盈利频率：

```
价格上涨 -> 补仓 -> 价格继续上涨 -> 继续补仓 -> 价格回归 -> 整体仓位盈利
```

其典型特征：
- 较高胜率（震荡行情中可达 80%-90%）
- 较高交易频率
- 震荡行情适应能力强
- 资金曲线短期表现平滑

但核心风险在单边行情中被极度放大：

```
单边行情 -> 持续浮亏 -> 不断补仓 -> 仓位快速扩大 -> 保证金压力 -> 强平/巨额亏损
```

### 1.2 项目定位

本项目**不追求**传统意义上的"无限马丁"，而是建立：

> **AI 市场状态识别 + 有限马丁 + 动态策略切换 + 多层风险控制**

系统的核心理念（贯穿全文）：

> **AI 不负责"预测赚钱"，而是负责判断"当前环境适不适合某种策略"。**

```
传统模式：
  马丁策略 -> 无论行情如何 -> 持续执行

本系统：
  市场数据 -> AI市场状态识别
          ├── 震荡      -> 马丁 + 均值回归
          ├── 转趋势    -> 降低马丁风险
          └── 强趋势    -> 停止马丁 + 趋势策略
```

---

## 2. 项目目标

### 2.1 核心功能目标（V1 必须实现）

| 编号 | 目标 | 优先级 |
|------|------|--------|
| G-01 | 自动识别当前市场状态（RANGE/TREND_UP/TREND_DOWN） | P0 |
| G-02 | 根据 AI 状态判断是否适合运行马丁策略 | P0 |
| G-03 | 震荡行情中允许有限马丁正常运行 | P0 |
| G-04 | 趋势形成过程中降低马丁补仓强度 | P0 |
| G-05 | 强趋势行情中禁止逆势继续补仓 | P0 |
| G-06 | 必要时从马丁策略切换到趋势策略 | P1 |
| G-07 | 设置并强制执行最大补仓次数 | P0 |
| G-08 | 设置并强制执行最大仓位限制 | P0 |
| G-09 | 账户级最大回撤熔断机制 | P0 |
| G-10 | 强制止损体系（多层止损） | P0 |
| G-11 | 极端行情压力测试通过 | P0 |
| G-12 | 最终运行于 OKX 模拟盘和实盘环境 | P0 |

### 2.2 量化目标（V1 验收参考值）

| 指标 | 目标值（相对普通马丁基线） |
|------|---------------------------|
| 最大回撤 | 降低 ≥ 50% |
| 爆仓风险 | 0 次（回测期间） |
| Sharpe Ratio | 提高 ≥ 30% |
| AI 趋势识别准确率 | TREND 类 Recall ≥ 70% |

---

## 3. 非目标（V1 阶段明确不做）

| 编号 | 非目标 | 说明 |
|------|--------|------|
| NG-01 | 不追求 AI 预测每根 K 线涨跌 | AI 只识别市场状态，不做逐根方向预测 |
| NG-02 | 不追求 100% 胜率 | 接受合理亏损，重在风险控制 |
| NG-03 | 不追求无限马丁 | 严格最大补仓次数，禁止无限补仓 |
| NG-04 | 不允许 AI 无限增加仓位 | 所有加仓受硬风控上限约束 |
| NG-05 | 不使用大语言模型（LLM）直接决定交易 | LLM 不参与实盘决策回路 |
| NG-06 | 不直接进入大资金实盘 | 先 Dry Run -> Demo -> 小资金实盘逐步推进 |
| NG-07 | 不在第一阶段开发完整独立量化平台 | 基于 Freqtrade + FreqAI 落地 |
| NG-08 | 不在第一阶段同时加入几十种策略 | V1 策略池：马丁 + 趋势跟随（EMA/海龟）+ 均值回归，共 3-4 种，但**逐个完成、各自独立回测达标再并入** |
| NG-11 | **不一次性并行开发多个策略** | 每个策略独立成 Phase、独立回测验证（Test A~D 框架），达标后才接入 Strategy Controller；未达标策略不进实盘池 |
| NG-09 | 不假设 QuantDinger 等外部系统接口 | V1 完全自给自足 |
| NG-10 | 不做跨交易所支持 | V1 仅支持 OKX |

---

## 4. 核心设计理念

### 4.1 风控优先级铁律

```
账户级熔断  >  强制止损  >  最大仓位  >  最大补仓次数  >  AI风险控制  >  策略信号
```

**无论 AI 判断是否正确，硬风控必须始终有效且最高优先级。**

### 4.2 异常失效安全（Fail-Safe）

任何模块异常时（AI 模型加载失败、行情中断、API 异常、订单异常等）：

```
默认行为 = 禁止新增仓位 + 必要时只允许风险退出
```

**系统异常时不能继续扩大风险。**

### 4.3 渐进验证原则

```
历史回测 -> 极端行情压力测试 -> Freqtrade Dry Run -> OKX Demo -> 小资金实盘 -> 逐步加资金
```

上一阶段未通过，不进入下一阶段。

### 4.4 策略逐个完成原则（NG-11）

```
单个策略独立实现 -> 独立回测达标（Test A~D 框架）-> 接入 Strategy Controller -> 观察切换
-> 下一策略独立实现 ...
```

- **不一次性并行开发多个策略**：每个策略独占一个 Phase，独立回测验证通过后才并入实盘池。
- 未达标 / 回测亏损的策略**不进入 Strategy Controller 调度**，避免策略间相互拖累。
- 新策略复用已有 `Risk Manager / AIRegimeGate / PositionManager` 共享接口，不另起炉灶。
- 已上线策略如需调整参数，走 hyperopt + 单策略回测，不影响其他策略。

---

# 第二部分：系统架构

## 5. 系统总体架构

```
                          ┌──────────────┐
                          │   OKX 交易所   │
                          └──────┬───────┘
                                 │ REST/WebSocket
                                 ↓
                      ┌─────────────────────┐
                      │   Freqtrade 核心引擎   │
                      │  (交易执行 + 数据总线)  │
                      └─────────┬───────────┘
                                │
           ┌────────────────────┼────────────────────┐
           │                    │                    │
           ↓                    ↓                    ↓
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │  Strategy    │    │    FreqAI    │    │ Risk Manager │
    │  Engines     │    │  (ML Pipeline)│    │  (硬风控核心) │
    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
           │                    │                    │
           │                    ↓                    │
           │             ┌──────────────┐            │
           │             │  LightGBM    │            │
           │             │  Classifier  │            │
           │             └──────┬───────┘            │
           │                    │ 市场状态概率         │
           │                    ↓                    │
           └────────────────────┼────────────────────┘
                                ↓
                      ┌─────────────────────┐
                      │ Strategy Controller │
                      │ (策略调度 + 状态机)   │
                      └─────────┬───────────┘
                                ↓
                  ┌─────────────┼─────────────┐
                  ↓             ↓             ↓
           有限马丁策略     趋势跟随策略      空仓/观望
                  └─────────────┼─────────────┘
                                ↓
                       Portfolio Manager
                       (仓位/资金管理)
                                ↓
                       Execution Manager
                       (下单 + 订单跟踪)
                                ↓
                              OKX
```

---

## 6. 模块清单与职责

| 模块编号 | 模块名称 | 核心职责 | 所在文件 |
|---------|---------|---------|---------|
| M-01 | Market Data | OHLCV/账户/持仓/订单数据获取与标准化 | Freqtrade 内置 + 自定义 DataProvider 扩展 |
| M-02 | Feature Engine | 技术指标计算、特征工程、特征标准化 | FreqAI FeaturePipeline + 自定义 |
| M-03 | AI Regime Engine | LightGBM 训练/预测、市场状态分类、概率输出 | FreqAI + AIMartingaleStrategy |
| M-04 | Strategy Controller | 策略状态机、策略调度、防频繁切换、降级逻辑 | strategy_controller.py |
| M-05 | Strategy Engine - Martingale | 有限马丁策略、ATR 动态补仓、补仓金额计算 | AIMartingaleStrategy.py |
| M-06 | Strategy Engine - Trend | 趋势跟随策略（EMA 突破、ADX 过滤） | TrendStrategy.py |
| M-07 | Strategy Engine - MeanReversion | 震荡行情均值回归（布林带、RSI 反转） | MeanReversionStrategy.py |
| M-08 | Strategy Engine - Turtle | 海龟趋势交易（唐奇安突破 + ATR 定仓位 + 盈利金字塔加仓 + 2ATR 止损） | TurtleStrategy.py |
| M-08 | Position Manager | 持仓跟踪、平均成本、DCA 计数、浮盈亏 | position_manager.py |
| M-09 | Risk Manager | 最大仓位、DCA 次数上限、止损、账户熔断 | risk_manager.py |
| M-10 | Execution Manager | 订单路由、重试、滑点保护、订单状态跟踪 | Freqtrade 内置 |
| M-11 | Logger & Monitor | 结构化日志、指标采集、告警通知 | 自定义 + FreqUI |

---

## 7. 数据流

```
OKX 行情/账户
    │
    ▼
OHLCV (15m + 1h)
    │
    ▼
Freqtrade DataProvider  ──────────► 账户权益/持仓/订单
    │                                          │
    ▼                                          │
Feature Engineering (TA 指标 + 衍生特征)       │
    │                                          │
    ▼                                          │
FreqAI Data Preparation (滑窗/标准化)          │
    │                                          │
    ▼                                          │
LightGBM Inference                             │
    │                                          │
    ▼                                          │
Market Regime Probabilities (RANGE/TREND_UP/TREND_DOWN)
    │                                          │
    ▼                                          │
Strategy Controller (状态机 + 切换决策)  ◄──────┘
    │
    ▼
Strategy Engine (马丁/趋势/均值回归 信号生成)
    │
    ▼
Position Manager (DCA 计数/仓位检查)
    │
    ▼
Risk Manager (硬风控 Gate: 熔断/止损/仓位上限)
    │  ── 通过 ──►
    │  ── 拒绝 ──► 记录风控拦截日志
    ▼
Execution (Freqtrade -> OKX REST API)
    │
    ▼
OKX 订单执行 + 回报
```

---

# 第三部分：核心模块详细设计

## 8. Market Data 市场数据模块

### 8.1 数据清单

| 数据类型 | 周期 | 用途 | 来源 |
|---------|------|------|------|
| OHLCV K 线 | 15m | 入场/补仓/短期行情判断，马丁策略主周期 | OKX / Freqtrade DataProvider |
| OHLCV K 线 | 1h | 市场状态识别、大周期趋势判断、AI 特征主周期 | OKX / Freqtrade DataProvider |
| OHLCV K 线 | 4h / 1d | 可选，大方向参考，V1 不强制 | - |
| Tick / 成交明细 | - | V1 不使用，V2 视需要扩展 | - |
| 交易量 | 随 K 线 | 成交量特征、量价背离 | K 线 Volume 字段 |
| 资金费率 | 8h | V1 暂不使用，V2 作为极端情绪特征 | OKX API |
| 账户权益 | 实时 | 回撤计算、仓位上限、熔断 | OKX / Freqtrade Wallets |
| 当前持仓 | 实时 | Position Manager | OKX / Freqtrade Trades |
| 订单状态 | 实时 | Execution Manager | OKX / Freqtrade Orders |

### 8.2 数据时效与回溯要求

| 参数 | 要求 |
|------|------|
| 15m K 线预热条数 | ≥ 800 根（约 8.3 天） |
| 1h K 线预热条数 | ≥ 500 根（约 20.8 天） |
| AI 训练历史数据 | ≥ 2 年 BTC/ETH 合约数据 |
| 实时数据延迟要求 | ≤ 5 秒 |

---

## 9. Feature Engine 特征工程

### 9.1 特征总表（V1）

AI 不直接使用原始价格，而是转换为标准化特征。特征分 5 大类：

| 类别 | 特征名 | 计算说明 |
|------|--------|---------|
| **趋势特征** | EMA20, EMA50, EMA200 | 指数移动平均线 |
| | EMA20 / EMA50, EMA50 / EMA200 | EMA 比率，反映趋势斜率 |
| | Price / EMA20, Price / EMA50, Price / EMA200 | 价格偏离均线程度 |
| **动量特征** | RSI(14) | 相对强弱指数 |
| | MACD(12,26,9) Line + Signal + Histogram | 指数平滑异同移动平均线 |
| | ROC(10), ROC(20) | 变动率 |
| | ADX(14), +DI, -DI | 平均趋向指数 + 方向性指标 |
| **波动率特征** | ATR(14), ATR%(14) | 平均真实波幅 + 百分比 ATR |
| | Bollinger Band Width(20,2) | 布林带宽度 = (上轨-下轨)/中轨 |
| | HV(20), HV(60) | 历史波动率（日收益率标准差年化） |
| **成交量特征** | Volume, Volume MA(20) | 成交量 + 均量 |
| | Volume Ratio = Volume / Volume MA(20) | 量比 |
| | Volume Change % | 成交量变化率 |
| **K 线行为特征** | ConsecutiveUpCount | 连续上涨 K 线数（截至当前） |
| | ConsecutiveDownCount | 连续下跌 K 线数 |
| | Return_N (N=1,3,5,10) | 过去 N 根 K 线收益率 |
| | MaxGain_N (N=5,10,20) | 过去 N 根最大涨幅 |
| | MaxLoss_N (N=5,10,20) | 过去 N 根最大跌幅 |
| | Body%, UpperShadow%, LowerShadow% | 单根 K 线形态特征 |

### 9.2 特征处理规则

1. **缺失值**：前向填充 + 极端值 clip
2. **标准化**：FreqAI 内置 StandardScaler / RobustScaler，训练集 fit，预测集 transform
3. **特征选择**：V1 使用全量特征，后续用 LightGBM feature_importances_ 裁剪
4. **多周期对齐**：1h 特征对齐到 15m 时间轴（forward fill，避免未来函数）

---

## 10. AI 市场状态识别

### 10.1 模型选型（V1 固定）

| 项目 | 选型 |
|------|------|
| 框架 | FreqAI（Freqtrade 官方 ML 集成） |
| 模型 | LightGBMClassifier（多分类） |
| 类别数 | 3 类：RANGE / TREND_UP / TREND_DOWN |
| 输出 | 各类别概率（softmax），不取单一 argmax |

### 10.2 模型输出示例与使用

```
输出概率（1h 周期）:
  RANGE        0.78
  TREND_UP     0.18
  TREND_DOWN   0.04
```

**不使用 argmax 硬分类**，全部策略使用概率阈值。
（概率定义见第 11 节阈值表）

### 10.3 多周期融合规则

```
最终决策 = 1h AI 状态为主 + 15m AI 状态校验

示例：
  1h = TREND_UP (0.72)
  15m = RANGE (0.58)
  → 结论：禁止空头马丁继续补仓（大周期优先级高）
```

**大周期（1h）状态否决小周期决策**，防止小周期震荡误判。

---

## 11. AI 标签设计

### 11.1 标签逻辑

**禁止使用**"下一根 K 线涨跌"作为唯一标签。系统关注的是：**未来一段时间是否形成持续趋势**。

**预测窗口 = 未来 30 根 1h K 线（约 30 小时 = 1.25 天）**

| 标签 | 判定条件（未来窗口内） |
|------|----------------------|
| **TREND_UP** | 1. 最大涨幅 ≥ UP_THRESHOLD（默认 5%，待回测优化）<br>2. 且 趋势持续条件：窗口末收盘价 > (窗口最高价 × 0.7)，即不冲高快速回落 |
| **TREND_DOWN** | 1. 最大跌幅 ≥ DOWN_THRESHOLD（默认 5%，待回测优化）<br>2. 且 趋势持续条件：窗口末收盘价 < (窗口最低价 + (窗口最高-窗口最低) × 0.3) |
| **RANGE** | 以上两者均不满足 |

### 11.2 标签去噪与平衡

- **重叠窗口滑窗生成标签**，步长 = 1 根 1h K 线
- **类别不平衡处理**：LightGBM `class_weight` 参数自动调整 + 必要时欠采样 RANGE
- **极值过滤**：训练时剔除极端插针（单根 K 线涨跌幅 > 20% 且 2 小时内回归）样本，视为异常值

---

## 12. 阈值参数配置（V1 初始值，全部待回测优化）

```
====================================
 AI 状态概率阈值
====================================
RANGE_THRESHOLD        = 0.65    # RANGE 概率 ≥ 此值，认为震荡可信
TREND_THRESHOLD        = 0.65    # TREND_UP/DOWN 概率 ≥ 此值，认为趋势可信
EXTREME_THRESHOLD      = 0.80    # TREND 概率 ≥ 此值，判定极端趋势

====================================
 马丁策略参数
====================================
MAX_DCA_COUNT          = 3       # 最大补仓次数（硬上限）
ATR_MULTIPLIER_1       = 0.8     # 补仓1距离 = 首仓入场价 × (首仓方向) - ATR_MULTIPLIER_1 × ATR
ATR_MULTIPLIER_2       = 1.6     # 补仓2距离
ATR_MULTIPLIER_3       = 2.4     # 补仓3距离
INITIAL_STAKE          = 10 USDT # 首仓金额（或 账户权益 × STAKE_PCT）
DCA_STAKE_1            = 1.0 × INITIAL_STAKE
DCA_STAKE_2            = 1.5 × INITIAL_STAKE
DCA_STAKE_3            = 2.0 × INITIAL_STAKE

====================================
 风险控制参数
====================================
MAX_POSITION_RATIO     = 0.10    # 单交易最大保证金 ≤ 账户权益 × 10%
MAX_TRADE_RISK         = 0.02    # 单交易最大风险 ≤ 账户权益 × 2%
MAX_TOTAL_EXPOSURE     = 0.50    # 总持仓保证金 ≤ 账户权益 × 50%
MAX_OPEN_TRADES        = 3       # 最大同时持仓数
STOPLOSS_INITIAL       = -0.25   # 首仓止损 -25%
STOPLOSS_DCA_1         = -0.15   # 补仓1后止损收紧至 -15%
STOPLOSS_DCA_2         = -0.08   # 补仓2后止损收紧至 -8%
STOPLOSS_DCA_3         = -0.04   # 补仓3后止损收紧至 -4%
TAKE_PROFIT            = 0.06    # 固定止盈 6%（基于平均成本）

====================================
 账户回撤熔断阈值
====================================
DRAWDOWN_WARNING       = 0.05    # 回撤 ≥5% → 新仓位降低 50% 金额
DRAWDOWN_STOP_DCA      = 0.08    # 回撤 ≥8% → 停止新增马丁补仓
DRAWDOWN_STOP_NEW      = 0.10    # 回撤 ≥10% → 停止所有新开仓
DRAWDOWN_EMERGENCY     = 0.12    # 回撤 ≥12% → 强制平仓所有风险仓位，进入全现金

====================================
 策略切换防抖
====================================
STATE_CONFIRM_COUNT    = 3       # 连续 N 根 K 线预测一致才真正切换
MIN_STATE_HOLD_BARS    = 8       # 状态最小持有 K 线数（防抖动）
```

> **⚠️ 以上数值仅为 V1 测试起点，全部必须通过历史回测 + 极端行情压力测试重新确定，不得直接用于实盘。**

---

## 13. 马丁策略模块（Martingale DCA）

### 13.1 有限马丁结构

```
首仓 (stake = INITIAL_STAKE)
  │
  ├── 价格不利移动 ATR_MULTIPLIER_1 × ATR
  │   → 补仓1 (stake = DCA_STAKE_1)
  │       │
  │       ├── 价格继续不利移动 ATR_MULTIPLIER_2 × ATR
  │       │   → 补仓2 (stake = DCA_STAKE_2)
  │       │       │
  │       │       ├── 价格继续不利移动 ATR_MULTIPLIER_3 × ATR
  │       │       │   → 补仓3 (stake = DCA_STAKE_3)
  │       │       │       └─────── 达到 MAX_DCA_COUNT=3 → 禁止继续补仓
  │       │       └── 价格有利 → 止盈/减仓
  │       └── 价格有利 → 止盈/减仓
  └── 价格有利 → 止盈（达到 TAKE_PROFIT）
```

### 13.2 ATR 动态补仓距离

传统固定百分比补仓（如每 1%）在不同波动率阶段效果差异巨大，改为：

```
DCA 触发价格 = 上一笔入场价 + (方向 × ATR × ATR_MULTIPLIER_N)

例：做多马丁
  首仓入场价 100,000 USDT，ATR = 2,000 USDT
  补仓1 = 100,000 - (2,000 × 0.8) = 98,400 （跌 1.6%）
  补仓2 = 98,400  - (2,000 × 1.6) = 95,200 （跌 4.8%）
  补仓3 = 95,200  - (2,000 × 2.4) = 90,400 （跌 9.6%）
```

### 13.3 AI 门控矩阵

AI 状态决定马丁当前可运行的程度：

| AI 状态（1h） | 多头马丁 | 空头马丁 | 备注 |
|--------------|---------|---------|------|
| RANGE ≥ 0.65 | ✅ 正常运行，全量 DCA 金额 | ✅ 正常运行，全量 DCA 金额 | 双向均可 |
| RANGE < 0.65 且 TREND < 0.65 | ⚠️ DCA 金额 × 0.5，MAX_DCA 降为 2 | ⚠️ DCA 金额 × 0.5，MAX_DCA 降为 2 | 降低风险 |
| TREND_UP ≥ 0.65 | ✅ 正常（顺趋势方向） | ❌ 禁止新增补仓，已有仓位收紧止损 | 空头马丁逆势，危险 |
| TREND_DOWN ≥ 0.65 | ❌ 禁止新增补仓，已有仓位收紧止损 | ✅ 正常（顺趋势方向） | 多头马丁逆势，危险 |
| TREND_UP ≥ 0.80（极端） | ✅ 正常，考虑启动趋势策略做多 | ⛔ 立即停止补仓 + 减仓 + 退出空头 | 极端趋势保护 |
| TREND_DOWN ≥ 0.80（极端） | ⛔ 立即停止补仓 + 减仓 + 退出多头 | ✅ 正常，考虑启动趋势策略做空 | 极端趋势保护 |

---

## 14. Strategy Controller 策略控制器

### 14.1 状态机设计

```
  ┌──────────┐     连续 N 次 TREND      ┌──────────────┐
  │  RANGE   │ ───────────────────────► │  TRANSITION  │
  │  (震荡)  │                          │  (过渡态)    │
  └────┬─────┘ ◄─────────────────────── └──────┬───────┘
       │        连续 N 次 RANGE                 │
       │                                       │ TREND 确认
       │                                       ▼
       │                                ┌──────────────┐
       │                                │ TREND_UP /   │
       │                                │ TREND_DOWN   │
       │                                │  (趋势态)    │
       │                                └──────┬───────┘
       │                                       │ 概率≥EXTREME
       │                                       ▼
       │                                ┌──────────────┐
       │                                │   EXTREME    │
       └────────────────────────────────│ (极端行情)  │
                    回撤触发熔断          └──────────────┘
```

### 14.2 状态切换确认规则

| 规则 | 说明 |
|------|------|
| 连续确认 | 同一状态连续 STATE_CONFIRM_COUNT（默认 3）根 K 线预测达到阈值，才真正切换 |
| 最小持有 | 切换后至少保持 MIN_STATE_HOLD_BARS（默认 8）根 K 线，禁止来回抖动 |
| 大周期优先 | 1h 状态否决 15m 状态 |
| 单向降级 | EXTREME 状态不直接跳回 RANGE，必须经过 TREND → TRANSITION → RANGE 逐级冷却 |

### 14.3 状态-策略映射表

| 系统状态 | 启用策略 | 禁用策略 | 风险等级 |
|---------|---------|---------|---------|
| RANGE | 有限马丁 + 均值回归 | 趋势跟随 / 海龟（不启用） | NORMAL |
| TRANSITION | 均值回归（小额），马丁降额 | 马丁全量，趋势跟随 / 海龟不启用 | CAUTION |
| TREND_UP | 趋势跟随做多（EMA 版）+ 海龟做多，马丁仅多头顺向 | 空头马丁补仓 | ELEVATED |
| TREND_DOWN | 趋势跟随做空（EMA 版）+ 海龟做空，马丁仅空头顺向 | 多头马丁补仓 | ELEVATED |
| EXTREME | 仅趋势跟随 / 海龟（顺向小额）或空仓 | 马丁全部禁用 | CRITICAL |
| DRAWDOWN_EMERGENCY | 全部禁用，仅平仓 | 一切新开仓 | LOCKDOWN |

> 注：趋势跟随（EMA 版）与海龟（TurtleStrategy）同属趋势引擎，二者**各自独立验证**后，
> 由 Strategy Controller 在 TREND 状态分配名额（实盘池保留其一或并存，以回测对比结果为准，见 Phase 7.5）。

---

## 15. 策略引擎明细

### 15.1 有限马丁策略 AIMartingaleStrategy

| 项目 | 说明 |
|------|------|
| 主周期 | 15m |
| 入场信号 | 布林带外碰 + RSI 超卖（做多）/ 超买（做空）+ AI 状态允许 |
| 止盈 | 平均成本 × (1 + TAKE_PROFIT)，固定 6%（对称） |
| 止损 | 按 DCA 次数分级收紧（见第 12 节 STOPLOSS_DCA_x） |
| DCA 触发 | 价格不利移动 ATR_MULTIPLIER_N × ATR + AI 门控通过 |
| 最大 DCA 次数 | MAX_DCA_COUNT = 3（硬限制，AI 无法突破） |
| 单仓上限 | MAX_POSITION_RATIO × 账户权益（硬限制） |
| 杠杆 | V1 固定 3x 逐仓（不使用高杠杆） |

### 15.1.1 有限马丁完整交易流程（一次交易的闭环）

> 对应 `user_data/strategies/AIMartingaleStrategy.py`。**这不是传统无限马丁**：
> 有补仓次数硬上限、仓位硬上限、账户回撤熔断、AI 状态门控四重约束。

```
[每根 15m K 线]
  │
  ├─ bot_loop_start：Strategy Controller 写入 current_regime / account_drawdown
  │
  ├─ 1) 状态校验（AI 门控，第 13.3 节）
  │     RANGE       → 马丁全量运行
  │     TREND_UP    → 仅多头马丁可开/补，空头马丁禁补仓
  │     TREND_DOWN  → 仅空头马丁可开/补，多头马丁禁补仓
  │     EXTREME     → 马丁全部禁止（交给趋势策略）
  │
  ├─ 2) 入场信号（populate_entry_trend）
  │     做多：收盘价 ≤ 布林下轨 且 RSI < 35
  │     做空：收盘价 ≥ 布林上轨 且 RSI > 65（需 allow_short_martingale=True）
  │
  ├─ 3) confirm_trade_entry 二次把关
  │     ✗ 状态不允许马丁          → 拒
  │     ✗ 账户回撤 ≥ 10%          → 拒（DRAWDOWN_STOP_NEW）
  │     ✗ 总持仓保证金 ≥ 50% 权益 → 拒（MAX_TOTAL_EXPOSURE）
  │     ✗ 同时在仓 ≥ MAX_OPEN_TRADES(3) → 拒
  │     ✓ → 首仓（custom_stake_amount：≤10% 权益，回撤≥5% 再降 50%）
  │
  ├─ 4) 持仓中：adjust_trade_position（DCA 补仓，第 13.2 节）
  │     价格不利移动 ATR_MULTIPLIER_N × ATR 触发补仓：
  │       补仓1：跌 0.8×ATR，金额 1.0×首仓
  │       补仓2：再跌 1.6×ATR，金额 1.5×首仓
  │       补仓3：再跌 2.4×ATR，金额 2.0×首仓
  │     ── 达到 MAX_DCA_COUNT=3 → 禁止继续补仓 ──
  │     拦截条件：回撤 ≥8% 停补仓 / 状态禁补仓 / 超单仓上限 → 不补
  │
  ├─ 5) 出场（custom_stoploss 同时管止盈 + 分级止损）
  │     止盈：平均成本 × (1 + 6%)（做多）/ × (1 - 6%)（做空）→ 全平
  │     分级止损（随补仓次数收紧）：
  │       首仓     -25%
  │       补仓1后  -15%
  │       补仓2后  -8%
  │       补仓3后  -4%
  │     EXTREME 状态：已有仓位止损再收紧至 ≤ -2%
  │
  └─ 6) 账户级熔断（独立风控线程，第 12 节）
        回撤 ≥5%  → 新仓金额降 50%
        回撤 ≥8%  → 停止新增马丁补仓
        回撤 ≥10% → 停止所有新开仓
        回撤 ≥12% → 强制平仓所有风险仓位，进入全现金（LOCKDOWN）
```

**关键差异 vs 传统马丁**：传统马丁无限加倍、直至价格回归或爆仓；本策略在
第 3 次补仓后即封顶，且分级止损把最大单笔亏损从"可能无限"压到「首仓 -25% /
末级 -4%」，配合账户熔断，从设计上规避「越亏越补→强平」死局。

### 15.2 趋势跟随策略 TrendStrategy

| 项目 | 说明 |
|------|------|
| 主周期 | 15m + 1h 双周期确认 |
| 入场信号 | EMA20 上穿 EMA50 + ADX ≥ 25 + AI TREND_UP ≥ 0.65（做多）<br>EMA20 下穿 EMA50 + ADX ≥ 25 + AI TREND_DOWN ≥ 0.65（做空） |
| 止盈 | 1:2 风险收益比 或 反向 EMA 交叉 |
| 止损 | ATR × 1.5 固定距离 |
| DCA | 不使用 DCA，纯单笔入场 |
| 最大持仓 | 同全局 MAX_OPEN_TRADES，分配 ≤ 2 个趋势仓位 |

### 15.3 均值回归策略 MeanReversionStrategy（辅助，V1 可简化）

| 项目 | 说明 |
|------|------|
| 主周期 | 15m |
| 入场信号 | 价格触布林带下轨 + RSI < 35 做多；上轨 + RSI > 65 做空 |
| 止盈 | 布林中轨 或 2% 固定 |
| 止损 | 布林带外侧 1σ |
| DCA | 不使用 |
| 用途 | TRANSITION 状态下小额替代马丁，保持收益 |

### 15.4 海龟趋势交易策略 TurtleStrategy（新增，独立 Phase 完成）

> 来源：经典海龟交易法（Richard Dennis, 1983）。与 TrendStrategy 同属趋势跟随，
> 但采用**唐奇安通道突破 + 盈利金字塔加仓 + 2ATR 硬止损**，是趋势行情的"加仓版"实现。
> 本策略**独立成 Phase 开发**，按第 4.4 节"策略逐个完成原则"回测达标后再接入调度。

| 项目 | 说明 |
|------|------|
| 主周期 | 15m（与趋势策略一致，便于状态机统一调度） |
| 入场信号 | 唐奇安通道突破：收盘价突破 N 日最高价做多 / 跌破 N 日最低价做空<br>系统一 S1：N=20 入场 / 10 离场；系统二 S2：N=55 入场 / 20 离场（V1 默认 S1） |
| 仓位（ATR 定头寸） | Unit = (risk_per_trade × 权益) / (ATR × 止损倍数)，波动大→仓位小，单笔风险恒定<br>对齐第 12 节 `MAX_TRADE_RISK = 0.02`，V1 起始 risk_per_trade=0.02 |
| 加仓（盈利金字塔） | 价格每向有利方向移动 0.5×ATR 加 1 个 Unit，最多 MAX_UNITS=4<br>**注意：盈利才加仓，与马丁"亏损补仓"方向相反，走独立加仓通道，不触发 MAX_DCA_COUNT** |
| 止损 | 2×ATR 硬止损（custom_stoploss），随加仓上移；单笔最大亏损 ≤ 账户 2% |
| 离场 | 反向唐奇安突破（S1: 10日 / S2: 20日）全平 |
| 杠杆 | 遵守 V1 固定 3x 逐仓（第 593 行），不自行改杠杆 |
| 状态机映射 | 仅在 `TREND_UP` / `TREND_DOWN` / `EXTREME(顺向)` 由 Strategy Controller 激活（见 `is_active_under_state`） |
| 文件 | `user_data/strategies/TurtleStrategy.py`（已实现骨架） |
| 回测要求 | 必须开启真实手续费 + 滑点（第 44 节）；独立跑 Test A~D 对比 EMA 版趋势策略 |

**与马丁的本质区别**：海龟是"追突破、盈利加仓、2ATR 即砍"，从根上规避马丁"越亏越补→强平"的死局，
符合本系统"防爆"定位。趋势行情下，海龟与马丁（RANGE 状态）天然互补、互不干扰。

---

## 16. Position Manager 仓位管理器

### 16.1 核心数据结构（每笔交易）

```json
{
  "trade_id": "BTCUSDT-20260820-123456",
  "pair": "BTC/USDT:USDT",
  "side": "long / short",
  "strategy": "martingale / trend / mean_reversion",
  "entry_price": 100000.0,
  "avg_price": 98000.0,
  "total_stake_amount": 40.0,
  "dca_count": 2,
  "dca_entries": [
    {"price": 100000, "stake": 10, "time": "..."},
    {"price": 98400,  "stake": 10, "time": "..."},
    {"price": 95200,  "stake": 20, "time": "..."}
  ],
  "unrealized_pnl": -1.23,
  "unrealized_pnl_pct": -3.08,
  "entry_time": "2026-08-20T12:00:00Z",
  "signal_grade": "A / B / C",
  "risk_level": "normal / elevated / critical",
  "stoploss_price": 91200.0,
  "takeprofit_price": 103880.0
}
```

### 16.2 账户级状态数据

```json
{
  "account_equity": 1000.00,
  "account_peak": 1020.00,
  "current_drawdown_pct": 1.96,
  "total_margin_used": 240.00,
  "exposure_ratio": 0.24,
  "open_trades_count": 3,
  "martingale_count": 2,
  "trend_count": 1,
  "ai_regime_1h": {"RANGE": 0.72, "TREND_UP": 0.22, "TREND_DOWN": 0.06},
  "ai_regime_15m": {"RANGE": 0.55, "TREND_UP": 0.35, "TREND_DOWN": 0.10},
  "system_state": "RANGE / TRANSITION / TREND_UP / ...",
  "drawdown_level": "normal / warning / stop_dca / stop_new / emergency"
}
```

---

## 17. Risk Manager 风险控制（硬风控核心）

### 17.1 风控检查时机

风控检查在**每一次交易动作前**强制执行，包括：
1. 新开仓
2. DCA 补仓
3. 加仓
4. 甚至平仓前（平仓逻辑也要确认不违反账户熔断规则）

任何一个风控规则命中，**直接拒绝操作**并记录 `RISK_BLOCKED` 日志。

### 17.2 风控规则优先级与明细

| 优先级 | 规则 | 触发条件 | 动作 |
|--------|------|---------|------|
| 1（最高）| **账户熔断 - EMERGENCY** | 回撤 ≥ 12% | 强制市价平仓所有持仓 → 系统进入 LOCKDOWN，禁止一切新开仓 |
| 2 | **账户熔断 - STOP_NEW** | 回撤 ≥ 10% | 禁止所有新开仓、禁止补仓；已有仓位正常止损止盈 |
| 3 | **账户熔断 - STOP_DCA** | 回撤 ≥ 8% | 禁止马丁新增补仓；允许趋势信号正常开仓（降额 50%） |
| 4 | **账户熔断 - WARNING** | 回撤 ≥ 5% | 所有新开仓/补仓 stake × 0.5 |
| 5 | **总暴露上限** | 总保证金 / 账户权益 ≥ 50% | 禁止新开仓、禁止补仓 |
| 6 | **单仓保证金上限** | 本笔累计保证金 / 账户权益 ≥ 10% | 禁止补仓、禁止加仓 |
| 7 | **同时持仓上限** | open_trades_count ≥ MAX_OPEN_TRADES=3 | 禁止新开仓 |
| 8 | **DCA 次数上限** | dca_count ≥ MAX_DCA_COUNT=3 | 禁止本交易继续补仓 |
| 9 | **止损检查** | 当前价格 ≤（多头）/ ≥（空头）止损价 | 触发市价平仓 |
| 10 | **AI 风控门控** | 状态机矩阵不允许（见 13.3） | 禁止对应方向的马丁补仓 |
| 11（最低）| **策略信号** | 原生策略入场/补仓信号 | 允许执行 |

### 17.3 止损体系（多层）

```
┌───────────────────────────────────────────────────┐
│  1. 固定分级止损（见第 12 节 STOPLOSS_DCA_x）        │
│     → 根据 DCA 次数收紧，DCA 越多止损越近            │
├───────────────────────────────────────────────────┤
│  2. ATR 动态止损（趋势策略用）                        │
│     → 止损 = 入场价 ∓ ATR(14) × 1.5                  │
├───────────────────────────────────────────────────┤
│  3. 趋势止损（大周期反向时收紧）                      │
│     → 1h AI TREND 逆势概率 ≥ 0.7 时止损减半距离      │
├───────────────────────────────────────────────────┤
│  4. 账户级熔断（最高优先级）                          │
│     → 回撤触发 LOCKDOWN，全部强制平仓                │
└───────────────────────────────────────────────────┘
```

**任何一层触发均立即执行，不需要等待其他层。**

---

# 第四部分：AI 模型设计

## 18. 模型训练流程

```
历史 OHLCV 数据 (≥ 2年)
    │
    ▼
数据清洗（去重/缺失值/异常值剔除）
    │
    ▼
特征工程（第 9 节全部特征）
    │
    ▼
标签生成（第 11 节 TREND_UP/TREND_DOWN/RANGE）
    │
    ▼
Train / Validation / Test 时间序列分割
  ├── Train: 前 70%（按时间，禁止 shuffle）
  ├── Validation: 中间 15%
  └── Test: 后 15%（未来数据，完全隔离）
    │
    ▼
LightGBMClassifier 训练（早停 + 类别权重）
    │
    ▼
模型评估（验证集 + 测试集）
    │  ├── Accuracy / Precision / Recall / F1
    │  ├── Confusion Matrix（重点关注 TREND 被误判为 RANGE 的比例）
    │  └── ROC-AUC / PR-AUC
    │
    ▼
特征重要性分析（可选裁剪）
    │
    ▼
模型持久化（FreqAI 目录）
    │
    ▼
FreqAI 加载 + 实时预测
```

---

## 19. AI 模型评估标准（重点）

| 指标 | 最低可接受值（V1） | 说明 |
|------|-------------------|------|
| Overall Accuracy | ≥ 60% | 三类总体准确率 |
| **TREND_UP Recall** | **≥ 70%** | 🔴 **最关键指标**：漏判上涨趋势是空头马丁最大杀手 |
| **TREND_DOWN Recall** | **≥ 70%** | 🔴 **第二关键**：漏判下跌趋势是多头马丁最大杀手 |
| RANGE Precision | ≥ 65% | 震荡判定中真正震荡的比例 |
| TREND F1 | ≥ 0.55 | 趋势类 F1 分数 |
| Confusion Matrix | TREND → RANGE 误判率 ≤ 30% | 该误判直接导致逆势补仓，必须严控 |

> **如果 TREND Recall 达不到 70%，不进入 V1 实盘。**
> 继续优化特征/标签/窗口，直至达标或调整为更保守阈值。

---

# 第五部分：存储、配置、日志、监控

## 20. 项目目录结构

```
ai-martingale/
│
├── user_data/
│   ├── strategies/
│   │   ├── AIMartingaleStrategy.py      # 马丁策略（主，震荡行情）
│   │   ├── TrendStrategy.py             # 趋势跟随策略（EMA+ADX，单笔）
│   │   ├── TurtleStrategy.py            # 海龟趋势交易（唐奇安+ATR仓位+盈利加仓）
│   │   └── MeanReversionStrategy.py     # 均值回归策略（辅助，V1 可简化）
│   │
│   ├── freqai/
│   │   ├── models/                      # 训练好的 LightGBM 模型（FreqAI 管理）
│   │   ├── data/                        # 特征 + 标签中间数据
│   │   └── config/                      # FreqAI 模型超参配置
│   │
│   ├── data/
│   │   └── okx/futures/                 # OHLCV 历史数据（feather）
│   │
│   ├── backtest_results/                # 回测报告
│   ├── hyperopt_results/                # 超参优化结果
│   └── logs/
│       ├── freqtrade_main.log           # 主日志（Freqtrade 输出）
│       ├── ai_regime.log                # AI 状态 + 决策专用日志
│       ├── risk_control.log             # 风控拦截专用日志
│       └── trades_execution.log         # 订单/成交专用日志
│
├── config/
│   ├── config.json                      # 通用配置（dry_run_wallet=100, exchange, etc.）
│   ├── freqai_config.json               # FreqAI + LightGBM 超参配置
│   ├── risk_config.json                 # 风控参数（阈值/熔断/止损）
│   └── strategy_params.json             # 策略参数（DCA 距离/金额等）
│
├── scripts/
│   ├── train_regime_model.py            # 离线训练标签 + 模型
│   ├── generate_labels.py               # 标签生成脚本（可单独运行分析）
│   ├── analyze_backtest.py              # 回测结果深度分析
│   ├── extreme_stress_test.py           # 极端行情压力测试脚本
│   └── download_data.py                 # 历史数据下载批量脚本
│
├── lib/（或 user_data/strategies/）
│   ├── strategy_controller.py           # Strategy Controller 状态机
│   ├── position_manager.py              # Position Manager
│   ├── risk_manager.py                  # Risk Manager
│   ├── ai_regime_gate.py                # AI 门控矩阵实现
│   └── feature_pipeline.py              # 特征工程共用函数
│
├── backtest/
│   └── batches/                         # 分批次回测脚本
│
└── README.md                            # 使用说明
```

---

## 21. 配置文件设计

### 21.1 核心配置概念清单

| 配置项 | 所在文件 | 说明 |
|--------|---------|------|
| MARKET_TIMEFRAME | config.json | 策略主周期，V1 = "15m" |
| REGIME_TIMEFRAME | freqai_config.json | AI 识别周期，V1 = "1h" |
| MAX_DCA_COUNT | strategy_params.json | 最大补仓次数 = 3 |
| RANGE_THRESHOLD | freqai_config.json | 震荡判定阈值 = 0.65 |
| TREND_THRESHOLD | freqai_config.json | 趋势判定阈值 = 0.65 |
| EXTREME_THRESHOLD | freqai_config.json | 极端趋势阈值 = 0.80 |
| MAX_POSITION_RATIO | risk_config.json | 单仓保证金上限比例 = 0.10 |
| MAX_TOTAL_EXPOSURE | risk_config.json | 总暴露上限 = 0.50 |
| MAX_OPEN_TRADES | config.json | 最大同时持仓 = 3 |
| DRAWDOWN_WARNING / STOP_DCA / STOP_NEW / EMERGENCY | risk_config.json | 四级回撤熔断阈值 |
| STAKE_AMOUNT / DCA_STAKE_MULTIPLIERS | strategy_params.json | 首仓金额 + 补仓倍数 |
| LEVERAGE | config.json | V1 固定 3x |

### 21.2 配置管理规则

- 所有配置**集中外置**，不硬编码在策略文件中（策略文件顶部常量区可保存一份默认值，优先级：配置文件 > 默认值）
- 配置文件使用**英文注释**，避免 Windows GBK 编码 `UnicodeDecodeError`（项目已知坑点）
- 所有阈值参数**不写死中文文档数值为最终值**，全部标注"待回测确定"
- 每次回测/实盘前，配置内容写入日志快照，确保可追溯

---

## 22. 日志系统

### 22.1 四类日志文件

| 日志文件 | 内容 | 字段（每笔） |
|---------|------|-------------|
| `freqtrade_main.log` | Freqtrade 通用日志（启动/策略/下单回报） | 标准格式 |
| `ai_regime.log` | AI 状态 + 策略切换决策 | `时间, 周期, pair, RANGE_prob, TREND_UP_prob, TREND_DOWN_prob, system_state_before, system_state_after, state_confirmed, strategy_in_use` |
| `risk_control.log` | 风控拦截 + 熔断 | `时间, 触发规则等级, 触发规则名, 触发条件值, 阈值, 被拒绝动作, 涉及交易ID, 账户权益, 回撤` |
| `trades_execution.log` | 每笔交易/补仓/平仓明细 | `时间, 动作(OPEN/DCA/CLOSE/STOP/TP), trade_id, pair, side, price, stake, dca_count, avg_price, pnl, pnl_pct, strategy, system_state` |

### 22.2 日志示例 - ai_regime.log

```
[2026-08-20 12:00:00] BTC/USDT:USDT 1h | RANGE=0.72 TREND_UP=0.22 TREND_DOWN=0.06 | STATE: RANGE (confirmed=3) | STRATEGY: martingale_active | DCA allowed: LONG=YES SHORT=YES
[2026-08-20 13:00:00] BTC/USDT:USDT 1h | RANGE=0.58 TREND_UP=0.38 TREND_DOWN=0.04 | STATE: TRANSITION (confirming_TREND_UP=1) | STRATEGY: martingale_reduced | DCA allowed: LONG=HALF SHORT=HALF
```

### 22.3 日志轮转

- 按日轮转（daily rotation）
- 保留 30 天
- 异常级别（ERROR/CRITICAL）同步输出到 stderr

---

## 23. 监控与告警

### 23.1 监控指标清单

| 指标 | 采集频率 | 告警级别 | 告警阈值（示例） |
|------|---------|---------|-----------------|
| 账户权益（实时） | 每 30 秒 | CRITICAL | 回撤 ≥ 10% |
| | | WARNING | 回撤 ≥ 5% |
| AI 模型预测成功率 | 每小时 | WARNING | 1h 内 TREND Recall < 60%（用已确认行情回溯） |
| 风控拦截次数 | 每 15 分钟 | WARNING | 15 分钟内拦截 ≥ 5 次（可能系统异常） |
| OKX API 错误率 | 每 5 分钟 | WARNING | 5 分钟内 API 错误 ≥ 3 次 |
| | | CRITICAL | 10 分钟内 API 错误 ≥ 10 次 → 进入安全模式 |
| 订单未成交超时 | 实时 | WARNING | 下单后 10 秒未成交 |
| 持仓总暴露 | 每 1 分钟 | WARNING | 暴露 ≥ 45% |
| | | CRITICAL | 暴露 ≥ 60%（超过硬上限） |
| 单交易 DCA 次数 | 实时 | CRITICAL | DCA_count > 3（不可能发生，若发生即 bug） |
| 系统状态（状态机） | 每 15 分钟 | INFO | 状态变更时记录 + 推送 |
| 程序存活心跳 | 每 1 分钟 | CRITICAL | 3 分钟无心跳 → 进程可能已死 |

### 23.2 告警通知渠道（V1 最低要求）

- **WARNING 及以上**：通过 FreqUI 显示 + 日志红色高亮
- **CRITICAL**：邮件 + 日志 CRITICAL + 可选 Telegram/Discord Webhook（实盘阶段必须）
- **LOCKDOWN 触发**：所有渠道立即推送 + 附账户权益、回撤明细、当前持仓快照

---

## 24. 异常处理与安全模式

### 24.1 触发安全模式的异常列表

| 异常场景 | 严重程度 | 安全模式行为 |
|---------|---------|-------------|
| AI 模型加载失败 / 输出为空 / 概率和 ≠ 1 | ERROR | 禁止马丁补仓；趋势策略也禁用；仅允许已有仓位止损/止盈；AI 状态降级为 "UNKNOWN" |
| 行情数据中断（超过 3 根 K 线未更新） | CRITICAL | 禁止所有新开仓；若中断 ≥ 10 分钟，允许用户选择是否保持现有仓位或全部平仓 |
| OKX REST/WebSocket API 异常（连续失败） | CRITICAL | 禁止新增仓位；尝试重连；超过重试上限则进入安全模式 |
| 订单状态异常（提交后无回报、部分成交卡住） | WARNING | 手动介入 + 记录；不自动对其他仓位操作 |
| 账户余额/权益读取失败 | CRITICAL | 禁止新开仓/补仓；风控计算无法确认时，默认按最保守 = 无可用余额处理 |
| 配置文件加载失败 / 编码错误（已知 Windows 坑） | CRITICAL | 拒绝启动；打印明确编码错误提示 |
| Position / Risk 模块内部异常（除零/空指针） | CRITICAL | 拒绝本次操作；不影响其他独立交易；连续 N 次异常则 LOCKDOWN |

### 24.2 安全模式退出条件

- **ERROR 级**：异常原因消除后，自动恢复（下一个 K 线/心跳周期）
- **CRITICAL 级**：必须**人工确认**（FreqUI 按钮或 REST API 调用）才能解除 LOCKDOWN
- 重启后默认进入 LOCKDOWN，人工确认后恢复交易

---

# 第六部分：质量保障（回测 + 压力测试）

## 25. 回测方案（四组必测对比）

### 25.1 测试矩阵

| 测试编号 | 名称 | 配置 | 角色 |
|---------|------|------|------|
| **Test A** | 传统马丁（基准） | 无 AI、无硬风控、无限补仓、固定百分比 DCA | 基线对比，用于量化 V1 改进幅度 |
| **Test B** | 有限马丁 + 硬风控 | MAX_DCA_COUNT=3、分级止损、账户回撤熔断、无 AI | 量化硬风控单独作用 |
| **Test C** | AI 马丁 | B 全部 + FreqAI LightGBM + AI 门控矩阵 | 量化 AI + 风控组合作用 |
| **Test D** | AI 动态策略（V1 完整） | C 全部 + 趋势策略 + Strategy Controller 状态机 | V1 最终方案 |

### 25.2 回测时间分段（Walk-Forward 风格）

| 批次 | 训练期 | 回测期（Out-of-Sample） |
|------|--------|-----------------------|
| Batch 1 | 2022.01 - 2024.06 | 2024.07 - 2024.12 |
| Batch 2 | 2022.07 - 2024.12 | 2025.01 - 2025.06 |
| Batch 3 | 2023.01 - 2025.06 | 2025.07 - 2025.12 |
| Batch 4 | 2023.07 - 2025.12 | 2026.01 - 2026.06 |

> **回测必须串行执行**（用户已确认），并行会导致电脑崩溃。
> **Dry Run Wallet = 100 USDT**（项目约定，所有回测统一）

### 25.3 对比指标表（四组横向对比）

| 指标 | Test A | Test B | Test C | Test D | 说明 |
|------|--------|--------|--------|--------|------|
| 总收益 % | | | | | |
| 最大回撤 % | | | | | 🔴 核心对比 |
| Sharpe Ratio | | | | | 🔴 风险调整收益 |
| Sortino Ratio | | | | | |
| Profit Factor | | | | | |
| 胜率 % | | | | | |
| 交易笔数 | | | | | |
| 最大连续亏损笔数 | | | | | |
| 最大仓位保证金 USDT | | | | | 仓位控制验证 |
| 爆仓次数 | | | | | 🔴 必须 = 0 for B/C/D |
| 马丁单平均 DCA 次数 | | | | | AI 门控效果 |
| 趋势策略贡献利润 % | - | - | - | | 策略切换价值 |
| AI TREND 漏判导致逆势补仓次数 | - | - | | | AI 质量指标 |

### 25.4 V1 回测通过门槛

1. Test D 相对 Test A **最大回撤降低 ≥ 50%**
2. Test B/C/D **爆仓次数 = 0**
3. Test D Sharpe Ratio ≥ Test A × 1.3
4. Test D 账户回撤 ≥ 12% 次数 = 0（从未触发 LOCKDOWN 是最好，但至少触发后无爆仓）
5. 四批次 Walk-Forward **全部盈利**（无单批次大幅亏损）

---

## 26. 极端行情压力测试（专门构造）

### 26.1 压力测试场景

| 场景编号 | 场景名称 | 构造方式（选择历史对应行情段） |
|---------|---------|------------------------------|
| ST-01 | BTC 连续上涨 | 2024 年 10 月 ETF 通过后大涨段 |
| ST-02 | BTC 连续下跌 | 2022 年 5 月 LUNA 崩盘 / 2022 年 11 月 FTX 崩盘 |
| ST-03 | 单日暴涨 | BTC 日内涨幅 ≥ 15% 行情段 |
| ST-04 | 单日暴跌 | BTC 日内跌幅 ≥ 15% 行情段 |
| ST-05 | 快速插针（Wick） | 上下插针 ≥ 10% 但 2 小时内回归（长上下影线） |
| ST-06 | 持续高波动 | ATR% 持续 > 历史 90 分位 |
| ST-07 | 持续低波动 | ATR% 持续 < 历史 10 分位（马丁低收益 + 偶发破位） |
| ST-08 | 突然放量 | 量比 ≥ 5 且价格突破 |
| ST-09 | 连续趋势（30+ 根趋势 K 线） | 单边连续 ≥ 30 根同方向 K 线 |

### 26.2 压力测试验证清单

针对每个场景，输出 **Yes/No** 检查表：

- [ ] 是否**未**无限补仓？（DCA_count 始终 ≤ 3）
- [ ] 是否**未**超过最大仓位上限？（单仓保证金 ≤ 10% 权益）
- [ ] 是否**未**超过总暴露上限？（总保证金 ≤ 50% 权益）
- [ ] 多层止损是否至少有一层正确触发？（未发生爆仓单）
- [ ] 回撤熔断四级是否按梯度正确触发？
- [ ] 趋势识别是否正确（TREND_* Recall）？AI 门控是否拦截了逆势补仓？
- [ ] 策略切换是否正确（震荡 → 过渡 → 趋势）？
- [ ] 异常后系统是否可恢复？

---

# 第七部分：部署与上线流程

## 27. 模拟盘到实盘上线流程

```
 ┌──────────────────┐
 │ 1. 历史回测全通过 │ ← 四组对比 + Walk-Forward + 9 个极端场景
 └────────┬─────────┘
          │ 所有门槛达成
          ▼
 ┌──────────────────┐
 │ 2. 极端行情压力测试│ ← 9 个场景全部通过检查清单
 └────────┬─────────┘
          │ 通过
          ▼
 ┌──────────────────┐
 │ 3. Freqtrade Dry │ ← 本地模拟，无真实 API 调用
 │    Run (≥ 2 周)   │ ← 至少经历一次明显震荡 + 一次明显趋势
 └────────┬─────────┘
          │ 交易频率/胜率/回撤与回测偏差 ≤ 20%
          ▼
 ┌──────────────────┐
 │ 4. OKX Demo 盘   │ ← OKX 官方沙箱，真实 API + 沙箱资金
 │    (≥ 4 周)       │ ← 覆盖完整市场周期（趋势+震荡+横盘）
 └────────┬─────────┘
          │ 无异常/无爆仓/风控全部正常触发
          │ 执行质量（滑点/延迟/手续费）可接受
          ▼
 ┌──────────────────┐
 │ 5. 小资金实盘    │ ← 总风险资金 = 用户可承受全部亏损金额
 │    (≥ 2 个月)     │ ← 杠杆 ≤ 2x，首月 max_open_trades 降为 2
 └────────┬─────────┘
          │ 实盘绩效 ≥ 回测的 70%，回撤 ≤ 回测的 120%
          ▼
 ┌──────────────────┐
 │ 6. 逐步提高资金  │ ← 每次增加不超过当前实盘资金的 50%
 └──────────────────┘
```

**上一阶段未通过，不进入下一阶段。**

---

## 28. 技术选型说明

### 28.1 基础栈

| 组件 | 选型 | 版本/规格 | 选型理由 |
|------|------|---------|---------|
| 交易框架 | Freqtrade | 2026.8-dev（项目已有版本） | 项目已有稳定环境 + FreqAI 原生集成 + 社区活跃 |
| ML 框架 | FreqAI | 随 Freqtrade | 与策略天然集成，特征/训练/预测全链路，避免自造轮子 |
| 模型 | LightGBM | 随 FreqAI 内置 | 表格数据 SOTA，训练快 + 可解释性（特征重要性）+ 小样本鲁棒 |
| 交易所 | OKX | V5 API | 合约流动性好 + Demo 沙箱完善 + 项目已有配置经验 |
| 交易品种 | BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT | 永续合约 | 高流动性 + 历史数据充足 + 避免山寨币极端插针风险 |
| 编程语言 | Python | 3.14（项目 .venv 中） | Freqtrade 原生语言 + ML 生态完善 |
| 数据格式 | Feather | - | 比 CSV 更快更小，Freqtrade 默认历史数据格式 |

### 28.2 依赖库（新增，需确认已安装）

| 库 | 用途 |
|----|------|
| lightgbm | 模型训练 + 推理（FreqAI 依赖） |
| scikit-learn | 标准化/评估指标 |
| pandas / numpy | 数据处理 |
| TA-Lib | 技术指标计算 |
| matplotlib / seaborn / plotly | 回测可视化（分析脚本） |
| pydantic | 配置校验（可选，推荐） |

### 28.3 系统约束

| 约束项 | 说明 |
|--------|------|
| 操作系统 | Windows（用户环境），Linux 可选部署环境 |
| Python 编码 | 启动前设置 `PYTHONUTF8=1`（项目已知坑点，避免中文配置 UnicodeDecodeError） |
| 内存 | ≥ 8GB（LightGBM 训练 + 回测） |
| 磁盘 | ≥ 20GB（历史数据 + 模型文件 + 回测结果） |
| 网络 | 需要稳定代理访问 OKX（用户已有 127.0.0.1:7890） |
| Python 版本 | 项目锁定 .venv Python 3.14.6，不用系统 Python |

---

## 29. 存储与数据管理

### 29.1 数据持久化

| 数据 | 存储格式 | 位置 | 保留策略 |
|------|---------|------|---------|
| 历史 OHLCV | Feather | `user_data/data/okx/futures/<pair>-<timeframe>-futures.feather` | 永久 |
| AI 模型文件 | FreqAI 格式（含元数据） | `user_data/freqai/models/` | 每个版本保留，至少保留最近 5 个可回滚版本 |
| 回测报告 | JSON + HTML | `user_data/backtest_results/` | 永久 |
| 交易记录（Dry Run/实盘） | SQLite（Freqtrade tradesv3.sqlite） | `user_data/` | 永久 |
| 日志 | 纯文本（行结构化） | `user_data/logs/` | 30 天轮转 |
| 配置快照 | JSON | `user_data/logs/config_snapshots/` | 每次启动/改配置时保留一份永久快照 |

---

## 30. 安全设计（V1 必须）

### 30.1 API 密钥管理

| 规则 | 说明 |
|------|------|
| 密钥文件 | `secret.json` 单独配置，不纳入版本控制（`.gitignore` 包含） |
| 密钥权限 | OKX 模拟盘/实盘使用**不同 API Key**；实盘 Key 仅开通**交易权限**，不开通提币/转账权限 |
| IP 白名单 | OKX 实盘 API Key **必须绑定服务器固定 IP**（用户实盘环境如有） |
| 密钥加密 | V1 至少文件权限锁定；V2 引入 OS 级密钥管理/环境变量注入 |
| 日志脱敏 | 任何日志中**不打印完整 API Key / Secret**，仅打印前 4 位 + 后 4 位掩码 |

### 30.2 网络安全

- FreqUI（Web 控制面板）绑定 `127.0.0.1`，不直接暴露公网
- FreqUI 启用用户名/密码（项目已有 admin/xxx，实盘必须更换强密码）
- 外部远程访问通过 SSH 隧道或 VPN，不端口映射

### 30.3 操作安全

- 实盘配置与模拟盘配置**严格分离目录**（项目已有 `configs/okx/模拟盘/` vs `实盘/` 结构，继续沿用）
- 任何参数变更先在 Dry Run → Demo 验证，再上实盘
- LOCKDOWN 触发后必须人工确认解除，不允许自动恢复交易

---

## 31. 部署架构（V1 单机）

```
┌──────────────────────────────────────────────────────┐
│                  用户 Windows PC / 服务器              │
│                                                        │
│  ┌────────────────────────────────────────────────┐   │
│  │  Freqtrade 进程（Python .venv）                 │   │
│  │  ├── Strategy Controller + AI 状态机           │   │
│  │  ├── 3 个策略 + FreqAI + LightGBM              │   │
│  │  ├── Position Manager + Risk Manager           │   │
│  │  └── Logger + 监控告警                          │   │
│  └───────────────────────────┬────────────────────┘   │
│                              │                        │
│  ┌──────────┐     HTTP/REST  │  WebSocket             │
│  │ FreqUI   │ ◄──────────────┘                       │
│  │ (127.0.0.1:8082)                                  │   │
│  └──────────┘                                         │   │
│                              │                        │
│  ┌──────────┐               │ HTTP/REST + WebSocket  │
│  │ 日志文件  │ ◄────────────┤                        │
│  │ SQLite DB │              │                        │
│  │ Feather   │              ▼                        │
│  │ 模型文件  │       ┌──────────────┐                │
│  └──────────┘       │  OKX 公开 API  │                │
│                     └──────────────┘                │
└──────────────────────────────────────────────────────┘
```

V1 单机部署，V2/V3 视需要拆分为微服务。

---

# 第八部分：开发计划与验收

## 32. Phase 开发计划（Phase 1 ~ Phase 9）

### Phase 1：Freqtrade 基础环境搭建

| 项 | 内容 |
|----|------|
| **目标** | Freqtrade + OKX + 历史数据 + 基础策略骨架跑通 |
| **交付物** | ① 历史数据下载脚本可用 ② 配置文件可运行 ③ 能进行 Dry Run 和基础回测 |
| **验收标准** | 执行 `download_data` 成功获取 BTC/ETH/SOL 15m+1h ≥ 2 年数据；空策略 Dry Run 启动无报错，FreqUI 可访问 |
| **任务明细** | P1-1 整理项目目录结构（第 20 节）<br>P1-2 编写批量下载脚本 `scripts/download_data.py`<br>P1-3 编写四套基础配置文件模板（config/freqai/risk/strategy_params）<br>P1-4 空策略骨架 `AIMartingaleStrategy.py` 注册所有模块接口（空实现 pass）<br>P1-5 验证 Dry Run + FreqUI + 基础回测（买入并持有的基准回测能跑通） |

---

### Phase 2：有限马丁策略实现

| 项 | 内容 |
|----|------|
| **目标** | 实现最大补仓次数 + 最大仓位 + ATR 动态补仓（无 AI、无硬风控前半部分） |
| **交付物** | AIMartingaleStrategy 含完整 DCA 逻辑（可运行） |
| **验收标准** | 回测中 DCA_count 始终 ≤ MAX_DCA_COUNT=3；任何交易不得超过单仓上限；补仓距离严格按 ATR 倍数执行 |
| **任务明细** | P2-1 ATR 指标集成 + DCA 距离计算（多空双向）<br>P2-2 DCA 金额分级（INITIAL/DCA1/2/3 stake）<br>P2-3 DCA 计数上限拦截<br>P2-4 止盈逻辑（固定 6% 基于 avg_price）<br>P2-5 单仓保证金上限 + 总暴露上限拦截 |
| **当前进度** | ✅ `user_data/strategies/AIMartingaleStrategy.py` 已实现：ATR 动态补仓距离、DCA 金额递增（1.0/1.5/2.0×）、MAX_DCA_COUNT=3 上限拦截、分级止损（-25%→-15%→-8%→-4%）、固定 6% 止盈、单仓/总仓上限、AI 门控占位（`_regime_allows_martingale` / `_regime_allows_dca`）。待跑通 Test B 回测验证达标。<br>⚠️ AI 门控与账户回撤由 `ai_regime_gate.py` / `risk_manager.py`（Phase 3/4）在 `bot_loop_start` 注入 `current_regime` / `account_drawdown`；当前为 RANGE 默认占位，独立回测可运行 |

---

### Phase 3：硬风控体系（止损 + 账户熔断）

| 项 | 内容 |
|----|------|
| **目标** | 实现多层止损 + 四级回撤熔断 + 风控规则统一入口 |
| **交付物** | `risk_manager.py` 模块 + 分级止损生效 + 回撤熔断逐级触发正确 |
| **验收标准** | 单边行情压力测试中，ST-02/ST-04 能被硬风控限制在可接受亏损，无爆仓；回撤达到阈值后对应动作正确执行 |
| **任务明细** | P3-1 Position Manager 实现（数据结构 + 浮盈亏/平均成本）<br>P3-2 Risk Manager 风控规则链（按优先级 5~9 层）<br>P3-3 分级止损（随 DCA 次数收紧）<br>P3-4 账户回撤计算 + 四级熔断动作（WARNING/STOP_DCA/STOP_NEW/EMERGENCY）<br>P3-5 `risk_control.log` 日志 + 风控拦截事件结构化记录 |

---

### Phase 4：FreqAI + LightGBM 接入

| 项 | 内容 |
|----|------|
| **目标** | FreqAI 集成，LightGBMClassifier 能训练 + 预测并输出到策略中 |
| **交付物** | FreqAI 配置 + 特征工程实现 + 预测流程打通 |
| **验收标准** | 运行 `freqtrade train` 能训练模型；预测在回测中能正确输出 3 类概率数组 |
| **任务明细** | P4-1 Feature Engine：第 9 节全部 5 大类特征实现<br>P4-2 FreqAI 配置文件编写（模型超参 + 训练窗口 + 滑窗）<br>P4-3 特征标准化 + 缺失值处理<br>P4-4 `train_regime_model.py` 离线训练脚本<br>P4-5 回测模式下策略能读取 FreqAI 预测结果并记录到日志 |

---

### Phase 5：市场状态标签 + 模型调优达标

| 项 | 内容 |
|----|------|
| **目标** | RANGE / TREND_UP / TREND_DOWN 三类标签实现，模型指标达到第 19 节验收标准 |
| **交付物** | `generate_labels.py` 脚本 + 训练评估报告（Confusion Matrix + Recall 数据） |
| **验收标准** | 测试集 TREND_UP Recall ≥ 70%，TREND_DOWN Recall ≥ 70%，TREND→RANGE 误判率 ≤ 30% |
| **任务明细** | P5-1 标签生成逻辑（第 11 节 30 根窗口 + 阈值 + 趋势持续条件）<br>P5-2 数据集时间序列分割（Train/Val/Test）<br>P5-3 LightGBM 调参（class_weight、早停、max_depth、learning_rate）<br>P5-4 类别不平衡处理（欠采样/过采样/权重）<br>P5-5 评估报告（混淆矩阵、分类报告、ROC 曲线、特征重要性） |

---

### Phase 6：AI 门控 + 马丁结合

| 项 | 内容 |
|----|------|
| **目标** | AI 状态概率 → 马丁补仓允许/降低/禁止矩阵正确生效 |
| **交付物** | `ai_regime_gate.py` + AIMartingaleStrategy 接入 AI 门控 |
| **验收标准** | 回测中 TREND_UP ≥ 0.65 后空头马丁不再补仓；极端 TREND ≥ 0.80 触发减仓/退出；AI 拦截动作全部记录日志 |
| **任务明细** | P6-1 多周期融合（1h 主 + 15m 校验）<br>P6-2 AI 门控矩阵（第 13.3 节表格）实现<br>P6-3 马丁补仓动作 **必须** 经过 Risk Manager → AI Gate → Strategy 顺序三重检查<br>P6-4 AI 状态转换专用日志 `ai_regime.log`<br>P6-5 与 Phase 3 硬风控优先级正确（硬风控否决 AI） |

---

### Phase 7：趋势跟随策略（EMA 版，TrendStrategy）

| 项 | 内容 |
|----|------|
| **目标** | 独立 TrendStrategy 实现 + 回测能盈利 |
| **交付物** | `TrendStrategy.py` |
| **验收标准** | 趋势行情段（2024.10 上涨 / 2022 崩盘下跌）趋势策略能跟上方向；纯趋势回测盈利；不使用 DCA |
| **任务明细** | P7-1 入场：EMA 金叉死叉 + ADX 强度过滤 + AI TREND 概率确认<br>P7-2 出场：ATR 止损 + 风险收益比止盈<br>P7-3 Position/Risk 模块复用（共享风控接口）<br>P7-4 纯趋势策略回测验证 |

> 按第 4.4 节"策略逐个完成原则"：TrendStrategy 独立回测达标后，才进入下一策略开发。

---

### Phase 7.5：海龟趋势交易策略（TurtleStrategy，独立 Phase）

| 项 | 内容 |
|----|------|
| **目标** | 独立 TurtleStrategy 实现 + 回测盈利，并与 EMA 版趋势策略对比优劣 |
| **交付物** | `TurtleStrategy.py`（已实现骨架）+ 海龟独立回测报告 |
| **验收标准** | 唐奇安突破信号正确触发；盈利金字塔加仓逻辑生效（仅盈利加仓）；2ATR 止损在回测中平均单笔亏损 ≤ 2% 权益；趋势段回测盈利；**未达标不接入 Strategy Controller** |
| **任务明细** | P7.5-1 唐奇安通道指标（S1/S2）+ ATR 计算<br>P7.5-2 入场/离场信号（突破入场、反向突破离场）<br>P7.5-3 `custom_stake`：ATR 定头寸（对齐 `MAX_TRADE_RISK=0.02`）<br>P7.5-4 `turtle_add_position`：盈利金字塔加仓（0.5×ATR/步，≤4 Unit），与马丁 DCA 通道隔离<br>P7.5-5 `custom_stoploss`：2×ATR 硬止损<br>P7.5-6 独立回测（Test A~D 框架）+ 与 TrendStrategy 对比（回撤/收益/交易笔数）<br>P7.5-7 达标后向 Strategy Controller 注册 `is_active_under_state`（仅 TREND/EXTREME 顺向激活） |

> 海龟与 EMA 趋势策略是**两种不同趋势实现**：EMA 单笔、海龟加仓。先各自独立验证，
> 再决定实盘池保留哪一个、或两者并存由状态机分配。任一未达标均不进实盘。

---

### Phase 8：Strategy Controller 状态机 + 策略切换

| 项 | 内容 |
|----|------|
| **目标** | RANGE → TRANSITION → TREND → EXTREME 状态机 + 防抖动 + 策略自动调度 |
| **交付物** | `strategy_controller.py` + Test D 完整 AI 动态策略回测 |
| **验收标准** | 防频繁切换生效（状态确认 N 根 K 线 + 最小持有）；状态转换符合单向降级规则；策略切换动作日志完整 |
| **任务明细** | P8-1 状态机实现（第 14.1 节图）<br>P8-2 切换防抖（连续确认 + 最小持有）<br>P8-3 状态→策略映射表（第 14.3 节）+ 资金分配（固定比例）<br>P8-4 Strategy Controller 暴露接口给所有策略调用<br>P8-5 Test D 完整回测（Test C + 趋势 + 状态机） |

---

### Phase 9：模拟盘 + 实盘前收尾

| 项 | 内容 |
|----|------|
| **目标** | 四组回测对比 + 极端压力测试全部通过 → OKX Demo 上线运行稳定 |
| **交付物** | 回测对比报告 + 压力测试报告 + OKX Demo ≥ 4 周运行日志 |
| **验收标准** | 第 25.4 节 5 项回测门槛全部达成；第 26.2 节 9 场景检查清单 100% Yes；Demo 盘 4 周无异常 |
| **任务明细** | P9-1 四组回测（A/B/C/D）× 四 Walk-Forward 批次 → 汇总报告<br>P9-2 极端行情 9 场景压力测试 + 检查清单<br>P9-3 监控告警实现（邮件/Webhook + 心跳）<br>P9-4 异常处理 + 安全模式（第 24 节）全覆盖<br>P9-5 OKX Demo 盘 ≥ 4 周连续运行，修复所有发现的 Bug<br>P9-6 上线前 Checklist（安全 + 配置 + 密钥）逐项确认 |

---

## 33. V1 验收标准（完整版）

### 33.1 功能验收（全部必须 Pass）

- [ ] OKX 行情（15m + 1h）正常获取，无中断后不崩溃
- [ ] Freqtrade 正常 Dry Run，FreqUI 可用
- [ ] FreqAI 正常训练 + 正常预测
- [ ] LightGBM 输出三类概率，概率和 = 1，无非数字异常
- [ ] AI 能够稳定区分 RANGE / TREND_UP / TREND_DOWN（测试集指标达标）
- [ ] 马丁 DCA_count 永远 ≤ MAX_DCA_COUNT=3（硬限制）
- [ ] ATR 动态补仓距离计算正确（对数 × 倍数验证）
- [ ] AI 门控可以禁止逆势方向补仓（可视化回测交易明细确认）
- [ ] 趋势策略独立运行能盈利
- [ ] Strategy Controller 状态机自动切换 + 防抖动生效
- [ ] 账户回撤熔断四级动作正确触发（回测插针验证）
- [ ] 多层止损至少一层触发（0 爆仓单）
- [ ] 异常情况下（AI 失败 / 行情中断 / API 错误）禁止新增仓位，进入安全模式
- [ ] 安全模式 CRITICAL 级需人工确认才能解除

### 33.2 风控验收（全部必须 Pass）

- [ ] **不允许** 无限补仓（历史回测全周期 MAX DCA_count = 3）
- [ ] **不允许** 单仓保证金超过 账户权益 × 10%
- [ ] **不允许** 总持仓保证金超过 账户权益 × 50%
- [ ] **不允许** 账户回撤超过 15%（硬上限 12% + 3% 滑点缓冲）
- [ ] AI 完全失效时（卸载 AI、只靠硬风控），账户仍然安全（不爆仓、不超过回撤上限）
- [ ] API 异常 / 网络异常 10 分钟内进入安全模式

### 33.3 回测验收（全部必须 Pass）

- [ ] Test A（普通马丁基线）报告生成
- [ ] Test B（有限马丁 + 硬风控）报告生成
- [ ] Test C（AI 马丁）报告生成
- [ ] Test D（AI 动态策略）报告生成
- [ ] 四份报告横向对比表（第 25.3 节指标）完成
- [ ] V1 回测门槛（25.4 节 5 项）全部达成
- [ ] 9 个极端行情压力测试（第 26.1 节）全部执行
- [ ] 压力测试检查清单（第 26.2 节）100% Yes

---

## 34. V1 最终运行逻辑总览

```
                        市场行情（OKX）
                              │
                              ▼
                     15m + 1h 多周期 OHLCV
                              │
                              ▼
                     Feature Engine（5 大类特征）
                              │
                              ▼
              FreqAI + LightGBMClassifier 推理
                              │
                              ▼
                   市场状态概率（3 类 + 多周期融合）
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   RANGE（确认）         TRANSITION          TREND_UP/DOWN（确认）
          │                   │                   │
          ▼                   ▼                   ▼
    马丁正常运行       降低风险/降额          趋势策略+顺向马丁
          │              禁止逆势补仓          禁止逆势马丁
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                       Position Manager
                              │
                              ▼
            Risk Manager 风控 Gate（10 层优先级）
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
         风控通过                       风控拒绝
                │                           │
                ▼                           ▼
          Execution 下单             写入 risk_control.log
                │
                ▼
         OKX 订单执行
                │
                ├── 正常成交 → 更新 Position → 更新账户
                └── 异常 → 进入异常处理流程

              ┌──────────────────────────────┐
              │  独立并行：账户回撤监控线程    │
              │   每 30 秒计算 Drawdown       │
              │   逐级触发 WARNING → ... → EMERGENCY（LOCKDOWN）
              └──────────────────────────────┘
```

---

# 第九部分：后续演进（V2/V3/V4）

## 35. V2 演进方向（模型增强 + 更多市场状态）

| 项目 | 说明 |
|------|------|
| 模型 Ensemble | LightGBM + XGBoost + CatBoost 加权投票，提升识别稳定性 |
| 状态扩充 | 新增 VOLATILE（高波动震荡）、EXTREME（极端单边）、LOW_LIQUIDITY（低流动性）等 5~6 类市场状态 |
| 资金费率特征 | 引入 8h 资金费率作为极端情绪特征 |
| Orderbook 特征 | Level-2 盘口深度/买卖压力特征 |
| 强化学习试训 | 小范围实验 RL 优化策略切换时机，不直接用于实盘 |

## 36. V3 动态风险预算与资金分配

| 项目 | 说明 |
|------|------|
| AI → 风险预算映射 | AI 状态直接输出 [0,1] 风险预算系数 |
| 策略资金分配器 | 根据风险预算，动态分配马丁/趋势/现金比例（例如震荡：马丁60%、趋势10%、现金30%；极端：马丁0%、趋势10%、现金90%） |
| Kelly Criterion 辅助 | 凯利公式辅助优化单仓风险比例（保守半凯利） |
| 组合风控 | 跨交易对相关性矩阵，高度相关仓位合并视为单一风险暴露 |

## 37. V4 多策略平台

| 项目 | 说明 |
|------|------|
| 策略池扩充 | Martingale / Mean Reversion / Trend Following / Breakout / Momentum / Grid / Arbitrage / Market Making 8 大策略族 |
| Strategy Controller v2 | 基于市场状态 + 策略近期动态绩效（Rolling Sharpe）动态调度策略权重 |
| Portfolio Optimizer | 马科维茨均值-方差/风险平价优化策略组合权重 |
| 多交易所支持 | Binance / Bybit 接入（V1 只有 OKX） |
| 分布式部署 | 策略/风控/执行 微服务化，单机 → 分布式 |

---

# 第十部分：项目风险与应对

## 38. 项目风险评估与应对措施

| 风险编号 | 风险描述 | 概率 | 影响 | 风险等级 | 应对措施 |
|---------|---------|------|------|---------|---------|
| R-01 | **AI 模型 TREND Recall 不达标**，导致漏判趋势、逆势补仓亏损 | 中 | 极高 | 🔴 高 | ① 不盲目上实盘，不达 70% 持续调优<br>② 调优后仍不达标 → 采取**更保守阈值**（TREND_THRESHOLD 从 0.65 降到 0.50，宁可多误判震荡为趋势，也不遗漏趋势）<br>③ 加入更多趋势特征（ADX 斜率、布林方向、量价背离） |
| R-02 | **历史过拟合**，回测表现好，实盘差 | 中 | 高 | 🔴 高 | ① 严格 Walk-Forward，训练/测试隔离<br>② Phase 5 用完全独立 Test 集评估<br>③ 特征不做海量搜索（V1 全量特征，不超参搜索上千组合）<br>④ Demo 盘至少 4 周验证，表现掉太多不进入实盘 |
| R-03 | **马丁策略在加密货币长期上涨趋势下，做空马丁长期亏损** | 高 | 高 | 🔴 高 | ① V1 只允许 AI 判断为 RANGE 或 TREND_DOWN 时做空马丁<br>② TREND_UP 哪怕刚超过 0.5 也禁止空马丁<br>③ 考虑 V1 实盘只做**多头马丁**，彻底规避空头长期风险（需用户确认） |
| R-04 | **高杠杆 + 手续费吞噬利润**，5m/15m 高频繁交易必然亏损 | 中 | 高 | 🟠 中 | ① V1 固定 3x 低杠杆（不使用 10x+）<br>② 交易频率监控：若 15m 马丁月交易笔数超阈值，降低信号灵敏度<br>③ 回测必须开启手续费 + 滑点模拟（Phase 1 配置） |
| R-05 | **OKX 模拟盘流动性远低于实盘**，导致信号触发但无法成交或滑点巨大 | 高 | 中 | 🟠 中 | ① Demo 盘只选 BTC/ETH/SOL 前三大流动性合约<br>② Demo 阶段详细记录每笔成交滑点，与回测假设对比，超过阈值则调整模型或只在高波动时段交易 |
| R-06 | **Windows 编码/路径 Bug**（项目已知 UnicodeDecodeError 坑） | 高 | 低 | 🟡 低 | ① 所有配置文件英文注释<br>② 启动前设置 `PYTHONUTF8=1`<br>③ 开发阶段在 Windows 实机运行，不只用 WSL/Linux 验证 |
| R-07 | **网络/代理波动导致行情/订单中断**，进入安全模式频繁触发 | 中 | 中 | 🟠 中 | ① 增加断线重连 + 指数退避重试<br>② 行情中断 ≤ 3 根 K 线不触发安全模式，仅告警<br>③ 本地 K 线缓存 + 插值作为临时 fallback |
| R-08 | **系统上线初期，参数非最优**，运行一段时间表现差 | 高 | 中 | 🟠 中 | ① 严格小资金起步，不急于加大资金<br>② 每月滚动训练（Walk-Forward 每月重新训练模型）<br>③ 参数改动必须先回测 → Demo 验证，再实盘 |
| R-09 | **极端黑天鹅行情**（例如 BTC 单日 -30%）超出回测样本 | 低 | 极高 | 🟠 中 | ① EMERGENCY 熔断从 12% 再保守评估，必要时降为 10%<br>② 极端行情压力测试加入人工合成黑天鹅（历史最大跌幅 ×1.5 倍）<br>③ 实盘资金全部为可承受全部亏损资金量 |

---

# 第十一部分：附录

## 39. 参考配置文件骨架（摘录，可直接作为开发模板）

### 39.1 risk_config.json（示例骨架）

```json
{
  "_comment": "Risk control parameters - All values are V1 starting points, optimize via backtest",
  "_encoding_warn": "Use ONLY English comments to avoid Windows GBK UnicodeDecodeError",

  "max_position_ratio": 0.10,
  "max_total_exposure": 0.50,
  "max_trade_risk": 0.02,

  "stoploss_initial_pct": -0.25,
  "stoploss_by_dca": [
    {"dca_count": 1, "stoploss_pct": -0.15},
    {"dca_count": 2, "stoploss_pct": -0.08},
    {"dca_count": 3, "stoploss_pct": -0.04}
  ],
  "takeprofit_pct": 0.06,

  "drawdown_levels": [
    {"level": "warning",    "drawdown_pct": 0.05, "action": "HALVE_NEW_STAKE"},
    {"level": "stop_dca",   "drawdown_pct": 0.08, "action": "BLOCK_NEW_DCA"},
    {"level": "stop_new",   "drawdown_pct": 0.10, "action": "BLOCK_NEW_TRADES"},
    {"level": "emergency",  "drawdown_pct": 0.12, "action": "FORCE_CLOSE_ALL"}
  ]
}
```

### 39.2 strategy_params.json（示例骨架）

```json
{
  "_comment": "Strategy parameters - All values are V1 starting points",

  "max_dca_count": 3,
  "initial_stake_usdt": 10,
  "dca_stake_multipliers": [1.0, 1.5, 2.0],
  "dca_atr_multipliers": [0.8, 1.6, 2.4],
  "atr_period": 14,

  "leverage": 3,
  "margin_mode": "isolated",

  "regime_thresholds": {
    "range": 0.65,
    "trend": 0.65,
    "extreme": 0.80
  },

  "state_switch": {
    "confirm_count": 3,
    "min_hold_bars": 8
  }
}
```

---

## 40. 最终设计原则（再强调一次）

> **整个系统的第一目标，不是让马丁赚得更多，而是让马丁在不适合自己的行情中主动退出。**

```
传统马丁：
  震荡 → 赚钱
  趋势 → 继续补仓 → 巨额亏损

AI 马丁（本系统）：
  震荡 → 正常运行
       ↓
  趋势初期 → 降低风险（降额/减少补仓）
       ↓
  趋势确认 → 停止马丁（禁止逆势补仓）
       ↓
  强趋势 → 切换趋势策略（顺向操作）
       ↓
  极端行情 → 空仓 / 熔断（保护本金）
```

**最终目标不是"永远使用马丁"，而是"只在马丁擅长的行情里使用马丁"。**

---

## 41. V1 的核心验证命题

> **V1 的核心不是把系统做得复杂，而是先验证一件事：**
>
> **AI 能否在马丁真正发生危险之前识别单边行情，并有效降低最大回撤。**

只要这一点通过 **回测（A/B/C/D 四组对比 + 9 个极端场景压力测试）+ 模拟盘（≥ 4 周 OKX Demo）** 的组合验证，后面的 V2/V3/V4（动态资金分配、多策略组合、自动策略切换、Ensemble 模型等）才有继续开发的价值。

---

# 第十二部分：开发规范与接口契约

## 42. 模块间接口契约定义（开发 Phase 必须对齐）

### 42.1 设计原则

所有模块统一遵循 **"硬风控否决一切"** 原则，返回值必须包含明确的通过/拒绝理由，方便写入 `risk_control.log`。

---

### 42.2 Risk Manager 风控接口（M-09）

所有交易动作（开仓/补仓/加仓/甚至平仓前确认）**必须先调用此接口**。

```python
# risk_manager.py 核心签名
class RiskDecision:
    allowed: bool                # 是否允许
    level: int                   # 命中规则的优先级（越小越严重，1 = EMERGENCY 最严重）
    rule_name: str               # 命中的规则名（如 "ACCOUNT_EMERGENCY" "DCA_COUNT_LIMIT"）
    triggered_value: float       # 触发时的实际值
    threshold_value: float       # 阈值
    reason: str                  # 人类可读拒绝原因，写入日志
    stake_multiplier: float = 1.0 # 如果是 WARNING 级降额，返回建议的 stake 倍率（如 0.5）

class RiskManager:
    def check(self,
              action: Literal["OPEN_NEW", "DCA_ADD", "ADD_SIZE", "CLOSE_POS"],
              trade_id: Optional[str],
              pair: str,
              side: Literal["long", "short"],
              requested_stake_usdt: float,
              dca_count_after: int,
              account_snapshot: AccountStateData) -> RiskDecision:
        """
        风控 Gate：按优先级 11 层规则链依次检查，遇到第一个命中即返回拒绝；
        全部通过返回 allowed=True。
        WARNING 级（回撤 5%）不拒绝但返回 stake_multiplier=0.5。
        """
```

**调用方（Strategy/Position）必须严格遵守返回值**：
- `allowed=False`：禁止操作，调用 `log_risk_blocked(decision)` 记录日志，直接 return
- `stake_multiplier != 1.0`：开仓/补仓金额 = 请求金额 × stake_multiplier

---

### 42.3 Strategy Controller 状态机接口（M-04）

```python
# strategy_controller.py 核心签名
class SystemState(str, Enum):
    RANGE = "RANGE"
    TRANSITION = "TRANSITION"
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    EXTREME = "EXTREME"
    LOCKDOWN = "LOCKDOWN"        # 由 Risk Manager 回撤触发，优先级最高，可覆盖 Controller

class RegimeProbs:
    ts: datetime
    range_p: float
    trend_up_p: float
    trend_down_p: float

class StrategyController:
    def on_new_bar(self,
                   regime_1h: RegimeProbs,
                   regime_15m: Optional[RegimeProbs],
                   drawdown_level: str) -> SystemState:
        """
        每根 1h K 线（同时参考 15m）调用一次。
        内部：确认计数 + 最小持有 K 线数 + 单向降级规则。
        注意：如果 Risk Manager 已经进入 LOCKDOWN，
        本方法必须无条件返回 LOCKDOWN，不允许状态机绕过。
        """

    def get_active_strategies(self) -> list[str]:
        """返回当前系统状态下允许启用的策略名列表"""

    def get_risk_multiplier(self) -> float:
        """返回当前状态下的 stake 倍率：RANGE=1.0, TRANSITION=0.6, TREND=0.8, EXTREME=0.3"""
```

---

### 42.4 Position Manager 仓位接口（M-08）

```python
# position_manager.py 核心签名
class PositionManager:
    def get_trade(self, trade_id: str) -> Optional[TradeData]:
        """按 trade_id 取完整仓位信息（见第 16.1 节 JSON 结构）"""

    def get_all_open_trades(self) -> list[TradeData]:
        """所有当前未平仓列表"""

    def calc_avg_price(self, trade_id: str) -> float:
        """根据 dca_entries 重新计算加权平均成本（防数值漂移）"""

    def calc_unrealized_pnl(self, trade_id: str, current_price: float) -> tuple[float, float]:
        """返回 (pnl_usdt, pnl_pct)，pct 基于总 stake 计算"""

    def can_add_more_dca(self, trade_id: str, requested_new_stake: float,
                         account_equity: float) -> tuple[bool, str]:
        """
        单仓侧检查：DCA 次数 + 单仓保证金上限是否还允许再加？
        返回 (can, reason)。注意：此检查 **不替代** RiskManager 全局检查！
        """

    def get_aggregate_exposure(self) -> tuple[float, float]:
        """返回 (total_margin_usdt, exposure_ratio = total/equity)"""
```

---

### 42.5 AI Regime Gate 门控矩阵接口（M-03 扩展）

```python
# ai_regime_gate.py 核心签名
class DCAPermission(str, Enum):
    FULL = "FULL"         # ✅ 全量 DCA
    HALF = "HALF"         # ⚠️ 降额 DCA（stake × 0.5, MAX_DCA 自动降 1）
    DENY = "DENY"         # ❌ 禁止新增补仓
    FORCE_EXIT = "FORCE_EXIT"  # ⛔ 立即减仓 + 启动退出

class AIRegimeGate:
    def query_dca_permission(self,
                             side: Literal["long", "short"],
                             regime_1h: RegimeProbs,
                             regime_15m: Optional[RegimeProbs]) -> DCAPermission:
        """
        实现第 13.3 节矩阵 6 × 2 场景。
        大周期否决：如果 1h 否决，15m 再支持也没用。
        """

    def new_entry_allowed(self, side: str, strategy: str,
                          regime_1h: RegimeProbs, system_state: SystemState) -> bool:
        """
        新开仓是否被 AI 状态 + 系统状态允许。
        例：TREND_UP 系统状态下，空头马丁新开仓 = false。
        """
```

---

### 42.6 模块调用顺序（铁律，不允许更改）

```
任何开仓 / 补仓动作：
  Strategy 信号生成
        │
        ▼
  AIRegimeGate.new_entry_allowed() / query_dca_permission()
        │ （AI 否决即在此返回，记录 ai_regime.log）
        ▼
  PositionManager.can_add_more_dca() （单仓侧检查）
        │
        ▼
  RiskManager.check()  ← 🔴 最高优先级，硬风控在此最终否决
        │ （拒绝 → 记录 risk_control.log，立即中止）
        ▼
  Freqtrade Execution → OKX API
```

**RiskManager 永远放最后一关**，防止任何模块绕过硬风控。

---

## 43. 未来函数（Look-Ahead Bias）防护规则

> 🔴 **量化系统头号杀手。** 回测收益翻倍，实盘腰斩归零。90% 的情况来自于"不小心在 t 时刻用了 t 时刻之后才知道的数据"。
> 以下规则违反任何一条，整个回测结果作废。

### 43.1 训练 / 验证 / 测试集绝对隔离

| 规则 | 要求 |
|------|------|
| 分割方式 | 纯时间顺序分割，**严禁 shuffle**。训练 = 前 70% 时间，Val = 中间 15%，Test = 后 15% |
| Test 集禁令 | Test 集**只允许在 Phase 5 的最后一步**运行一次评估指标，**绝不能**用 Test 集调参/选特征/选模型 |
| Walk-Forward 要求 | 第 25.2 节 4 个批次训练必须是滚动窗口，Batch N 不能偷看 Batch N+1 的训练数据 |
| 早停（Early Stop）| LightGBM 早停**只能用 Val 集**，不能用 Test 集 |

### 43.2 特征 / 标签工程禁令

- **特征标准化**：`scaler.fit()` 只在 Train 集上 fit，Val/Test/实时预测一律 `transform()`，**不允许重新 fit**
- **标签窗口**：标签定义中的"未来 30 根 K 线"，必须严格是 `close[t+1 : t+30]`，**不能包含 t 这根**（t 时刻还没收完，信息不完整）
- **多周期对齐**：1h 特征用于 15m 决策时，用**最近已收盘的完整 1h K 线** forward fill，**绝对不允许**用当前还在走的未收盘 1h K 线的实时生成特征
- **ATR/EMA 等指标**：使用 pandas/TA-Lib 标准实现，严禁自定义 shift(-1) 往前偷看

### 43.3 回测引擎配置

```json
// config.json 强制（V1 默认，不能改）
{
  "freqai": {
    "include_incomplete_features": false,
    "feature_parameters": {
      "label_period_candles": 30,
      "label_shift": 1
    }
  }
}
```

- `include_incomplete_features = false`：FreqAI 自动丢弃当前未完整窗口的特征
- `label_shift = 1`：标签从下一根 K 线开始，防止偷看当根

### 43.4 未来函数自检机制（V1 必须实现）

Phase 2 起写一个 `scripts/check_lookahead.py` 脚本，针对回测结果自动检查：
1. 打印任何特征与"未来收益"的相关系数，**单一特征 IC 绝对值 ≥ 0.15 → 99% 是未来函数 Bug**，立即排查
2. 训练期 vs 测试期指标差异过大（例如 Train Accuracy = 98% 但 Test = 50%）→ 黄色警告，可能过拟合也可能未来函数
3. 发现可疑立即停止，不继续后面的 Phase。

---

## 44. 手续费、资金费率、滑点模拟模型

### 44.1 OKX 合约费率标准（V1 回测内置写死）

| 项目 | Maker（挂单成交） | Taker（吃单成交） |
|------|------------------|------------------|
| 手续费率 | **0.02% (0.0002)** | **0.05% (0.0005)** |
| 下单类型对应 | 限价单（限价挂在盘口内） | 市价单 / IOC 限价 / 止损触发单 |

### 44.2 模拟策略（回测配置）

```json
// config.json backtest 部分
{
  "backtest_fee_mode": "search_daily",
  "fee": {
    "maker": 0.0002,
    "taker": 0.0005
  },
  "backtest_slippage_model": "static",
  "slippage": {
    "entry": 0.0005,
    "exit": 0.0010
  }
}
```

### 44.3 滑点模型（自适应增强版）

除了上面的基础滑点，回测分析脚本 `analyze_backtest.py` 中还要做一个**滑点放大模型**：

```python
def realistic_slippage(volatility_atr_pct: float, is_stoploss_exit: bool) -> float:
    """
    波动率越高，实际滑点越大；止损退出实际要在真实行情多付出滑点。
    """
    base = max(0.0005, volatility_atr_pct * 0.05)  # ATR 1% → 滑点 0.05%
    if is_stoploss_exit:
        base *= 2.0  # 止损退出是追价，滑点翻倍
    return min(base, 0.005)  # 上限 0.5%，单次不至于太夸张
```

最终回测报告要出两版：**"Freqtrade 默认滑点版" + "增强滑点保守版"**，保守版才作为实盘预期参考。

### 44.4 资金费率近似模拟

合约每 8 小时收一次资金费率，马丁持仓几天以上会累计：

- 回测阶段：不做精确逐笔计算，**按年化 -2% 额外惩罚**从总收益中扣，作为资金费率的近似（实际多空资金费率基本抵消，长期净成本不大，取保守 2%）
- 实盘 / Demo 阶段：直接用 OKX 真实返回的资金费流水，无需模拟

---

## 45. 信号分级（A/B/C 级）设计

在 `TradeData.signal_grade` 字段写入，用于事后绩效归因分析（不同等级信号表现分开统计）。

| 等级 | 定义（开仓/补仓信号均需判定） | stake 调整 |
|------|------------------------------|-----------|
| **A 级 - 高置信共振** | 同时满足：<br>1. 主指标信号（布林 + RSI 极端 / EMA 交叉）<br>2. 辅助指标信号（MACD 方向一致 + ADX ≤ 25 震荡）<br>3. AI 状态：RANGE ≥ 0.75 或 对应 TREND ≥ 0.70（顺向）<br>4. 无 1h 反向预警 | × 1.0（标准 stake） |
| **B 级 - 标准信号** | 同时满足：<br>1. 主指标信号<br>2. AI 状态：RANGE ≥ 0.65 或 顺向 TREND ≥ 0.65<br>（辅助指标可以 1 个不满足，但不能反向） | × 0.7 |
| **C 级 - 高风险信号** | 满足：<br>1. 只有单一主指标触发，辅助指标犹豫<br>2. AI 概率在边界（RANGE 0.55~0.65 区间）<br>3. Position Manager 提示当前该方向浮亏累积 | × 0.4 + DCA 次数上限自动降为 2 + 止损收紧 1.5x（止损距离 ÷ 1.5） |
| **不触发** | 以下任何一项 → 直接放弃信号：<br>• AI 逆向概率 ≥ 0.55<br>• 系统状态 = TRANSITION 且该信号方向为马丁逆势<br>• Risk Manager 检查不通过（当然此步独立检查） | - |

**强制规则**：C 级信号占总信号比例 **> 30% 时**，自动降低信号灵敏度（如提高 RSI 超买阈值、布林带外碰距离），避免系统为了交易次数而放低质量信号。

---

# 第十三部分：增强风控 + 质量保障补充

## 46. 多币种相关性组合风控

### 46.1 背景问题

BTC / ETH / SOL 历史 30 天相关系数经常 ≥ 0.85。如果同时开 BTC 多 + ETH 多 + SOL 多，虽然表面是 3 个独立仓位，但实际 ≈ 3 笔同时押注同一个方向，风险暴露叠加。

### 46.2 组合风控规则

1. **相关性矩阵计算**：每天 00:00 UTC 跑一次 `correlation_matrix = 过去 60 天 1h 收益率 Pearson 相关系数`
2. **同方向簇合并**：
   - 按 long / short 分组
   - 用完全图聚类：相关性 ≥ 0.75 的交易对合并为一个"簇"
   - 同一个簇的所有仓位保证金相加，视为**单一虚拟仓位**
3. **簇级别上限检查**：
   - 单簇保证金总额 ≤ 账户权益 × 20%（单仓上限是 10%，给 2x 放宽但有顶）
   - 同方向所有簇总额 ≤ 账户权益 × 35%（禁止单向全押）
4. **规则位置**：Risk Manager 第 6 层与第 5 层之间（单仓保证金之后、总暴露之前）插入

### 46.3 典型示例

```
账户权益 = 1000 USDT
相关性矩阵：BTC-ETH=0.92, BTC-SOL=0.81, ETH-SOL=0.86
→ 3 币全在一个簇 CLUSTER_CRYPTO_MAJORS

BTC LONG 保证金 = 85 USDT（OK）
ETH LONG 保证金 = 75 USDT → 簇总额 = 160 ≤ 200（OK）
尝试开 SOL LONG 50 USDT → 簇总额 = 210 > 200 → RISK_BLOCKED
```

---

## 47. 单元测试要求

### 47.1 必须覆盖的模块（V1 最低要求）

| 模块 | 单测场景数（最低） | 覆盖目标 | 关键断言 |
|------|-------------------|---------|---------|
| **RiskManager** | ≥ 40 | ≥ 85% | 11 层规则每层至少：<br>• 命中（刚好在阈值上）<br>• 未命中（差一点点）<br>• 极端超阈值<br>EMERGENCY 触发后 `LOCKDOWN=true` 后续全部被拒 |
| **PositionManager** | ≥ 15 | ≥ 80% | DCA 条目依次加入后 `avg_price` 精度误差 ≤ 0.01 USDT；PnL 计算手算交叉验证；DCA 次数到 3 后 can_add = false |
| **AIRegimeGate** | ≥ 15 | ≥ 90% | 第 13.3 节矩阵 6×2 共 12 条**每条 1 个用例**；边界值 0.6499/0.6501 各测一次 |
| **StrategyController** | ≥ 20 | ≥ 85% | 状态机转换：5 状态 × 每状态输入 TREND/RANGE/EXTREME → 新状态符合单向降级；连续确认 2/3/4 根 K 线防抖逻辑；最小持有 8 根期间不能跳回 |
| **ExtremeHandler**（极端行情处理器） | ≥ 25 | ≥ 85% | 第 51 节 5 级极端级别 × 多空 × 响应断言；插针豁免；波动率尖峰 |

### 47.2 单测执行规则

- Phase 1~9 每个 Phase 验收前，必须运行：`pytest -q --cov=lib --cov-report=term-missing`，覆盖率达标才允许 Phase 通过
- RiskManager / AIRegimeGate 的单测 **不允许任何一个版本变红色（FAIL）**，否则禁止合并
- 回测前先跑单测，避免"因为风控 bug 导致回测报告看着好看"的浪费

---

## 48. 做空马丁决策标准（解决 R-03 高风险）

**R-03 是 V1 最高概率发生的风险**（加密货币长期上涨趋势，做空马丁长期亏损概率远高于做多马丁）。

### 48.1 默认值（V1 实盘阶段）

```python
# strategy_params.json 顶层开关
ALLOW_SHORT_MARTINGALE = false   # 🔴 V1 实盘默认关闭空头马丁
```

→ **V1 实盘只运行多头马丁 + 双向趋势跟随**。

### 48.2 如果后续要开启空头马丁，必须**同时满足全部条件**

打开 `ALLOW_SHORT_MARTINGALE=true` 后，还需要每一笔空马丁新开仓都额外过下面 5 条过滤器（写在 `AIRegimeGate.new_entry_allowed` 里）：

| # | 附加条件 | 说明 |
|---|---------|------|
| 1 | 1h RANGE_prob ≥ 0.70（比多头 0.65 更严格） | 震荡必须更确定 |
| 2 | BTC 价格 < EMA200(1h)，即 **大周期熊市中** | 加密市场长期涨，只有在熊市（价格跌破 200 均线）才允许空马丁 |
| 3 | 1h TREND_UP_prob ≤ 0.30（几乎没有上涨概率） | 防漏判上涨 |
| 4 | 最近 24h BTC 资金费率 ≥ 0.01%（正，多头付空头，做空还能赚资金费） | 让资金费率站在我们这边 |
| 5 | 当前总多头马丁仓位 = 0（不同时持有多马丁 + 空马丁） | 防止两边互相锁仓浪费手续费 |

5 条有任何 1 条不满足 → 直接禁止空头马丁新开仓。

---

## 49. 模型版本管理与回滚机制

### 49.1 模型命名规范

```
model_lgbm_v<MAJOR>_<YYYYMMDD>_<TAG>
  │          │        │          │
  │          │        │          └─ 可选：DEV / STAGE / PROD
  │          │        └─ 训练日期
  │          └─ 主版本号（重大变更 +1，特征/标签定义变了 +1）
  └─ 固定前缀 + 模型类型
```

示例：`model_lgbm_v3_20260915_PROD`

### 49.2 每个模型版本必须保存的元数据（JSON）

| 字段 | 说明 |
|------|------|
| model_version | 版本全名 |
| train_timerange | 训练数据时间窗口（如 20230101-20251231） |
| feature_list | 训练用特征名列表（按顺序） |
| label_version | 标签算法版本号（方便回滚） |
| label_thresholds | `up=5% down=5% window=30` |
| test_metrics | Test 集的 Accuracy / TREND_UP Recall / TREND_DOWN Recall / Confusion Matrix |
| backtest_ref_snapshot | 对应 Test C / Test D 的回测快照文件名 |
| author | 谁训练的 |

### 49.3 存储与回滚

```
user_data/freqai/models/
├── registry.json                    # 模型注册表（激活版本历史）
├── model_lgbm_v1_20260801_DEV/
├── model_lgbm_v2_20260901_STAGE/
├── model_lgbm_v2_20260915_PROD/     # 当前激活
└── rollback_candidates/             # 保留最近 5 个 PROD 版本，一键回滚
```

- `registry.json` 记录每次切换：切换时间、从哪个版本切到哪个版本、切换理由（指标提升 / Bug 修复 / 临时回滚）
- 线上 Demo / 实盘激活新版本前必须走：**回测达标 → Demo 小仓运行 3 个完整日 → 正式激活**
- 紧急情况（模型 1h 内 TREND 漏判 ≥ 2 次导致逆势补仓）：FreqUI 一键回退到前一个 PROD 版本，并立即发送 CRITICAL 告警

---

## 50. 交易执行细则

### 50.1 下单类型矩阵

| 动作 | 下单类型 | 说明 |
|------|---------|------|
| 马丁首仓开仓 | **限价 LIMIT（Post-Only=True）** | 挂在盘口内侧，赚 Maker 0.02% 费率；马丁不急着入场 |
| 马丁 DCA 补仓 | **限价 LIMIT（Post-Only=False）** | 补仓通常是跌了要吃单，Taker 但省点滑点，允许接盘口 |
| 趋势策略开仓 | **限价 IOC**（立即成交或取消） | 趋势信号出来要尽快入场，追不上就放弃 |
| 止盈 TP | **限价 LIMIT**（挂单长期挂着） | Freqtrade 内置 ROI 机制，自动挂限价单 |
| **止损 / 强制平仓（熔断）** | **市价 MARKET 或 限价 IOC × 2 级** | 🔴 保命优先，第一级 IOC 限价（当前价 × 0.995 多/×1.005 空），2 秒未成交 → 升级市价单 |
| 手动 FreqUI 平仓 | **限价 IOC → 市价兜底** | 同止损 |

### 50.2 滑点保护（订单执行前再检查一次）

每次向 OKX 提交订单前（特别是市价单 / 止损单）：

```python
MAX_ALLOWED_SLIPPAGE_PCT = 0.003   # 0.3% 绝对上限（可配置）

current_spread_pct = (ask - bid) / mid
if current_spread_pct > MAX_ALLOWED_SLIPPAGE_PCT * 0.5:  # 盘口价差已经太大
    # 马丁补仓：直接取消本次补仓，等下一根 K 线
    # 止损平仓：必须出，升级到市价 + 额外 0.2% 缓冲，接受成本
    pass
```

### 50.3 订单重试机制

| 错误类型 | 重试 | 策略 |
|---------|------|------|
| OKX 网络超时 / -1（未知） | 最多 2 次 | 第 1 次等 2s → 第 2 次等 5s → 失败记 CRITICAL 日志并告警 |
| 余额不足 / 超过持仓上限 / 保证金不够 | ❌ 不重试 | 立即失败，风控可能需要重新计算暴露 |
| 订单 ID 不存在 / 重复下单 | ❌ 不重试 | 查询订单状态确认，避免重复下单 |
| 非交易时段 / 维护中 | 指数退避 10s → 30s → 60s | 进入行情中断安全模式流程 |

---

# 第十四部分：极端行情（暴涨暴跌/插针）处理机制

## 51. 极端行情实时响应方案

> 🎯 你特别问的重点章节。
> 这一层是**超越 Risk Manager 常规回撤熔断**的、行情侧独立的实时保护。
> 与回撤熔断并行：**任一侧先触发，就取更严格的动作执行。**

---

### 51.1 极端行情量化分级定义（5 级）

```
Level 0: NORMAL        正常
Level 1: EXCURSION_W   暴涨暴跌预警（单 K 线异常移动）
Level 2: EXCURSION_E   暴涨暴跌升级（大 K 线或 24h 累计大波动）
Level 3: VOL_SQUEEZE   波动率挤压 / 持续单边
Level 4: EXTREME_S     极端行情（相当于 Strategy Controller EXTREME 状态）
```

每个级别的量化触发条件（命中任意一个即升对应级）：

| 级别 | 触发条件（任一满足即触发） | 持续冷却时间 |
|------|--------------------------|-------------|
| **L1 - 预警** | 1. 单根 15m K 线 涨/跌幅 **≥ 3%**<br>2. 10 秒内实时价格移动 **≥ 1%**（tick 级瞬时抖动） | 2 根 15m K 线 |
| **L2 - 升级** | 1. 单根 1h K 线 涨/跌幅 **≥ 5%**<br>2. 24h 累计涨跌幅 **≥ 15%**<br>3. L1 在 1h 内触发 ≥ 2 次 → 自动升级 L2 | 4 根 1h K 线 |
| **L3 - 挤压** | 1. 连续 5 根 15m K 线 **同方向**（全红 or 全绿）且累计 ≥ 8%<br>2. ATR(14) **≥ 过去 30 天 ATR 的 95 分位** 且持续 ≥ 3 根 1h | 6 根 1h K 线 |
| **L4 - 极端** | 1. 单根 1h K 线 涨/跌幅 **≥ 10%**<br>2. 24h 累计涨跌幅 **≥ 25%**<br>3. L2/L3 任何一个 4h 内触发 ≥ 3 次 | 24 小时（禁止提前结束） |

冷却时间：触发后进入该级别，冷却时间内即使条件不满足也保持当前级别，防止来回跳。L4 强制保持 24 小时，**确保极端情绪完全释放**。

---

### 51.2 插针（Long Wick / 假突破）豁免规则

暴涨暴跌中很常见一种假动作：**瞬间插针到极端价位，几秒钟内又拉回来**。这种不能当真实趋势，否则马丁会被假止损。

判定条件（任一满足即判为 WICK 插针）：
```
1. (high - low) > 3 × max(abs(open - close), 1)
   → 整根 K 线振幅 ≥ 3 倍实体长度，典型长上下影
2. |close - prev_close| < (high - low) × 0.3
   → 收盘价回到上一根 K 线附近，波动绝大多数被长影吃掉
3. 该根 K 线期间成交量 ≤ 过去 20 根均量 × 0.6
   → 无量插针，假动作概率大（放巨量插针是真实的，不豁免）
```

**插针豁免的应用范围：**
- ✅ 豁免 L1/L2 的升级（插针 15m 大 K 线不触发极端级别）
- ✅ 豁免 Strategy Controller 的新状态切换
- ❌ **不豁免止损/爆仓保护**（插针是真的会打到止损被强平的！止损线照常有效，甚至临时宽 0.5% 但不取消）
- ❌ **不允许在插针期间马丁补仓**（防止补到假插针半山腰被反向实锤套进去）

---

### 51.3 分级响应动作表（L1 → L4 逐级加码）

| 级别 | 新开仓 | 马丁 DCA 补仓 | 趋势策略 | 已有仓位止损 | 系统状态 |
|------|-------|-------------|---------|-------------|---------|
| **L0 正常** | 允许全量 | 按 AI 矩阵 | 允许全量 | 正常分级止损 | System State |
| **L1 预警** | Stake × **0.5** | **禁止**新补仓（无论 AI 怎么说） | 顺向允许，逆向禁止 | 止损线**收紧 20%**（止损距离 × 0.8） | 强制 TRANSITION |
| **L2 升级** | **禁止一切新开仓** | ❌ 全面禁止 | ❌ 趋势策略也禁止 | 止损线收紧 50% + 移动到**保本位**（多头：≥ avg_price，空头：≤ avg_price）<br>对逆势单直接发出"建议立即手动评估"告警 | 强制 EXTREME（非LOCKDOWN） |
| **L3 挤压** | ❌ 禁止 | ❌ 禁止 | ❌ 禁止 | **逆势持仓立即触发 IOC 平仓**（砍仓保本金）<br>顺向持仓自动止损移到成本线 + 盈利部分启动 trailing stop（ATR × 1） | 强制 EXTREME |
| **L4 极端** | ❌ 禁止 | ❌ 禁止 | ❌ 禁止 | **所有持仓启动"两级退出程序"**：<br>① 第一级：IOC 限价平 50% 仓位（先降一半风险）<br>② 第二级：剩余 50% 启动 trailing stop（ATR × 0.5），反弹到关键位（如 EMA20）再平<br>③ 如果同步触发账户回撤 ≥ 12% → 直接走 EMERGENCY 全部市价 | 自动 LOCKDOWN（不区分） |

---

### 51.4 爆仓防护最后一道防线（保证金/强平线监控）

独立线程 5 秒跑一次，不依赖任何 K 线收盘，也不被其他模块状态影响：

```python
def liquidation_protection_safeguard():
    for trade in all_open_trades:
        # 1. 计算当前强平预估价（OKX 给的强平价 or 自算）
        estimated_liq_price = okx_get_liquidation_price(trade)
        current_price = get_latest_price(trade.pair)
        distance_to_liq_pct = abs(current_price - estimated_liq_price) / current_price

        # 2. 三档红线
        if distance_to_liq_pct < 0.05:          # 距强平 < 5% → CRITICAL
            alert.critical(f"{trade.pair} 强平危险！剩余 {distance_to_liq_pct:.2%}")
            # 直接发市价单，对冲掉该仓位 100%（不管任何系统状态）
            emergency_market_close(trade, reason="LIQ_PROTECTION_5PCT")
        elif distance_to_liq_pct < 0.10:        # 距强平 < 10% → 立即减仓一半
            alert.warning(f"{trade.pair} 接近强平 10% 线")
            emergency_close_half(trade)
        elif distance_to_liq_pct < 0.15:        # 距强平 < 15% → 禁止本交易补仓 + 告警
            risk_manager.block_trade_dca(trade)
```

**这条是物理层：哪怕 Strategy Controller、Risk Manager 全崩了，只要进程还活着，这条线必须保住不被强平。**

---

### 51.5 历史典型极端案例对应处理路径

| 历史案例（参考时间） | 实际行情 | 预期系统动作 |
|---------------------|---------|-------------|
| **2022-05 LUNA 崩盘** | BTC 单周从 $38k → $25k（-34%），连续 7 根日阴线 | ① 第 2 根大阴线触发 L2 升级 → 禁止一切马丁<br>② 第 4 根 L3 挤压 → 多头立即砍仓<br>③ 一周内累计回撤肯定 ≥ 12% → LOCKDOWN<br>④ 整个崩溃期中**不会有一笔多头马丁补仓**（AI TREND_DOWN 也会识别到） |
| **2022-11 FTX 破产** | BTC 单日从 $21k → $15.5k（-26%） | ① 日内第一小时 -12% 直接跳 L4 极端<br>② L4 自动程序：IOC 平 50% 风险仓位 + 剩余 50% trailing<br>③ 插针到 $15.5k 时刻：**强平监控**距离检查生效，不允许被 OKX 强平，系统自己先平 |
| **2024-10 BTC ETF 通过** | BTC 10 月整月 +39%，连续逼空上涨 | ① 连续多日 L1/L2 切换 → 空头马丁 10 月初就被全面禁止（AI TREND_UP 早就触发）<br>② 不允许做空头马丁（第 48 节默认规则已经保护）<br>③ 趋势策略多头一直开着（从 EMA 金叉一直吃到尾） |
| **2023-03 美国银行危机** | BTC 2 天从 $20k → $26.5k（+32%）暴涨 + 插针 | ① 开盘第一小时 +8% → L2 升级<br>② 盘中插针：WICK 豁免识别 → 不胡乱砍仓，但是禁止插针期间补仓<br>③ 后续持续 + 涨 → TREND_UP 识别 → 空马丁禁止补仓 |
| **常规插针（5 秒下探 8% 又拉回）** | 常见于低流动性时段 | WICK 判定命中 → ① 不升级系统级别<br>② 止损线**临时放宽 0.5%**（典型防止假插针被扫损）<br>③ 马丁补仓在 WICK 这 15m 内 **不允许任何补仓**，等下一根 K 线确认收盘实体是否真实大跌 |

---

### 51.6 系统组件关系图

```
OKX 实时行情（每 2 秒 Ticker + 每根 K 线收盘）
    │
    ├──（每根 15m/1h 收盘）────────► ExtremerHandler.scan_bar()
    │                                   检查 5 个级别条件 + WICK 判定
    │                                         │
    │                                         ▼
    │                               升级到对应 Level + 冷却计时器启动
    │                                         │
    │                                         ▼
    │                               执行第 51.3 节响应动作表
    │                               → stake 倍率 / 禁止补仓 / 收紧止损
    │                               → 通知 StrategyController 覆盖系统状态
    │                                         │
    │                                         ▼
    │                               RiskManager 最终 Gate（动作在这里落地）
    │
    └──（每 5 秒实时）──────────► LiquidationSafeguard.run()
                                        距离强平百分比检查
                                              │
                                    distance < 15% / 10% / 5%
                                              │
                                              ▼
                              禁止补仓 → 减半 → 直接市价全平（保命）
```

---

# 第十五部分：运维与环境规范

## 52. 运维 SOP 标准操作手册

### 52.1 日常启动命令

```powershell
# ============= 前置必做 =============
# 1. 设置 UTF-8 编码（防止配置 UnicodeDecodeError）
$env:PYTHONUTF8 = "1"

# 2. 切换目录
Set-Location "d:\量化分析软件\freqtrade"

# ============= 启动模式 =============
# 模式 A：Dry Run（本机模拟，不连真实 API）
& ".venv\Scripts\freqtrade.exe" trade `
  --config config\config.json `
  --config config\freqai_config.json `
  --config config\risk_config.json `
  --config config\strategy_params.json `
  --dry-run

# 模式 B：OKX Demo 盘（交易所沙箱）
& ".venv\Scripts\freqtrade.exe" trade `
  --config user_data\configs\okx\模拟盘\config.json `
  --config config\risk_config.json `
  --config config\strategy_params.json

# 模式 C：OKX 实盘（⚠️ 高风险，确认再运行）
& ".venv\Scripts\freqtrade.exe" trade `
  --config user_data\configs\okx\实盘\config.json `
  --config config\risk_config.json `
  --config config\strategy_params.json

# 模式 D：回测（必须加上 --export trades，串行运行）
& ".venv\Scripts\freqtrade.exe" backtesting `
  --strategy AIMartingaleStrategy `
  --config config\config.json `
  --config config\freqai_config.json `
  --config config\risk_config.json `
  --config config\strategy_params.json `
  --timerange 20240101-20241231 `
  --export trades `
  --export-filename user_data\backtest_results\test_d_batch1
```

启动后检查：
- 日志没有 ERROR/CRITICAL 级别行
- FreqUI 能打开 http://127.0.0.1:8082 登录
- 系统状态显示非 LOCKDOWN（首次启动默认 LOCKDOWN，手动解除一次）
- AI 预测正常：看 `ai_regime.log` 有概率输出

### 52.2 LOCKDOWN 触发与解除 Checklist

**LOCKDOWN 触发时的处理流程：**

1. **立即响应**：收到 CRITICAL 告警，打开日志 + FreqUI
2. **确认持仓**：`FreqUI → Trades → Open Trades` 看剩余仓位，如果 EMERGENCY 触发应该已空仓，没清完手动补清
3. **定位根因**：查看 `risk_control.log` → 找 `EMERGENCY` / `CRITICAL` 行，确认是哪条规则触发
   - 回撤触发？ → 看最近 24h 行情 + AI 状态是否漏判趋势
   - 强平保护触发？ → 看是哪笔交易距强平 < 5%
   - 极端行情 L4 自动触发？ → 等待 24h 自然冷却
4. **修复措施**：
   - 参数问题 → 改配置 + 做对应场景回测确认修复 → 配置快照入库
   - AI 漏判 → 训练 v+1 模型（标签补样本）→ Demo 验证 3 天
5. **LOCKDOWN 解除**（满足全部才能解）：
   - [ ] 根因已明确 + 修复方案已回测通过
   - [ ] 当前系统状态 ≥ L0（不是 L4 冷却中）
   - [ ] 账户权益快照已记录
   - [ ] 在 FreqUI 点击 **FORCE START** 按钮（或 REST API），密码二次确认
   - [ ] 解除后前 2 小时 stake 倍率强制 0.5，不允许开 C 级信号

### 52.3 月度模型重训练流程

每月 1 号 UTC 00:00 执行：

1. `python scripts/download_data.py` → 下载上月最新数据入库
2. `python scripts/generate_labels.py --version current` → 生成新标签，检查 TREND/RANGE 比例是否稳定
3. `python scripts/train_regime_model.py --train-timerange "<2026年8月>" --test-timerange "20260801-"`
4. **Test 集指标检查**（第 19 节 6 项全部达标吗？）：
   - ✅ 指标达标 → 进入 Step 5
   - ❌ 指标下滑 → 回滚到上月模型 + 记录原因（可能行情特征变了，需要调标签阈值 / 加特征）
5. `Dry Run 3 天` → 回测同期 `Test C / Test D` 指标是否与上月持平
6. `Demo 小仓运行 3 天` → 实际交易频次 / AI 状态与历史一致
7. **正式切换 PROD 版本** → `registry.json` 登记

---

## 53. 绩效归因分类模板

每笔交易平仓后写入 `trades_execution.log` 的 `exit_reason_class` 字段，每月统计各分类占比：

| CLASS 编号 | 英文标签 | 定义 | 健康占比目标 |
|-----------|---------|------|-------------|
| C1 | `NORMAL_TP` | 正常止盈（ROI 命中 / 达到 take_profit_pct） | ≥ 65% |
| C2 | `GRADED_STOPLOSS` | DCA 分级止损（正常范围内被打掉） | 15% ~ 25% |
| C3 | `DCA_FULL_STOPLOSS` | DCA 达到 MAX_DCA_COUNT=3 后，行情仍未回归被止损 | ≤ 8% |
| C4 | `DRAWDOWN_EMERGENCY_EXIT` | 账户回撤熔断 LOCKDOWN 强制平仓 | ≤ 2%（单次都不应该有，> 0 就要复盘） |
| C5 | `AI_MISSED_TREND_LOSS` | 🔴 **AI 漏判导致的逆势亏损**<br>条件：平仓时的历史数据回检，发现入场后 20 根 K 线内 TREND 概率实际 ≥ 0.70 但 AI 当时判了 RANGE，结果逆势补仓亏 | ≤ **10%**（>10% → 必须调标签/重训 AI） |
| C6 | `EXTREME_HANDLER_EXIT` | 第 51 节极端行情处理下的平仓（L3/L4 主动退出） | ≤ 5% |
| C7 | `SAFE_MODE_EXIT` | 异常进入安全模式下的强制退出 | ≤ 1%（> 0 代表系统不稳定） |
| C8 | `MANUAL_EXIT` | 手动 FreqUI 平仓 | 不统计 |

**每月复盘看板 3 项核心指标：**
1. `C5 / 总平仓数 ≤ 10%` → AI 质量
2. `C4 + C6 + C7 合计 ≤ 5%` → 风控/异常稳定性
3. `C3 / (C1 + C2 + C3) ≤ 10%` → 马丁 DCA 摊低成本策略有效性（拉满 3 次还不回来的比例过高 → 补仓距离 / 金额不对）

---

## 54. 环境隔离规范

| 维度 | DEV 开发环境 | STAGE / DEMO 模拟盘 | PROD 实盘 |
|------|-------------|-------------------|----------|
| 运行场景 | 本地 Dry Run、回测、调试 | OKX Demo 沙箱 API（沙箱资金） | OKX LIVE（真实资金） |
| 配置目录 | `config/`（通用模板） | `user_data/configs/okx/模拟盘/` | `user_data/configs/okx/实盘/` |
| API Key | 无（Dry Run 不调用） | OKX Demo 专属 Key，仅 Demo 权限 | 独立 Key，**仅开通交易权限、绝对禁止提币权限**，IP 白名单绑定 |
| 模型版本 | `_DEV` 后缀，随便玩 | `_STAGE` 后缀，稳定候选 | `_PROD` 后缀，每月只允许切换 1 次，紧急回滚例外 |
| 账户初始资金 | dry_run_wallet = 100 USDT（项目约定） | OKX 沙箱资金，初始 ≥ 10,000 USDT | 真实资金 ≤ 用户可承受 100% 亏损金额 |
| 杠杆 / 风险 | 可用于压力测试，随便调 | V1 默认 3x，参数调优阶段 2x 起步 | 第 1 个月 2x + max_open_trades=2，第 2 个月达标后再升 3x |
| stake 倍率 | 1.0 | 1.0 | 起步 0.5 → 稳定后升 1.0 |
| FreqUI 监听地址 | 127.0.0.1:8080 | 127.0.0.1:8081 | 127.0.0.1:8082（项目已有） |
| 允许重启 / 改参数 | 随时 | 工作日白天，通知本人 | **禁止随意改参数**，改参必须经过 Dry Run → Demo 3 天 |
| 日志保留 | 7 天 | 90 天 | 永久 |
| 监控告警 | 仅日志 | WARNING 及以上邮件通知 | CRITICAL 邮件 + Telegram/Discord Webhook + **短信**（可选） |

**跨环境禁令（违反即事故）：**
- ❌ 绝对禁止把 PROD 的 Key 复制到 DEV / STAGE 配置里
- ❌ 绝对禁止不经过 STAGE 验证直接把 DEV 参数推 PROD
- ❌ 绝对禁止同一套模型不同时配置在三个环境里各自跑（DEV 可能是 v3-dev，PROD 还在 v1-prod，各跑各的）

---

只要这一点通过 **回测（A/B/C/D 四组对比 + 9 个极端场景压力测试）+ 模拟盘（≥ 4 周 OKX Demo）** 的组合验证，后面的 V2/V3/V4（动态资金分配、多策略组合、自动策略切换、Ensemble 模型等）才有继续开发的价值。

---

**文档结束**
