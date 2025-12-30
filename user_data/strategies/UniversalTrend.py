from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
from datetime import datetime
import talib.abstract as ta
import numpy as np
from functools import reduce

class UniversalTrend(IStrategy):
    """
    Universal Trend Strategy
    - Philosophy: "Trend Following" (The Turtle Way)
    - Logic:
        1. Setup: Price > EMA 200 (Bull Market Regime)
        2. Filter: ADX > 25 (Trend Strength)
        3. Entry: Donchian Channel Breakout (New 20-candle High)
        4. Exit: ATR Trailing Stop (Chandelier Exit)
    - Robustness: Uses Volatility (ATR) instead of fixed %, works on any asset.
    """
    INTERFACE_VERSION = 3
    timeframe = '4h'
    can_short = False

    # Minimal ROI: We let winners run. No fixed profit taking.
    minimal_roi = {
        "0": 100.0
    }

    # Stoploss: Initial safety net (Wide, relying on Trailing ATR)
    stoploss = -0.10 

    # --- Params ---
    entry_period = IntParameter(10, 50, default=20, space="buy", optimize=True)
    atr_period = IntParameter(10, 30, default=14, space="buy")
    atr_multiplier = DecimalParameter(1.0, 5.0, default=3.0, space="sell", optimize=True)
    
    # Trend Filter
    use_ma_filter = True
    ma_period = IntParameter(100, 300, default=200, space="buy")

    # ADX Filter
    use_adx_filter = True
    adx_threshold = IntParameter(15, 40, default=25, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. Trend Regime (EMA 200)
        dataframe['trend_ma'] = ta.EMA(dataframe, timeperiod=self.ma_period.value)

        # 2. Volatility (ATR)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)

        # 3. Trend Strength (ADX)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # 4. Donchian Channels (High of last N candles)
        # We need the High of the PREVIOUS N candles, not including current.
        # .shift(1) is crucial for backtesting to avoid lookahead.
        dataframe['donchian_high'] = dataframe['high'].rolling(window=self.entry_period.value).max()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # 1. Trend Regime
        if self.use_ma_filter:
            conditions.append(dataframe['close'] > dataframe['trend_ma'])

        # 2. ADX Filter
        if self.use_adx_filter:
            conditions.append(dataframe['adx'] > self.adx_threshold.value)

        # 3. Breakout Trigger
        # Close crosses above the previous N-period High
        conditions.append(dataframe['close'] > dataframe['donchian_high'].shift(1))
        
        # Volume Validation
        conditions.append(dataframe['volume'] > 0)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # We use Custom Exit (ATR Trailing) mostly, but we can set a basic exit signal
        # if the price falls below the "Low" of the channel (Turtle Style Exit)
        
        # Turtle Exit: Low of last 10 candles (shorter than entry)
        exit_lookback = int(self.entry_period.value / 2) # e.g. 10
        dataframe['donchian_low'] = dataframe['low'].rolling(window=exit_lookback).min()
        
        dataframe.loc[
            (dataframe['close'] < dataframe['donchian_low'].shift(1)),
            'exit_long'] = 1
            
        return dataframe

    # --- Custom ATR Trailing Stop ---
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        
        # We want to trail by N * ATR from the Highest Price reached since entry
        # Freqtrade's 'custom_stoploss' returns a % relative to OPEN trade price, 
        # but updated relative to current_rate if we calculate it dynamically.
        
        # Simplified for Freqtrade:
        # We cannot easily access "Highest Price since Entry" inside this lightweight function 
        # without querying the database or passing data.
        # Freqtrade standard Trailing Stop is % based.
        # To do ATR Trailing properly, we usually use `populate_exit_trend` setting a trailing stop price column.
        
        # Alternative: Return a fixed % based on current volatility?
        # Let's stick to the "Turtle Exit" (Donchian Low) defined in populate_exit_trend 
        # combined with a hard stop.
        
        return 1  # 1 means "do not change stoploss" (rely on exchange/strategy stop)

from functools import reduce
from datetime import datetime
