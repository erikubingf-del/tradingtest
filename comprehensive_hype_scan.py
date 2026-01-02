#!/usr/bin/env python3
"""
COMPREHENSIVE HYPE STOCK SCANNER - 30+ Years of Data

Scans 300+ stocks across all major bubbles:
- Dot-com bubble (1999-2000)
- Housing/Financial bubble (2007-2008)
- Various sector bubbles (biotech, cannabis, crypto, EV, AI)
- COVID bubble (2020-2021)

Identifies all instances of: HIGH MOMENTUM + BREAKDOWN signals

REQUIREMENTS:
    pip install yfinance pandas numpy tqdm

USAGE:
    python comprehensive_hype_scan.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

try:
    import yfinance as yf
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    import yfinance as yf
    HAS_TQDM = False
    print("Install tqdm for progress bar: pip install tqdm")

# ============================================================================
# COMPREHENSIVE STOCK UNIVERSE - ALL BUBBLES
# ============================================================================

# Dot-com era survivors and crashers (1999-2000)
DOTCOM_STOCKS = [
    'CSCO', 'INTC', 'MSFT', 'ORCL', 'DELL', 'QCOM', 'JNPR', 'AMAT',
    'YHOO', 'EBAY', 'AMZN', 'BIDU', 'NFLX', 'PCLN',
    'EMC', 'SUNW', 'PALM', 'CMGI', 'JDSU', 'GLW',
]

# Financial crisis era (2007-2008)
FINANCIAL_STOCKS = [
    'BAC', 'C', 'JPM', 'WFC', 'GS', 'MS', 'AIG', 'LEH',
    'MER', 'BSC', 'WM', 'CFC', 'FNM', 'FRE',
    'XLF', 'KBE', 'KRE',
]

# Housing/Construction bubble
HOUSING_STOCKS = [
    'DHI', 'LEN', 'PHM', 'TOL', 'KBH', 'NVR', 'MDC', 'MTH',
    'HD', 'LOW', 'SHW', 'MAS',
]

# Biotech bubbles (multiple periods)
BIOTECH_STOCKS = [
    'GILD', 'BIIB', 'AMGN', 'CELG', 'REGN', 'VRTX', 'ALXN', 'ILMN',
    'MRNA', 'BNTX', 'NVAX', 'INO', 'SRNE', 'CODX',
    'IBB', 'XBI', 'LABU',
]

# Cannabis bubble (2018-2019)
CANNABIS_STOCKS = [
    'CGC', 'TLRY', 'ACB', 'CRON', 'APHA', 'HEXO', 'OGI', 'VFF',
    'MJ', 'YOLO', 'THCX',
]

# Crypto/Blockchain (2017-2018, 2020-2021)
CRYPTO_STOCKS = [
    'COIN', 'RIOT', 'MARA', 'HUT', 'BITF', 'HIVE', 'CLSK',
    'SQ', 'PYPL', 'SI', 'MSTR',
]

# EV bubble (2020-2021)
EV_STOCKS = [
    'TSLA', 'NIO', 'XPEV', 'LI', 'RIVN', 'LCID', 'FSR', 'NKLA',
    'QS', 'CHPT', 'BLNK', 'PLUG', 'FCEL', 'BE',
    'GOEV', 'WKHS', 'RIDE', 'HYLN',
]

# COVID/Stay-at-home bubble (2020-2021)
COVID_STOCKS = [
    'ZM', 'PTON', 'DOCU', 'TDOC', 'CHWY', 'W', 'ETSY', 'SHOP',
    'ROKU', 'SNAP', 'PINS', 'TWTR', 'SPOT',
    'DDOG', 'NET', 'CRWD', 'ZS', 'OKTA', 'SNOW', 'PLTR', 'U',
]

# Fintech bubble (2020-2021)
FINTECH_STOCKS = [
    'AFRM', 'HOOD', 'UPST', 'SOFI', 'LMND', 'ROOT', 'OPEN',
    'LC', 'TREE', 'LPRO',
]

# Meme stocks
MEME_STOCKS = [
    'GME', 'AMC', 'BB', 'BBBY', 'NOK', 'EXPR', 'KOSS',
    'SPCE', 'WISH', 'CLOV', 'SKLZ',
]

# SPAC/De-SPAC disasters
SPAC_STOCKS = [
    'NKLA', 'QS', 'RIDE', 'HYLN', 'GOEV', 'FSR', 'LAZR', 'VLDR',
    'MVST', 'PTRA', 'ARVL', 'GGPI', 'PSNY',
]

# AI/Tech bubble (2023-2024)
AI_STOCKS = [
    'NVDA', 'AMD', 'SMCI', 'ARM', 'PLTR', 'AI', 'SNOW', 'MDB',
    'PATH', 'DDOG', 'CRWD', 'NET',
]

# Commodity/Mining bubbles
COMMODITY_STOCKS = [
    'FCX', 'NEM', 'GOLD', 'AEM', 'KGC', 'AG',
    'CLF', 'X', 'NUE', 'STLD',
    'XOM', 'CVX', 'OXY', 'DVN', 'EOG', 'PXD', 'FANG',
]

# Solar/Clean energy bubble
SOLAR_STOCKS = [
    'ENPH', 'SEDG', 'RUN', 'SPWR', 'FSLR', 'JKS', 'CSIQ',
    'TAN', 'ICLN', 'QCLN',
]

# 3D Printing bubble (2013-2014)
PRINT3D_STOCKS = [
    'DDD', 'SSYS', 'XONE', 'VJET',
]

# Social media stocks
SOCIAL_STOCKS = [
    'META', 'SNAP', 'PINS', 'TWTR', 'MTCH', 'BMBL',
]

# Large cap tech for comparison (quality stocks)
QUALITY_STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'AMD', 'TSM',
    'AVGO', 'ADBE', 'CRM', 'ORCL', 'IBM', 'CSCO', 'INTC',
    'JPM', 'V', 'MA', 'BAC', 'WFC',
    'JNJ', 'PFE', 'UNH', 'MRK', 'ABT',
    'PG', 'KO', 'PEP', 'WMT', 'COST', 'HD',
]

# Combine all stocks
ALL_STOCKS = list(set(
    DOTCOM_STOCKS + FINANCIAL_STOCKS + HOUSING_STOCKS + BIOTECH_STOCKS +
    CANNABIS_STOCKS + CRYPTO_STOCKS + EV_STOCKS + COVID_STOCKS +
    FINTECH_STOCKS + MEME_STOCKS + SPAC_STOCKS + AI_STOCKS +
    COMMODITY_STOCKS + SOLAR_STOCKS + PRINT3D_STOCKS + SOCIAL_STOCKS +
    QUALITY_STOCKS
))

print(f"Total stocks to scan: {len(ALL_STOCKS)}")

# Stock categories for analysis
STOCK_CATEGORIES = {}
for stock in DOTCOM_STOCKS: STOCK_CATEGORIES[stock] = 'dotcom'
for stock in FINANCIAL_STOCKS: STOCK_CATEGORIES[stock] = 'financial'
for stock in HOUSING_STOCKS: STOCK_CATEGORIES[stock] = 'housing'
for stock in BIOTECH_STOCKS: STOCK_CATEGORIES[stock] = 'biotech'
for stock in CANNABIS_STOCKS: STOCK_CATEGORIES[stock] = 'cannabis'
for stock in CRYPTO_STOCKS: STOCK_CATEGORIES[stock] = 'crypto'
for stock in EV_STOCKS: STOCK_CATEGORIES[stock] = 'ev'
for stock in COVID_STOCKS: STOCK_CATEGORIES[stock] = 'covid'
for stock in FINTECH_STOCKS: STOCK_CATEGORIES[stock] = 'fintech'
for stock in MEME_STOCKS: STOCK_CATEGORIES[stock] = 'meme'
for stock in SPAC_STOCKS: STOCK_CATEGORIES[stock] = 'spac'
for stock in AI_STOCKS: STOCK_CATEGORIES[stock] = 'ai'
for stock in COMMODITY_STOCKS: STOCK_CATEGORIES[stock] = 'commodity'
for stock in SOLAR_STOCKS: STOCK_CATEGORIES[stock] = 'solar'
for stock in PRINT3D_STOCKS: STOCK_CATEGORIES[stock] = '3dprint'
for stock in SOCIAL_STOCKS: STOCK_CATEGORIES[stock] = 'social'
for stock in QUALITY_STOCKS: STOCK_CATEGORIES[stock] = 'quality'

# ============================================================================
# DATA FETCHING
# ============================================================================

def fetch_stock_data(ticker, period='max'):
    """Fetch maximum available history for a stock"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)

        if df is None or len(df) < 300:
            return None

        df.columns = [c.lower() for c in df.columns]
        df = df.dropna(subset=['close'])

        return df
    except Exception as e:
        return None


def calculate_indicators(df):
    """Calculate momentum and technical indicators"""
    close = df['close']

    # Momentum
    df['mom_12m'] = close.pct_change(252)
    df['mom_6m'] = close.pct_change(126)
    df['mom_3m'] = close.pct_change(63)
    df['mom_1m'] = close.pct_change(21)

    # Moving averages
    df['sma_20'] = close.rolling(20).mean()
    df['sma_50'] = close.rolling(50).mean()
    df['sma_200'] = close.rolling(200).mean()

    # Position relative to MAs
    df['above_20sma'] = close > df['sma_20']
    df['above_50sma'] = close > df['sma_50']
    df['above_200sma'] = close > df['sma_200']
    df['pct_above_200sma'] = (close / df['sma_200'] - 1)

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Forward returns
    df['fwd_1m'] = close.shift(-21) / close - 1
    df['fwd_3m'] = close.shift(-63) / close - 1
    df['fwd_6m'] = close.shift(-126) / close - 1
    df['fwd_12m'] = close.shift(-252) / close - 1

    # Max drawdown forward
    for period, name in [(63, 'max_dd_3m'), (126, 'max_dd_6m'), (252, 'max_dd_12m')]:
        dd_list = []
        for i in range(len(close)):
            if i + period >= len(close):
                dd_list.append(np.nan)
            else:
                future = close.iloc[i:i+period+1]
                dd_list.append((future.min() - close.iloc[i]) / close.iloc[i])
        df[name] = dd_list

    return df


def find_breakdown_signals(df, ticker):
    """Find all breakdown signals in the data"""
    signals = []

    for i, (date, row) in enumerate(df.iterrows()):
        # Skip if not enough data
        if pd.isna(row['mom_12m']) or pd.isna(row['above_50sma']):
            continue

        # Check for breakdown signal
        # HIGH MOMENTUM + BELOW 50 SMA
        if row['mom_12m'] >= 1.0 and row['above_50sma'] == False:
            signal = {
                'date': date,
                'ticker': ticker,
                'category': STOCK_CATEGORIES.get(ticker, 'other'),
                'price': row['close'],
                'mom_12m': row['mom_12m'],
                'mom_6m': row['mom_6m'],
                'mom_3m': row['mom_3m'],
                'rsi': row['rsi'],
                'above_50sma': row['above_50sma'],
                'above_200sma': row['above_200sma'],
                'pct_above_200sma': row['pct_above_200sma'],
                'fwd_1m': row['fwd_1m'],
                'fwd_3m': row['fwd_3m'],
                'fwd_6m': row['fwd_6m'],
                'fwd_12m': row['fwd_12m'],
                'max_dd_3m': row['max_dd_3m'],
                'max_dd_6m': row['max_dd_6m'],
                'max_dd_12m': row['max_dd_12m'],
            }
            signals.append(signal)

    return signals


# ============================================================================
# MAIN SCAN
# ============================================================================

def main():
    print("="*100)
    print("COMPREHENSIVE HYPE STOCK SCANNER - 30+ YEARS")
    print("="*100)

    all_signals = []
    successful = 0
    failed = 0

    print(f"\nScanning {len(ALL_STOCKS)} stocks...")

    iterator = tqdm(ALL_STOCKS) if HAS_TQDM else ALL_STOCKS

    for ticker in iterator:
        if not HAS_TQDM:
            print(f"  {ticker}...", end=" ", flush=True)

        df = fetch_stock_data(ticker)

        if df is None:
            failed += 1
            if not HAS_TQDM:
                print("FAILED")
            continue

        # Calculate indicators
        df = calculate_indicators(df)

        # Find signals
        signals = find_breakdown_signals(df, ticker)
        all_signals.extend(signals)

        successful += 1
        if not HAS_TQDM:
            years = (df.index.max() - df.index.min()).days / 365
            print(f"OK ({years:.1f} years, {len(signals)} signals)")

        time.sleep(0.1)  # Rate limiting

    print(f"\nSuccessfully scanned: {successful}/{len(ALL_STOCKS)}")
    print(f"Failed: {failed}/{len(ALL_STOCKS)}")
    print(f"Total signals found: {len(all_signals)}")

    if not all_signals:
        print("\nNo signals found!")
        return

    # Create DataFrame
    signals_df = pd.DataFrame(all_signals)
    signals_df['date'] = pd.to_datetime(signals_df['date'])
    signals_df = signals_df.sort_values('date')

    # ============================================================================
    # ANALYSIS
    # ============================================================================

    print("\n" + "="*100)
    print("SIGNAL ANALYSIS")
    print("="*100)

    print(f"\nDate range: {signals_df['date'].min().strftime('%Y-%m-%d')} to {signals_df['date'].max().strftime('%Y-%m-%d')}")
    print(f"Unique stocks: {signals_df['ticker'].nunique()}")
    print(f"Total signals: {len(signals_df)}")

    # Analyze by filter
    print("\n" + "-"*100)
    print("WIN RATE BY FILTER")
    print("-"*100)

    # All signals (100%+ mom, below 50 SMA)
    all_valid = signals_df.dropna(subset=['fwd_12m'])
    print(f"\nAll signals (100%+ mom, below 50 SMA): {len(all_valid)}")
    print(f"  Win rate (stock declined): {(all_valid['fwd_12m'] < 0).mean()*100:.1f}%")
    print(f"  Avg 12M return: {all_valid['fwd_12m'].mean()*100:+.1f}%")

    # Below 200 SMA filter
    below_200 = all_valid[all_valid['above_200sma'] == False]
    print(f"\nBelow 200 SMA filter: {len(below_200)}")
    print(f"  Win rate (stock declined): {(below_200['fwd_12m'] < 0).mean()*100:.1f}%")
    print(f"  Avg 12M return: {below_200['fwd_12m'].mean()*100:+.1f}%")
    print(f"  Avg SHORT return: {-below_200['fwd_12m'].mean()*100:+.1f}%")

    # By category
    print("\n" + "-"*100)
    print("WIN RATE BY CATEGORY (Below 200 SMA filter)")
    print("-"*100)

    print(f"\n{'Category':<15} {'Signals':<10} {'Win Rate':<12} {'Avg Short Ret':<15}")
    print("-"*55)

    for cat in sorted(below_200['category'].unique()):
        cat_signals = below_200[below_200['category'] == cat]
        if len(cat_signals) < 5:
            continue
        win_rate = (cat_signals['fwd_12m'] < 0).mean() * 100
        avg_ret = -cat_signals['fwd_12m'].mean() * 100
        print(f"{cat:<15} {len(cat_signals):<10} {win_rate:>8.1f}% {avg_ret:>+12.1f}%")

    # By momentum bucket
    print("\n" + "-"*100)
    print("WIN RATE BY MOMENTUM BUCKET (Below 200 SMA)")
    print("-"*100)

    print(f"\n{'Momentum':<15} {'Signals':<10} {'Win Rate':<12} {'Avg Short Ret':<15}")
    print("-"*55)

    for low, high in [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 100.0)]:
        subset = below_200[(below_200['mom_12m'] >= low) & (below_200['mom_12m'] < high)]
        if len(subset) < 5:
            continue
        win_rate = (subset['fwd_12m'] < 0).mean() * 100
        avg_ret = -subset['fwd_12m'].mean() * 100
        print(f"{low*100:.0f}-{high*100:.0f}%{'':<8} {len(subset):<10} {win_rate:>8.1f}% {avg_ret:>+12.1f}%")

    # By decade
    print("\n" + "-"*100)
    print("WIN RATE BY DECADE (Below 200 SMA)")
    print("-"*100)

    below_200['decade'] = (below_200['date'].dt.year // 10) * 10

    print(f"\n{'Decade':<12} {'Signals':<10} {'Win Rate':<12} {'Avg Short Ret':<15}")
    print("-"*50)

    for decade in sorted(below_200['decade'].unique()):
        dec_signals = below_200[below_200['decade'] == decade]
        if len(dec_signals) < 3:
            continue
        win_rate = (dec_signals['fwd_12m'] < 0).mean() * 100
        avg_ret = -dec_signals['fwd_12m'].mean() * 100
        print(f"{int(decade)}s{'':<8} {len(dec_signals):<10} {win_rate:>8.1f}% {avg_ret:>+12.1f}%")

    # Non-quality stocks only
    print("\n" + "-"*100)
    print("EXCLUDING QUALITY STOCKS")
    print("-"*100)

    non_quality = below_200[below_200['category'] != 'quality']
    print(f"\nNon-quality stocks only: {len(non_quality)}")
    print(f"  Win rate: {(non_quality['fwd_12m'] < 0).mean()*100:.1f}%")
    print(f"  Avg SHORT return: {-non_quality['fwd_12m'].mean()*100:+.1f}%")

    # Save results
    signals_df.to_csv('comprehensive_breakdown_signals.csv', index=False)
    below_200.to_csv('below_200sma_signals.csv', index=False)

    # Summary statistics for backtesting
    print("\n" + "="*100)
    print("BACKTEST SIMULATION (5% position size, 12-month hold)")
    print("="*100)

    # Simulate trading
    non_quality = non_quality.copy()
    non_quality['short_return'] = -non_quality['fwd_12m']
    non_quality['year'] = non_quality['date'].dt.year

    # One trade per stock per year
    yearly_results = []
    for year in sorted(non_quality['year'].unique()):
        year_signals = non_quality[non_quality['year'] == year]
        seen = set()
        year_trades = []

        for _, row in year_signals.iterrows():
            if row['ticker'] in seen:
                continue
            seen.add(row['ticker'])
            year_trades.append({
                'year': year,
                'ticker': row['ticker'],
                'category': row['category'],
                'short_return': row['short_return'],
                'pnl': 5000 * row['short_return']  # 5% of $100k
            })

        yearly_results.extend(year_trades)

    trades_df = pd.DataFrame(yearly_results)

    if len(trades_df) > 0:
        print(f"\n{'Year':<8} {'Trades':<8} {'Win Rate':<12} {'Avg Return':<12} {'P&L':<12}")
        print("-"*60)

        total_pnl = 0
        for year in sorted(trades_df['year'].unique()):
            yt = trades_df[trades_df['year'] == year]
            win_rate = (yt['short_return'] > 0).mean() * 100
            avg_ret = yt['short_return'].mean() * 100
            pnl = yt['pnl'].sum()
            total_pnl += pnl
            print(f"{year:<8} {len(yt):<8} {win_rate:>8.1f}% {avg_ret:>+10.1f}% ${pnl:>10,.0f}")

        print("-"*60)
        years = trades_df['year'].max() - trades_df['year'].min() + 1
        print(f"{'TOTAL':<8} {len(trades_df):<8} {(trades_df['short_return']>0).mean()*100:>8.1f}% "
              f"{trades_df['short_return'].mean()*100:>+10.1f}% ${total_pnl:>10,.0f}")

        print(f"\nTradesper year: {len(trades_df)/years:.1f}")
        print(f"Total P&L: ${total_pnl:,.0f}")
        print(f"Annualized P&L: ${total_pnl/years:,.0f}")

        trades_df.to_csv('comprehensive_short_trades.csv', index=False)

    print("\n" + "="*100)
    print("FILES SAVED")
    print("="*100)
    print("""
- comprehensive_breakdown_signals.csv: All breakdown signals
- below_200sma_signals.csv: Filtered to below 200 SMA
- comprehensive_short_trades.csv: Backtest trades
""")


if __name__ == '__main__':
    main()
