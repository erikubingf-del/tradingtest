# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file

"""
BTC 200MA Regime Strategy
=========================
Based on research from Bitcoin Magazine Pro and multiple backtests showing
this simple strategy OUTPERFORMS buy-and-hold.

Core Rule:
- Price > 200 MA = BULL MARKET → Hold leveraged long
- Price < 200 MA = BEAR MARKET → Hold 100% cash (no position)

Why it works:
1. Captures the majority of upside during bull markets
2. Preserves capital during bear markets (avoids 50-80% drawdowns)
3. Simple, robust, no overfitting

Sources:
- https://www.bitcoinmagazinepro.com/bitcoin-research/a-simple-strategy-that-has-outperformed-bitcoin/
- https://medium.com/@chrispark_ic/beating-bitcoin-a-quants-journey-through-failed-models-to-a-winning-strategy-b372f8b58678
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
)
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class BTC200MARegime(IStrategy):
    """
    200 Moving Average Regime Strategy

    Ultra-simple strategy that beats buy-and-hold:
    - LONG when price > 200 MA (bull regime)
    - CASH when price < 200 MA (bear regime)

    NO SHORTING - just long or cash.
    """

    INTERFACE_VERSION = 3

    # ==================== Hyperopt Parameters ====================

    # MA period (research suggests 200 days = ~1200 candles at 4h, but we'll test 50-period which = 200h = 8.3 days on 4h)
    # For 4h timeframe: 200 days = 1200 candles, but that's a lot
    # Let's use a range that makes sense for 4h: 50-300 period
    ma_period = IntParameter(100, 300, default=200, space="buy", optimize=True)

    # Re-entry buffer: require price to be X% above MA to enter (avoid whipsaws)
    entry_buffer = DecimalParameter(0.0, 0.03, default=0.01, space="buy", optimize=True)

    # Exit buffer: exit when price falls X% below MA
    exit_buffer = DecimalParameter(0.0, 0.03, default=0.005, space="sell", optimize=True)

    # ==================== Strategy Settings ====================

    # ROI - Very high, let the trend run
    minimal_roi = {
        "0": 0.50,       # 50% take profit (let it run!)
        "10080": 0.20,   # 20% after 7 days
        "43200": 0.10,   # 10% after 30 days
    }

    # Stop Loss - Wide stop, trust the 200MA exit
    stoploss = -0.15

    # Trailing Stop - Lock in profits during strong trends
    trailing_stop = True
    trailing_stop_positive = 0.03      # Start trailing at 3% profit
    trailing_stop_positive_offset = 0.05  # Trigger trailing at 5% profit
    trailing_only_offset_is_reached = True

    # Timeframe
    timeframe = '4h'

    # IMPORTANT: NO SHORTING - Long only strategy
    can_short = False

    # Startup candle count
    startup_candle_count = 300

    # Order types
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': True,
    }

    # ==================== Indicator Population ====================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Calculate the 200 MA for regime detection."""

        # Calculate MAs for all periods in hyperopt range (100-300, every value)
        for period in range(100, 301):  # 100, 101, 102, ... 300
            dataframe[f'ma_{period}'] = ta.SMA(dataframe, timeperiod=period)

        # EMA 200 for reference
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        # Additional trend confirmation
        dataframe['ma_50'] = ta.SMA(dataframe, timeperiod=50)

        # Golden/Death Cross detection
        dataframe['golden_cross'] = (
            (dataframe['ma_50'] > dataframe['ma_200']) &
            (dataframe['ma_50'].shift(1) <= dataframe['ma_200'].shift(1))
        ).astype(int)

        dataframe['death_cross'] = (
            (dataframe['ma_50'] < dataframe['ma_200']) &
            (dataframe['ma_50'].shift(1) >= dataframe['ma_200'].shift(1))
        ).astype(int)

        # Bull regime: price above 200 MA
        dataframe['bull_regime'] = (dataframe['close'] > dataframe['ma_200']).astype(int)

        # RSI for additional timing (optional)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # ATR for volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    # ==================== Entry Conditions ====================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Enter LONG when in bull regime (price > 200 MA).
        That's it. Simple.
        """

        ma_col = f'ma_{self.ma_period.value}'
        entry_threshold = 1 + self.entry_buffer.value

        # LONG ENTRY: Price above 200 MA (with optional buffer)
        dataframe.loc[
            (
                (dataframe['close'] > dataframe[ma_col] * entry_threshold) &  # Above MA with buffer
                (dataframe['close'] > dataframe['ma_50']) &  # Additional confirmation
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    # ==================== Exit Conditions ====================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit when regime changes to bearish (price < 200 MA).
        """

        ma_col = f'ma_{self.ma_period.value}'
        exit_threshold = 1 - self.exit_buffer.value

        # EXIT LONG: Price falls below 200 MA (with buffer)
        dataframe.loc[
            (
                (dataframe['close'] < dataframe[ma_col] * exit_threshold) |  # Below MA
                (dataframe['death_cross'] == 1)  # Or death cross occurred
            ),
            'exit_long'] = 1

        return dataframe

    # ==================== Custom Methods ====================

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        """
        Use 2x leverage during bull regime as per the research.
        Conservative leverage captures more upside while limiting risk.
        """
        return 2.0

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """Fixed $100 per trade."""
        return 100.0
