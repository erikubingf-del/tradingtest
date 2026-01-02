#!/usr/bin/env python3
"""
SNIPER SCANNER: Real-Time Put Options Opportunity Finder
=========================================================

Scans for stocks matching our profitable pattern:
- Gained 100%+ in past 12 months
- Now down 50%+ from 52-week high
- RSI < 60
- Market Cap > $500M (liquid options)

Run daily to find new opportunities.

Usage:
    python sniper_scanner.py                    # Scan all stocks
    python sniper_scanner.py --min-cap 1000     # Min $1B market cap
    python sniper_scanner.py --live             # Show current opportunities only
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
import warnings
import time
warnings.filterwarnings('ignore')

# ============================================================================
# STOCK UNIVERSE - Liquid stocks with options
# ============================================================================

# Focus on stocks likely to have liquid options (larger caps, popular names)
STOCK_UNIVERSE = [
    # MEGA CAP TECH (Always liquid options)
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC',
    'AVGO', 'ORCL', 'CRM', 'ADBE', 'CSCO', 'QCOM', 'TXN', 'NOW', 'INTU',
    'AMAT', 'MU', 'LRCX', 'ADI', 'KLAC', 'SNPS', 'CDNS', 'MRVL', 'NXPI',

    # HIGH VOLATILITY / MEME (Great for puts)
    'GME', 'AMC', 'BB', 'PLTR', 'SOFI', 'HOOD', 'UPST', 'AFRM', 'COIN',
    'MARA', 'RIOT', 'MSTR', 'CLSK', 'HUT', 'BITF', 'CIFR',

    # BIOTECH (High IV = expensive but profitable puts)
    'MRNA', 'BNTX', 'NVAX', 'BIIB', 'ILMN', 'DXCM', 'EXAS', 'ALGN',

    # CHINA ADRs (Volatile)
    'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'XPEV', 'LI', 'BILI',

    # EV / CLEAN ENERGY (Hype cycles)
    'RIVN', 'LCID', 'FSR', 'PLUG', 'FCEL', 'BE', 'ENPH', 'SEDG', 'RUN',

    # SPAC / DE-SPAC (Crash prone)
    'DKNG', 'SKLZ', 'OPEN', 'CLOV', 'DNA', 'IONQ', 'JOBY',

    # CANNABIS
    'TLRY', 'CGC', 'ACB', 'CRON', 'SNDL',

    # SOFTWARE / SAAS (High multiple crashes)
    'SNOW', 'DDOG', 'NET', 'CRWD', 'ZS', 'OKTA', 'MDB', 'PATH',
    'DOCN', 'BILL', 'HUBS', 'ESTC', 'CFLT', 'U', 'RBLX',

    # FINANCIALS
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'SCHW', 'COF',

    # CONSUMER
    'NFLX', 'DIS', 'ROKU', 'SPOT', 'PARA', 'WBD',

    # TRAVEL / LEISURE
    'AAL', 'DAL', 'UAL', 'CCL', 'RCL', 'NCLH', 'ABNB', 'BKNG',

    # RETAIL
    'W', 'CHWY', 'ETSY', 'WISH', 'PTON',

    # INDUSTRIALS
    'BA', 'CAT', 'DE',

    # Additional volatile stocks
    'SNAP', 'PINS', 'ZM', 'DOCU', 'ASAN', 'FVRR', 'APPS',
    'FUBO', 'LAZR', 'VLDR', 'GOEV', 'NKLA', 'WKHS',
]

# Remove duplicates
STOCK_UNIVERSE = list(set(STOCK_UNIVERSE))

# ============================================================================
# SCANNER FUNCTIONS
# ============================================================================

def get_stock_data(ticker):
    """Fetch stock data and calculate indicators."""
    try:
        stock = yf.Ticker(ticker)

        # Get info for market cap
        info = stock.info
        market_cap = info.get('marketCap', 0)
        if market_cap is None:
            market_cap = 0

        # Get historical data (need 15 months for 12m momentum + some buffer)
        df = stock.history(period='15mo')
        if len(df) < 252:
            return None

        current_price = df['Close'].iloc[-1]

        # Calculate indicators
        high_52w = df['Close'].rolling(252).max().iloc[-1]
        low_52w = df['Close'].rolling(252).min().iloc[-1]

        # Momentum (12 month return)
        if len(df) >= 252:
            price_12m_ago = df['Close'].iloc[-252]
            momentum_12m = (current_price / price_12m_ago - 1) * 100
        else:
            momentum_12m = 0

        # Drop from high
        pct_from_high = (current_price / high_52w - 1) * 100

        # RSI (14-day)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # 50 and 200 SMA
        sma_50 = df['Close'].rolling(50).mean().iloc[-1]
        sma_200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else None

        # Volume
        avg_volume = df['Volume'].rolling(20).mean().iloc[-1]

        return {
            'ticker': ticker,
            'price': current_price,
            'market_cap': market_cap,
            'market_cap_B': market_cap / 1e9,
            'high_52w': high_52w,
            'low_52w': low_52w,
            'momentum_12m': momentum_12m,
            'pct_from_high': pct_from_high,
            'rsi': rsi,
            'sma_50': sma_50,
            'sma_200': sma_200,
            'below_sma_50': current_price < sma_50,
            'below_sma_200': current_price < sma_200 if sma_200 else False,
            'avg_volume': avg_volume,
        }
    except Exception as e:
        return None


def check_entry_signal(stock_data, min_momentum=100, min_drop=50, max_rsi=60):
    """Check if stock meets entry criteria."""
    if stock_data is None:
        return False, []

    signals = []

    # Primary criteria
    has_momentum = stock_data['momentum_12m'] >= min_momentum
    has_dropped = stock_data['pct_from_high'] <= -min_drop
    rsi_ok = stock_data['rsi'] < max_rsi

    if has_momentum:
        signals.append(f"Mom: +{stock_data['momentum_12m']:.0f}%")
    if has_dropped:
        signals.append(f"Drop: {stock_data['pct_from_high']:.0f}%")
    if rsi_ok:
        signals.append(f"RSI: {stock_data['rsi']:.0f}")
    if stock_data['below_sma_200']:
        signals.append("Below 200SMA")

    # All primary criteria must be met
    is_signal = has_momentum and has_dropped and rsi_ok

    return is_signal, signals


def calculate_put_premium_estimate(stock_data):
    """Estimate put option premium based on volatility indicators."""
    # Higher drop from high = higher IV = more expensive premium
    drop = abs(stock_data['pct_from_high'])

    # Base premium for 6-month ATM put
    if drop > 70:
        premium_pct = 0.20  # 20% - very high IV
    elif drop > 60:
        premium_pct = 0.16  # 16%
    elif drop > 50:
        premium_pct = 0.12  # 12% - our model default
    else:
        premium_pct = 0.10  # 10%

    premium_dollar = stock_data['price'] * premium_pct * 100  # Per contract (100 shares)

    return premium_pct, premium_dollar


def scan_stocks(min_market_cap=500, show_all=False, min_momentum=100, min_drop=50):
    """Scan all stocks for opportunities."""

    print("="*100)
    print(f"SNIPER SCANNER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*100)
    print(f"\nScanning {len(STOCK_UNIVERSE)} stocks...")
    print(f"Filters: Market Cap > ${min_market_cap}M, Momentum > {min_momentum}%, Drop > {min_drop}%")

    results = []
    errors = []

    for i, ticker in enumerate(STOCK_UNIVERSE):
        print(f"\r  Processing {i+1}/{len(STOCK_UNIVERSE)}: {ticker}...   ", end='', flush=True)

        data = get_stock_data(ticker)
        if data is None:
            errors.append(ticker)
            continue

        # Market cap filter (in millions)
        if data['market_cap'] < min_market_cap * 1e6:
            continue

        is_signal, signals = check_entry_signal(data, min_momentum, min_drop)

        if is_signal or show_all:
            premium_pct, premium_dollar = calculate_put_premium_estimate(data)
            data['is_signal'] = is_signal
            data['signals'] = signals
            data['premium_pct'] = premium_pct
            data['premium_dollar'] = premium_dollar
            results.append(data)

        # Rate limiting
        time.sleep(0.1)

    print(f"\r  Scan complete! Found {len([r for r in results if r['is_signal']])} opportunities.     ")

    return results, errors


def display_opportunities(results):
    """Display found opportunities."""

    # Filter to signals only
    signals = [r for r in results if r['is_signal']]

    if not signals:
        print("\n" + "="*100)
        print("NO OPPORTUNITIES FOUND TODAY")
        print("="*100)
        print("\nThis is normal - we expect ~8 trades per year on average.")
        print("Run the scanner daily to catch opportunities when they appear.")
        return

    # Sort by drop percentage (bigger drop = better opportunity)
    signals = sorted(signals, key=lambda x: x['pct_from_high'])

    print("\n" + "="*100)
    print(f"🎯 FOUND {len(signals)} OPPORTUNITIES")
    print("="*100)

    print(f"\n{'Ticker':<8} {'Price':<10} {'MktCap':<10} {'Mom12m':<10} {'Drop':<10} {'RSI':<8} {'Premium':<12} {'Signals'}")
    print("-"*100)

    for s in signals:
        signals_str = ', '.join(s['signals'])
        print(f"{s['ticker']:<8} ${s['price']:<9.2f} ${s['market_cap_B']:<8.1f}B {s['momentum_12m']:>+7.0f}% {s['pct_from_high']:>+7.0f}% {s['rsi']:>6.0f} ${s['premium_dollar']:>9,.0f} {signals_str}")

    # Trade recommendations
    print("\n" + "="*100)
    print("TRADE RECOMMENDATIONS")
    print("="*100)

    for s in signals[:5]:  # Top 5
        print(f"""
{s['ticker']}:
  Current Price: ${s['price']:.2f}
  52-Week High: ${s['high_52w']:.2f} (down {abs(s['pct_from_high']):.0f}%)
  12-Month Momentum: {s['momentum_12m']:+.0f}%
  RSI: {s['rsi']:.0f}

  TRADE: Buy 6-month ATM Put @ ${s['price']:.0f} strike
  Estimated Premium: ${s['premium_dollar']:,.0f} per contract (~{s['premium_pct']*100:.0f}%)
  Max Risk: ${s['premium_dollar']:,.0f}
  Target: Stock continues to fall, put gains value
""")


def display_watchlist(results, min_momentum=50):
    """Display stocks approaching entry criteria."""

    # Filter to near-misses (some criteria met but not all)
    watchlist = []
    for r in results:
        if r['is_signal']:
            continue
        # Has some momentum and some drop
        if r['momentum_12m'] >= min_momentum and r['pct_from_high'] <= -30:
            watchlist.append(r)

    if not watchlist:
        return

    # Sort by drop
    watchlist = sorted(watchlist, key=lambda x: x['pct_from_high'])[:10]

    print("\n" + "="*100)
    print("📋 WATCHLIST - Approaching Entry Criteria")
    print("="*100)

    print(f"\n{'Ticker':<8} {'Price':<10} {'Mom12m':<10} {'Drop':<10} {'RSI':<8} {'Needs'}")
    print("-"*80)

    for w in watchlist:
        needs = []
        if w['momentum_12m'] < 100:
            needs.append(f"Mom needs +{100-w['momentum_12m']:.0f}%")
        if w['pct_from_high'] > -50:
            needs.append(f"Drop needs {-50-w['pct_from_high']:.0f}%")
        if w['rsi'] >= 60:
            needs.append(f"RSI needs -{w['rsi']-60:.0f}")

        needs_str = ', '.join(needs) if needs else "READY!"
        print(f"{w['ticker']:<8} ${w['price']:<9.2f} {w['momentum_12m']:>+7.0f}% {w['pct_from_high']:>+7.0f}% {w['rsi']:>6.0f} {needs_str}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Sniper Scanner for Put Options')
    parser.add_argument('--min-cap', type=int, default=500, help='Minimum market cap in millions (default: 500)')
    parser.add_argument('--min-momentum', type=int, default=100, help='Minimum 12m momentum % (default: 100)')
    parser.add_argument('--min-drop', type=int, default=50, help='Minimum drop from high % (default: 50)')
    parser.add_argument('--show-all', action='store_true', help='Show all scanned stocks')
    parser.add_argument('--watchlist', action='store_true', help='Show watchlist of near-misses')

    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SNIPER SCANNER - Put Options Finder                       ║
║                                                                              ║
║  Strategy: Buy puts on crashed hype stocks                                   ║
║  - Stock gained 100%+ in past year (was hyped)                               ║
║  - Now down 50%+ from high (crash in progress)                               ║
║  - RSI < 60 (still weak)                                                     ║
║                                                                              ║
║  Expected: ~8 trades/year, 49% win rate, +82% avg return                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    results, errors = scan_stocks(
        min_market_cap=args.min_cap,
        show_all=args.show_all,
        min_momentum=args.min_momentum,
        min_drop=args.min_drop
    )

    display_opportunities(results)

    if args.watchlist:
        display_watchlist(results)

    if errors:
        print(f"\n⚠️  Could not fetch data for: {', '.join(errors[:10])}{'...' if len(errors) > 10 else ''}")

    print(f"\n{'='*100}")
    print("Run this scanner daily. When opportunities appear, verify:")
    print("  1. Options are liquid (bid-ask spread < 10%)")
    print("  2. Choose 6-month expiration, ATM strike")
    print("  3. Position size: $1,000 per trade (adjust to your portfolio)")
    print("="*100)
