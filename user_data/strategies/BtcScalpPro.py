from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, stoploss_from_open
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import pandas_ta as pta

class BtcScalpPro(IStrategy):
    """
    BTC Scalp Pro Strategy (High Frequency)
    - Aim: "Quick Trading" to capture all gains and avoid losses.
    - Logic: Heikin Ashi + EWO + RSI on 5m timeframe.
    """
    INTERFACE_VERSION = 3
    can_short = True # Scalping needs to play both sides

    # Hyperopt parameters
    buy_rsi = IntParameter(10, 50, default=30, space="buy")
    sell_rsi = IntParameter(50, 90, default=70, space="sell")
    
    # EWO limits
    ewo_high = DecimalParameter(2.0, 10.0, default=5.0, space="buy")
    ewo_low = DecimalParameter(-10.0, -2.0, default=-5.0, space="buy")

    # Fast EMA
    fast_ema = IntParameter(5, 20, default=10, space="buy")
    slow_ema = IntParameter(20, 50, default=30, space="buy")

    # ROI table: Quick Scalps
    minimal_roi = {
        "0": 0.04,     # Take 4% instantly
        "10": 0.02,    # Take 2% after 10 mins
        "20": 0.01     # Take 1% after 20 mins
    }

    # Stoploss: Tight for Scalping
    stoploss = -0.03  # 3% max loss per trade

    # Trailing stop: Crucial for scalping
    trailing_stop = True
    trailing_stop_positive = 0.005    # Lock in at 0.5%
    trailing_stop_positive_offset = 0.01 # Trail after 1% gain
    trailing_only_offset_is_reached = True

    # Timeframe
    timeframe = '5m' # High Frequency

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. Heikin Ashi
        heikinashi = qtpylib.heikinashi(dataframe)
        dataframe['ha_open'] = heikinashi['open']
        dataframe['ha_close'] = heikinashi['close']
        dataframe['ha_high'] = heikinashi['high']
        dataframe['ha_low'] = heikinashi['low']

        # 2. EWO (Elliott Wave Oscillator)
        # qtpylib.ewo doesn't exist, using manual calculation
        # EWO = EMA(5) - EMA(35) of Close (Simplified for crypto)
        fast_ma = ta.EMA(dataframe['ha_close'], timeperiod=5)
        slow_ma = ta.EMA(dataframe['ha_close'], timeperiod=35)
        dataframe['ewo'] = fast_ma - slow_ma

        # 3. RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # 4. EMA
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=10)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=30)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['ewo'] > self.ewo_high.value) &           # Strong Momentum
                (dataframe['rsi'] < self.sell_rsi.value) &           # Not Overbought
                (dataframe['ha_close'] > dataframe['ema_fast']) &    # Trend Up
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['ewo'] < self.ewo_low.value) &            # Strong Down Momentum
                (dataframe['rsi'] > self.buy_rsi.value) &            # Not Oversold
                (dataframe['ha_close'] < dataframe['ema_fast']) &    # Trend Down
                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit long if RSI is high or EWO Drops
        dataframe.loc[
            (
                (dataframe['rsi'] > 80) |
                (dataframe['ewo'] < 0)
            ),
            'exit_long'] = 1

        # Exit short if RSI is low or EWO Rises
        dataframe.loc[
            (
                (dataframe['rsi'] < 20) |
                (dataframe['ewo'] > 0)
            ),
            'exit_short'] = 1
            
        return dataframe
