from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, stoploss_from_open
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class BtcProfitMaximizer(IStrategy):
    """
    BTC Profit Maximizer Strategy (Trend Following)
    - Aim: Capture Bull Market gains (Beat Buy & Hold).
    - Logic:
        1. Trend: EMA Short > EMA Long (Golden Cross logic).
        2. Momentum: MACD > Signal.
        3. Volatility: Close > BB Middle (Breakout).
    """
    INTERFACE_VERSION = 3
    can_short = False # Shorting failed backtest. Reverting to Long Only.

    # Hyperopt parameters
    buy_rsi = IntParameter(20, 70, default=100, space="buy") # Disable RSI check (Aggressive)
    
    # EMA Trend (Aggressive Golden Cross)
    ema_short_period = IntParameter(10, 50, default=9, space="buy")
    ema_long_period = IntParameter(50, 200, default=21, space="buy")

    # ROI table: Let profits run!
    minimal_roi = {
        "0": 0.50,      # Aim for moon
        "240": 0.20,
        "480": 0.10,
        "960": 0.05
    }

    # Stoploss: Wide breathing room
    stoploss = -0.15  # 15% max risk

    # Trailing stop: Wide to avoid shakeouts
    trailing_stop = True
    trailing_stop_positive = 0.05     # Lock in at 5%
    trailing_stop_positive_offset = 0.10 # Trail only after 10% gain
    trailing_only_offset_is_reached = True

    # Timeframe
    timeframe = '4h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. Trend Indicators (EMA)
        for val in self.ema_short_period.range:
            dataframe[f'ema_short_{val}'] = ta.EMA(dataframe, timeperiod=val)
        
        for val in self.ema_long_period.range:
            dataframe[f'ema_long_{val}'] = ta.EMA(dataframe, timeperiod=val)

        # 2. Momentum (MACD)
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # 3. Volatility (Bollinger Bands)
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upperband'] = bollinger['upperband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_lowerband'] = bollinger['lowerband']

        # 4. RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_short = f'ema_short_{self.ema_short_period.value}'
        ema_long = f'ema_long_{self.ema_long_period.value}'
        
        dataframe.loc[
            (
                (dataframe[ema_short] > dataframe[ema_long]) &  # Golden Cross (Trend Up)
                (dataframe['macd'] > dataframe['macdsignal']) & # MACD Momentum Up
                (dataframe['close'] > dataframe['bb_middleband']) & # Trading above average
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        # Shorting logic (Inverse)
        dataframe.loc[
            (
                (dataframe[ema_short] < dataframe[ema_long]) &  # Death Cross (Trend Down)
                (dataframe['macd'] < dataframe['macdsignal']) & # Momentum Down
                (dataframe['close'] < dataframe['bb_middleband']) &
                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit when trend reverses
        ema_short = f'ema_short_{self.ema_short_period.value}'
        ema_long = f'ema_long_{self.ema_long_period.value}'

        dataframe.loc[
            (
                (dataframe[ema_short] < dataframe[ema_long]) # Trend reversed to down
            ),
            'exit_long'] = 1

        dataframe.loc[
            (
                (dataframe[ema_short] > dataframe[ema_long]) # Trend reversed to up
            ),
            'exit_short'] = 1
            
        return dataframe
