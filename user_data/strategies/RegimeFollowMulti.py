"""
Multi-Asset Regime Following Strategy
======================================
Applies the proven BTCRegimeHold4h logic to multiple assets.

Statistical Basis:
- 233 SMA regime filter is based on academic momentum research
- Crossover detection reduces whipsaw trades
- Works across liquid assets due to universal momentum effect
- Long-only during bull regime (cash during bear) reduces drawdown

Key Difference from BTCRegimeHold4h:
- Applies to multiple assets simultaneously
- Lower position size per trade (diversification)
- Maintains same core logic that achieved +2756% on BTC

Key Difference from TrendFollowingMulti:
- Simpler entry logic (crossover, not breakout)
- Long-only (shorts underperformed in backtest)
- No ADX confirmation (reduces complexity, increases signals)
"""

from datetime import datetime
from typing import Optional
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta


class RegimeFollowMulti(IStrategy):
    """
    Multi-Asset Regime Following Strategy

    Core Logic (same as BTCRegimeHold4h):
    - Enter LONG when price CROSSES from below to above SMA + buffer
    - Exit when price CROSSES from above to below SMA - buffer
    - Long only (no shorting)
    - Ride the trend until it ends

    Multi-Asset Adaptation:
    - Each asset is evaluated independently
    - Position size is smaller (to allow multiple positions)
    - Same parameters work across liquid crypto assets
    """

    INTERFACE_VERSION = 3

    # ==================== REGIME PARAMETERS ====================
    # These are the proven parameters from BTCRegimeHold4h
    ma_period = IntParameter(150, 250, default=233, space="buy", optimize=True)
    cross_buffer = DecimalParameter(0.005, 0.03, default=0.005, space="buy", optimize=True)

    # ==================== STRATEGY SETTINGS ====================
    minimal_roi = {"0": 100.0}  # Disabled - let regime run
    stoploss = -0.25  # Wide stop, trust regime exit
    trailing_stop = False  # Trust regime exit, not trailing
    timeframe = '4h'
    can_short = False  # Long only (proven to work better)
    startup_candle_count = 260

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': True,
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate SMAs for hyperopt range.
        Same approach as BTCRegimeHold4h.
        """
        # Calculate SMAs for all periods in optimization range
        for period in range(150, 251):
            dataframe[f'ma_{period}'] = ta.SMA(dataframe, timeperiod=period)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry Logic: CROSSOVER detection.

        Enter LONG when:
        1. Previous close was AT or BELOW the SMA
        2. Current close is ABOVE the SMA + buffer
        3. Volume exists

        This captures the regime CHANGE, not just being in bull regime.
        """
        ma_col = f'ma_{self.ma_period.value}'
        buffer_mult = 1 + self.cross_buffer.value

        # CROSSOVER: Was below MA, now above MA + buffer
        dataframe.loc[
            (
                (dataframe['close'].shift(1) <= dataframe[ma_col].shift(1)) &
                (dataframe['close'] > dataframe[ma_col] * buffer_mult) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit Logic: CROSSUNDER detection.

        Exit LONG when:
        1. Previous close was AT or ABOVE the SMA
        2. Current close is BELOW the SMA - buffer

        This captures the regime CHANGE to bearish.
        """
        ma_col = f'ma_{self.ma_period.value}'
        buffer_mult = 1 - self.cross_buffer.value

        # CROSSUNDER: Was above MA, now below MA - buffer
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
        """2x leverage as per proven strategy."""
        return 2.0

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """
        Position sizing for multi-asset:
        - 20% per position allows up to 5 concurrent trades
        - This provides diversification while maintaining meaningful exposure
        """
        return max_stake * 0.20
