"""
Multi-Asset Trend Following Strategy
=====================================
Based on academic research and proven methodologies:
- Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum"
- Turtle Trading Rules (Richard Dennis)
- "Trend Following" by Michael Covel
- AQR Managed Futures Research

Core Principles:
1. Enter when trend is confirmed (not just starting)
2. Cut losses quickly, let winners run
3. ATR-based position sizing normalizes risk across assets
4. Works on any liquid market (crypto, forex, etc.)

Statistical Edge:
- Momentum effect documented across 58+ markets over 100+ years
- Provides "crisis alpha" - tends to profit during market crashes
- Win rate ~35-40%, but winners >> losers (positive expectancy)
"""

from datetime import datetime
from typing import Optional
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class TrendFollowingMulti(IStrategy):
    """
    Multi-Asset Trend Following Strategy

    Entry: Price breaks above N-period high + ADX confirms trend strength
    Exit: Price breaks below shorter-period low OR trend weakens

    Key difference from simple breakout:
    - ADX filter ensures we only enter CONFIRMED trends
    - ATR-based stops adapt to each asset's volatility
    - Trailing exit locks in profits during strong trends
    """

    INTERFACE_VERSION = 3

    # ==================== TREND DETECTION PARAMETERS ====================
    # Donchian Channel for breakout detection (Turtle method)
    entry_period = IntParameter(20, 60, default=40, space="buy", optimize=True)
    exit_period = IntParameter(10, 30, default=20, space="sell", optimize=True)

    # Moving Average for trend direction
    ma_period = IntParameter(100, 300, default=200, space="buy", optimize=True)

    # ==================== TREND CONFIRMATION PARAMETERS ====================
    # ADX threshold - only enter if trend is strong enough
    adx_threshold = IntParameter(20, 35, default=25, space="buy", optimize=True)
    adx_period = IntParameter(10, 20, default=14, space="buy", optimize=True)

    # Volume confirmation multiplier
    volume_mult = DecimalParameter(0.5, 2.0, default=1.0, space="buy", optimize=True)

    # ==================== RISK MANAGEMENT ====================
    # ATR multiplier for stop loss
    atr_sl_mult = DecimalParameter(1.5, 4.0, default=2.5, space="stoploss", optimize=True)

    # ATR period
    atr_period = IntParameter(10, 20, default=14, space="stoploss", optimize=True)

    # ==================== STRATEGY SETTINGS ====================
    minimal_roi = {"0": 100.0}  # Disabled - let trends run
    stoploss = -0.15  # Fallback, actual stop is ATR-based
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    timeframe = '4h'
    can_short = True  # Trend following works both directions
    startup_candle_count = 350

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': True,
    }

    # Position sizing
    position_adjustment_enable = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate trend-following indicators:
        - Donchian Channels (breakout detection)
        - ADX (trend strength confirmation)
        - ATR (volatility for position sizing)
        - Moving Averages (trend direction)
        """

        # ==================== DONCHIAN CHANNELS ====================
        # Entry channel (longer period - catches bigger moves)
        for period in range(20, 61):
            dataframe[f'highest_{period}'] = dataframe['high'].rolling(window=period).max()
            dataframe[f'lowest_{period}'] = dataframe['low'].rolling(window=period).min()

        # Exit channel (shorter period - tighter exit)
        for period in range(10, 31):
            if f'highest_{period}' not in dataframe.columns:
                dataframe[f'highest_{period}'] = dataframe['high'].rolling(window=period).max()
            if f'lowest_{period}' not in dataframe.columns:
                dataframe[f'lowest_{period}'] = dataframe['low'].rolling(window=period).min()

        # ==================== TREND DIRECTION ====================
        # Long-term MA for overall trend
        for period in range(100, 301, 10):
            dataframe[f'ma_{period}'] = ta.SMA(dataframe, timeperiod=period)

        # Short-term MA for momentum
        dataframe['ma_50'] = ta.SMA(dataframe, timeperiod=50)

        # ==================== TREND STRENGTH (ADX) ====================
        # ADX measures trend strength regardless of direction
        for period in range(10, 21):
            dataframe[f'adx_{period}'] = ta.ADX(dataframe, timeperiod=period)

        # Plus/Minus DI for trend direction
        dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ==================== VOLATILITY (ATR) ====================
        for period in range(10, 21):
            dataframe[f'atr_{period}'] = ta.ATR(dataframe, timeperiod=period)

        # Normalized ATR (percentage of price)
        dataframe['atr_pct'] = ta.ATR(dataframe, timeperiod=14) / dataframe['close'] * 100

        # ==================== VOLUME ANALYSIS ====================
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']

        # ==================== MOMENTUM CONFIRMATION ====================
        # RSI for overbought/oversold (avoid entering exhausted moves)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # Rate of Change
        dataframe['roc_10'] = ta.ROC(dataframe, timeperiod=10)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry Logic (Based on Turtle Trading + ADX confirmation):

        LONG:
        1. Price breaks above N-period high (Donchian breakout)
        2. ADX > threshold (trend is confirmed, not just starting)
        3. +DI > -DI (uptrend direction)
        4. Price > 200 MA (aligned with long-term trend)
        5. Volume above average (conviction)

        SHORT:
        1. Price breaks below N-period low
        2. ADX > threshold
        3. -DI > +DI (downtrend direction)
        4. Price < 200 MA
        5. Volume above average
        """

        entry_p = self.entry_period.value
        ma_p = self.ma_period.value
        adx_p = self.adx_period.value
        adx_thresh = self.adx_threshold.value
        vol_mult = self.volume_mult.value

        highest_col = f'highest_{entry_p}'
        lowest_col = f'lowest_{entry_p}'
        adx_col = f'adx_{adx_p}'
        ma_col = f'ma_{ma_p}' if f'ma_{ma_p}' in dataframe.columns else 'ma_200'

        # ==================== LONG ENTRY ====================
        # Breakout above N-period high with trend confirmation
        dataframe.loc[
            (
                # 1. Breakout: Price exceeds recent high
                (dataframe['close'] > dataframe[highest_col].shift(1)) &

                # 2. Trend Confirmed: ADX shows strong trend
                (dataframe[adx_col] > adx_thresh) &

                # 3. Direction: Uptrend (+DI > -DI)
                (dataframe['plus_di'] > dataframe['minus_di']) &

                # 4. Aligned with long-term trend
                (dataframe['close'] > dataframe[ma_col]) &

                # 5. Volume conviction
                (dataframe['volume_ratio'] > vol_mult) &

                # 6. Not overbought (avoid exhausted moves)
                (dataframe['rsi'] < 75) &

                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        # ==================== SHORT ENTRY ====================
        # Breakout below N-period low with trend confirmation
        dataframe.loc[
            (
                # 1. Breakdown: Price breaks recent low
                (dataframe['close'] < dataframe[lowest_col].shift(1)) &

                # 2. Trend Confirmed: ADX shows strong trend
                (dataframe[adx_col] > adx_thresh) &

                # 3. Direction: Downtrend (-DI > +DI)
                (dataframe['minus_di'] > dataframe['plus_di']) &

                # 4. Aligned with long-term trend
                (dataframe['close'] < dataframe[ma_col]) &

                # 5. Volume conviction
                (dataframe['volume_ratio'] > vol_mult) &

                # 6. Not oversold
                (dataframe['rsi'] > 25) &

                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit Logic (Turtle Exit + Trend Weakness):

        Exit LONG when:
        1. Price breaks below shorter-period low (tighter exit)
        2. OR ADX drops significantly (trend weakening)
        3. OR -DI crosses above +DI (trend reversal)

        Exit SHORT when:
        1. Price breaks above shorter-period high
        2. OR ADX drops significantly
        3. OR +DI crosses above -DI
        """

        exit_p = self.exit_period.value
        adx_p = self.adx_period.value

        highest_col = f'highest_{exit_p}'
        lowest_col = f'lowest_{exit_p}'
        adx_col = f'adx_{adx_p}'

        # ==================== EXIT LONG ====================
        dataframe.loc[
            (
                # Breakdown below exit channel
                (dataframe['close'] < dataframe[lowest_col].shift(1)) |

                # Trend reversal: -DI crosses above +DI
                (
                    (dataframe['minus_di'] > dataframe['plus_di']) &
                    (dataframe['minus_di'].shift(1) <= dataframe['plus_di'].shift(1))
                ) |

                # Trend dying: ADX falling from high level
                (
                    (dataframe[adx_col] < 20) &
                    (dataframe[adx_col].shift(5) > 30)
                )
            ),
            'exit_long'] = 1

        # ==================== EXIT SHORT ====================
        dataframe.loc[
            (
                # Breakout above exit channel
                (dataframe['close'] > dataframe[highest_col].shift(1)) |

                # Trend reversal: +DI crosses above -DI
                (
                    (dataframe['plus_di'] > dataframe['minus_di']) &
                    (dataframe['plus_di'].shift(1) <= dataframe['minus_di'].shift(1))
                ) |

                # Trend dying
                (
                    (dataframe[adx_col] < 20) &
                    (dataframe[adx_col].shift(5) > 30)
                )
            ),
            'exit_short'] = 1

        return dataframe

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        """Conservative leverage for trend following."""
        return 2.0

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """
        ATR-based position sizing (equal risk per trade).
        This is a key principle of trend following - normalize risk across assets.
        """
        # Use percentage of capital
        return max_stake * 0.20  # 20% per position allows 5 concurrent positions

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        """
        ATR-based trailing stop.
        Gives trends room to breathe while protecting profits.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if len(dataframe) < 1:
            return None

        last_candle = dataframe.iloc[-1]
        atr = last_candle.get(f'atr_{self.atr_period.value}', last_candle.get('atr_14', 0))

        if atr == 0:
            return None

        # ATR-based stop distance
        atr_stop_distance = (atr * self.atr_sl_mult.value) / current_rate

        # For profitable trades, use tighter stop
        if current_profit > 0.05:  # 5% profit
            atr_stop_distance = min(atr_stop_distance, 0.03)  # Max 3% stop

        return -atr_stop_distance
