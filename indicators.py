"""
Technical Indicators for Trend Following

Implements indicators used by:
- Turtle Trading (Donchian Channels, ATR)
- Time Series Momentum (Return-based momentum)
- Moving Average Systems
- Volatility measures
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional


class TrendIndicators:
    """
    Core trend-following indicators.
    """

    @staticmethod
    def donchian_channel(
        high: pd.Series,
        low: pd.Series,
        period: int = 20
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Donchian Channel (used in Turtle Trading).

        Returns:
            upper: Highest high of period
            lower: Lowest low of period
            middle: Midpoint
        """
        upper = high.rolling(window=period).max()
        lower = low.rolling(window=period).min()
        middle = (upper + lower) / 2

        return upper, lower, middle

    @staticmethod
    def atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 20
    ) -> pd.Series:
        """
        Calculate Average True Range (ATR).
        Used for position sizing and stops in Turtle system.
        """
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    @staticmethod
    def exponential_atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 20
    ) -> pd.Series:
        """
        Exponential Average True Range.
        More responsive to recent volatility.
        """
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(span=period, adjust=False).mean()

        return atr

    @staticmethod
    def sma(prices: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average."""
        return prices.rolling(window=period).mean()

    @staticmethod
    def ema(prices: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return prices.ewm(span=period, adjust=False).mean()

    @staticmethod
    def momentum(prices: pd.Series, period: int = 252) -> pd.Series:
        """
        Calculate momentum (rate of change).

        Args:
            prices: Price series
            period: Lookback period (252 = 1 year for daily data)

        Returns:
            Momentum as percentage change
        """
        return prices.pct_change(periods=period)

    @staticmethod
    def time_series_momentum(
        prices: pd.Series,
        lookback_months: int = 12
    ) -> pd.Series:
        """
        Time Series Momentum as per Moskowitz, Ooi, Pedersen (2012).

        Uses approximately 21 trading days per month.
        """
        lookback_days = lookback_months * 21
        return prices.pct_change(periods=lookback_days)

    @staticmethod
    def volatility(
        returns: pd.Series,
        period: int = 60,
        annualize: bool = True
    ) -> pd.Series:
        """
        Calculate rolling realized volatility.

        Args:
            returns: Return series
            period: Lookback period
            annualize: Whether to annualize (multiply by sqrt(252))
        """
        vol = returns.rolling(window=period).std()
        if annualize:
            vol = vol * np.sqrt(252)
        return vol

    @staticmethod
    def sharpe_rolling(
        returns: pd.Series,
        period: int = 252,
        rf_rate: float = 0.0
    ) -> pd.Series:
        """
        Rolling Sharpe ratio.
        """
        excess_returns = returns - rf_rate / 252
        mean_return = excess_returns.rolling(window=period).mean() * 252
        vol = returns.rolling(window=period).std() * np.sqrt(252)
        return mean_return / vol


class MomentumIndicators:
    """
    Momentum-specific indicators for ranking and selection.
    """

    @staticmethod
    def absolute_momentum(
        prices: pd.Series,
        lookback: int = 252,
        threshold: float = 0.0
    ) -> pd.Series:
        """
        Absolute momentum signal.
        Returns 1 if momentum > threshold, 0 otherwise.
        """
        mom = prices.pct_change(periods=lookback)
        signal = (mom > threshold).astype(int)
        return signal

    @staticmethod
    def relative_momentum(
        prices: pd.DataFrame,
        lookback: int = 252
    ) -> pd.DataFrame:
        """
        Relative momentum ranking across assets.
        Returns rank (1 = best momentum).
        """
        momentum = prices.pct_change(periods=lookback)
        # Rank in descending order (1 = highest momentum)
        ranks = momentum.rank(axis=1, ascending=False)
        return ranks

    @staticmethod
    def dual_momentum_signal(
        asset_prices: pd.Series,
        benchmark_prices: pd.Series,
        cash_rate: float = 0.0,
        lookback: int = 252
    ) -> pd.Series:
        """
        Dual Momentum signal (Antonacci).

        Returns:
            1: Long asset (beat benchmark and has positive absolute momentum)
            0: Go to cash
        """
        asset_mom = asset_prices.pct_change(periods=lookback)
        bench_mom = benchmark_prices.pct_change(periods=lookback)

        # Absolute momentum check (beats cash)
        abs_signal = asset_mom > (cash_rate * lookback / 252)

        # Relative momentum check (beats benchmark)
        rel_signal = asset_mom > bench_mom

        # Need both for full signal
        signal = (abs_signal & rel_signal).astype(int)

        return signal

    @staticmethod
    def multi_timeframe_momentum(
        prices: pd.Series,
        lookbacks: list = [21, 63, 126, 252]
    ) -> pd.Series:
        """
        Ensemble momentum using multiple timeframes.
        Average of momentum signals across lookbacks.
        """
        signals = []
        for lb in lookbacks:
            mom = prices.pct_change(periods=lb)
            signal = (mom > 0).astype(float)
            signals.append(signal)

        # Average signal strength
        ensemble = pd.concat(signals, axis=1).mean(axis=1)
        return ensemble


class BreakoutIndicators:
    """
    Breakout detection for Turtle-style trading.
    """

    @staticmethod
    def channel_breakout(
        close: pd.Series,
        high: pd.Series,
        low: pd.Series,
        entry_period: int = 20,
        exit_period: int = 10
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Turtle-style channel breakout signals.

        Returns:
            entry_signal: 1 for long entry, -1 for short entry, 0 for no signal
            exit_signal: 1 for exit long, -1 for exit short
        """
        # Entry channels
        entry_high = high.rolling(window=entry_period).max().shift(1)
        entry_low = low.rolling(window=entry_period).min().shift(1)

        # Exit channels
        exit_low = low.rolling(window=exit_period).min().shift(1)
        exit_high = high.rolling(window=exit_period).max().shift(1)

        # Entry signals
        long_entry = (close > entry_high).astype(int)
        short_entry = -(close < entry_low).astype(int)
        entry_signal = long_entry + short_entry

        # Exit signals (exit long when hits exit low, exit short when hits exit high)
        exit_long = (close < exit_low).astype(int)
        exit_short = -(close > exit_high).astype(int)
        exit_signal = exit_long + exit_short

        return entry_signal, exit_signal

    @staticmethod
    def volatility_breakout(
        close: pd.Series,
        atr: pd.Series,
        period: int = 20,
        multiplier: float = 2.0
    ) -> pd.Series:
        """
        Volatility expansion breakout.
        Signal when price moves more than N * ATR from moving average.
        """
        ma = close.rolling(window=period).mean()
        upper = ma + multiplier * atr
        lower = ma - multiplier * atr

        long_signal = (close > upper).astype(int)
        short_signal = -(close < lower).astype(int)

        return long_signal + short_signal


class TrendFilters:
    """
    Trend filters to avoid counter-trend trades.
    """

    @staticmethod
    def ma_trend_filter(
        prices: pd.Series,
        short_period: int = 50,
        long_period: int = 200
    ) -> pd.Series:
        """
        Moving average trend filter.
        Returns 1 for uptrend, -1 for downtrend, 0 for neutral.
        """
        short_ma = prices.rolling(window=short_period).mean()
        long_ma = prices.rolling(window=long_period).mean()

        uptrend = ((short_ma > long_ma) & (prices > short_ma)).astype(int)
        downtrend = -((short_ma < long_ma) & (prices < short_ma)).astype(int)

        return uptrend + downtrend

    @staticmethod
    def price_vs_ma(prices: pd.Series, period: int = 200) -> pd.Series:
        """
        Simple trend filter: price above/below long MA.
        """
        ma = prices.rolling(window=period).mean()
        return (prices > ma).astype(int) * 2 - 1  # Returns 1 or -1

    @staticmethod
    def adx_filter(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
        threshold: float = 25.0
    ) -> pd.Series:
        """
        ADX trend strength filter.
        Returns True if ADX > threshold (strong trend).
        """
        # Calculate +DM and -DM
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Smoothed values
        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * pd.Series(plus_dm).ewm(span=period, adjust=False).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).ewm(span=period, adjust=False).mean() / atr

        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(span=period, adjust=False).mean()

        return adx > threshold


def calculate_all_indicators(
    df: pd.DataFrame,
    config: dict = None
) -> pd.DataFrame:
    """
    Calculate all trend-following indicators for a price DataFrame.

    Args:
        df: DataFrame with 'open', 'high', 'low', 'close', 'volume' columns
        config: Optional configuration dictionary

    Returns:
        DataFrame with all indicators added
    """
    result = df.copy()

    # Ensure lowercase columns
    result.columns = [c.lower() for c in result.columns]

    high = result['high']
    low = result['low']
    close = result['close']

    # Donchian Channels (Turtle Trading)
    result['donchian_upper_20'], result['donchian_lower_20'], result['donchian_mid_20'] = \
        TrendIndicators.donchian_channel(high, low, 20)
    result['donchian_upper_55'], result['donchian_lower_55'], result['donchian_mid_55'] = \
        TrendIndicators.donchian_channel(high, low, 55)

    # ATR
    result['atr_20'] = TrendIndicators.atr(high, low, close, 20)
    result['atr_14'] = TrendIndicators.atr(high, low, close, 14)

    # Moving Averages
    result['sma_50'] = TrendIndicators.sma(close, 50)
    result['sma_200'] = TrendIndicators.sma(close, 200)
    result['ema_20'] = TrendIndicators.ema(close, 20)
    result['ema_50'] = TrendIndicators.ema(close, 50)

    # Momentum (various lookbacks)
    result['mom_1m'] = TrendIndicators.momentum(close, 21)
    result['mom_3m'] = TrendIndicators.momentum(close, 63)
    result['mom_6m'] = TrendIndicators.momentum(close, 126)
    result['mom_12m'] = TrendIndicators.momentum(close, 252)

    # Returns and volatility
    result['returns'] = close.pct_change()
    result['volatility_60d'] = TrendIndicators.volatility(result['returns'], 60)

    # Breakout signals
    result['breakout_signal'], result['exit_signal'] = \
        BreakoutIndicators.channel_breakout(close, high, low, 20, 10)

    # Trend filters
    result['ma_trend'] = TrendFilters.ma_trend_filter(close, 50, 200)
    result['price_trend'] = TrendFilters.price_vs_ma(close, 200)

    # Multi-timeframe momentum
    result['mtf_momentum'] = MomentumIndicators.multi_timeframe_momentum(close)

    # Absolute momentum signal
    result['abs_mom_signal'] = MomentumIndicators.absolute_momentum(close, 252)

    return result


if __name__ == "__main__":
    # Test indicators
    import yfinance as yf

    print("Testing indicators on SPY data...")
    spy = yf.download("SPY", start="2020-01-01", end="2024-01-01", progress=False)
    spy.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in spy.columns]

    result = calculate_all_indicators(spy)

    print("\nIndicator columns added:")
    print([c for c in result.columns if c not in spy.columns])

    print("\nLast 5 rows of key indicators:")
    key_cols = ['close', 'atr_20', 'mom_12m', 'breakout_signal', 'ma_trend']
    print(result[key_cols].tail())
