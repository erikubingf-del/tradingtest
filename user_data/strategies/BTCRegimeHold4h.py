from datetime import datetime
from typing import Optional
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta

class BTCRegimeHold4h(IStrategy):
    INTERFACE_VERSION = 3
    ma_period = IntParameter(150, 250, default=233, space="buy", optimize=True)
    cross_buffer = DecimalParameter(0.005, 0.03, default=0.005, space="buy", optimize=True)
    minimal_roi = {"0": 100.0}
    stoploss = -0.25
    trailing_stop = False
    timeframe = '4h'
    can_short = False
    startup_candle_count = 250
    order_types = {'entry': 'limit', 'exit': 'limit', 'stoploss': 'market', 'stoploss_on_exchange': True}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for period in range(150, 251):
            dataframe[f'ma_{period}'] = ta.SMA(dataframe, timeperiod=period)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ma_col = f'ma_{self.ma_period.value}'
        buffer_mult = 1 + self.cross_buffer.value
        dataframe.loc[
            (
                (dataframe['close'].shift(1) <= dataframe[ma_col].shift(1)) &
                (dataframe['close'] > dataframe[ma_col] * buffer_mult) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ma_col = f'ma_{self.ma_period.value}'
        buffer_mult = 1 - self.cross_buffer.value
        dataframe.loc[
            (
                (dataframe['close'].shift(1) >= dataframe[ma_col].shift(1)) &
                (dataframe['close'] < dataframe[ma_col] * buffer_mult)
            ),
            'exit_long'] = 1
        return dataframe

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 2.0

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        return max_stake * 0.95
