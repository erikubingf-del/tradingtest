#!/usr/bin/env python3
"""
ENHANCED BACKTEST: Put Options with Early Exit Strategies
==========================================================

Compares different exit strategies:
1. Hold to expiration (6 months) - current strategy
2. Take profit at 50% gain
3. Take profit at 100% gain
4. Take profit at 200% gain
5. Trailing stop (exit when stock rebounds X% from low)

With puts, we don't need stop-losses - max loss is premium paid.
But early profit-taking can lock in gains before stock recovers.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
import sys
warnings.filterwarnings('ignore')

# Stock universe from sniper_scanner_v2
SP500 = [
    'AAPL', 'ABBV', 'ABT', 'ACN', 'ADBE', 'ADI', 'ADM', 'ADP', 'ADSK', 'AEE',
    'AEP', 'AES', 'AFL', 'AIG', 'AIZ', 'AJG', 'AKAM', 'ALB', 'ALGN', 'ALL',
    'ALLE', 'AMAT', 'AMCR', 'AMD', 'AME', 'AMGN', 'AMP', 'AMT', 'AMZN', 'ANET',
    'ANSS', 'AON', 'AOS', 'APA', 'APD', 'APH', 'APTV', 'ARE', 'ATO', 'AVB',
    'AVGO', 'AVY', 'AWK', 'AXON', 'AXP', 'AZO', 'BA', 'BAC', 'BALL', 'BAX',
    'BBWI', 'BBY', 'BDX', 'BEN', 'BF-B', 'BG', 'BIIB', 'BIO', 'BK', 'BKNG',
    'BKR', 'BLDR', 'BLK', 'BMY', 'BR', 'BRK-B', 'BRO', 'BSX', 'BWA', 'BXP',
    'C', 'CAG', 'CAH', 'CARR', 'CAT', 'CB', 'CBOE', 'CBRE', 'CCI', 'CCL',
    'CDNS', 'CDW', 'CE', 'CEG', 'CF', 'CFG', 'CHD', 'CHRW', 'CHTR', 'CI',
    'CINF', 'CL', 'CLX', 'CMA', 'CMCSA', 'CME', 'CMG', 'CMI', 'CMS', 'CNC',
    'CNP', 'COF', 'COO', 'COP', 'COR', 'COST', 'CPAY', 'CPB', 'CPRT', 'CPT',
    'CRL', 'CRM', 'CSCO', 'CSGP', 'CSX', 'CTAS', 'CTLT', 'CTRA', 'CTSH', 'CTVA',
    'CVS', 'CVX', 'CZR', 'D', 'DAL', 'DD', 'DE', 'DECK', 'DFS', 'DG',
    'DGX', 'DHI', 'DHR', 'DIS', 'DLR', 'DLTR', 'DOC', 'DOV', 'DOW', 'DPZ',
    'DRI', 'DTE', 'DUK', 'DVA', 'DVN', 'DXCM', 'EA', 'EBAY', 'ECL', 'ED',
    'EFX', 'EG', 'EIX', 'EL', 'ELV', 'EMN', 'EMR', 'ENPH', 'EOG', 'EPAM',
    'EQIX', 'EQR', 'EQT', 'ES', 'ESS', 'ETN', 'ETR', 'ETSY', 'EVRG', 'EW',
    'EXC', 'EXPD', 'EXPE', 'EXR', 'F', 'FANG', 'FAST', 'FCX', 'FDS', 'FDX',
    'FE', 'FFIV', 'FI', 'FICO', 'FIS', 'FITB', 'FLT', 'FMC', 'FOX', 'FOXA',
    'FRT', 'FSLR', 'FTNT', 'FTV', 'GD', 'GDDY', 'GE', 'GEHC', 'GEN', 'GILD',
    'GIS', 'GL', 'GLW', 'GM', 'GNRC', 'GOOG', 'GOOGL', 'GPC', 'GPN', 'GRMN',
    'GS', 'GWW', 'HAL', 'HAS', 'HBAN', 'HCA', 'HD', 'HES', 'HIG', 'HII',
    'HLT', 'HOLX', 'HON', 'HPE', 'HPQ', 'HRL', 'HSIC', 'HST', 'HSY', 'HUBB',
    'HUM', 'HWM', 'IBM', 'ICE', 'IDXX', 'IEX', 'IFF', 'ILMN', 'INCY', 'INTC',
    'INTU', 'INVH', 'IP', 'IPG', 'IQV', 'IR', 'IRM', 'ISRG', 'IT', 'ITW',
    'IVZ', 'J', 'JBHT', 'JBL', 'JCI', 'JKHY', 'JNJ', 'JNPR', 'JPM', 'K',
    'KDP', 'KEY', 'KEYS', 'KHC', 'KIM', 'KLAC', 'KMB', 'KMI', 'KMX', 'KO',
    'KR', 'KVUE', 'L', 'LDOS', 'LEN', 'LH', 'LHX', 'LIN', 'LKQ', 'LLY',
    'LMT', 'LNT', 'LOW', 'LRCX', 'LULU', 'LUV', 'LVS', 'LW', 'LYB', 'LYV',
    'MA', 'MAA', 'MAR', 'MAS', 'MCD', 'MCHP', 'MCK', 'MCO', 'MDLZ', 'MDT',
    'MET', 'META', 'MGM', 'MHK', 'MKC', 'MKTX', 'MLM', 'MMC', 'MMM', 'MNST',
    'MO', 'MOH', 'MOS', 'MPC', 'MPWR', 'MRK', 'MRNA', 'MRO', 'MS', 'MSCI',
    'MSFT', 'MSI', 'MTB', 'MTCH', 'MTD', 'MU', 'NCLH', 'NDAQ', 'NDSN', 'NEE',
    'NEM', 'NFLX', 'NI', 'NKE', 'NOC', 'NOW', 'NRG', 'NSC', 'NTAP', 'NTRS',
    'NUE', 'NVDA', 'NVR', 'NWS', 'NWSA', 'NXPI', 'O', 'ODFL', 'OKE', 'OMC',
    'ON', 'ORCL', 'ORLY', 'OTIS', 'OXY', 'PANW', 'PARA', 'PAYC', 'PAYX', 'PCAR',
    'PCG', 'PEG', 'PEP', 'PFE', 'PFG', 'PG', 'PGR', 'PH', 'PHM', 'PKG',
    'PLD', 'PM', 'PNC', 'PNR', 'PNW', 'PODD', 'POOL', 'PPG', 'PPL', 'PRU',
    'PSA', 'PSX', 'PTC', 'PWR', 'PXD', 'PYPL', 'QCOM', 'QRVO', 'RCL', 'REG',
    'REGN', 'RF', 'RJF', 'RL', 'RMD', 'ROK', 'ROL', 'ROP', 'ROST', 'RSG',
    'RTX', 'RVTY', 'SBAC', 'SBUX', 'SCHW', 'SHW', 'SJM', 'SLB', 'SMCI', 'SNA',
    'SNPS', 'SO', 'SPG', 'SPGI', 'SRE', 'STE', 'STLD', 'STT', 'STX', 'STZ',
    'SWK', 'SWKS', 'SYF', 'SYK', 'SYY', 'T', 'TAP', 'TDG', 'TDY', 'TECH',
    'TEL', 'TER', 'TFC', 'TFX', 'TGT', 'TJX', 'TMO', 'TMUS', 'TPR', 'TRGP',
    'TRMB', 'TROW', 'TRV', 'TSCO', 'TSLA', 'TSN', 'TT', 'TTWO', 'TXN', 'TXT',
    'TYL', 'UAL', 'UBER', 'UDR', 'UHS', 'ULTA', 'UNH', 'UNP', 'UPS', 'URI',
    'USB', 'V', 'VFC', 'VICI', 'VLO', 'VLTO', 'VMC', 'VRSK', 'VRSN', 'VRTX',
    'VST', 'VTR', 'VTRS', 'VZ', 'WAB', 'WAT', 'WBA', 'WBD', 'WDC', 'WEC',
    'WELL', 'WFC', 'WM', 'WMB', 'WMT', 'WRB', 'WRK', 'WST', 'WTW', 'WY',
    'WYNN', 'XEL', 'XOM', 'XYL', 'YUM', 'ZBH', 'ZBRA', 'ZION', 'ZTS',
]

HIGH_VOL = [
    'GME', 'AMC', 'BB', 'BBBY', 'WISH', 'CLOV', 'SOFI', 'PLTR', 'HOOD', 'UPST', 'AFRM',
    'SKLZ', 'OPEN', 'SPCE', 'ASTS', 'IONQ', 'DNA', 'RKLB',
    'MARA', 'RIOT', 'COIN', 'MSTR', 'HUT', 'BITF', 'CLSK', 'CIFR', 'CAN', 'GREE',
    'BTBT', 'SOS', 'BTDR', 'IREN', 'WULF',
    'RIVN', 'LCID', 'FSR', 'NKLA', 'GOEV', 'WKHS', 'RIDE', 'ARVL', 'FFIE', 'MULN',
    'PLUG', 'FCEL', 'BE', 'BLDP', 'BLNK', 'CHPT', 'STEM', 'RUN', 'NOVA', 'ARRY',
    'SHLS', 'MAXN', 'SPWR', 'SUNW', 'JKS', 'CSIQ', 'DQ',
    'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'XPEV', 'LI', 'BILI', 'TME', 'IQ',
    'DIDI', 'TAL', 'EDU', 'GOTU', 'YY', 'HUYA', 'DOYU', 'VIPS', 'ZH',
    'TLRY', 'CGC', 'ACB', 'CRON', 'SNDL', 'HEXO', 'OGI', 'VFF', 'GRWG',
    'PATH', 'DOCN', 'BILL', 'U', 'RBLX', 'SNOW', 'DDOG', 'NET', 'CRWD', 'ZS',
    'OKTA', 'MDB', 'ESTC', 'CFLT', 'GTLB', 'SUMO', 'NEWR', 'DT', 'HUBS',
    'BNTX', 'NVAX', 'SGEN', 'SRPT', 'BMRN', 'ALNY', 'RARE', 'IONS',
    'EXAS', 'PACB', 'TWST', 'BEAM', 'CRSP', 'NTLA', 'EDIT', 'VERV',
    'PTON', 'W', 'CHWY', 'FUBO', 'LAZR', 'VLDR', 'SNAP', 'ROKU', 'DOCU', 'ZM',
    'ASAN', 'FVRR', 'APPS', 'DKNG', 'PENN', 'DASH', 'ABNB', 'LYFT',
    'AAL', 'DAL', 'UAL', 'LUV', 'JBLU', 'SAVE', 'CCL', 'RCL', 'NCLH',
    'SHOP', 'SQ',
]

ALL_STOCKS = list(set(SP500 + HIGH_VOL))

# ============================================================================
# PUT RETURN CALCULATION WITH DIFFERENT EXIT STRATEGIES
# ============================================================================

PREMIUM = 0.12  # 12% premium for 6-month ATM put

def calculate_put_return(stock_drop, premium=PREMIUM):
    """
    Calculate put return based on stock drop.
    stock_drop: negative = stock fell, positive = stock rose
    """
    if stock_drop < 0:  # Stock fell = put wins
        intrinsic = abs(stock_drop)
        ret = (intrinsic - premium) / premium
        return min(ret, 10.0)  # Cap at 1000%
    else:  # Stock rose = put loses
        # Time value remaining depends on how much stock rose
        if stock_drop < 0.05:
            return -0.80  # Small rise = keep some premium
        elif stock_drop < 0.15:
            return -0.95
        else:
            return -1.00  # Total loss


def find_signals_with_path(df, ticker, min_momentum=1.0, min_drop=-0.50, max_rsi=60):
    """
    Find signals AND track price path over 6 months for exit strategy testing.
    Returns signals with weekly price snapshots.
    """
    signals = []

    # Check intervals: weekly (5 trading days) for 6 months
    check_days = [5, 10, 15, 21, 42, 63, 84, 105, 126]  # ~1w, 2w, 3w, 1m, 2m, 3m, 4m, 5m, 6m

    for i in range(252, len(df) - 126):
        row = df.iloc[i]

        # Skip if missing data
        if pd.isna(row['mom_12m']) or pd.isna(row['rsi']):
            continue

        # Check entry criteria
        has_momentum = row['mom_12m'] >= min_momentum
        has_dropped = row['pct_from_high'] <= min_drop
        rsi_ok = row['rsi'] < max_rsi

        if has_momentum and has_dropped and rsi_ok:
            entry_price = row['Close']

            # Get price path over next 6 months
            price_path = {}
            for days in check_days:
                if i + days < len(df):
                    future_price = df.iloc[i + days]['Close']
                    price_path[f'day_{days}'] = (future_price / entry_price) - 1
                else:
                    price_path[f'day_{days}'] = None

            # Also track minimum price (max drop) over period
            if i + 126 < len(df):
                future_prices = df.iloc[i:i+127]['Close']
                min_price = future_prices.min()
                max_drop = (min_price / entry_price) - 1
            else:
                max_drop = None

            signals.append({
                'date': df.iloc[i]['Date'],
                'ticker': ticker,
                'price': entry_price,
                'mom_12m': row['mom_12m'],
                'pct_from_high': row['pct_from_high'],
                'rsi': row['rsi'],
                'max_drop': max_drop,  # Deepest drop during 6 months
                **price_path
            })

    return signals


def download_stock_history(ticker, start_date='1998-01-01'):
    """Download full historical data for a stock."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=datetime.now().strftime('%Y-%m-%d'))
        if len(df) < 252:
            return None
        df['ticker'] = ticker
        df = df.reset_index()
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        return df
    except:
        return None


def calculate_indicators(df):
    """Calculate all technical indicators."""
    df = df.copy()
    df['sma_50'] = df['Close'].rolling(50).mean()
    df['sma_200'] = df['Close'].rolling(200).mean()
    df['high_52w'] = df['Close'].rolling(252).max()
    df['pct_from_high'] = (df['Close'] - df['high_52w']) / df['high_52w']
    df['mom_12m'] = df['Close'].pct_change(252)
    df['mom_6m'] = df['Close'].pct_change(126)

    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    return df


def apply_exit_strategies(signals_df):
    """
    Apply different exit strategies and calculate returns for each.
    """
    results = signals_df.copy()

    # Strategy 1: Hold to expiration (6 months)
    results['ret_hold'] = results['day_126'].apply(
        lambda x: calculate_put_return(x) if pd.notna(x) else np.nan
    )

    # Strategy 2: Take profit at 50% gain (stock drops ~18% = 6%/12% premium = 50% gain)
    # Stock drop needed: 0.12 + 0.12*0.50 = 0.18 (18%)
    def exit_50pct(row):
        target_drop = -0.18  # Stock needs to drop 18% for 50% profit
        for days in [5, 10, 15, 21, 42, 63, 84, 105, 126]:
            col = f'day_{days}'
            if pd.notna(row[col]) and row[col] <= target_drop:
                return 0.50  # 50% profit
        # If never hit target, use expiration
        if pd.notna(row['day_126']):
            return calculate_put_return(row['day_126'])
        return np.nan

    results['ret_exit_50'] = results.apply(exit_50pct, axis=1)

    # Strategy 3: Take profit at 100% gain (stock drops ~24%)
    def exit_100pct(row):
        target_drop = -0.24  # Stock needs to drop 24% for 100% profit
        for days in [5, 10, 15, 21, 42, 63, 84, 105, 126]:
            col = f'day_{days}'
            if pd.notna(row[col]) and row[col] <= target_drop:
                return 1.00  # 100% profit
        if pd.notna(row['day_126']):
            return calculate_put_return(row['day_126'])
        return np.nan

    results['ret_exit_100'] = results.apply(exit_100pct, axis=1)

    # Strategy 4: Take profit at 200% gain (stock drops ~36%)
    def exit_200pct(row):
        target_drop = -0.36  # Stock needs to drop 36% for 200% profit
        for days in [5, 10, 15, 21, 42, 63, 84, 105, 126]:
            col = f'day_{days}'
            if pd.notna(row[col]) and row[col] <= target_drop:
                return 2.00  # 200% profit
        if pd.notna(row['day_126']):
            return calculate_put_return(row['day_126'])
        return np.nan

    results['ret_exit_200'] = results.apply(exit_200pct, axis=1)

    # Strategy 5: Exit at max drop (perfect timing - theoretical max)
    results['ret_max'] = results['max_drop'].apply(
        lambda x: calculate_put_return(x) if pd.notna(x) else np.nan
    )

    return results


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("="*100)
    print("ENHANCED BACKTEST: Put Options with Exit Strategies")
    print("="*100)
    print(f"\nStock universe: {len(ALL_STOCKS)} stocks")
    print("Testing exit strategies:")
    print("  1. Hold to expiration (6 months)")
    print("  2. Take profit at 50% gain (18% stock drop)")
    print("  3. Take profit at 100% gain (24% stock drop)")
    print("  4. Take profit at 200% gain (36% stock drop)")
    print("  5. Perfect timing (max drop - theoretical)")
    print("\nDownloading data (this may take 15-30 minutes)...\n")

    all_signals = []
    successful = 0
    start_time = time.time()

    for i, ticker in enumerate(ALL_STOCKS):
        pct = (i + 1) / len(ALL_STOCKS) * 100
        elapsed = time.time() - start_time
        eta = (elapsed / (i + 1)) * (len(ALL_STOCKS) - i - 1) if i > 0 else 0

        print(f"\r  [{pct:5.1f}%] {ticker:<6} | {successful} stocks done | ETA: {eta/60:.1f} min   ", end='', flush=True)

        df = download_stock_history(ticker)
        if df is None:
            continue

        df = calculate_indicators(df)
        signals = find_signals_with_path(df, ticker)

        if signals:
            all_signals.extend(signals)
            successful += 1

        time.sleep(0.05)

    print(f"\r  [100.0%] Complete! {successful} stocks with signals.                    ")

    if not all_signals:
        print("\nNo signals found!")
        sys.exit(1)

    # Convert to DataFrame
    signals_df = pd.DataFrame(all_signals)
    signals_df['year'] = signals_df['date'].dt.year
    signals_df['quarter'] = signals_df['date'].dt.to_period('Q')

    # Dedupe: 1 trade per stock per quarter
    signals_df = signals_df.sort_values('date')
    signals_df = signals_df.drop_duplicates(subset=['ticker', 'quarter'])
    signals_df = signals_df[signals_df['year'] >= 1998]

    # Apply exit strategies
    print("\nApplying exit strategies...")
    signals_df = apply_exit_strategies(signals_df)

    # ========================================================================
    # COMPARE STRATEGIES
    # ========================================================================

    print("\n" + "="*100)
    print("EXIT STRATEGY COMPARISON")
    print("="*100)

    strategies = {
        'Hold to Expiration': 'ret_hold',
        'Exit at 50% Profit': 'ret_exit_50',
        'Exit at 100% Profit': 'ret_exit_100',
        'Exit at 200% Profit': 'ret_exit_200',
        'Perfect Timing (Max)': 'ret_max',
    }

    print(f"\n{'Strategy':<25} {'Trades':<8} {'Win%':<8} {'Avg Ret':<10} {'Total P&L':<15} {'ROI':<10}")
    print("-"*85)

    comparison = []
    for name, col in strategies.items():
        valid = signals_df[col].dropna()
        trades = len(valid)
        if trades == 0:
            continue
        wins = (valid > 0).sum()
        win_pct = wins / trades * 100
        avg_ret = valid.mean() * 100
        total_pnl = valid.sum() * 1000
        roi = avg_ret

        comparison.append({
            'strategy': name,
            'trades': trades,
            'wins': wins,
            'win_pct': win_pct,
            'avg_ret': avg_ret,
            'total_pnl': total_pnl,
            'roi': roi
        })

        print(f"{name:<25} {trades:<8} {win_pct:>5.0f}% {avg_ret:>+8.0f}% ${total_pnl:>+12,.0f} {roi:>+7.0f}%")

    # Year by year for best strategy
    print("\n" + "="*100)
    print("YEAR-BY-YEAR: Hold to Expiration vs Exit at 100%")
    print("="*100)

    print(f"\n{'Year':<6} {'Trades':<8} {'Hold P&L':<12} {'Exit@100 P&L':<14} {'Difference':<12} {'Better':<10}")
    print("-"*75)

    total_hold = 0
    total_exit = 0

    for year in sorted(signals_df['year'].unique()):
        y = signals_df[signals_df['year'] == year]

        hold_valid = y['ret_hold'].dropna()
        exit_valid = y['ret_exit_100'].dropna()

        if len(hold_valid) == 0:
            continue

        hold_pnl = hold_valid.sum() * 1000
        exit_pnl = exit_valid.sum() * 1000
        diff = exit_pnl - hold_pnl
        better = "Exit@100" if diff > 0 else "Hold"

        total_hold += hold_pnl
        total_exit += exit_pnl

        print(f"{year:<6} {len(hold_valid):<8} ${hold_pnl:>+10,.0f} ${exit_pnl:>+12,.0f} ${diff:>+10,.0f} {better:<10}")

    print("-"*75)
    diff = total_exit - total_hold
    better = "Exit@100" if diff > 0 else "Hold"
    print(f"{'TOTAL':<6} {'':<8} ${total_hold:>+10,.0f} ${total_exit:>+12,.0f} ${diff:>+10,.0f} {better:<10}")

    # Save results
    signals_df.to_csv('backtest_exits_signals.csv', index=False)
    pd.DataFrame(comparison).to_csv('backtest_exits_comparison.csv', index=False)

    print(f"\n\nResults saved to:")
    print("  - backtest_exits_signals.csv (all signals with returns)")
    print("  - backtest_exits_comparison.csv (strategy comparison)")

    # Summary
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)

    best = max(comparison, key=lambda x: x['total_pnl'])
    hold = next(c for c in comparison if c['strategy'] == 'Hold to Expiration')

    print(f"""
BEST STRATEGY: {best['strategy']}
  Total P&L: ${best['total_pnl']:+,.0f}
  Win Rate: {best['win_pct']:.0f}%
  Avg Return: {best['avg_ret']:+.0f}%

vs HOLD TO EXPIRATION:
  Total P&L: ${hold['total_pnl']:+,.0f}
  Improvement: ${best['total_pnl'] - hold['total_pnl']:+,.0f} ({(best['total_pnl'] / hold['total_pnl'] - 1) * 100:+.0f}%)

NOTE: "Perfect Timing" is theoretical (impossible to achieve in practice).
      The best practical strategy is Exit at 100% or 200% depending on results.
""")
