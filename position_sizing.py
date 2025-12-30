"""
Position Sizing and Risk Management Module

Implements position sizing methods from:
- Turtle Trading (ATR-based, pyramiding)
- Volatility targeting
- Kelly Criterion (modified)
- Fixed fractional
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Position:
    """Represents a single position in a security."""
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    units: int
    direction: int  # 1 for long, -1 for short
    stop_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    pyramid_level: int = 1  # Number of times we've added to position


class PositionSizer:
    """
    ATR-based position sizing as used in Turtle Trading.
    """

    def __init__(
        self,
        risk_per_trade: float = 0.01,  # 1% risk per unit
        max_units_per_market: int = 4,
        max_correlated_units: int = 10,
        max_total_units: int = 12,
        atr_stop_multiple: float = 2.0
    ):
        self.risk_per_trade = risk_per_trade
        self.max_units_per_market = max_units_per_market
        self.max_correlated_units = max_correlated_units
        self.max_total_units = max_total_units
        self.atr_stop_multiple = atr_stop_multiple

    def calculate_unit_size(
        self,
        account_value: float,
        atr: float,
        price: float,
        point_value: float = 1.0  # For futures, this would be contract multiplier
    ) -> int:
        """
        Calculate position size in units using Turtle formula.

        Unit Size = (Account × Risk%) / (ATR × Point Value)
        """
        if atr <= 0 or price <= 0:
            return 0

        dollar_risk = account_value * self.risk_per_trade
        dollar_volatility = atr * point_value

        units = int(dollar_risk / dollar_volatility)

        # Convert to shares (for stocks/ETFs)
        shares = int(units / price * dollar_volatility)

        return max(1, shares)

    def calculate_stop_price(
        self,
        entry_price: float,
        atr: float,
        direction: int
    ) -> float:
        """
        Calculate stop loss price (2N stop in Turtle terms).
        """
        stop_distance = self.atr_stop_multiple * atr

        if direction == 1:  # Long
            return entry_price - stop_distance
        else:  # Short
            return entry_price + stop_distance

    def can_add_pyramid(
        self,
        position: Position,
        current_price: float,
        atr: float,
        pyramid_threshold: float = 0.5
    ) -> bool:
        """
        Check if we can add to position (pyramiding).

        Add every 0.5N above entry for longs, below for shorts.
        """
        if position.pyramid_level >= self.max_units_per_market:
            return False

        price_move = current_price - position.entry_price
        required_move = pyramid_threshold * atr * position.direction

        return (price_move * position.direction) >= required_move

    def calculate_position_value(
        self,
        shares: int,
        price: float
    ) -> float:
        """Calculate total position value."""
        return shares * price


class VolatilityTargeting:
    """
    Volatility-targeted position sizing (AQR style).
    """

    def __init__(
        self,
        target_volatility: float = 0.10,  # 10% annualized
        vol_lookback: int = 60,
        max_leverage: float = 2.0,
        min_weight: float = 0.0
    ):
        self.target_volatility = target_volatility
        self.vol_lookback = vol_lookback
        self.max_leverage = max_leverage
        self.min_weight = min_weight

    def calculate_weight(
        self,
        realized_vol: float,
        signal_strength: float = 1.0
    ) -> float:
        """
        Calculate position weight based on volatility targeting.

        Weight = (Target Vol / Realized Vol) × Signal Strength
        """
        if realized_vol <= 0:
            return 0.0

        raw_weight = (self.target_volatility / realized_vol) * signal_strength

        # Apply limits
        weight = np.clip(raw_weight, self.min_weight, self.max_leverage)

        return weight

    def calculate_portfolio_weights(
        self,
        volatilities: pd.Series,
        signals: pd.Series,
        correlations: Optional[pd.DataFrame] = None
    ) -> pd.Series:
        """
        Calculate weights for multiple assets with correlation adjustment.
        """
        raw_weights = {}

        for ticker in volatilities.index:
            if ticker in signals.index:
                vol = volatilities[ticker]
                signal = signals[ticker]
                raw_weights[ticker] = self.calculate_weight(vol, signal)

        weights = pd.Series(raw_weights)

        # If correlations provided, adjust for diversification
        if correlations is not None and len(weights) > 1:
            # Simple adjustment: reduce weights for highly correlated assets
            for i, ticker1 in enumerate(weights.index):
                for ticker2 in weights.index[i+1:]:
                    if ticker1 in correlations.index and ticker2 in correlations.columns:
                        corr = correlations.loc[ticker1, ticker2]
                        if abs(corr) > 0.7:
                            # Reduce both positions
                            reduction = 0.5 * (abs(corr) - 0.7) / 0.3
                            weights[ticker1] *= (1 - reduction)
                            weights[ticker2] *= (1 - reduction)

        return weights


class ScaleInManager:
    """
    Manages scaling into and out of positions based on trend strength.
    Starts with small position (2-5%), increases as trend proves itself.
    """

    def __init__(
        self,
        initial_pct: float = 0.02,   # Start with 2%
        max_pct: float = 0.10,       # Max 10%
        scale_threshold: float = 0.05,  # Scale up after 5% profit
        scale_increment: float = 0.02   # Add 2% each time
    ):
        self.initial_pct = initial_pct
        self.max_pct = max_pct
        self.scale_threshold = scale_threshold
        self.scale_increment = scale_increment

    def get_initial_weight(self) -> float:
        """Get initial position weight for new entry."""
        return self.initial_pct

    def should_scale_up(
        self,
        entry_price: float,
        current_price: float,
        current_weight: float,
        direction: int
    ) -> Tuple[bool, float]:
        """
        Determine if we should add to position.

        Returns:
            (should_add, new_weight)
        """
        if current_weight >= self.max_pct:
            return False, current_weight

        pnl_pct = (current_price - entry_price) / entry_price * direction

        if pnl_pct >= self.scale_threshold:
            new_weight = min(current_weight + self.scale_increment, self.max_pct)
            return True, new_weight

        return False, current_weight

    def should_reduce(
        self,
        entry_price: float,
        current_price: float,
        current_weight: float,
        direction: int
    ) -> Tuple[bool, float]:
        """
        Determine if we should reduce position.

        Returns:
            (should_reduce, new_weight)
        """
        pnl_pct = (current_price - entry_price) / entry_price * direction

        # Reduce if losing more than half the scale threshold
        if pnl_pct < -self.scale_threshold / 2:
            new_weight = max(current_weight - self.scale_increment, self.initial_pct)
            return True, new_weight

        return False, current_weight


class RiskManager:
    """
    Portfolio-level risk management.
    """

    def __init__(
        self,
        max_portfolio_heat: float = 0.20,    # Max 20% of portfolio at risk
        max_correlation_exposure: float = 0.30,
        max_sector_exposure: float = 0.25,
        max_single_position: float = 0.10,
        drawdown_reduction_threshold: float = 0.10,
        drawdown_reduction_factor: float = 0.20
    ):
        self.max_portfolio_heat = max_portfolio_heat
        self.max_correlation_exposure = max_correlation_exposure
        self.max_sector_exposure = max_sector_exposure
        self.max_single_position = max_single_position
        self.drawdown_reduction_threshold = drawdown_reduction_threshold
        self.drawdown_reduction_factor = drawdown_reduction_factor

        self.peak_equity = 0.0

    def check_position_limits(
        self,
        proposed_weight: float,
        current_weights: Dict[str, float],
        ticker: str,
        correlation_group: Optional[str] = None,
        sector: Optional[str] = None
    ) -> float:
        """
        Check and adjust proposed weight against all limits.
        """
        # Single position limit
        adjusted_weight = min(proposed_weight, self.max_single_position)

        # Correlation group limit
        if correlation_group:
            group_exposure = sum(
                w for t, w in current_weights.items()
                if t != ticker  # Will add this ticker's weight below
            )
            # Simplified: assume all in same group
            max_additional = max(0, self.max_correlation_exposure - group_exposure)
            adjusted_weight = min(adjusted_weight, max_additional)

        return adjusted_weight

    def calculate_portfolio_heat(
        self,
        positions: Dict[str, Position],
        account_value: float
    ) -> float:
        """
        Calculate total portfolio heat (capital at risk).
        """
        total_risk = 0.0

        for ticker, pos in positions.items():
            if pos.direction == 1:  # Long
                risk_per_share = pos.entry_price - pos.stop_price
            else:  # Short
                risk_per_share = pos.stop_price - pos.entry_price

            position_risk = risk_per_share * pos.units
            total_risk += position_risk

        return total_risk / account_value if account_value > 0 else 0.0

    def apply_drawdown_rule(
        self,
        current_equity: float,
        base_weight: float
    ) -> float:
        """
        Apply Turtle-style drawdown reduction rule.
        If down 10%, reduce position sizes by 20%.
        """
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            return base_weight

        if self.peak_equity <= 0:
            return base_weight

        drawdown = (self.peak_equity - current_equity) / self.peak_equity

        if drawdown > self.drawdown_reduction_threshold:
            # Reduce proportionally
            reduction_levels = int(drawdown / self.drawdown_reduction_threshold)
            reduction = 1 - (self.drawdown_reduction_factor * reduction_levels)
            return base_weight * max(0.2, reduction)  # Never reduce below 20%

        return base_weight


class KellyCriterion:
    """
    Modified Kelly Criterion for position sizing.
    Uses historical win rate and average win/loss.
    """

    def __init__(
        self,
        kelly_fraction: float = 0.25,  # Use 1/4 Kelly for safety
        lookback_trades: int = 100
    ):
        self.kelly_fraction = kelly_fraction
        self.lookback_trades = lookback_trades
        self.trade_history: List[float] = []

    def add_trade(self, pnl_pct: float):
        """Add a completed trade to history."""
        self.trade_history.append(pnl_pct)
        if len(self.trade_history) > self.lookback_trades:
            self.trade_history.pop(0)

    def calculate_kelly(self) -> float:
        """
        Calculate Kelly fraction.
        f* = (bp - q) / b
        where:
        - b = odds (avg_win / avg_loss)
        - p = probability of winning
        - q = probability of losing = 1 - p
        """
        if len(self.trade_history) < 10:
            return self.kelly_fraction * 0.1  # Conservative start

        wins = [t for t in self.trade_history if t > 0]
        losses = [t for t in self.trade_history if t < 0]

        if not wins or not losses:
            return self.kelly_fraction * 0.1

        p = len(wins) / len(self.trade_history)
        q = 1 - p

        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))

        if avg_loss == 0:
            return self.kelly_fraction

        b = avg_win / avg_loss
        kelly = (b * p - q) / b

        # Apply safety fraction
        return max(0, kelly * self.kelly_fraction)


def calculate_optimal_weights(
    signals: pd.Series,
    volatilities: pd.Series,
    correlations: pd.DataFrame,
    target_vol: float = 0.10,
    max_position: float = 0.10,
    max_total_exposure: float = 1.0
) -> pd.Series:
    """
    Calculate optimal portfolio weights combining multiple factors.

    Args:
        signals: Signal strength for each asset (-1 to 1)
        volatilities: Realized volatility for each asset
        correlations: Correlation matrix
        target_vol: Target portfolio volatility
        max_position: Maximum single position size
        max_total_exposure: Maximum total long exposure

    Returns:
        Portfolio weights
    """
    n_assets = len(signals)

    if n_assets == 0:
        return pd.Series()

    # Start with volatility-targeted weights
    raw_weights = {}
    for ticker in signals.index:
        if ticker in volatilities.index and volatilities[ticker] > 0:
            # Weight inversely proportional to volatility, scaled by signal
            vol_weight = target_vol / volatilities[ticker]
            signal = signals[ticker]
            raw_weights[ticker] = vol_weight * signal
        else:
            raw_weights[ticker] = 0.0

    weights = pd.Series(raw_weights)

    # Normalize if total exceeds maximum
    long_exposure = weights[weights > 0].sum()
    if long_exposure > max_total_exposure:
        scale = max_total_exposure / long_exposure
        weights = weights.clip(lower=0) * scale

    # Cap individual positions
    weights = weights.clip(upper=max_position, lower=-max_position)

    return weights


if __name__ == "__main__":
    # Test position sizer
    sizer = PositionSizer()

    # Example: Calculate position size
    account = 100000
    atr = 2.50
    price = 50.0

    shares = sizer.calculate_unit_size(account, atr, price)
    print(f"Account: ${account:,}")
    print(f"ATR: ${atr:.2f}")
    print(f"Price: ${price:.2f}")
    print(f"Position size: {shares} shares")
    print(f"Position value: ${shares * price:,.2f}")
    print(f"Risk per share: ${sizer.atr_stop_multiple * atr:.2f}")
    print(f"Total risk: ${shares * sizer.atr_stop_multiple * atr:,.2f}")
    print(f"Risk %: {(shares * sizer.atr_stop_multiple * atr) / account:.2%}")
