"""
TREND FOLLOWING BOT - STRATEGY SPECIFICATION
=============================================

This document defines the EXACT rules for the trend-following bot.
Every decision is logged to CSV for verification and backtesting.

TARGET: 20% CAGR over 10-year periods
METHOD: Adaptive leverage on confirmed trends across 50+ assets

================================================================================
STRATEGY RULES
================================================================================

1. ENTRY CRITERIA (ALL must be TRUE)
------------------------------------
   a) 12-Month Momentum > 0
      - Formula: (Close - Close_252days_ago) / Close_252days_ago > 0

   b) Price > 200-day SMA
      - Formula: Close > SMA(Close, 200)

   c) 50-day SMA > 200-day SMA (Golden Cross)
      - Formula: SMA(Close, 50) > SMA(Close, 200)

   d) Donchian Breakout (20-day high)
      - Formula: Close > Highest_High(20) [previous day]

   e) No existing position in this asset

   ENTRY SIZE: 2% of portfolio

2. LEVERAGE INCREASE CRITERIA (ALL must be TRUE)
------------------------------------------------
   a) Position is profitable > 3%
      - Formula: (Current_Price - Entry_Price) / Entry_Price > 0.03

   b) Held position for at least 10 days

   c) All 3 trend signals still agree:
      - 12-month momentum > 0
      - Price > 50-day SMA
      - Price > 200-day SMA

   LEVERAGE: Increase to 1.5x

3. MAXIMUM LEVERAGE CRITERIA (ALL must be TRUE)
-----------------------------------------------
   a) Position is profitable > 8%
      - Formula: (Current_Price - Entry_Price) / Entry_Price > 0.08

   b) Held position for at least 20 days

   c) 12-month momentum is ACCELERATING
      - Formula: Mom_12m_today > Mom_12m_5days_ago

   d) ATR is stable or decreasing (low volatility)
      - Formula: ATR_20 <= ATR_20_10days_ago * 1.2

   LEVERAGE: Increase to 2.0x (maximum)

4. LEVERAGE DECREASE CRITERIA (ANY triggers deleverage)
-------------------------------------------------------
   a) Pullback from peak > 2%
      - Formula: (Peak_Price - Current_Price) / Peak_Price > 0.02

   b) Momentum weakening
      - Formula: Mom_12m_today < Mom_12m_5days_ago * 0.8

   c) Price crosses below 50-day SMA

   d) Held with leverage > 60 days

   ACTION: Reduce leverage to 1.0x

5. EXIT CRITERIA (ANY triggers exit)
------------------------------------
   a) Stop Loss: Price drops 8% from entry
      - Formula: (Current_Price - Entry_Price) / Entry_Price < -0.08

   b) Trailing Stop: Price drops 3 ATR from peak
      - Formula: Current_Price < Peak_Price - 3 * ATR_20

   c) Trend Reversal: Price < 200-day SMA AND 50-day SMA < 200-day SMA

   d) Momentum Reversal: 12-month momentum turns negative
      - Formula: Mom_12m < 0

   e) Signal Reversal: Entry criteria now favors opposite direction

6. POSITION SIZING
------------------
   - Initial: 2% of portfolio per position
   - After leverage: Up to 4% effective exposure (2% * 2x)
   - Maximum positions: 20 concurrent
   - Maximum per sector: 4 positions
   - Maximum correlated exposure: 30%

7. RISK MANAGEMENT
------------------
   - Maximum portfolio leverage: 1.5x average
   - Maximum drawdown trigger: -15% reduces all positions by 50%
   - Daily loss limit: -3% halts new entries for the day

================================================================================
CSV OUTPUT COLUMNS
================================================================================

Daily log file: trades_YYYYMMDD.csv

Columns:
- date: YYYY-MM-DD
- ticker: Asset symbol
- action: SCAN | ENTRY | HOLD | LEVERAGE_UP | LEVERAGE_DOWN | EXIT
- position_status: NONE | OPEN | CLOSED
- direction: LONG | SHORT | NONE

Price Data:
- close: Current close price
- high_20d: 20-day high (Donchian)
- low_20d: 20-day low (Donchian)
- sma_50: 50-day SMA
- sma_200: 200-day SMA

Indicators:
- mom_12m: 12-month momentum (%)
- mom_12m_5d_ago: Momentum 5 days ago (for acceleration)
- atr_20: 20-day ATR
- atr_20_10d_ago: ATR 10 days ago
- volatility_60d: 60-day realized volatility

Position Info (if open):
- entry_date: When position opened
- entry_price: Entry price
- days_held: Days in position
- current_pnl_pct: Unrealized P&L %
- peak_price: Highest price since entry
- peak_pnl_pct: Best P&L achieved
- current_leverage: Current leverage (1.0, 1.5, or 2.0)
- position_size_pct: Position as % of portfolio

Signals:
- signal_momentum: 1 (bullish) / 0 (neutral) / -1 (bearish)
- signal_ma_cross: 1 / 0 / -1
- signal_price_vs_ma: 1 / 0 / -1
- signal_breakout: 1 / 0 / -1
- signal_combined: Average of above signals

Decision:
- decision: The action taken
- decision_reason: Detailed explanation
- entry_criteria_met: True/False
- leverage_up_criteria_met: True/False
- leverage_down_criteria_met: True/False
- exit_criteria_met: True/False

Portfolio:
- portfolio_equity: Current portfolio value
- portfolio_cash: Available cash
- portfolio_positions: Number of open positions
- portfolio_leverage: Average portfolio leverage

================================================================================
"""

# Strategy constants - these are the EXACT rules
STRATEGY_PARAMS = {
    # Entry
    'entry_mom_threshold': 0.0,           # 12m momentum > 0%
    'entry_position_size': 0.02,          # 2% initial position

    # Leverage up
    'leverage_up_profit': 0.03,           # 3% profit required
    'leverage_up_days': 10,               # 10 days minimum hold
    'leverage_medium': 1.5,               # First leverage level

    # Max leverage
    'leverage_max_profit': 0.08,          # 8% profit required
    'leverage_max_days': 20,              # 20 days minimum hold
    'leverage_max': 2.0,                  # Maximum leverage

    # Leverage down
    'leverage_down_pullback': 0.02,       # 2% pullback from peak
    'leverage_down_mom_decay': 0.8,       # 20% momentum decay
    'leverage_max_duration': 60,          # Max days with leverage

    # Exit
    'exit_stop_loss': -0.08,              # -8% stop loss
    'exit_trailing_atr': 3.0,             # 3 ATR trailing stop

    # Risk management
    'max_positions': 20,
    'max_sector_positions': 4,
    'max_correlated_exposure': 0.30,
    'max_portfolio_leverage': 1.5,
    'drawdown_reduction_trigger': -0.15,
    'daily_loss_halt': -0.03,
}
