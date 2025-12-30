#!/usr/bin/env python3
"""
SMART LEVERAGE TRADING BOT
==========================
Live trading bot using the exact same logic as the backtest.

Usage:
  python smart_leverage_bot.py                    # Show today's recommendations
  python smart_leverage_bot.py --signals          # Show all asset signals
  python smart_leverage_bot.py --execute          # Auto-execute signals
  python smart_leverage_bot.py --capital 100000   # Set starting capital

Run daily before market open to get trading recommendations.
"""

import pandas as pd
import numpy as np
import os
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# STRATEGY PARAMETERS (Exact same as backtest)
# ============================================================================
PARAMS = {
    # Entry signals
    'mom_12m_min': 0.10,          # 10% 12-month momentum
    'mom_6m_min': 0.05,           # 5% 6-month momentum
    'mom_3m_min': 0.02,           # 2% 3-month momentum
    'mom_1m_min': 0.01,           # 1% 1-month momentum
    'min_signals': 3,             # Need 3+ signals to enter

    # Leverage tiers
    'leverage_tier_1': 1.0,       # Base (0-2 signals)
    'leverage_tier_2': 1.5,       # Moderate (3 signals)
    'leverage_tier_3': 2.0,       # Strong (4 signals)
    'leverage_tier_4': 3.0,       # Very strong (5+ signals)

    # Deleverage triggers
    'deleverage_pullback': 0.02,  # 2% pullback from high
    'deleverage_mom_decay': 0.40, # 40% momentum decay

    # Exit triggers
    'stop_loss': -0.04,           # 4% stop loss
    'trailing_atr_base': 2.0,     # 2.0 ATR trailing stop
    'trailing_atr_leveraged': 1.5,# 1.5 ATR when leveraged

    # Position sizing
    'position_size': 0.05,        # 5% per position
    'max_positions': 12,          # Maximum 12 positions
}


@dataclass
class Position:
    ticker: str
    entry_date: str
    entry_price: float
    shares: float
    leverage: float
    highest_price: float
    peak_momentum: float
    current_price: float = 0.0
    current_pnl_pct: float = 0.0
    signal_strength: int = 0
    signals: str = ""


@dataclass
class Signal:
    ticker: str
    action: str  # BUY, SELL, LEVERAGE_UP, DELEVERAGE, HOLD
    current_price: float
    signal_strength: int
    signals: str
    reason: str
    recommended_leverage: float
    recommended_shares: float = 0.0
    urgency: str = "NORMAL"  # NORMAL, HIGH, CRITICAL


class SmartLeverageBot:
    def __init__(self, data_dir: str = 'historical_data', portfolio_file: str = 'portfolio.json'):
        self.data_dir = data_dir
        self.portfolio_file = portfolio_file
        self.data: Dict[str, pd.DataFrame] = {}
        self.positions: Dict[str, Position] = {}
        self.portfolio_value = 100000
        self.cash = 100000

        self._load_data()
        self._load_portfolio()

    def _load_data(self):
        """Load and prepare market data"""
        print("Loading market data...")
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.csv') and filename != 'data_summary.csv':
                ticker = filename.replace('.csv', '')
                filepath = os.path.join(self.data_dir, filename)
                try:
                    df = pd.read_csv(filepath, header=[0, 1, 2])
                    df.columns = [col[0] for col in df.columns]
                    df = df.rename(columns={df.columns[0]: 'Date'})
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                    df = df.dropna(subset=['Date'])
                    df.set_index('Date', inplace=True)
                    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    if 'Close' in df.columns and len(df) > 252:
                        df = self._calculate_indicators(df)
                        self.data[ticker] = df
                except Exception as e:
                    pass
        print(f"  Loaded {len(self.data)} assets")

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators"""
        df = df.copy()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['Mom_12m'] = df['Close'].pct_change(252)
        df['Mom_6m'] = df['Close'].pct_change(126)
        df['Mom_3m'] = df['Close'].pct_change(63)
        df['Mom_1m'] = df['Close'].pct_change(21)
        df['Donchian_High'] = df['High'].rolling(20).max()
        df['TR'] = np.maximum(df['High'] - df['Low'],
                              np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                        abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()
        return df

    def _load_portfolio(self):
        """Load current portfolio from file"""
        if os.path.exists(self.portfolio_file):
            with open(self.portfolio_file, 'r') as f:
                data = json.load(f)
                self.portfolio_value = data.get('portfolio_value', 100000)
                self.cash = data.get('cash', 100000)
                for ticker, pos_data in data.get('positions', {}).items():
                    self.positions[ticker] = Position(**pos_data)
            print(f"  Loaded portfolio: ${self.portfolio_value:,.0f} ({len(self.positions)} positions)")
        else:
            print("  No portfolio file found. Starting fresh with $100,000")

    def save_portfolio(self):
        """Save current portfolio to file"""
        data = {
            'portfolio_value': self.portfolio_value,
            'cash': self.cash,
            'last_updated': datetime.now().isoformat(),
            'positions': {ticker: asdict(pos) for ticker, pos in self.positions.items()}
        }
        with open(self.portfolio_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"\nPortfolio saved to {self.portfolio_file}")

    def _get_latest_data(self, ticker: str) -> Optional[pd.Series]:
        """Get latest data for a ticker"""
        if ticker not in self.data:
            return None
        df = self.data[ticker]
        if len(df) == 0:
            return None
        return df.iloc[-1]

    def _get_signal_strength(self, ticker: str) -> Tuple[int, str]:
        """Calculate signal strength and description"""
        row = self._get_latest_data(ticker)
        if row is None:
            return 0, ""

        signals = []
        score = 0

        mom_12m = row.get('Mom_12m', 0)
        mom_6m = row.get('Mom_6m', 0)
        mom_3m = row.get('Mom_3m', 0)
        mom_1m = row.get('Mom_1m', 0)
        sma50 = row.get('SMA50', 0)
        sma200 = row.get('SMA200', 0)
        donchian = row.get('Donchian_High', 0)
        price = row['Close']

        if not pd.isna(mom_12m) and mom_12m > PARAMS['mom_12m_min']:
            score += 1
            signals.append(f"Mom12m={mom_12m*100:.1f}%")
        if not pd.isna(mom_6m) and mom_6m > PARAMS['mom_6m_min']:
            score += 1
            signals.append(f"Mom6m={mom_6m*100:.1f}%")
        if not pd.isna(mom_3m) and mom_3m > PARAMS['mom_3m_min']:
            score += 1
            signals.append(f"Mom3m={mom_3m*100:.1f}%")
        if not pd.isna(mom_1m) and mom_1m > PARAMS['mom_1m_min']:
            score += 1
            signals.append(f"Mom1m={mom_1m*100:.1f}%")

        if not pd.isna(sma50) and not pd.isna(sma200):
            if sma50 > sma200:
                signals.append("GoldenCross")
            if price > sma50:
                signals.append("AboveSMA50")

        if not pd.isna(donchian) and price >= donchian:
            score += 1
            signals.append("Breakout")

        return score, " | ".join(signals)

    def _check_entry(self, ticker: str) -> Tuple[bool, int, str]:
        """Check if we should enter a position"""
        score, signals = self._get_signal_strength(ticker)

        if score < PARAMS['min_signals']:
            return False, score, signals

        row = self._get_latest_data(ticker)
        if row is None:
            return False, 0, ""

        sma50 = row.get('SMA50')
        sma200 = row.get('SMA200')
        price = row['Close']

        if pd.isna(sma50) or pd.isna(sma200):
            return False, score, signals
        if price <= sma50 or sma50 <= sma200:
            return False, score, signals

        return True, score, signals

    def _get_leverage_for_strength(self, strength: int) -> float:
        """Map signal strength to leverage"""
        if strength <= 2:
            return PARAMS['leverage_tier_1']
        elif strength == 3:
            return PARAMS['leverage_tier_2']
        elif strength == 4:
            return PARAMS['leverage_tier_3']
        else:
            return PARAMS['leverage_tier_4']

    def _check_exit(self, pos: Position) -> Tuple[bool, str, str]:
        """Check if we should exit a position"""
        row = self._get_latest_data(pos.ticker)
        if row is None:
            return False, "", "NO_DATA"

        price = row['Close']
        pnl_pct = (price - pos.entry_price) / pos.entry_price

        # Stop loss
        if pnl_pct * pos.leverage <= PARAMS['stop_loss']:
            return True, "STOP_LOSS", f"PnL={pnl_pct*100:.1f}% hit stop at {PARAMS['stop_loss']*100}%"

        # Trailing stop
        atr = row.get('ATR')
        if not pd.isna(atr) and pos.highest_price > 0:
            mult = PARAMS['trailing_atr_leveraged'] if pos.leverage > 1 else PARAMS['trailing_atr_base']
            trail_stop = pos.highest_price - mult * atr
            if price < trail_stop:
                return True, "TRAILING_STOP", f"Price ${price:.2f} < Stop ${trail_stop:.2f}"

        return False, "", ""

    def _check_deleverage(self, pos: Position) -> Tuple[bool, str]:
        """Check if we should reduce leverage"""
        row = self._get_latest_data(pos.ticker)
        if row is None:
            return False, ""

        price = row['Close']

        # Pullback check
        if pos.highest_price > 0:
            pullback = (pos.highest_price - price) / pos.highest_price
            if pullback > PARAMS['deleverage_pullback']:
                return True, f"Pullback={pullback*100:.1f}% from high"

        # Momentum decay
        mom_12m = row.get('Mom_12m', 0)
        if not pd.isna(mom_12m) and pos.peak_momentum > 0:
            decay = 1 - (mom_12m / pos.peak_momentum) if pos.peak_momentum > 0 else 0
            if decay > PARAMS['deleverage_mom_decay']:
                return True, f"Momentum decay={decay*100:.1f}%"

        return False, ""

    def generate_signals(self) -> List[Signal]:
        """Generate trading signals for all assets"""
        signals = []

        # Check existing positions first
        for ticker, pos in list(self.positions.items()):
            row = self._get_latest_data(ticker)
            if row is None:
                continue

            price = row['Close']
            pos.current_price = price
            pos.current_pnl_pct = (price - pos.entry_price) / pos.entry_price

            # Update highest price
            if price > pos.highest_price:
                pos.highest_price = price

            strength, sig_str = self._get_signal_strength(ticker)
            pos.signal_strength = strength
            pos.signals = sig_str

            # Check exit
            should_exit, exit_type, reason = self._check_exit(pos)
            if should_exit:
                signals.append(Signal(
                    ticker=ticker,
                    action="SELL",
                    current_price=price,
                    signal_strength=strength,
                    signals=sig_str,
                    reason=reason,
                    recommended_leverage=0,
                    recommended_shares=pos.shares,
                    urgency="HIGH" if exit_type == "STOP_LOSS" else "NORMAL"
                ))
                continue

            # Check deleverage
            if pos.leverage > 1:
                should_delev, delev_reason = self._check_deleverage(pos)
                if should_delev:
                    signals.append(Signal(
                        ticker=ticker,
                        action="DELEVERAGE",
                        current_price=price,
                        signal_strength=strength,
                        signals=sig_str,
                        reason=delev_reason,
                        recommended_leverage=1.0,
                        urgency="NORMAL"
                    ))
                    continue

            # Check leverage increase
            new_lev = self._get_leverage_for_strength(strength)
            if new_lev > pos.leverage and pos.current_pnl_pct > 0.02:
                signals.append(Signal(
                    ticker=ticker,
                    action="LEVERAGE_UP",
                    current_price=price,
                    signal_strength=strength,
                    signals=sig_str,
                    reason=f"Strength {strength} -> Leverage {pos.leverage}x to {new_lev}x",
                    recommended_leverage=new_lev,
                    urgency="NORMAL"
                ))
            else:
                signals.append(Signal(
                    ticker=ticker,
                    action="HOLD",
                    current_price=price,
                    signal_strength=strength,
                    signals=sig_str,
                    reason=f"PnL: {pos.current_pnl_pct*100:+.1f}%",
                    recommended_leverage=pos.leverage,
                    urgency="NORMAL"
                ))

        # Check for new entries
        if len([s for s in signals if s.action != "SELL"]) < PARAMS['max_positions']:
            candidates = []
            for ticker in self.data:
                if ticker in self.positions:
                    continue

                can_enter, strength, sig_str = self._check_entry(ticker)
                if can_enter:
                    row = self._get_latest_data(ticker)
                    price = row['Close']
                    leverage = self._get_leverage_for_strength(strength)

                    pos_value = self.portfolio_value * PARAMS['position_size']
                    shares = pos_value / price

                    candidates.append(Signal(
                        ticker=ticker,
                        action="BUY",
                        current_price=price,
                        signal_strength=strength,
                        signals=sig_str,
                        reason=f"Strength={strength}",
                        recommended_leverage=leverage,
                        recommended_shares=shares,
                        urgency="NORMAL"
                    ))

            # Sort by strength and add top candidates
            candidates.sort(key=lambda x: -x.signal_strength)
            signals.extend(candidates)

        return signals

    def print_recommendations(self):
        """Print today's trading recommendations"""
        signals = self.generate_signals()

        print("\n" + "=" * 80)
        print(f"SMART LEVERAGE BOT - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 80)

        buys = [s for s in signals if s.action == "BUY"]
        sells = [s for s in signals if s.action == "SELL"]
        lev_ups = [s for s in signals if s.action == "LEVERAGE_UP"]
        delevs = [s for s in signals if s.action == "DELEVERAGE"]
        holds = [s for s in signals if s.action == "HOLD"]

        print(f"\n💰 PORTFOLIO: ${self.portfolio_value:,.0f} | CASH: ${self.cash:,.0f} | POSITIONS: {len(self.positions)}/{PARAMS['max_positions']}")

        # SELL SIGNALS
        if sells:
            print("\n" + "🔴 " + "-" * 76)
            print("   SELL - EXIT THESE POSITIONS")
            print("   " + "-" * 74)
            for s in sells:
                pos = self.positions.get(s.ticker)
                pnl = pos.current_pnl_pct * 100 if pos else 0
                print(f"   {s.ticker:<10} @ ${s.current_price:>10,.2f} | PnL: {pnl:+.1f}% | {s.reason}")

        # DELEVERAGE SIGNALS
        if delevs:
            print("\n" + "🟡 " + "-" * 76)
            print("   DELEVERAGE - REDUCE TO 1x")
            print("   " + "-" * 74)
            for s in delevs:
                print(f"   {s.ticker:<10} @ ${s.current_price:>10,.2f} | {s.reason}")

        # LEVERAGE UP SIGNALS
        if lev_ups:
            print("\n" + "🟢 " + "-" * 76)
            print("   LEVERAGE UP")
            print("   " + "-" * 74)
            for s in lev_ups:
                print(f"   {s.ticker:<10} @ ${s.current_price:>10,.2f} | {s.reason}")

        # BUY SIGNALS
        if buys:
            slots_available = PARAMS['max_positions'] - len(self.positions) + len(sells)
            print("\n" + "🟢 " + "-" * 76)
            print(f"   BUY - NEW POSITIONS (showing top {min(slots_available, len(buys))} of {len(buys)} candidates)")
            print("   " + "-" * 74)
            for s in buys[:slots_available]:
                pos_value = self.portfolio_value * PARAMS['position_size']
                print(f"   {s.ticker:<10} @ ${s.current_price:>10,.2f} | Str={s.signal_strength} | Lev={s.recommended_leverage}x | Size=${pos_value:,.0f}")
                print(f"              Signals: {s.signals[:60]}")

        # CURRENT HOLDINGS
        if holds:
            print("\n" + "📊 " + "-" * 76)
            print("   CURRENT HOLDINGS - HOLD")
            print("   " + "-" * 74)
            print(f"   {'Ticker':<10} {'Price':>12} {'Entry':>12} {'PnL':>10} {'Lev':>6} {'Str':>5}")
            print("   " + "-" * 60)
            for s in sorted(holds, key=lambda x: -self.positions[x.ticker].current_pnl_pct):
                pos = self.positions.get(s.ticker)
                if pos:
                    pnl = pos.current_pnl_pct * 100
                    print(f"   {s.ticker:<10} ${s.current_price:>11,.2f} ${pos.entry_price:>11,.2f} {pnl:>+9.1f}% {pos.leverage:>5.1f}x {s.signal_strength:>5}")

        # SUMMARY
        print("\n" + "=" * 80)
        print(f"ACTIONS TODAY: {len(sells)} SELL | {len(delevs)} DELEVERAGE | {len(lev_ups)} LEVERAGE UP | {len(buys)} BUY candidates")
        print("=" * 80)

    def print_all_signals(self):
        """Print signals for all assets"""
        print("\n" + "=" * 80)
        print(f"ALL ASSET SIGNALS - {datetime.now().strftime('%Y-%m-%d')}")
        print("=" * 80)

        print(f"\n  {'Ticker':<12} {'Price':>12} {'Str':>5} {'Entry?':>7} {'Signals'}")
        print("  " + "-" * 75)

        assets = []
        for ticker in sorted(self.data.keys()):
            row = self._get_latest_data(ticker)
            if row is None:
                continue

            price = row['Close']
            strength, sigs = self._get_signal_strength(ticker)
            can_enter, _, _ = self._check_entry(ticker)
            assets.append((ticker, price, strength, can_enter, sigs))

        # Sort by strength
        assets.sort(key=lambda x: -x[2])

        for ticker, price, strength, can_enter, sigs in assets:
            entry_str = "✅ YES" if can_enter else "NO"
            in_port = "📍" if ticker in self.positions else "  "
            print(f"{in_port}{ticker:<10} ${price:>11,.2f} {strength:>5} {entry_str:>7}   {sigs[:45]}")

    def execute_signal(self, signal: Signal):
        """Execute a trading signal"""
        if signal.action == "BUY":
            row = self._get_latest_data(signal.ticker)
            mom_12m = row.get('Mom_12m', 0) if row is not None else 0

            pos_value = self.portfolio_value * PARAMS['position_size']
            if self.cash >= pos_value:
                self.positions[signal.ticker] = Position(
                    ticker=signal.ticker,
                    entry_date=datetime.now().strftime('%Y-%m-%d'),
                    entry_price=signal.current_price,
                    shares=signal.recommended_shares,
                    leverage=signal.recommended_leverage,
                    highest_price=signal.current_price,
                    peak_momentum=mom_12m if not pd.isna(mom_12m) else 0,
                    current_price=signal.current_price,
                    current_pnl_pct=0,
                    signal_strength=signal.signal_strength,
                    signals=signal.signals
                )
                self.cash -= pos_value
                print(f"  ✅ BUY {signal.ticker} @ ${signal.current_price:,.2f} x {signal.recommended_shares:.4f} shares @ {signal.recommended_leverage}x")

        elif signal.action == "SELL":
            if signal.ticker in self.positions:
                pos = self.positions[signal.ticker]
                pnl = (signal.current_price - pos.entry_price) * pos.shares * pos.leverage
                self.cash += pos.shares * pos.entry_price + pnl
                del self.positions[signal.ticker]
                print(f"  ✅ SELL {signal.ticker} @ ${signal.current_price:,.2f} | PnL: ${pnl:+,.0f}")

        elif signal.action == "LEVERAGE_UP":
            if signal.ticker in self.positions:
                old_lev = self.positions[signal.ticker].leverage
                self.positions[signal.ticker].leverage = signal.recommended_leverage
                print(f"  ✅ LEVERAGE UP {signal.ticker}: {old_lev}x -> {signal.recommended_leverage}x")

        elif signal.action == "DELEVERAGE":
            if signal.ticker in self.positions:
                old_lev = self.positions[signal.ticker].leverage
                self.positions[signal.ticker].leverage = 1.0
                print(f"  ✅ DELEVERAGE {signal.ticker}: {old_lev}x -> 1.0x")

        self._update_portfolio_value()

    def _update_portfolio_value(self):
        """Recalculate portfolio value"""
        self.portfolio_value = self.cash
        for ticker, pos in self.positions.items():
            row = self._get_latest_data(ticker)
            if row is not None:
                price = row['Close']
                upnl = (price - pos.entry_price) * pos.shares * pos.leverage
                self.portfolio_value += pos.shares * pos.entry_price + upnl

    def auto_execute(self):
        """Automatically execute all signals"""
        signals = self.generate_signals()

        print("\n" + "=" * 80)
        print("EXECUTING SIGNALS")
        print("=" * 80)

        # Execute in order: SELL, DELEVERAGE, LEVERAGE_UP, BUY
        for action in ["SELL", "DELEVERAGE", "LEVERAGE_UP", "BUY"]:
            action_signals = [s for s in signals if s.action == action]
            if action == "BUY":
                max_new = PARAMS['max_positions'] - len(self.positions)
                action_signals = sorted(action_signals, key=lambda x: -x.signal_strength)[:max_new]

            for s in action_signals:
                self.execute_signal(s)

        self.save_portfolio()
        print(f"\n💰 Portfolio Value: ${self.portfolio_value:,.0f} | Cash: ${self.cash:,.0f}")


def main():
    parser = argparse.ArgumentParser(description='Smart Leverage Trading Bot')
    parser.add_argument('--signals', action='store_true', help='Show all asset signals')
    parser.add_argument('--execute', action='store_true', help='Auto-execute all signals')
    parser.add_argument('--capital', type=float, help='Set initial capital')
    args = parser.parse_args()

    bot = SmartLeverageBot()

    if args.capital:
        bot.portfolio_value = args.capital
        bot.cash = args.capital
        bot.positions = {}
        bot.save_portfolio()
        print(f"Reset portfolio to ${args.capital:,.0f}")
        return

    if args.signals:
        bot.print_all_signals()
    elif args.execute:
        bot.auto_execute()
    else:
        bot.print_recommendations()


if __name__ == '__main__':
    main()
