# 🛡️ Sentinel V7 — Reinforcement Learning Swing Trading System

**Status:** Active Development
**Core Framework:** Stable-Baselines3 (PPO)
**Domain:** Algorithmic Trading / Reinforcement Learning
**Architecture:** Config-driven ML pipeline

Sentinel V7 is a **Reinforcement Learning based trading system** designed to learn swing-trading strategies from historical market data and news sentiment.

The system trains a **Proximal Policy Optimization (PPO)** agent to interact with a simulated trading environment and learn optimal buy/sell/hold decisions.

The architecture emphasizes:

* **Reproducibility**
* **Experiment tracking**
* **Modular ML pipelines**
* **Config-driven experimentation**

All experiments are controlled through a central configuration file (`settings.py`), allowing systematic testing of different environments, reward functions, and hyperparameters.

---

# 1. Project Goal

The objective of Sentinel V7 is to build an **AI trading agent that can learn profitable trading behavior from historical data**, using:

* market indicators
* volatility regimes
* macro context
* sentiment information

The agent learns a **policy** that maximizes long-term portfolio value by interacting with a simulated trading environment.

Key goals:

• learn profitable swing-trading strategies
• minimize over-trading and drawdowns
• create a reproducible ML experimentation framework
• evaluate RL trading vs classical baselines

---

# 2. System Architecture

The system is structured as a **modular ML pipeline**.

All major experiment parameters are defined in:

```
config/settings.py
```

This file acts as the **Control Room** of the project.

Changing parameters in this file automatically updates the behavior of the entire pipeline.

---

# 3. Project Pipeline

The project workflow consists of the following stages/python files.

| Step | Script           | Purpose                                     |
| ---- | ---------------- | ------------------------------------------- |
| 1    | `data_engine.py` | Downloads and builds the hybrid dataset     |
| 2    | `processor.py`   | Feature engineering and feature scaling     |
| 3    | `train.py`       | Trains the PPO reinforcement learning agent |
| 4    | `backtest.py`    | Evaluates the trained model on unseen data  |
| 5    | `optimize.py`    | Hyperparameter optimization using Optuna    |
| 6    | `live_trader.py` | Deploys the trained model for live trading  |

---

# 4. Data Sources

The system combines **market data and news sentiment**.

## Market Data — Yahoo Finance

Retrieved via:

```
yfinance
```

Used features include:

• Open
• High
• Low
• Close
• Volume

These form the base dataset for all technical indicators.

---

## News Data — Alpaca API

The Alpaca API is used to retrieve **financial news headlines** related to the traded asset.

From this data the system derives:

• news intensity (news frequency)
• sentiment scores

These features allow the agent to consider **market sentiment** alongside technical indicators.

---

# 5. Feature Engineering

The raw data is transformed into a set of **technical, macro, and contextual features**.

Feature generation occurs in:

```
core/processor.py
```

### 5.1 Technical Indicators

Derived from price and volume data.

Examples:

| Feature                 | Description                    |
| ----------------------- | ------------------------------ |
| RSI                     | Relative Strength Index        |
| MACD Histogram          | Momentum indicator             |
| Bollinger Band Position | Relative position within bands |
| ATR Percent             | Volatility indicator           |
| Volume Z-Score          | Normalized trading volume      |

---

### 5.2 Volatility Regime Features

The agent receives information about the current volatility environment.

Examples:

• short-term realized volatility
• long-term realized volatility
• volatility regime classification

---

### 5.3 Market Context

Macro-market indicators are incorporated to provide broader context.

Examples:

| Feature           | Source          |
| ----------------- | --------------- |
| QQQ returns       | Nasdaq ETF      |
| ARKK returns      | Innovation ETF  |
| Relative strength | Stock vs market |

---

### 5.4 Macro Risk Indicators

These capture overall market risk.

Examples:

| Feature | Description                 |
| ------- | --------------------------- |
| VIX_Z   | Z-score of volatility index |
| TNX_Z   | Z-score of treasury yields  |

---

### 5.5 Time Features

For hourly trading models the agent receives cyclical time information.

Examples:

• sin(time)
• cos(time)
• minutes to market close

These allow the model to learn **intraday behavioral patterns**.

---

# 6. Feature Scaling

All features are normalized using:

```
RobustScaler
```

This scaler is chosen because it is robust to financial data outliers.

The scaler is:

• fitted during training
• saved to the experiment artifact directory
• reused during inference and backtesting

---

# 7. Reinforcement Learning Environment

The trading environment is implemented in:

```
core/environment.py
```

The agent interacts with the environment in discrete timesteps.

At each timestep the agent receives:

```
Observation = market_features + portfolio_state
```

Portfolio state features include:

• whether a position is open
• unrealized profit/loss
• remaining cash ratio
• time spent in the trade

---

# 8. Action Space

The agent can operate under two trading styles.

### Discrete 3 (Conviction Trading)

```
0 → Sell all
1 → Buy all
2 → Hold
```

Encourages decisive swing-trading behavior.

---

### Discrete 5 (Scaling)

```
0 → Sell 100%
1 → Sell 50%
2 → Hold
3 → Buy 50%
4 → Buy 100%
```

Allows gradual position sizing.

---

# 9. Reward Function

The reward function determines how the agent learns.

Two strategies are implemented.

### Absolute Asymmetric Reward

```
profit reward = +1x
loss penalty = -2x
```

Encourages strong loss aversion and capital preservation.

---

### Pure PnL Reward

```
reward = portfolio return
```

Directly optimizes profitability.

---

# 10. Hyperparameter Optimization

The PPO hyperparameters are optimized using **Optuna**.

```
scripts/optimize.py
```

Parameters optimized include:

• learning rate
• batch size
• discount factor (gamma)
• entropy coefficient

Optimization uses a **train/validation split** to avoid overfitting.

---

# 11. Artifact Tracking (Reproducibility)

Each experiment automatically generates an artifact directory.

Example:

```
artifacts/
ppo_TSLA_1h_d5_asym_pen10_lr00007_bs128_g091_v1/
```

This folder contains:

| File                | Purpose               |
| ------------------- | --------------------- |
| model.zip           | trained PPO policy    |
| scaler.pkl          | feature scaler        |
| metadata.json       | experiment parameters |
| backtest_ledger.csv | executed trades       |

This design ensures **full reproducibility of every experiment**.

---

# 12. Running the Pipeline

### 1️⃣ Configure experiment

Edit:

```
config/settings.py
```

Set:

• asset symbol
• timeframe
• action space
• reward function
• training dates

---

### 2️⃣ Build dataset

```
python scripts/data_engine.py
```

Downloads market and news data.

---

### 3️⃣ Train the RL agent

```
python scripts/train.py
```

This step:

• creates the environment
• trains the PPO model
• saves the trained policy

---

### 4️⃣ Backtest the strategy

```
python scripts/backtest.py
```

This evaluates the model on **unseen test data**.

Outputs include:

• portfolio value
• total return
• transaction log

---

### 5️⃣ Optimize PPO hyperparameters (optional)

```
python scripts/optimize.py
```

Runs an Optuna search to find better PPO settings.

---

# 13. Future Work

Potential improvements include:

• multi-asset portfolios
• risk-adjusted reward functions
• transaction cost modeling
• ensemble RL agents
• live trading deployment

---

If you want, I can also help you add **two things that teachers often expect in ML project READMEs but are currently missing**:

1️⃣ **A visual architecture diagram of the pipeline**
2️⃣ **An explanation of PPO and reinforcement learning in this project**

Both usually improve project grading significantly.
