#!/usr/bin/env python3
"""
COMPREHENSIVE BACKTEST: 600+ Stocks Put Options Strategy
=========================================================

Backtests the put options strategy across 600+ stocks from 1998-2025.
Shows year-by-year ROI and P&L with real historical data.

Run locally: python backtest_600_stocks.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
import sys
warnings.filterwarnings('ignore')

# ============================================================================
# STOCK UNIVERSE - 600+ STOCKS
# ============================================================================

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
    # Meme/Retail
    'GME', 'AMC', 'BB', 'BBBY', 'WISH', 'CLOV', 'SOFI', 'PLTR', 'HOOD', 'UPST', 'AFRM',
    'SKLZ', 'OPEN', 'SPCE', 'ASTS', 'IONQ', 'DNA', 'RKLB',
    # Crypto
    'MARA', 'RIOT', 'COIN', 'MSTR', 'HUT', 'BITF', 'CLSK', 'CIFR', 'CAN', 'GREE',
    'BTBT', 'SOS', 'BTDR', 'IREN', 'WULF',
    # EV/Clean Energy
    'RIVN', 'LCID', 'FSR', 'NKLA', 'GOEV', 'WKHS', 'RIDE', 'ARVL', 'FFIE', 'MULN',
    'PLUG', 'FCEL', 'BE', 'BLDP', 'BLNK', 'CHPT', 'STEM', 'RUN', 'NOVA', 'ARRY',
    'SHLS', 'MAXN', 'SPWR', 'SUNW', 'JKS', 'CSIQ', 'DQ',
    # China ADRs
    'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'XPEV', 'LI', 'BILI', 'TME', 'IQ',
    'DIDI', 'TAL', 'EDU', 'GOTU', 'YY', 'HUYA', 'DOYU', 'VIPS', 'ZH',
    # Cannabis
    'TLRY', 'CGC', 'ACB', 'CRON', 'SNDL', 'HEXO', 'OGI', 'VFF', 'GRWG',
    # High-vol Software
    'PATH', 'DOCN', 'BILL', 'U', 'RBLX', 'SNOW', 'DDOG', 'NET', 'CRWD', 'ZS',
    'OKTA', 'MDB', 'ESTC', 'CFLT', 'GTLB', 'SUMO', 'NEWR', 'DT', 'HUBS',
    # Biotech
    'BNTX', 'NVAX', 'SGEN', 'SRPT', 'BMRN', 'ALNY', 'RARE', 'IONS',
    'EXAS', 'PACB', 'TWST', 'BEAM', 'CRSP', 'NTLA', 'EDIT', 'VERV',
    # Other volatile
    'PTON', 'W', 'CHWY', 'FUBO', 'LAZR', 'VLDR', 'SNAP', 'ROKU', 'DOCU', 'ZM',
    'ASAN', 'FVRR', 'APPS', 'DKNG', 'PENN', 'DASH', 'ABNB', 'LYFT',
    # Travel
    'AAL', 'DAL', 'UAL', 'LUV', 'JBLU', 'SAVE', 'CCL', 'RCL', 'NCLH',
    # Retail
    'SHOP', 'SQ',
]

ALL_STOCKS = list(set(SP500 + HIGH_VOL))

# ============================================================================
# BACKTEST FUNCTIONS
# ============================================================================

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

    # Moving averages
    df['sma_50'] = df['Close'].rolling(50).mean()
    df['sma_200'] = df['Close'].rolling(200).mean()

    # 52-week high
    df['high_52w'] = df['Close'].rolling(252).max()
    df['pct_from_high'] = (df['Close'] - df['high_52w']) / df['high_52w']

    # Momentum
    df['mom_12m'] = df['Close'].pct_change(252)
    df['mom_6m'] = df['Close'].pct_change(126)

    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Forward returns (for backtest)
    df['fwd_6m'] = df['Close'].shift(-126) / df['Close'] - 1

    return df


def find_signals(df, ticker, min_momentum=1.0, min_drop=-0.50, max_rsi=60):
    """Find all entry signals in historical data."""
    signals = []

    for i in range(252, len(df) - 126):
        row = df.iloc[i]

        # Skip if missing data
        if pd.isna(row['mom_12m']) or pd.isna(row['fwd_6m']) or pd.isna(row['rsi']):
            continue

        # Check entry criteria
        has_momentum = row['mom_12m'] >= min_momentum
        has_dropped = row['pct_from_high'] <= min_drop
        rsi_ok = row['rsi'] < max_rsi

        if has_momentum and has_dropped and rsi_ok:
            signals.append({
                'date': df.iloc[i]['Date'],
                'ticker': ticker,
                'price': row['Close'],
                'mom_12m': row['mom_12m'],
                'pct_from_high': row['pct_from_high'],
                'rsi': row['rsi'],
                'fwd_6m': row['fwd_6m'],
            })

    return signals


def calculate_put_return(fwd_6m, premium=0.12):
    """Calculate put option return."""
    if fwd_6m < 0:
        intrinsic = abs(fwd_6m)
        ret = (intrinsic - premium) / premium
        return min(ret, 10.0)  # Cap at 1000%
    else:
        if fwd_6m < 0.05:
            return -0.80
        elif fwd_6m < 0.15:
            return -0.95
        else:
            return -1.00


# ============================================================================
# MAIN BACKTEST
# ============================================================================

if __name__ == "__main__":
    print("="*100)
    print("600+ STOCK BACKTEST: Put Options Strategy (1998-2025)")
    print("="*100)
    print(f"\nStock universe: {len(ALL_STOCKS)} stocks")
    print("Strategy: Buy 6-month ATM puts on crashed hype stocks")
    print("Criteria: Momentum >= 100%, Drop >= 50%, RSI < 60")
    print("\nDownloading historical data (this may take 15-30 minutes)...\n")

    all_signals = []
    successful = 0
    failed = []

    start_time = time.time()

    for i, ticker in enumerate(ALL_STOCKS):
        pct = (i + 1) / len(ALL_STOCKS) * 100
        elapsed = time.time() - start_time
        eta = (elapsed / (i + 1)) * (len(ALL_STOCKS) - i - 1) if i > 0 else 0

        print(f"\r  [{pct:5.1f}%] {ticker:<6} | {successful} stocks done | ETA: {eta/60:.1f} min   ", end='', flush=True)

        df = download_stock_history(ticker)
        if df is None:
            failed.append(ticker)
            continue

        df = calculate_indicators(df)
        signals = find_signals(df, ticker)

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

    # Calculate put returns
    signals_df['put_return'] = signals_df['fwd_6m'].apply(calculate_put_return)

    # Dedupe: 1 trade per stock per quarter
    signals_df = signals_df.sort_values('date')
    signals_df = signals_df.drop_duplicates(subset=['ticker', 'quarter'])

    # Filter to post-1998
    signals_df = signals_df[signals_df['year'] >= 1998]

    # ========================================================================
    # RESULTS
    # ========================================================================

    print("\n" + "="*100)
    print("BACKTEST RESULTS")
    print("="*100)

    print(f"\nTotal Signals: {len(signals_df)}")
    print(f"Unique Stocks: {signals_df['ticker'].nunique()}")
    print(f"Date Range: {signals_df['date'].min().strftime('%Y-%m-%d')} to {signals_df['date'].max().strftime('%Y-%m-%d')}")

    # Year by year
    print("\n" + "="*100)
    print("YEAR-BY-YEAR PERFORMANCE ($1,000 per trade)")
    print("="*100)

    print(f"\n{'Year':<6} {'Trades':<8} {'Wins':<6} {'Losses':<8} {'Win%':<8} {'Avg Ret':<10} {'Year P&L':<12} {'Cumulative':<12} {'ROI':<10}")
    print("-"*100)

    cumulative = 0
    yearly_results = []

    for year in sorted(signals_df['year'].unique()):
        y = signals_df[signals_df['year'] == year]
        wins = (y['put_return'] > 0).sum()
        losses = (y['put_return'] <= 0).sum()
        win_rate = wins / len(y) * 100 if len(y) > 0 else 0
        avg_ret = y['put_return'].mean() * 100
        pnl = y['put_return'].sum() * 1000
        cumulative += pnl

        # ROI = P&L / capital at risk (trades * $1000)
        capital_at_risk = len(y) * 1000
        roi = (pnl / capital_at_risk * 100) if capital_at_risk > 0 else 0

        yearly_results.append({
            'year': year, 'trades': len(y), 'wins': wins, 'losses': losses,
            'win_rate': win_rate, 'avg_ret': avg_ret, 'pnl': pnl, 'roi': roi
        })

        print(f"{year:<6} {len(y):<8} {wins:<6} {losses:<8} {win_rate:>5.0f}% {avg_ret:>+8.0f}% ${pnl:>+10,.0f} ${cumulative:>+10,.0f} {roi:>+7.0f}%")

    print("-"*100)
    total_trades = len(signals_df)
    total_wins = (signals_df['put_return'] > 0).sum()
    total_losses = (signals_df['put_return'] <= 0).sum()
    overall_win = total_wins / total_trades * 100
    overall_avg = signals_df['put_return'].mean() * 100
    overall_roi = cumulative / (total_trades * 1000) * 100

    print(f"{'TOTAL':<6} {total_trades:<8} {total_wins:<6} {total_losses:<8} {overall_win:>5.0f}% {overall_avg:>+8.0f}% ${cumulative:>+10,.0f}            {overall_roi:>+7.0f}%")

    # Summary stats
    years = len(yearly_results)
    profitable_years = sum(1 for y in yearly_results if y['pnl'] > 0)

    print("\n" + "="*100)
    print("SUMMARY STATISTICS")
    print("="*100)

    print(f"""
OVERALL PERFORMANCE:
  Total Trades: {total_trades}
  Trades per Year: {total_trades/years:.1f}
  Win Rate: {overall_win:.1f}%
  Average Return per Trade: {overall_avg:+.1f}%

PROFITABILITY:
  Total P&L: ${cumulative:+,.0f}
  Average Annual P&L: ${cumulative/years:+,.0f}
  Overall ROI: {overall_roi:+.1f}%
  Profitable Years: {profitable_years}/{years} ({profitable_years/years*100:.0f}%)

BEST/WORST:
  Best Year: {max(yearly_results, key=lambda x: x['pnl'])['year']} (${max(yearly_results, key=lambda x: x['pnl'])['pnl']:+,.0f})
  Worst Year: {min(yearly_results, key=lambda x: x['pnl'])['year']} (${min(yearly_results, key=lambda x: x['pnl'])['pnl']:+,.0f})
  Best ROI: {max(yearly_results, key=lambda x: x['roi'])['year']} ({max(yearly_results, key=lambda x: x['roi'])['roi']:+.0f}%)

WITH $10,000 ALLOCATED:
  Expected Annual P&L: ${cumulative/years:+,.0f}
  Expected Annual ROI: {overall_roi:+.1f}%
""")

    # Top stocks
    print("="*100)
    print("TOP 15 MOST PROFITABLE STOCKS")
    print("="*100)

    by_stock = signals_df.groupby('ticker').agg({
        'put_return': ['count', 'sum', 'mean']
    }).reset_index()
    by_stock.columns = ['ticker', 'trades', 'total_ret', 'avg_ret']
    by_stock['pnl'] = by_stock['total_ret'] * 1000
    by_stock = by_stock.sort_values('pnl', ascending=False)

    print(f"\n{'Ticker':<8} {'Trades':<8} {'Avg Ret':<10} {'Total P&L':<12}")
    print("-"*45)
    for _, row in by_stock.head(15).iterrows():
        print(f"{row['ticker']:<8} {int(row['trades']):<8} {row['avg_ret']*100:>+7.0f}% ${row['pnl']:>+10,.0f}")

    # Save results
    signals_df.to_csv('backtest_600_signals.csv', index=False)
    pd.DataFrame(yearly_results).to_csv('backtest_600_yearly.csv', index=False)
    by_stock.to_csv('backtest_600_by_stock.csv', index=False)

    print(f"\n\nResults saved to:")
    print("  - backtest_600_signals.csv (all signals)")
    print("  - backtest_600_yearly.csv (yearly summary)")
    print("  - backtest_600_by_stock.csv (by stock)")
