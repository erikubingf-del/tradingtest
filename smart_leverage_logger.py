"""
SMART LEVERAGE - Detailed Trade Log Generator
Outputs every buy, sell, leverage change, and indicator signal
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, field


PARAMS = {
    'mom_12m_min': 0.10,
    'mom_6m_min': 0.05,
    'mom_3m_min': 0.02,
    'mom_1m_min': 0.01,
    'leverage_weak': 1.0,
    'leverage_moderate': 1.5,
    'leverage_strong': 2.0,
    'leverage_very_strong': 3.0,
    'deleverage_pullback': 0.02,
    'deleverage_mom_decay': 0.40,
    'stop_loss': -0.04,
    'trailing_atr_base': 2.0,
    'trailing_atr_leveraged': 1.5,
    'position_size': 0.05,
    'max_positions': 12,
}


@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    leverage: float = 1.0
    highest_price: float = 0.0
    peak_momentum: float = 0.0
    entry_signals: str = ""


@dataclass
class LogEntry:
    date: str
    action: str
    ticker: str
    price: float
    shares: float
    leverage: float
    pnl_pct: float
    reason: str
    signals: str
    portfolio_value: float
    cash: float
    num_positions: int


class SmartLeverageLogger:
    def __init__(self, data_dir: str = 'historical_data', initial_capital: float = 100000):
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.log_entries: List[LogEntry] = []
        self.equity_curve = []
        self.peak_equity = initial_capital

        print("Loading data...")
        self.data = self._load_all_data()
        self.all_dates = self._get_all_trading_dates()

    def _load_all_data(self) -> Dict[str, pd.DataFrame]:
        data = {}
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
                        data[ticker] = df
                except:
                    pass
        print(f"  Loaded {len(data)} assets")
        return data

    def _get_all_trading_dates(self):
        all_dates = set()
        for df in self.data.values():
            all_dates.update(df.index.tolist())
        return pd.DatetimeIndex(sorted(all_dates))

    def _calculate_indicators(self, df):
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

    def _get_signals(self, ticker: str, date: datetime) -> Tuple[int, str]:
        """Get signal count and description"""
        if ticker not in self.data or date not in self.data[ticker].index:
            return 0, ""

        row = self.data[ticker].loc[date]
        signals = []
        score = 0

        mom_12m = row.get('Mom_12m', 0)
        mom_6m = row.get('Mom_6m', 0)
        mom_3m = row.get('Mom_3m', 0)
        mom_1m = row.get('Mom_1m', 0)
        sma50 = row.get('SMA50', 0)
        sma200 = row.get('SMA200', 0)
        donchian = row.get('Donchian_High', 0)

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
            if row['Close'] > sma50:
                signals.append("AboveSMA50")

        if not pd.isna(donchian) and row['Close'] >= donchian:
            signals.append("Breakout")

        return score, " | ".join(signals)

    def _check_entry(self, ticker: str, date: datetime) -> Tuple[bool, int, str]:
        score, signals = self._get_signals(ticker, date)

        if score < 3:
            return False, 0, ""

        if ticker not in self.data or date not in self.data[ticker].index:
            return False, 0, ""

        row = self.data[ticker].loc[date]
        sma50 = row.get('SMA50')
        sma200 = row.get('SMA200')

        if pd.isna(sma50) or pd.isna(sma200):
            return False, 0, ""
        if row['Close'] <= sma50 or sma50 <= sma200:
            return False, 0, ""

        return True, score, signals

    def _get_leverage_for_strength(self, strength: int) -> float:
        if strength <= 2:
            return PARAMS['leverage_weak']
        elif strength == 3:
            return PARAMS['leverage_moderate']
        elif strength == 4:
            return PARAMS['leverage_strong']
        else:
            return PARAMS['leverage_very_strong']

    def _log(self, date, action, ticker, price, shares, leverage, pnl_pct, reason, signals, portfolio_value):
        self.log_entries.append(LogEntry(
            date=date.strftime('%Y-%m-%d'),
            action=action,
            ticker=ticker,
            price=round(price, 4),
            shares=round(shares, 4),
            leverage=leverage,
            pnl_pct=round(pnl_pct * 100, 2),
            reason=reason,
            signals=signals,
            portfolio_value=round(portfolio_value, 2),
            cash=round(self.capital, 2),
            num_positions=len(self.positions)
        ))

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nGenerating detailed log: {start_date} to {end_date}")
        print("=" * 70)

        for ticker in self.data:
            self.data[ticker] = self._calculate_indicators(self.data[ticker])

        start_dt, end_dt = pd.Timestamp(start_date), pd.Timestamp(end_date)
        trading_dates = [d for d in self.all_dates if start_dt <= d <= end_dt]

        self.capital = self.initial_capital
        self.positions = {}
        self.log_entries = []
        self.equity_curve = []
        self.peak_equity = self.initial_capital

        for i, date in enumerate(trading_dates):
            if i < 252:
                continue

            # Calculate portfolio value first
            portfolio_value = self.capital
            for ticker, pos in self.positions.items():
                if ticker in self.data and date in self.data[ticker].index:
                    price = self.data[ticker].loc[date, 'Close']
                    upnl = (price - pos.entry_price) * pos.shares * pos.leverage
                    portfolio_value += pos.shares * pos.entry_price + upnl

            # Process existing positions
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                row = self.data[ticker].loc[date]
                price = row['Close']
                old_leverage = pos.leverage

                # Update tracking
                if price > pos.highest_price:
                    pos.highest_price = price

                mom_12m = row.get('Mom_12m', 0)
                if not pd.isna(mom_12m) and mom_12m > pos.peak_momentum:
                    pos.peak_momentum = mom_12m

                pnl_pct = (price - pos.entry_price) / pos.entry_price
                score, signals = self._get_signals(ticker, date)

                # Check deleverage
                should_delev = False
                delev_reason = ""

                if pos.highest_price > 0:
                    pullback = (pos.highest_price - price) / pos.highest_price
                    if pullback > PARAMS['deleverage_pullback']:
                        should_delev = True
                        delev_reason = f"Pullback={pullback*100:.1f}%"

                if not pd.isna(mom_12m) and pos.peak_momentum > 0:
                    decay = 1 - (mom_12m / pos.peak_momentum) if pos.peak_momentum > 0 else 0
                    if decay > PARAMS['deleverage_mom_decay']:
                        should_delev = True
                        delev_reason = f"MomDecay={decay*100:.1f}%"

                if should_delev and pos.leverage > 1.0:
                    pos.leverage = 1.0
                    self._log(date, "DELEVERAGE", ticker, price, pos.shares, pos.leverage,
                             pnl_pct, delev_reason, signals, portfolio_value)

                # Check exit
                should_exit = False
                exit_reason = ""

                # Stop loss
                if pnl_pct * pos.leverage <= PARAMS['stop_loss']:
                    should_exit = True
                    exit_reason = f"StopLoss (PnL={pnl_pct*100:.1f}%)"

                # Trailing stop
                atr = row.get('ATR')
                if not pd.isna(atr) and pos.highest_price > 0 and not should_exit:
                    mult = PARAMS['trailing_atr_leveraged'] if pos.leverage > 1 else PARAMS['trailing_atr_base']
                    trail_stop = pos.highest_price - mult * atr
                    if price < trail_stop:
                        should_exit = True
                        exit_reason = f"TrailingStop (High={pos.highest_price:.2f}, Stop={trail_stop:.2f})"

                if should_exit:
                    pnl = (price - pos.entry_price) * pos.shares * pos.leverage
                    self._log(date, "SELL", ticker, price, pos.shares, pos.leverage,
                             pnl_pct, exit_reason, signals, portfolio_value)
                    self.capital += pos.shares * pos.entry_price + pnl
                    del self.positions[ticker]
                    continue

                # Check leverage increase
                new_lev = self._get_leverage_for_strength(score)
                if new_lev > pos.leverage and pnl_pct > 0.02:  # Only increase if profitable
                    old_lev = pos.leverage
                    pos.leverage = new_lev
                    self._log(date, "LEVERAGE_UP", ticker, price, pos.shares, pos.leverage,
                             pnl_pct, f"Strength={score} ({old_lev}x->{new_lev}x)", signals, portfolio_value)

            # New entries
            if len(self.positions) < PARAMS['max_positions']:
                for ticker in self.data:
                    if ticker in self.positions:
                        continue

                    can_enter, strength, signals = self._check_entry(ticker, date)
                    if can_enter and date in self.data[ticker].index:
                        row = self.data[ticker].loc[date]
                        price = row['Close']

                        pos_value = portfolio_value * PARAMS['position_size']
                        if self.capital < pos_value:
                            continue

                        shares = pos_value / price
                        leverage = self._get_leverage_for_strength(strength)

                        mom_12m = row.get('Mom_12m', 0)
                        if pd.isna(mom_12m):
                            mom_12m = 0

                        pos = Position(
                            ticker=ticker,
                            entry_date=date,
                            entry_price=price,
                            shares=shares,
                            leverage=leverage,
                            highest_price=price,
                            peak_momentum=mom_12m,
                            entry_signals=signals
                        )
                        self.positions[ticker] = pos
                        self.capital -= pos_value

                        self._log(date, "BUY", ticker, price, shares, leverage,
                                 0, f"Strength={strength}", signals, portfolio_value)

                        if len(self.positions) >= PARAMS['max_positions']:
                            break

            # Recalc portfolio value
            portfolio_value = self.capital
            for ticker, pos in self.positions.items():
                if ticker in self.data and date in self.data[ticker].index:
                    price = self.data[ticker].loc[date, 'Close']
                    upnl = (price - pos.entry_price) * pos.shares * pos.leverage
                    portfolio_value += pos.shares * pos.entry_price + upnl

            if portfolio_value > self.peak_equity:
                self.peak_equity = portfolio_value

            self.equity_curve.append((date, portfolio_value))

            if i % 2000 == 0:
                years = (date - trading_dates[252]).days / 365.25
                if years > 0:
                    cagr = (portfolio_value / self.initial_capital) ** (1/years) - 1
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio_value:,.0f} | CAGR: {cagr*100:.1f}%")

        return self._save_logs()

    def _save_logs(self):
        # Save detailed log
        log_df = pd.DataFrame([{
            'Date': e.date,
            'Action': e.action,
            'Ticker': e.ticker,
            'Price': e.price,
            'Shares': e.shares,
            'Leverage': e.leverage,
            'PnL%': e.pnl_pct,
            'Reason': e.reason,
            'Signals': e.signals,
            'Portfolio': e.portfolio_value,
            'Cash': e.cash,
            'NumPositions': e.num_positions
        } for e in self.log_entries])

        log_df.to_csv('smart_leverage_detailed_log.csv', index=False)
        print(f"\nSaved {len(log_df)} log entries to smart_leverage_detailed_log.csv")

        # Summary stats
        buys = len([e for e in self.log_entries if e.action == 'BUY'])
        sells = len([e for e in self.log_entries if e.action == 'SELL'])
        lev_ups = len([e for e in self.log_entries if e.action == 'LEVERAGE_UP'])
        delevs = len([e for e in self.log_entries if e.action == 'DELEVERAGE'])

        print(f"\nSummary:")
        print(f"  Total BUY entries: {buys}")
        print(f"  Total SELL exits: {sells}")
        print(f"  Leverage increases: {lev_ups}")
        print(f"  Deleverages: {delevs}")

        return log_df


def main():
    print("\n" + "=" * 70)
    print("SMART LEVERAGE - DETAILED TRADE LOG")
    print("=" * 70)

    bt = SmartLeverageLogger('historical_data', 100000)
    log_df = bt.run_backtest()

    # Show first 50 entries
    print("\n" + "=" * 70)
    print("FIRST 50 LOG ENTRIES:")
    print("=" * 70)
    print(log_df.head(50).to_string())

    # Show last 50 entries
    print("\n" + "=" * 70)
    print("LAST 50 LOG ENTRIES:")
    print("=" * 70)
    print(log_df.tail(50).to_string())

    return log_df


if __name__ == '__main__':
    main()
