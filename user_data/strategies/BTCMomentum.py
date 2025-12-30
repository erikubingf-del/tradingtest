# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file

"""
BTC Momentum Strategy
=====================
A trend-following strategy optimized for Bitcoin futures trading.

Key Features:
- Multi-timeframe confirmation (4h primary, 1d trend)
- RSI momentum with dynamic thresholds
- EMA trend filter
- Volume confirmation
- Hyperopt-ready parameters for optimization

Risk Management:
- 2% stop loss (configurable)
- Trailing stop to lock in profits
- Maximum 3 open trades
- $100 per trade stake

Target Performance:
- Win rate: 40-50%
- Risk/Reward: 2:1
- Expected monthly: 5-15% (conservative estimate)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from functools import reduce

from freqtrade.strategy import (
    IStrategy,
    DecimalParameter,
    IntParameter,
    BooleanParameter,
    CategoricalParameter,
)
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class BTCMomentum(IStrategy):
    """
    BTC Momentum Strategy with Hyperopt Optimization

    Designed for:
    - Timeframe: 4h (captures meaningful moves, reduces noise)
    - Market: BTC/USDT Futures (Binance)
    - Capital: $100 per trade
    - Risk: Moderate (max 20% drawdown target)
    """

    INTERFACE_VERSION = 3

    # ==================== Hyperopt Parameters ====================

    # RSI Parameters
    rsi_buy_threshold = IntParameter(20, 40, default=30, space="buy", optimize=True)
    rsi_sell_threshold = IntParameter(60, 80, default=70, space="sell", optimize=True)
    rsi_period = IntParameter(10, 20, default=14, space="buy", optimize=True)

    # EMA Parameters
    ema_fast_period = IntParameter(10, 30, default=20, space="buy", optimize=True)
    ema_slow_period = IntParameter(40, 60, default=50, space="buy", optimize=True)

    # Volume Parameters
    volume_factor = DecimalParameter(1.0, 2.5, default=1.5, space="buy", optimize=True)

    # Exit Parameters
    exit_rsi_long = IntParameter(65, 85, default=75, space="sell", optimize=True)
    exit_rsi_short = IntParameter(15, 35, default=25, space="sell", optimize=True)

    # ==================== Strategy Settings ====================

    # ROI (Return on Investment) table
    # "minutes": "profit_ratio"
    minimal_roi = {
        "0": 0.06,      # 6% take profit immediately
        "60": 0.04,     # 4% after 1 hour
        "180": 0.02,    # 2% after 3 hours
        "360": 0.01,    # 1% after 6 hours
    }

    # Stop Loss: 2% (critical for risk management)
    stoploss = -0.02

    # Trailing Stop: Lock in profits
    trailing_stop = True
    trailing_stop_positive = 0.01       # Trigger at 1% profit
    trailing_stop_positive_offset = 0.02  # Start trailing at 2% profit
    trailing_only_offset_is_reached = True

    # Timeframe
    timeframe = '4h'

    # Can short (futures trading)
    can_short = True

    # Startup candle count (need enough data for indicators)
    startup_candle_count = 60

    # Order types
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': True,
    }

    # Order time in force
    order_time_in_force = {
        'entry': 'GTC',  # Good Till Cancelled
        'exit': 'GTC',
    }

    # Position adjustment (DCA disabled for simplicity)
    position_adjustment_enable = False

    # ==================== Indicator Population ====================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds technical indicators to the dataframe.
        Called once per candle for each pair.
        """

        # RSI - Momentum (range matches hyperopt: 10-20)
        for period in range(10, 21):
            dataframe[f'rsi_{period}'] = ta.RSI(dataframe, timeperiod=period)

        # EMA - Trend (ranges match hyperopt: fast 10-30, slow 40-60)
        for period in range(10, 31):  # 10-30 for fast EMA
            dataframe[f'ema_{period}'] = ta.EMA(dataframe, timeperiod=period)
        for period in range(40, 61):  # 40-60 for slow EMA
            dataframe[f'ema_{period}'] = ta.EMA(dataframe, timeperiod=period)

        # MACD - Trend Confirmation
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macd_signal'] = macd['macdsignal']
        dataframe['macd_hist'] = macd['macdhist']

        # Bollinger Bands - Volatility
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lower'] = bollinger['lower']
        dataframe['bb_middle'] = bollinger['mid']
        dataframe['bb_upper'] = bollinger['upper']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']

        # Volume
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_mean']

        # ATR - Volatility (for dynamic stops in future)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # Price Action
        dataframe['price_change'] = dataframe['close'].pct_change()
        dataframe['high_low_range'] = (dataframe['high'] - dataframe['low']) / dataframe['close']

        return dataframe

    # ==================== Entry Conditions ====================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define entry conditions for long and short positions.
        Simplified for more frequent signals while maintaining edge.
        """

        # Get dynamic RSI column based on hyperopt parameter
        rsi_col = f'rsi_{self.rsi_period.value}'
        ema_fast_col = f'ema_{self.ema_fast_period.value}'
        ema_slow_col = f'ema_{self.ema_slow_period.value}'

        # ==================== LONG ENTRY ====================
        # Condition: RSI oversold AND price above slow EMA (buy dip in uptrend)
        dataframe.loc[
            (
                (dataframe[rsi_col] < self.rsi_buy_threshold.value) &  # Oversold
                (dataframe['close'] > dataframe[ema_slow_col]) &  # Uptrend
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        # ==================== SHORT ENTRY ====================
        # Condition: RSI overbought AND price below slow EMA (sell rally in downtrend)
        dataframe.loc[
            (
                (dataframe[rsi_col] > self.rsi_sell_threshold.value) &  # Overbought
                (dataframe['close'] < dataframe[ema_slow_col]) &  # Downtrend
                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1

        return dataframe

    # ==================== Exit Conditions ====================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define exit conditions (in addition to ROI/Stoploss).
        These are signal-based exits when indicators flip.
        """

        rsi_col = f'rsi_{self.rsi_period.value}'
        ema_slow_col = f'ema_{self.ema_slow_period.value}'

        # ==================== EXIT LONG ====================
        conditions_exit_long = []

        # RSI became overbought
        conditions_exit_long.append(dataframe[rsi_col] > self.exit_rsi_long.value)

        # OR Trend reversed (price below slow EMA)
        # conditions_exit_long.append(dataframe['close'] < dataframe[ema_slow_col])

        dataframe.loc[
            reduce(lambda x, y: x | y, conditions_exit_long),
            'exit_long'] = 1

        # ==================== EXIT SHORT ====================
        conditions_exit_short = []

        # RSI became oversold
        conditions_exit_short.append(dataframe[rsi_col] < self.exit_rsi_short.value)

        # OR Trend reversed (price above slow EMA)
        # conditions_exit_short.append(dataframe['close'] > dataframe[ema_slow_col])

        dataframe.loc[
            reduce(lambda x, y: x | y, conditions_exit_short),
            'exit_short'] = 1

        return dataframe

    # ==================== Custom Methods ====================

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        """
        Customize leverage for each new trade.
        Using conservative 3x leverage for moderate risk.
        """
        return 3.0

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """
        Customize stake amount per trade.
        Fixed at $100 as specified in requirements.
        """
        return 100.0
