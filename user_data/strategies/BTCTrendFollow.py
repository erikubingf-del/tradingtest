# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file

"""
BTC Trend Follow Strategy (MAX Strategy)
=========================================
Based on academic research from QuantPedia (2024):
"Revisiting Trend-Following and Mean-Reversion Strategies in Bitcoin"

Key Finding: Buy BTC when it reaches a 20-day maximum - this momentum effect
has proven profitable from 2015-2024, including through the 2022-2024 bear market.

Research Source:
- https://quantpedia.com/revisiting-trend-following-and-mean-reversion-strategies-in-bitcoin/
- SSRN Paper: Beluská & Vojtko (2024)

The MAX strategy outperformed buy-and-hold with lower drawdowns.
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional
from functools import reduce

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
)
from pandas import DataFrame
import talib.abstract as ta


class BTCTrendFollow(IStrategy):
    """
    BTC Trend Following Strategy based on Academic Research

    Core Logic:
    - LONG: Buy when price reaches 20-day high (momentum breakout)
    - SHORT: Sell when price reaches 20-day low (momentum breakdown)

    This captures the momentum effect documented in academic research.
    """

    INTERFACE_VERSION = 3

    # ==================== Hyperopt Parameters ====================

    # Lookback period for MAX/MIN detection (research suggests 20 days optimal)
    lookback_period = IntParameter(10, 30, default=20, space="buy", optimize=True)

    # Confirmation: Price must be X% above/below the lookback high/low
    breakout_threshold = DecimalParameter(0.0, 0.02, default=0.005, space="buy", optimize=True)

    # ATR-based stop loss multiplier
    atr_sl_multiplier = DecimalParameter(1.5, 4.0, default=2.5, space="stoploss", optimize=True)

    # ==================== Strategy Settings ====================

    # ROI - Let winners run (research shows trend continuation)
    minimal_roi = {
        "0": 0.15,       # 15% take profit
        "1440": 0.08,    # 8% after 1 day
        "4320": 0.04,    # 4% after 3 days
        "10080": 0.02,   # 2% after 7 days
    }

    # Stop Loss: Wide stop as recommended by research
    # "Stop-losses don't work well... unless a very wide stop loss is set"
    stoploss = -0.08

    # Trailing Stop
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # Timeframe - Daily for trend following
    timeframe = '4h'

    # Can short
    can_short = True

    # Startup candle count
    startup_candle_count = 50

    # Order types
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': True,
    }

    # ==================== Indicator Population ====================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate MAX/MIN indicators based on research.
        """

        # Calculate rolling high/low for different lookback periods
        for period in range(10, 31):
            # Highest high in lookback period
            dataframe[f'highest_{period}'] = dataframe['high'].rolling(window=period * 6).max()  # 6 candles = 1 day at 4h
            # Lowest low in lookback period
            dataframe[f'lowest_{period}'] = dataframe['low'].rolling(window=period * 6).min()

        # ATR for volatility-based stops
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # Simple trend filter
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        # Volume confirmation
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()

        return dataframe

    # ==================== Entry Conditions ====================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        MAX Strategy: Buy when price reaches lookback-period high.
        This captures the momentum/breakout effect from research.
        """

        lookback = self.lookback_period.value
        threshold = self.breakout_threshold.value

        highest_col = f'highest_{lookback}'
        lowest_col = f'lowest_{lookback}'

        # ==================== LONG ENTRY (MAX Strategy) ====================
        # Buy when close >= highest high of lookback period (breakout)
        dataframe.loc[
            (
                (dataframe['close'] >= dataframe[highest_col] * (1 - threshold)) &  # At or near the high
                (dataframe['close'] > dataframe['ema_50']) &  # Above short-term trend
                (dataframe['volume'] > dataframe['volume_mean'] * 0.5) &  # Some volume
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        # ==================== SHORT ENTRY (MIN Strategy) ====================
        # Sell when close <= lowest low of lookback period (breakdown)
        dataframe.loc[
            (
                (dataframe['close'] <= dataframe[lowest_col] * (1 + threshold)) &  # At or near the low
                (dataframe['close'] < dataframe['ema_50']) &  # Below short-term trend
                (dataframe['volume'] > dataframe['volume_mean'] * 0.5) &
                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1

        return dataframe

    # ==================== Exit Conditions ====================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit when momentum reverses.
        """

        lookback = self.lookback_period.value
        lowest_col = f'lowest_{lookback}'
        highest_col = f'highest_{lookback}'

        # Exit long if price drops to lookback low (momentum died)
        dataframe.loc[
            (
                (dataframe['close'] <= dataframe[lowest_col] * 1.02) &  # Near the low
                (dataframe['close'] < dataframe['ema_50'])
            ),
            'exit_long'] = 1

        # Exit short if price rises to lookback high (momentum reversed)
        dataframe.loc[
            (
                (dataframe['close'] >= dataframe[highest_col] * 0.98) &
                (dataframe['close'] > dataframe['ema_50'])
            ),
            'exit_short'] = 1

        return dataframe

    # ==================== Custom Methods ====================

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        """Conservative 2x leverage for trend following."""
        return 2.0

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """Fixed $100 per trade."""
        return 100.0
