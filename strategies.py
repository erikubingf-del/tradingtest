"""
Trend Following Strategies

Implementations based on:
1. Turtle Trading System (Donchian Breakout)
2. Time Series Momentum (AQR/Moskowitz style)
3. Dual Momentum (Gary Antonacci)
4. Combined/Ensemble Strategy

Each strategy returns signals and position weights.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from indicators import (
    TrendIndicators, MomentumIndicators, BreakoutIndicators, TrendFilters
)
from position_sizing import (
    PositionSizer, VolatilityTargeting, ScaleInManager, RiskManager
)


class Signal(Enum):
    """Trading signals."""
    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class TradeSignal:
    """Represents a trading signal with metadata."""
    ticker: str
    date: pd.Timestamp
    signal: Signal
    strength: float  # 0 to 1
    strategy: str
    entry_price: float = 0.0
    stop_price: float = 0.0
    target_weight: float = 0.0
    reason: str = ""


class TurtleStrategy:
    """
    Turtle Trading System implementation.

    Entry: Donchian channel breakout (20 or 55 day)
    Exit: Opposite channel breakout (10 or 20 day) or stop loss
    Position sizing: ATR-based
    Pyramiding: Add every 0.5N
    """

    def __init__(
        self,
        entry_period: int = 20,
        exit_period: int = 10,
        atr_period: int = 20,
        use_system2: bool = False,  # Use 55/20 instead of 20/10
        skip_on_previous_win: bool = True
    ):
        if use_system2:
            self.entry_period = 55
            self.exit_period = 20
        else:
            self.entry_period = entry_period
            self.exit_period = exit_period

        self.atr_period = atr_period
        self.skip_on_previous_win = skip_on_previous_win
        self.sizer = PositionSizer()

        # Track last signals for skip rule
        self.last_signals: Dict[str, Tuple[Signal, float]] = {}

    def generate_signals(
        self,
        data: pd.DataFrame,
        ticker: str
    ) -> pd.DataFrame:
        """
        Generate trading signals for a single asset.

        Args:
            data: OHLCV DataFrame
            ticker: Ticker symbol

        Returns:
            DataFrame with signals
        """
        df = data.copy()

        # Calculate channels
        upper, lower, mid = TrendIndicators.donchian_channel(
            df['high'], df['low'], self.entry_period
        )
        exit_upper, exit_lower, _ = TrendIndicators.donchian_channel(
            df['high'], df['low'], self.exit_period
        )

        # Calculate ATR
        atr = TrendIndicators.atr(df['high'], df['low'], df['close'], self.atr_period)

        # Shift channels (look at previous period for breakout)
        upper_prev = upper.shift(1)
        lower_prev = lower.shift(1)

        # Entry signals
        df['long_entry'] = df['close'] > upper_prev
        df['short_entry'] = df['close'] < lower_prev

        # Exit signals
        df['long_exit'] = df['close'] < exit_lower.shift(1)
        df['short_exit'] = df['close'] > exit_upper.shift(1)

        # ATR for position sizing and stops
        df['atr'] = atr

        # Stop prices
        df['long_stop'] = df['close'] - 2 * atr
        df['short_stop'] = df['close'] + 2 * atr

        # Generate signal column
        df['signal'] = 0
        df.loc[df['long_entry'], 'signal'] = 1
        df.loc[df['short_entry'], 'signal'] = -1

        df['ticker'] = ticker

        return df

    def get_position_size(
        self,
        account_value: float,
        atr: float,
        price: float
    ) -> int:
        """Calculate position size using Turtle formula."""
        return self.sizer.calculate_unit_size(account_value, atr, price)


class MomentumStrategy:
    """
    Time Series Momentum Strategy.

    Based on Moskowitz, Ooi, Pedersen (2012) and AQR research.
    Uses 12-month lookback, volatility-scaled positions.
    """

    def __init__(
        self,
        lookback_months: int = 12,
        vol_target: float = 0.10,
        vol_lookback: int = 60,
        use_ensemble: bool = True,
        ensemble_lookbacks: List[int] = [1, 3, 6, 12]
    ):
        self.lookback_months = lookback_months
        self.lookback_days = lookback_months * 21
        self.vol_target = vol_target
        self.vol_lookback = vol_lookback
        self.use_ensemble = use_ensemble
        self.ensemble_lookbacks = ensemble_lookbacks

        self.vol_targeter = VolatilityTargeting(
            target_volatility=vol_target,
            vol_lookback=vol_lookback
        )

    def generate_signals(
        self,
        data: pd.DataFrame,
        ticker: str
    ) -> pd.DataFrame:
        """Generate momentum signals."""
        df = data.copy()

        # Calculate returns
        df['returns'] = df['close'].pct_change()

        # Realized volatility
        df['volatility'] = df['returns'].rolling(window=self.vol_lookback).std() * np.sqrt(252)

        if self.use_ensemble:
            # Multi-timeframe momentum
            signals = []
            for lb in self.ensemble_lookbacks:
                lb_days = lb * 21
                mom = df['close'].pct_change(periods=lb_days)
                sig = (mom > 0).astype(float)
                signals.append(sig)

            # Average signal
            df['momentum'] = pd.concat(signals, axis=1).mean(axis=1)
            df['signal'] = df['momentum'].apply(lambda x: 1 if x >= 0.5 else (-1 if x <= 0.25 else 0))
        else:
            # Single lookback
            df['momentum'] = df['close'].pct_change(periods=self.lookback_days)
            df['signal'] = (df['momentum'] > 0).astype(int)

        # Volatility-scaled weight
        df['weight'] = self.vol_target / df['volatility'].clip(lower=0.01)
        df['weight'] = df['weight'].clip(upper=2.0)  # Max 2x leverage

        df['ticker'] = ticker

        return df

    def rank_assets(
        self,
        data_dict: Dict[str, pd.DataFrame],
        date: pd.Timestamp
    ) -> pd.DataFrame:
        """
        Rank assets by momentum for cross-sectional selection.
        """
        rankings = []

        for ticker, df in data_dict.items():
            if date not in df.index:
                continue

            row = df.loc[date]
            if 'momentum' in row:
                rankings.append({
                    'ticker': ticker,
                    'momentum': row['momentum'],
                    'volatility': row.get('volatility', 0.15),
                    'signal': row['signal']
                })

        if not rankings:
            return pd.DataFrame()

        rank_df = pd.DataFrame(rankings)
        rank_df['rank'] = rank_df['momentum'].rank(ascending=False)

        return rank_df.sort_values('rank')


class DualMomentumStrategy:
    """
    Dual Momentum Strategy (Gary Antonacci).

    Combines:
    1. Absolute momentum: Is return positive over lookback?
    2. Relative momentum: Does asset beat benchmark?

    If both true: Long asset
    If absolute fails: Go to safe asset (bonds/cash)
    """

    def __init__(
        self,
        lookback_months: int = 12,
        benchmark_ticker: str = "SPY",
        safe_ticker: str = "TLT"
    ):
        self.lookback_months = lookback_months
        self.lookback_days = lookback_months * 21
        self.benchmark_ticker = benchmark_ticker
        self.safe_ticker = safe_ticker

    def generate_signals(
        self,
        asset_data: pd.DataFrame,
        benchmark_data: pd.DataFrame,
        ticker: str
    ) -> pd.DataFrame:
        """
        Generate dual momentum signals.

        Returns DataFrame with signal indicating:
        1: Long the asset
        0: Go to safe asset (bonds)
        """
        df = asset_data.copy()

        # Asset momentum
        df['asset_momentum'] = df['close'].pct_change(periods=self.lookback_days)

        # Align benchmark data
        benchmark_close = benchmark_data['close'].reindex(df.index, method='ffill')
        df['bench_momentum'] = benchmark_close.pct_change(periods=self.lookback_days)

        # Absolute momentum: asset return > 0 (or T-bill rate)
        df['abs_momentum'] = df['asset_momentum'] > 0

        # Relative momentum: asset > benchmark
        df['rel_momentum'] = df['asset_momentum'] > df['bench_momentum']

        # Signal: Need both absolute and relative
        df['signal'] = (df['abs_momentum'] & df['rel_momentum']).astype(int)

        df['ticker'] = ticker

        return df


class CombinedStrategy:
    """
    Combined/Ensemble Strategy.

    Combines signals from multiple strategies:
    1. Turtle breakout signals
    2. Time series momentum
    3. Moving average trend filter

    Entry only when multiple signals agree.
    Position sized by volatility targeting with scale-in.
    """

    def __init__(
        self,
        turtle_weight: float = 0.3,
        momentum_weight: float = 0.4,
        ma_weight: float = 0.3,
        agreement_threshold: float = 0.5,  # Need >50% agreement to trade
        initial_position: float = 0.02,
        max_position: float = 0.10
    ):
        self.turtle_weight = turtle_weight
        self.momentum_weight = momentum_weight
        self.ma_weight = ma_weight
        self.agreement_threshold = agreement_threshold

        self.turtle = TurtleStrategy()
        self.momentum = MomentumStrategy()

        self.scale_manager = ScaleInManager(
            initial_pct=initial_position,
            max_pct=max_position
        )

    def generate_signals(
        self,
        data: pd.DataFrame,
        ticker: str
    ) -> pd.DataFrame:
        """
        Generate combined strategy signals.
        """
        df = data.copy()

        # Get individual strategy signals
        turtle_df = self.turtle.generate_signals(data, ticker)
        momentum_df = self.momentum.generate_signals(data, ticker)

        # Moving average filter
        df['ma_50'] = TrendIndicators.sma(df['close'], 50)
        df['ma_200'] = TrendIndicators.sma(df['close'], 200)
        df['ma_signal'] = ((df['close'] > df['ma_50']) & (df['ma_50'] > df['ma_200'])).astype(int)
        df['ma_signal'] = df['ma_signal'] - ((df['close'] < df['ma_50']) & (df['ma_50'] < df['ma_200'])).astype(int)

        # Combine signals with weights
        df['turtle_signal'] = turtle_df['signal']
        df['momentum_signal'] = momentum_df['signal']

        # Normalize to [-1, 1]
        df['turtle_norm'] = df['turtle_signal'].clip(-1, 1)
        df['momentum_norm'] = df['momentum_signal'].clip(-1, 1)
        df['ma_norm'] = df['ma_signal'].clip(-1, 1)

        # Weighted combination
        df['combined_signal'] = (
            self.turtle_weight * df['turtle_norm'] +
            self.momentum_weight * df['momentum_norm'] +
            self.ma_weight * df['ma_norm']
        )

        # Final signal based on threshold
        df['signal'] = 0
        df.loc[df['combined_signal'] > self.agreement_threshold, 'signal'] = 1
        df.loc[df['combined_signal'] < -self.agreement_threshold, 'signal'] = -1

        # Signal strength (for position sizing)
        df['signal_strength'] = df['combined_signal'].abs()

        # ATR for stops
        df['atr'] = TrendIndicators.atr(df['high'], df['low'], df['close'], 20)
        df['volatility'] = momentum_df['volatility']

        df['ticker'] = ticker

        return df

    def calculate_weight(
        self,
        signal_strength: float,
        volatility: float,
        current_pnl: float = 0.0
    ) -> float:
        """
        Calculate position weight with scale-in logic.
        """
        # Start with initial position
        base_weight = self.scale_manager.initial_pct

        # Scale by signal strength
        weight = base_weight * signal_strength

        # Volatility targeting
        target_vol = 0.10
        vol_scalar = target_vol / max(volatility, 0.01)
        weight *= min(vol_scalar, 2.0)  # Cap at 2x

        # Scale up if profitable
        if current_pnl > self.scale_manager.scale_threshold:
            weight = min(weight + self.scale_manager.scale_increment,
                        self.scale_manager.max_pct)

        return min(weight, self.scale_manager.max_pct)


class TrendScanner:
    """
    Scans universe of assets for trending opportunities.
    Ranks by trend strength and filters for quality.
    """

    def __init__(
        self,
        min_momentum: float = 0.0,
        min_adx: float = 20.0,
        max_positions: int = 20,
        min_liquidity_days: int = 252
    ):
        self.min_momentum = min_momentum
        self.min_adx = min_adx
        self.max_positions = max_positions
        self.min_liquidity_days = min_liquidity_days

    def scan(
        self,
        data_dict: Dict[str, pd.DataFrame],
        date: pd.Timestamp
    ) -> List[Dict]:
        """
        Scan all assets and return ranked opportunities.
        """
        opportunities = []

        for ticker, df in data_dict.items():
            if date not in df.index:
                continue

            # Check minimum history
            data_to_date = df[df.index <= date]
            if len(data_to_date) < self.min_liquidity_days:
                continue

            row = data_to_date.iloc[-1]

            # Check momentum threshold
            if 'mom_12m' in row and row['mom_12m'] > self.min_momentum:
                opportunities.append({
                    'ticker': ticker,
                    'date': date,
                    'momentum': row.get('mom_12m', 0),
                    'volatility': row.get('volatility_60d', 0.15),
                    'signal': row.get('signal', 0),
                    'signal_strength': row.get('signal_strength', 0),
                    'atr': row.get('atr_20', 0),
                    'close': row.get('close', 0)
                })

        # Sort by momentum
        opportunities.sort(key=lambda x: x['momentum'], reverse=True)

        # Return top N
        return opportunities[:self.max_positions]

    def filter_correlated(
        self,
        opportunities: List[Dict],
        correlations: pd.DataFrame,
        max_correlation: float = 0.7
    ) -> List[Dict]:
        """
        Filter out highly correlated assets, keeping highest momentum.
        """
        if not opportunities:
            return []

        selected = [opportunities[0]]

        for opp in opportunities[1:]:
            ticker = opp['ticker']
            is_correlated = False

            for selected_opp in selected:
                sel_ticker = selected_opp['ticker']
                if ticker in correlations.index and sel_ticker in correlations.columns:
                    corr = abs(correlations.loc[ticker, sel_ticker])
                    if corr > max_correlation:
                        is_correlated = True
                        break

            if not is_correlated:
                selected.append(opp)

        return selected


def create_strategy(strategy_name: str, **kwargs):
    """
    Factory function to create strategy instances.
    """
    strategies = {
        'turtle': TurtleStrategy,
        'momentum': MomentumStrategy,
        'dual_momentum': DualMomentumStrategy,
        'combined': CombinedStrategy
    }

    if strategy_name not in strategies:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    return strategies[strategy_name](**kwargs)


if __name__ == "__main__":
    import yfinance as yf

    # Test strategies
    print("Testing strategies on SPY...")

    spy = yf.download("SPY", start="2020-01-01", end="2024-01-01", progress=False)
    spy.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in spy.columns]

    # Test Turtle Strategy
    print("\n=== Turtle Strategy ===")
    turtle = TurtleStrategy()
    turtle_signals = turtle.generate_signals(spy, "SPY")
    print(f"Long entries: {(turtle_signals['signal'] == 1).sum()}")
    print(f"Short entries: {(turtle_signals['signal'] == -1).sum()}")

    # Test Momentum Strategy
    print("\n=== Momentum Strategy ===")
    momentum = MomentumStrategy()
    mom_signals = momentum.generate_signals(spy, "SPY")
    print(f"Long signals: {(mom_signals['signal'] == 1).sum()}")
    print(f"Average volatility: {mom_signals['volatility'].mean():.2%}")

    # Test Combined Strategy
    print("\n=== Combined Strategy ===")
    combined = CombinedStrategy()
    combined_signals = combined.generate_signals(spy, "SPY")
    print(f"Long signals: {(combined_signals['signal'] == 1).sum()}")
    print(f"Short signals: {(combined_signals['signal'] == -1).sum()}")
    print(f"Neutral: {(combined_signals['signal'] == 0).sum()}")
