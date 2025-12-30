# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file

import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, stoploss_from_open
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class BtcMomentumRider(IStrategy):
    """
    BTC Momentum Rider Strategy
    - Timeframe: 4h
    - Trend: EMA (Optimized)
    - Momentum: RSI (Optimized)
    """
    INTERFACE_VERSION = 3

    # Hyperopt parameters
    buy_rsi = IntParameter(10, 50, default=34, space="buy")
    sell_rsi = IntParameter(60, 90, default=70, space="sell")
    ema_period = IntParameter(20, 200, default=75, space="buy")
    
    # ROI table: "time_in_minutes": "profit_ratio"
    minimal_roi = {
        "0": 0.04,
        "30": 0.02,
        "60": 0.01
    }

    # Stoploss: 2%
    stoploss = -0.02

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Timeframe
    timeframe = '4h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA for trend (Optimized period)
        # We calculate multiple to allow hyperopt to pick, or just one dynamic?
        # Standard Freqtrade pattern: Generate for all potential values OR just use the .value in backtest/hyperopt if careful.
        # Ideally, we should compute the one we need. But inside populate_indicators, 'self.ema_period.value' is available.
        
        for val in self.ema_period.range:
            dataframe[f'ema_{val}'] = ta.EMA(dataframe, timeperiod=val)

        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Use the optimized parameter value
        ema_col = f'ema_{self.ema_period.value}'
        
        dataframe.loc[
            (
                (dataframe['close'] > dataframe[ema_col]) &  # Uptrend
                (dataframe['rsi'] < self.buy_rsi.value) &    # Optimized Buy
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['close'] < dataframe[ema_col]) &  # Downtrend
                (dataframe['rsi'] > self.sell_rsi.value) &   # Optimized Sell
                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_col = f'ema_{self.ema_period.value}'
        
        dataframe.loc[
            (
                (dataframe['close'] < dataframe[ema_col]) &
                (dataframe['rsi'] > self.sell_rsi.value)
            ),
            'exit_long'] = 1

        dataframe.loc[
            (
                (dataframe['close'] > dataframe[ema_col]) &
                (dataframe['rsi'] < self.buy_rsi.value)
            ),
            'exit_short'] = 1
            
        return dataframe
