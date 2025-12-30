#!/usr/bin/env python3
"""
SMART LEVERAGE - EXACT ETF RECOMMENDATIONS

Maps each position to actual tradeable ETFs with specific dollar amounts.
Run this daily to get your exact buy orders.
"""

import json
from datetime import datetime

# Current portfolio from Smart Leverage Bot
PORTFOLIO_CAPITAL = 100000
POSITION_SIZE = 0.05  # 5% per position = $5,000

# Current holdings from the bot
CURRENT_HOLDINGS = [
    {'asset': 'NATGAS', 'price': 3.94, 'leverage': 2.0, 'signals': 4},
    {'asset': 'DAX', 'price': 19909.14, 'leverage': 2.0, 'signals': 4},
    {'asset': 'NASDAQ', 'price': 19486.79, 'leverage': 2.0, 'signals': 4},
    {'asset': 'COFFEE', 'price': 321.00, 'leverage': 1.5, 'signals': 3},
    {'asset': 'NIKKEI', 'price': 39894.54, 'leverage': 1.5, 'signals': 3},
    {'asset': 'HANGSENG', 'price': 20041.42, 'leverage': 1.5, 'signals': 3},
    {'asset': 'XLK', 'price': 116.51, 'leverage': 1.5, 'signals': 3},
    {'asset': 'CORN', 'price': 452.25, 'leverage': 1.5, 'signals': 3},
]

# ETF MAPPING - Maps each asset to its leveraged ETF equivalent
ETF_MAP = {
    # US INDICES
    'SP500': {
        1.0: {'ticker': 'SPY', 'name': 'SPDR S&P 500 ETF'},
        1.5: {'ticker': 'SPY+SSO', 'name': '50% SPY + 50% SSO (avg 1.5x)'},
        2.0: {'ticker': 'SSO', 'name': 'ProShares Ultra S&P500 (2x)'},
        3.0: {'ticker': 'UPRO', 'name': 'ProShares UltraPro S&P500 (3x)'},
    },
    'NASDAQ': {
        1.0: {'ticker': 'QQQ', 'name': 'Invesco QQQ Trust'},
        1.5: {'ticker': 'QQQ+QLD', 'name': '50% QQQ + 50% QLD (avg 1.5x)'},
        2.0: {'ticker': 'QLD', 'name': 'ProShares Ultra QQQ (2x)'},
        3.0: {'ticker': 'TQQQ', 'name': 'ProShares UltraPro QQQ (3x)'},
    },
    'DOW': {
        1.0: {'ticker': 'DIA', 'name': 'SPDR Dow Jones ETF'},
        2.0: {'ticker': 'DDM', 'name': 'ProShares Ultra Dow30 (2x)'},
        3.0: {'ticker': 'UDOW', 'name': 'ProShares UltraPro Dow30 (3x)'},
    },
    'RUSSELL2000': {
        1.0: {'ticker': 'IWM', 'name': 'iShares Russell 2000 ETF'},
        2.0: {'ticker': 'UWM', 'name': 'ProShares Ultra Russell2000 (2x)'},
        3.0: {'ticker': 'TNA', 'name': 'Direxion Russell 2000 Bull 3x'},
    },

    # INTERNATIONAL INDICES
    'DAX': {
        1.0: {'ticker': 'EWG', 'name': 'iShares MSCI Germany ETF'},
        1.5: {'ticker': 'EWG', 'name': 'iShares Germany (use 1.5x margin)'},
        2.0: {'ticker': 'EWG', 'name': 'iShares Germany (use 2x margin or futures)'},
    },
    'NIKKEI': {
        1.0: {'ticker': 'EWJ', 'name': 'iShares MSCI Japan ETF'},
        1.5: {'ticker': 'EWJ', 'name': 'iShares Japan (use 1.5x margin)'},
        2.0: {'ticker': 'EZJ', 'name': 'ProShares Ultra MSCI Japan (2x)'},
    },
    'HANGSENG': {
        1.0: {'ticker': 'EWH', 'name': 'iShares MSCI Hong Kong ETF'},
        1.5: {'ticker': 'EWH', 'name': 'iShares HK (use 1.5x margin)'},
        2.0: {'ticker': 'EWH', 'name': 'iShares HK (use 2x margin)'},
    },
    'FTSE': {
        1.0: {'ticker': 'EWU', 'name': 'iShares MSCI UK ETF'},
        2.0: {'ticker': 'EWU', 'name': 'iShares UK (use 2x margin)'},
    },

    # COMMODITIES
    'GOLD': {
        1.0: {'ticker': 'GLD', 'name': 'SPDR Gold Shares'},
        2.0: {'ticker': 'UGL', 'name': 'ProShares Ultra Gold (2x)'},
        3.0: {'ticker': 'UGLD', 'name': 'Velocity 3x Long Gold'},
    },
    'SILVER': {
        1.0: {'ticker': 'SLV', 'name': 'iShares Silver Trust'},
        2.0: {'ticker': 'AGQ', 'name': 'ProShares Ultra Silver (2x)'},
        3.0: {'ticker': 'USLV', 'name': 'Velocity 3x Long Silver'},
    },
    'CRUDE': {
        1.0: {'ticker': 'USO', 'name': 'United States Oil Fund'},
        2.0: {'ticker': 'UCO', 'name': 'ProShares Ultra Bloomberg Crude (2x)'},
        3.0: {'ticker': 'OILU', 'name': 'MicroSectors Oil 3x Leveraged'},
    },
    'NATGAS': {
        1.0: {'ticker': 'UNG', 'name': 'United States Natural Gas Fund'},
        2.0: {'ticker': 'BOIL', 'name': 'ProShares Ultra Natural Gas (2x)'},
        3.0: {'ticker': 'BOIL', 'name': 'BOIL (2x) - no 3x available, use margin'},
    },
    'CORN': {
        1.0: {'ticker': 'CORN', 'name': 'Teucrium Corn Fund'},
        1.5: {'ticker': 'CORN', 'name': 'Teucrium Corn (use margin for 1.5x)'},
        2.0: {'ticker': 'CORN', 'name': 'Teucrium Corn (use margin for 2x)'},
    },
    'WHEAT': {
        1.0: {'ticker': 'WEAT', 'name': 'Teucrium Wheat Fund'},
        2.0: {'ticker': 'WEAT', 'name': 'Teucrium Wheat (use margin for 2x)'},
    },
    'SOYBEANS': {
        1.0: {'ticker': 'SOYB', 'name': 'Teucrium Soybean Fund'},
        2.0: {'ticker': 'SOYB', 'name': 'Teucrium Soybean (use margin)'},
    },
    'COFFEE': {
        1.0: {'ticker': 'JO', 'name': 'iPath Coffee ETN'},
        1.5: {'ticker': 'JO', 'name': 'iPath Coffee (use 1.5x margin)'},
        2.0: {'ticker': 'JO', 'name': 'iPath Coffee (use 2x margin)'},
    },
    'SUGAR': {
        1.0: {'ticker': 'CANE', 'name': 'Teucrium Sugar Fund'},
        2.0: {'ticker': 'CANE', 'name': 'Teucrium Sugar (use margin)'},
    },
    'COTTON': {
        1.0: {'ticker': 'BAL', 'name': 'iPath Cotton ETN'},
        2.0: {'ticker': 'BAL', 'name': 'iPath Cotton (use margin)'},
    },
    'COPPER': {
        1.0: {'ticker': 'CPER', 'name': 'United States Copper Index Fund'},
        2.0: {'ticker': 'CPER', 'name': 'CPER (use margin for 2x)'},
    },
    'PLATINUM': {
        1.0: {'ticker': 'PPLT', 'name': 'Aberdeen Physical Platinum Shares'},
        2.0: {'ticker': 'PPLT', 'name': 'PPLT (use margin for 2x)'},
    },

    # SECTORS
    'XLK': {
        1.0: {'ticker': 'XLK', 'name': 'Technology Select Sector SPDR'},
        1.5: {'ticker': 'XLK+TECL', 'name': '75% XLK + 25% TECL (avg 1.5x)'},
        2.0: {'ticker': 'ROM', 'name': 'ProShares Ultra Technology (2x)'},
        3.0: {'ticker': 'TECL', 'name': 'Direxion Technology Bull 3x'},
    },
    'XLF': {
        1.0: {'ticker': 'XLF', 'name': 'Financial Select Sector SPDR'},
        2.0: {'ticker': 'UYG', 'name': 'ProShares Ultra Financials (2x)'},
        3.0: {'ticker': 'FAS', 'name': 'Direxion Financial Bull 3x'},
    },
    'XLE': {
        1.0: {'ticker': 'XLE', 'name': 'Energy Select Sector SPDR'},
        2.0: {'ticker': 'DIG', 'name': 'ProShares Ultra Energy (2x)'},
        3.0: {'ticker': 'ERX', 'name': 'Direxion Energy Bull 3x'},
    },
    'XLV': {
        1.0: {'ticker': 'XLV', 'name': 'Health Care Select Sector SPDR'},
        2.0: {'ticker': 'RXL', 'name': 'ProShares Ultra Health Care (2x)'},
        3.0: {'ticker': 'CURE', 'name': 'Direxion Healthcare Bull 3x'},
    },

    # CURRENCIES
    'EURUSD': {
        1.0: {'ticker': 'FXE', 'name': 'Invesco CurrencyShares Euro Trust'},
        2.0: {'ticker': 'ULE', 'name': 'ProShares Ultra Euro (2x)'},
    },
    'USDJPY': {
        1.0: {'ticker': 'FXY', 'name': 'Invesco CurrencyShares Yen Trust'},
        2.0: {'ticker': 'YCL', 'name': 'ProShares Ultra Yen (2x)'},
    },
    'GBPUSD': {
        1.0: {'ticker': 'FXB', 'name': 'Invesco CurrencyShares British Pound'},
        2.0: {'ticker': 'FXB', 'name': 'FXB (use margin for 2x)'},
    },
    'DXY': {
        1.0: {'ticker': 'UUP', 'name': 'Invesco DB US Dollar Index Bullish'},
        2.0: {'ticker': 'UUP', 'name': 'UUP (use margin for 2x)'},
    },

    # BONDS
    'TNOTE10': {
        1.0: {'ticker': 'IEF', 'name': 'iShares 7-10 Year Treasury Bond ETF'},
        2.0: {'ticker': 'UST', 'name': 'ProShares Ultra 7-10 Year Treasury (2x)'},
    },
    'TBOND': {
        1.0: {'ticker': 'TLT', 'name': 'iShares 20+ Year Treasury Bond ETF'},
        2.0: {'ticker': 'UBT', 'name': 'ProShares Ultra 20+ Year Treasury (2x)'},
        3.0: {'ticker': 'TMF', 'name': 'Direxion Daily 20+ Year Treasury Bull 3x'},
    },

    # CRYPTO
    'BTC': {
        1.0: {'ticker': 'IBIT', 'name': 'iShares Bitcoin Trust'},
        2.0: {'ticker': 'BITX', 'name': '2x Bitcoin Strategy ETF'},
    },
    'ETH': {
        1.0: {'ticker': 'ETHA', 'name': 'iShares Ethereum Trust'},
        2.0: {'ticker': 'ETHA', 'name': 'ETHA (use margin for 2x)'},
    },
}

def get_etf_recommendation(asset, leverage):
    """Get ETF recommendation for an asset at a specific leverage"""
    if asset not in ETF_MAP:
        return None

    etf_options = ETF_MAP[asset]

    # Find the best match
    if leverage in etf_options:
        return etf_options[leverage]
    elif leverage == 1.5 and 1.0 in etf_options:
        # For 1.5x, suggest mixing 1x and 2x
        base = etf_options[1.0]
        if 2.0 in etf_options:
            lev2 = etf_options[2.0]
            return {
                'ticker': f"50% {base['ticker']} + 50% {lev2['ticker']}",
                'name': f"Mix for 1.5x: Half {base['name']}, Half {lev2['name']}"
            }
        return {'ticker': base['ticker'], 'name': f"{base['name']} (use 1.5x margin)"}
    elif leverage == 2.0 and 1.0 in etf_options:
        base = etf_options[1.0]
        return {'ticker': base['ticker'], 'name': f"{base['name']} (use 2x margin)"}
    elif leverage == 3.0 and 2.0 in etf_options:
        lev2 = etf_options[2.0]
        return {'ticker': lev2['ticker'], 'name': f"{lev2['name']} (use 1.5x margin for 3x total)"}

    return etf_options.get(1.0, {'ticker': 'N/A', 'name': 'No ETF available'})


def main():
    print("\n" + "="*80)
    print("SMART LEVERAGE - ETF BUY RECOMMENDATIONS")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("="*80)

    print(f"\nPORTFOLIO: ${PORTFOLIO_CAPITAL:,}")
    print(f"Position Size: {POSITION_SIZE*100:.0f}% = ${PORTFOLIO_CAPITAL * POSITION_SIZE:,.0f} per position")

    print("\n" + "-"*80)
    print("CURRENT POSITIONS - WHAT TO BUY:")
    print("-"*80)

    total_investment = 0

    print(f"\n{'Asset':<12} {'Lev':<5} {'ETF Ticker':<15} {'$ Amount':<12} {'ETF Name'}")
    print("-"*80)

    for pos in CURRENT_HOLDINGS:
        asset = pos['asset']
        leverage = pos['leverage']
        investment = PORTFOLIO_CAPITAL * POSITION_SIZE  # $5,000 per position

        etf = get_etf_recommendation(asset, leverage)

        if etf:
            # For leveraged ETFs, you invest the base amount (not levered amount)
            # because the ETF provides the leverage
            print(f"{asset:<12} {leverage}x   {etf['ticker']:<15} ${investment:>10,.0f} {etf['name']}")
            total_investment += investment

    print("-"*80)
    print(f"{'TOTAL':<12} {'':<5} {'':<15} ${total_investment:>10,.0f}")
    print(f"{'CASH':<12} {'':<5} {'':<15} ${PORTFOLIO_CAPITAL - total_investment:>10,.0f}")

    print("\n" + "="*80)
    print("DETAILED BREAKDOWN:")
    print("="*80)

    for pos in CURRENT_HOLDINGS:
        asset = pos['asset']
        leverage = pos['leverage']
        signals = pos['signals']
        investment = PORTFOLIO_CAPITAL * POSITION_SIZE

        etf = get_etf_recommendation(asset, leverage)

        print(f"\n{asset} ({leverage}x leverage, {signals} signals):")
        print(f"  Investment: ${investment:,.0f}")

        if etf:
            if '+' in etf['ticker']:
                # Split position
                parts = etf['ticker'].split('+')
                print(f"  Option 1 (Mixed ETFs for {leverage}x):")
                print(f"    - Buy ${investment/2:,.0f} of {parts[0].strip()}")
                print(f"    - Buy ${investment/2:,.0f} of {parts[1].strip()}")
            elif 'margin' in etf['name'].lower():
                print(f"  Option 1 (ETF + Margin):")
                print(f"    - Buy ${investment:,.0f} of {etf['ticker']}")
                print(f"    - Use {leverage}x margin in your broker")
            else:
                print(f"  Buy: ${investment:,.0f} of {etf['ticker']}")
            print(f"  ETF: {etf['name']}")

    print("\n" + "="*80)
    print("SIMPLE IMPLEMENTATION (NO MARGIN):")
    print("="*80)
    print("""
If you want to avoid margin accounts, here's a simplified approach:

For 2x leverage positions:
  - Use 2x leveraged ETFs directly (SSO, QLD, BOIL, etc.)
  - These ETFs rebalance daily, so there's some decay over time
  - Best for positions held < 1 month

For 1.5x leverage positions:
  - Mix 50% 1x ETF + 50% 2x ETF
  - Example: $2,500 QQQ + $2,500 QLD = ~1.5x NASDAQ exposure

For 3x leverage positions:
  - Use 3x leveraged ETFs (UPRO, TQQQ, etc.)
  - Higher decay, best for short-term trades < 2 weeks

IMPORTANT: Leveraged ETFs have volatility decay!
  - For long holds (>1 month), consider futures or margin instead
  - Rebalance monthly to maintain target leverage
""")

    print("\n" + "="*80)
    print("RISK WARNING:")
    print("="*80)
    print("""
Smart Leverage Strategy Statistics (1980-2024):
  - CAGR: ~21%
  - Max Drawdown: ~60%
  - You WILL experience 40-60% drawdowns at some point
  - Only invest what you can afford to lose

Current portfolio is 40% invested ($40,000) with 60% cash ($60,000).
This cash buffer helps manage risk during drawdowns.
""")


if __name__ == '__main__':
    main()
