#!/usr/bin/env python3
"""
TREND FOLLOWING TRADING BOT
===========================

Implements the strategy defined in strategy_spec.py with full CSV logging.
Every decision is logged with all indicator values for verification.

Usage:
    python trading_bot.py --start 1980-01-01 --end 1985-12-31 --output trades.csv
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import csv
import os
from tqdm import tqdm

from strategy_spec import STRATEGY_PARAMS


@dataclass
class DailyRecord:
    """Single row in the daily CSV log."""
    # Date and asset
    date: str
    ticker: str
    asset_name: str

    # Action taken
    action: str  # SCAN, ENTRY, HOLD, LEVERAGE_UP, LEVERAGE_DOWN, EXIT
    position_status: str  # NONE, OPEN, CLOSED
    direction: str  # LONG, SHORT, NONE

    # Price data
    close: float
    high_20d: float
    low_20d: float
    sma_50: float
    sma_200: float

    # Indicators
    mom_12m: float
    mom_12m_5d_ago: float
    atr_20: float
    atr_20_10d_ago: float
    volatility_60d: float

    # Position info (if open)
    entry_date: str = ""
    entry_price: float = 0.0
    days_held: int = 0
    current_pnl_pct: float = 0.0
    peak_price: float = 0.0
    peak_pnl_pct: float = 0.0
    current_leverage: float = 1.0
    position_size_pct: float = 0.0

    # Signals (-1, 0, 1)
    signal_momentum: int = 0
    signal_ma_cross: int = 0
    signal_price_vs_ma: int = 0
    signal_breakout: int = 0
    signal_combined: float = 0.0

    # Decision details
    decision: str = ""
    decision_reason: str = ""
    entry_criteria_met: bool = False
    leverage_up_criteria_met: bool = False
    leverage_down_criteria_met: bool = False
    exit_criteria_met: bool = False

    # Portfolio state
    portfolio_equity: float = 0.0
    portfolio_cash: float = 0.0
    portfolio_positions: int = 0
    portfolio_leverage: float = 1.0


@dataclass
class Position:
    """Represents an open position."""
    ticker: str
    asset_name: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: float
    direction: int  # 1 = LONG, -1 = SHORT
    leverage: float = 1.0
    peak_price: float = 0.0
    peak_pnl_pct: float = 0.0
    position_value: float = 0.0


class TradingBot:
    """
    Trend following bot with full CSV logging.
    """

    def __init__(
        self,
        initial_capital: float = 100000,
        output_file: str = "trades.csv"
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.output_file = output_file

        self.positions: Dict[str, Position] = {}
        self.records: List[DailyRecord] = []
        self.equity_history: List[Tuple[str, float]] = []

        self.params = STRATEGY_PARAMS

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required indicators."""
        result = df.copy()

        # Price
        close = result['close']
        high = result['high']
        low = result['low']

        # Moving averages
        result['sma_50'] = close.rolling(50).mean()
        result['sma_200'] = close.rolling(200).mean()

        # Donchian channels
        result['high_20d'] = high.rolling(20).max()
        result['low_20d'] = low.rolling(20).min()

        # Momentum
        result['mom_12m'] = close.pct_change(252)
        result['mom_12m_5d_ago'] = result['mom_12m'].shift(5)

        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        result['atr_20'] = tr.rolling(20).mean()
        result['atr_20_10d_ago'] = result['atr_20'].shift(10)

        # Volatility
        returns = close.pct_change()
        result['volatility_60d'] = returns.rolling(60).std() * np.sqrt(252)

        return result

    def check_entry_criteria(self, row: pd.Series, ticker: str) -> Tuple[bool, str]:
        """
        Check if entry criteria are met.
        Returns (met, reason)
        """
        reasons = []

        # 1. 12-month momentum > 0
        if pd.isna(row['mom_12m']) or row['mom_12m'] <= self.params['entry_mom_threshold']:
            return False, f"Momentum {row.get('mom_12m', 0):.1%} <= 0%"
        reasons.append(f"Mom={row['mom_12m']:.1%}")

        # 2. Price > 200-day SMA
        if pd.isna(row['sma_200']) or row['close'] <= row['sma_200']:
            return False, f"Price {row['close']:.2f} <= SMA200 {row.get('sma_200', 0):.2f}"
        reasons.append(f"Price>SMA200")

        # 3. 50-day SMA > 200-day SMA (Golden Cross)
        if pd.isna(row['sma_50']) or row['sma_50'] <= row['sma_200']:
            return False, f"SMA50 {row.get('sma_50', 0):.2f} <= SMA200 {row.get('sma_200', 0):.2f}"
        reasons.append(f"GoldenCross")

        # 4. Donchian breakout (close > previous 20-day high)
        if pd.isna(row['high_20d']):
            return False, "No 20-day high data"

        # We compare to shifted high (yesterday's 20-day high)
        prev_high = row.get('high_20d_prev', row['high_20d'])
        if row['close'] <= prev_high * 0.99:  # Allow 1% tolerance
            return False, f"No breakout: {row['close']:.2f} <= {prev_high:.2f}"
        reasons.append(f"Breakout>{prev_high:.2f}")

        # 5. No existing position
        if ticker in self.positions:
            return False, "Already have position"

        return True, " | ".join(reasons)

    def check_leverage_up_criteria(
        self,
        row: pd.Series,
        position: Position,
        current_price: float
    ) -> Tuple[bool, str]:
        """Check if we should increase leverage."""
        reasons = []

        # Calculate current P&L
        pnl_pct = (current_price - position.entry_price) / position.entry_price
        if position.direction == -1:
            pnl_pct = -pnl_pct

        days_held = (pd.Timestamp(row.name) - position.entry_date).days

        # Already at max leverage
        if position.leverage >= self.params['leverage_max']:
            return False, f"Already at max leverage {position.leverage}x"

        # 1. Profit > 3%
        if pnl_pct < self.params['leverage_up_profit']:
            return False, f"PnL {pnl_pct:.1%} < {self.params['leverage_up_profit']:.0%} required"
        reasons.append(f"PnL={pnl_pct:.1%}")

        # 2. Held at least 10 days
        if days_held < self.params['leverage_up_days']:
            return False, f"Held {days_held}d < {self.params['leverage_up_days']}d required"
        reasons.append(f"Days={days_held}")

        # 3. All signals still agree
        if row['close'] <= row['sma_50']:
            return False, "Price below SMA50"
        if row['close'] <= row['sma_200']:
            return False, "Price below SMA200"
        if row['mom_12m'] <= 0:
            return False, "Momentum negative"
        reasons.append("Signals agree")

        # Determine target leverage
        if pnl_pct >= self.params['leverage_max_profit'] and days_held >= self.params['leverage_max_days']:
            # Check for max leverage
            mom_accelerating = row['mom_12m'] > row['mom_12m_5d_ago'] if not pd.isna(row['mom_12m_5d_ago']) else False
            atr_stable = row['atr_20'] <= row['atr_20_10d_ago'] * 1.2 if not pd.isna(row['atr_20_10d_ago']) else True

            if mom_accelerating and atr_stable:
                reasons.append(f"Max leverage criteria met")
                return True, " | ".join(reasons) + f" -> {self.params['leverage_max']}x"

        return True, " | ".join(reasons) + f" -> {self.params['leverage_medium']}x"

    def check_leverage_down_criteria(
        self,
        row: pd.Series,
        position: Position,
        current_price: float
    ) -> Tuple[bool, str]:
        """Check if we should decrease leverage."""
        if position.leverage <= 1.0:
            return False, "Already at 1x"

        days_held = (pd.Timestamp(row.name) - position.entry_date).days

        # 1. Pullback from peak > 2%
        if position.peak_price > 0:
            pullback = (position.peak_price - current_price) / position.peak_price
            if position.direction == -1:
                pullback = -pullback

            if pullback > self.params['leverage_down_pullback']:
                return True, f"Pullback {pullback:.1%} > {self.params['leverage_down_pullback']:.0%}"

        # 2. Momentum weakening
        if not pd.isna(row['mom_12m_5d_ago']) and row['mom_12m_5d_ago'] > 0:
            mom_ratio = row['mom_12m'] / row['mom_12m_5d_ago']
            if mom_ratio < self.params['leverage_down_mom_decay']:
                return True, f"Momentum decay {mom_ratio:.1%}"

        # 3. Price crosses below 50-day SMA
        if row['close'] < row['sma_50']:
            return True, "Price < SMA50"

        # 4. Held with leverage too long
        if days_held > self.params['leverage_max_duration']:
            return True, f"Leverage duration {days_held}d > {self.params['leverage_max_duration']}d"

        return False, ""

    def check_exit_criteria(
        self,
        row: pd.Series,
        position: Position,
        current_price: float
    ) -> Tuple[bool, str]:
        """Check if we should exit the position."""
        pnl_pct = (current_price - position.entry_price) / position.entry_price
        if position.direction == -1:
            pnl_pct = -pnl_pct

        # 1. Stop loss
        if pnl_pct < self.params['exit_stop_loss']:
            return True, f"STOP LOSS: PnL {pnl_pct:.1%} < {self.params['exit_stop_loss']:.0%}"

        # 2. Trailing stop (3 ATR from peak)
        if position.peak_price > 0 and not pd.isna(row['atr_20']):
            trailing_stop = position.peak_price - self.params['exit_trailing_atr'] * row['atr_20']
            if position.direction == -1:
                trailing_stop = position.peak_price + self.params['exit_trailing_atr'] * row['atr_20']

            if (position.direction == 1 and current_price < trailing_stop) or \
               (position.direction == -1 and current_price > trailing_stop):
                return True, f"TRAILING STOP: Price {current_price:.2f} vs stop {trailing_stop:.2f}"

        # 3. Trend reversal
        if row['close'] < row['sma_200'] and row['sma_50'] < row['sma_200']:
            return True, "TREND REVERSAL: Death cross and price < SMA200"

        # 4. Momentum reversal
        if row['mom_12m'] < 0 and position.direction == 1:
            return True, f"MOMENTUM REVERSAL: 12m momentum = {row['mom_12m']:.1%}"

        return False, ""

    def calculate_signals(self, row: pd.Series) -> Dict:
        """Calculate individual signal values."""
        signals = {}

        # Momentum signal
        if pd.isna(row['mom_12m']):
            signals['momentum'] = 0
        elif row['mom_12m'] > 0.05:
            signals['momentum'] = 1
        elif row['mom_12m'] < -0.05:
            signals['momentum'] = -1
        else:
            signals['momentum'] = 0

        # MA cross signal
        if pd.isna(row['sma_50']) or pd.isna(row['sma_200']):
            signals['ma_cross'] = 0
        elif row['sma_50'] > row['sma_200'] * 1.02:
            signals['ma_cross'] = 1
        elif row['sma_50'] < row['sma_200'] * 0.98:
            signals['ma_cross'] = -1
        else:
            signals['ma_cross'] = 0

        # Price vs MA signal
        if pd.isna(row['sma_200']):
            signals['price_vs_ma'] = 0
        elif row['close'] > row['sma_200'] * 1.02:
            signals['price_vs_ma'] = 1
        elif row['close'] < row['sma_200'] * 0.98:
            signals['price_vs_ma'] = -1
        else:
            signals['price_vs_ma'] = 0

        # Breakout signal
        if pd.isna(row['high_20d']) or pd.isna(row['low_20d']):
            signals['breakout'] = 0
        elif row['close'] >= row['high_20d']:
            signals['breakout'] = 1
        elif row['close'] <= row['low_20d']:
            signals['breakout'] = -1
        else:
            signals['breakout'] = 0

        # Combined signal
        signals['combined'] = (signals['momentum'] + signals['ma_cross'] +
                               signals['price_vs_ma'] + signals['breakout']) / 4

        return signals

    def get_portfolio_state(self) -> Tuple[float, float, int, float]:
        """Calculate current portfolio state."""
        position_value = sum(
            p.position_value * p.leverage for p in self.positions.values()
        )
        equity = self.cash + position_value
        n_positions = len(self.positions)

        if position_value > 0:
            avg_leverage = sum(p.leverage * p.position_value for p in self.positions.values()) / position_value
        else:
            avg_leverage = 1.0

        return equity, self.cash, n_positions, avg_leverage

    def create_record(
        self,
        date: pd.Timestamp,
        ticker: str,
        asset_name: str,
        row: pd.Series,
        action: str,
        decision: str,
        decision_reason: str,
        position: Optional[Position] = None
    ) -> DailyRecord:
        """Create a daily record for CSV logging."""
        signals = self.calculate_signals(row)
        equity, cash, n_pos, avg_lev = self.get_portfolio_state()

        # Position info
        if position:
            days_held = (date - position.entry_date).days
            current_price = row['close']
            pnl_pct = (current_price - position.entry_price) / position.entry_price
            if position.direction == -1:
                pnl_pct = -pnl_pct
            entry_date = position.entry_date.strftime('%Y-%m-%d')
        else:
            days_held = 0
            pnl_pct = 0
            entry_date = ""

        record = DailyRecord(
            date=date.strftime('%Y-%m-%d'),
            ticker=ticker,
            asset_name=asset_name,
            action=action,
            position_status="OPEN" if position else "NONE",
            direction="LONG" if position and position.direction == 1 else ("SHORT" if position and position.direction == -1 else "NONE"),

            close=row['close'],
            high_20d=row.get('high_20d', 0) or 0,
            low_20d=row.get('low_20d', 0) or 0,
            sma_50=row.get('sma_50', 0) or 0,
            sma_200=row.get('sma_200', 0) or 0,

            mom_12m=row.get('mom_12m', 0) or 0,
            mom_12m_5d_ago=row.get('mom_12m_5d_ago', 0) or 0,
            atr_20=row.get('atr_20', 0) or 0,
            atr_20_10d_ago=row.get('atr_20_10d_ago', 0) or 0,
            volatility_60d=row.get('volatility_60d', 0) or 0,

            entry_date=entry_date,
            entry_price=position.entry_price if position else 0,
            days_held=days_held,
            current_pnl_pct=pnl_pct,
            peak_price=position.peak_price if position else 0,
            peak_pnl_pct=position.peak_pnl_pct if position else 0,
            current_leverage=position.leverage if position else 1.0,
            position_size_pct=position.position_value / equity * 100 if position and equity > 0 else 0,

            signal_momentum=signals['momentum'],
            signal_ma_cross=signals['ma_cross'],
            signal_price_vs_ma=signals['price_vs_ma'],
            signal_breakout=signals['breakout'],
            signal_combined=signals['combined'],

            decision=decision,
            decision_reason=decision_reason,
            entry_criteria_met=action == "ENTRY",
            leverage_up_criteria_met=action == "LEVERAGE_UP",
            leverage_down_criteria_met=action == "LEVERAGE_DOWN",
            exit_criteria_met=action == "EXIT",

            portfolio_equity=equity,
            portfolio_cash=cash,
            portfolio_positions=n_pos,
            portfolio_leverage=avg_lev
        )

        return record

    def run(
        self,
        data: Dict[str, pd.DataFrame],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Run the trading bot and generate CSV log.
        """
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)

        # Calculate indicators for all assets
        print("Calculating indicators...")
        processed_data = {}
        asset_names = {}

        for ticker, df in data.items():
            asset_names[ticker] = df['asset_name'].iloc[0] if 'asset_name' in df.columns else ticker
            df_processed = self.calculate_indicators(df.drop(columns=['asset_name'], errors='ignore'))
            df_processed['high_20d_prev'] = df_processed['high_20d'].shift(1)
            processed_data[ticker] = df_processed

        # Get all trading dates
        all_dates = set()
        for df in processed_data.values():
            all_dates.update(df.index)
        dates = sorted([d for d in all_dates if start <= d <= end])

        print(f"Running bot from {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")
        print(f"Assets: {len(processed_data)}")
        print("=" * 60)

        # Main loop
        for date in tqdm(dates, desc="Processing"):
            # Get current prices and update positions
            for ticker, position in list(self.positions.items()):
                if ticker not in processed_data:
                    continue

                df = processed_data[ticker]
                if date not in df.index:
                    continue

                row = df.loc[date]
                current_price = row['close']

                # Update position values
                position.position_value = position.shares * current_price

                # Update peak
                if position.direction == 1:
                    if current_price > position.peak_price:
                        position.peak_price = current_price
                else:
                    if position.peak_price == 0 or current_price < position.peak_price:
                        position.peak_price = current_price

                # Calculate peak P&L
                pnl_pct = (current_price - position.entry_price) / position.entry_price
                if position.direction == -1:
                    pnl_pct = -pnl_pct
                position.peak_pnl_pct = max(position.peak_pnl_pct, pnl_pct)

                # Check exit criteria
                exit_met, exit_reason = self.check_exit_criteria(row, position, current_price)
                if exit_met:
                    # Exit position
                    self.cash += position.position_value
                    record = self.create_record(
                        date, ticker, asset_names[ticker], row,
                        action="EXIT",
                        decision="CLOSE POSITION",
                        decision_reason=exit_reason,
                        position=position
                    )
                    record.position_status = "CLOSED"
                    self.records.append(record)
                    del self.positions[ticker]
                    continue

                # Check leverage down
                lev_down_met, lev_down_reason = self.check_leverage_down_criteria(row, position, current_price)
                if lev_down_met and position.leverage > 1.0:
                    old_lev = position.leverage
                    position.leverage = 1.0
                    record = self.create_record(
                        date, ticker, asset_names[ticker], row,
                        action="LEVERAGE_DOWN",
                        decision=f"REDUCE LEVERAGE {old_lev}x -> 1.0x",
                        decision_reason=lev_down_reason,
                        position=position
                    )
                    self.records.append(record)
                    continue

                # Check leverage up
                lev_up_met, lev_up_reason = self.check_leverage_up_criteria(row, position, current_price)
                if lev_up_met:
                    old_lev = position.leverage
                    # Determine new leverage
                    pnl = (current_price - position.entry_price) / position.entry_price
                    days = (date - position.entry_date).days

                    if pnl >= self.params['leverage_max_profit'] and days >= self.params['leverage_max_days']:
                        new_lev = self.params['leverage_max']
                    else:
                        new_lev = self.params['leverage_medium']

                    if new_lev > old_lev:
                        position.leverage = new_lev
                        record = self.create_record(
                            date, ticker, asset_names[ticker], row,
                            action="LEVERAGE_UP",
                            decision=f"INCREASE LEVERAGE {old_lev}x -> {new_lev}x",
                            decision_reason=lev_up_reason,
                            position=position
                        )
                        self.records.append(record)
                        continue

                # Hold
                record = self.create_record(
                    date, ticker, asset_names[ticker], row,
                    action="HOLD",
                    decision="MAINTAIN POSITION",
                    decision_reason=f"PnL={pnl_pct:.1%}, Days={position.peak_pnl_pct}",
                    position=position
                )
                self.records.append(record)

            # Scan for new entries
            for ticker, df in processed_data.items():
                if date not in df.index:
                    continue
                if ticker in self.positions:
                    continue
                if len(self.positions) >= self.params['max_positions']:
                    continue

                row = df.loc[date]
                entry_met, entry_reason = self.check_entry_criteria(row, ticker)

                if entry_met:
                    # Calculate position size
                    equity = self.cash + sum(p.position_value for p in self.positions.values())
                    position_value = equity * self.params['entry_position_size']

                    if position_value > self.cash:
                        continue  # Not enough cash

                    shares = position_value / row['close']

                    position = Position(
                        ticker=ticker,
                        asset_name=asset_names[ticker],
                        entry_date=date,
                        entry_price=row['close'],
                        shares=shares,
                        direction=1,  # LONG
                        leverage=1.0,
                        peak_price=row['close'],
                        peak_pnl_pct=0,
                        position_value=position_value
                    )

                    self.cash -= position_value
                    self.positions[ticker] = position

                    record = self.create_record(
                        date, ticker, asset_names[ticker], row,
                        action="ENTRY",
                        decision="OPEN LONG POSITION",
                        decision_reason=entry_reason,
                        position=position
                    )
                    self.records.append(record)

            # Record equity
            equity, _, _, _ = self.get_portfolio_state()
            self.equity_history.append((date.strftime('%Y-%m-%d'), equity))

        # Save to CSV
        self.save_csv()

        return pd.DataFrame([asdict(r) for r in self.records])

    def save_csv(self):
        """Save all records to CSV."""
        if not self.records:
            print("No records to save")
            return

        df = pd.DataFrame([asdict(r) for r in self.records])
        df.to_csv(self.output_file, index=False)
        print(f"\nSaved {len(self.records)} records to {self.output_file}")

        # Also save equity curve
        equity_file = self.output_file.replace('.csv', '_equity.csv')
        equity_df = pd.DataFrame(self.equity_history, columns=['date', 'equity'])
        equity_df.to_csv(equity_file, index=False)
        print(f"Saved equity curve to {equity_file}")


def run_bot_simulation():
    """Run the bot on synthetic 1980-1985 data."""
    from historical_simulation import HistoricalSimulator

    print("=" * 60)
    print("TREND FOLLOWING BOT - CSV SIMULATION")
    print("=" * 60)

    # Generate data
    sim = HistoricalSimulator()
    data = sim.generate_synthetic_data(1980, 1985)

    # Run bot
    bot = TradingBot(initial_capital=100000, output_file="trades_1980_1985.csv")
    records_df = bot.run(data, "1980-01-01", "1985-12-31")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    entries = records_df[records_df['action'] == 'ENTRY']
    exits = records_df[records_df['action'] == 'EXIT']
    leverage_ups = records_df[records_df['action'] == 'LEVERAGE_UP']
    leverage_downs = records_df[records_df['action'] == 'LEVERAGE_DOWN']

    print(f"Total entries: {len(entries)}")
    print(f"Total exits: {len(exits)}")
    print(f"Leverage increases: {len(leverage_ups)}")
    print(f"Leverage decreases: {len(leverage_downs)}")

    if bot.equity_history:
        initial = bot.initial_capital
        final = bot.equity_history[-1][1]
        years = 6
        cagr = (final / initial) ** (1/years) - 1
        print(f"\nInitial: ${initial:,.0f}")
        print(f"Final: ${final:,.0f}")
        print(f"CAGR: {cagr:.1%}")

    print(f"\nCSV file: {bot.output_file}")

    return records_df


if __name__ == "__main__":
    records = run_bot_simulation()
