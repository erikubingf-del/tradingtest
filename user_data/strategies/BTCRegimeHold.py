from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, stoploss_from_open
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class BTCRegimeHold(IStrategy):
    """
    BTC Regime Hold Strategy
    - Logic: 
        - Enter when price > MA(233) * 1.005
        - Exit when price < MA(233)
        - Leverage: 2x (Implied in analysis, not code)
    """
    INTERFACE_VERSION = 3
    can_short = False 

    # Parameters from User Claim
    ma_period = IntParameter(200, 300, default=233, space="buy")
    cross_buffer = DecimalParameter(0.001, 0.01, default=0.005, space="buy")
    exit_buffer = DecimalParameter(0.001, 0.01, default=0.005, space="sell") # 0.5% buffer

    # ROI: Hold forever (until exit signal)
    minimal_roi = {
        "0": 100.0 
    }

    # Stoploss: -25% (Wide)
    stoploss = -0.25 

    # Trailing stop: None
    trailing_stop = False

    # Timeframe: 4h
    timeframe = '4h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. Simple Moving Average (SMA), not EMA
        dataframe['ma_regime'] = ta.SMA(dataframe, timeperiod=self.ma_period.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry: Cross FROM BELOW to ABOVE MA * 1.005
        # We simulate "Cross" by checking if close > threshold and OPEN < threshold (or previous close)
        # But simply close > buffer is usually enough for Freqtrade if we rely on "exit" to clear position.
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ma_regime'] * (1 + self.cross_buffer.value)) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit: Price crosses FROM ABOVE to BELOW MA * 0.995
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['ma_regime'] * (1 - self.exit_buffer.value)) 
            ),
            'exit_long'] = 1
        return dataframe
