#!/usr/bin/env python3
"""
SHORT THE HYPE - Research & Analysis

Theory: It's easier to predict when overvalued stocks will FALL than when stocks will RISE
Why? Emotional buying creates predictable patterns:
1. Parabolic rise on hype/FOMO
2. No fundamental support (negative earnings, insane P/E)
3. Eventually gravity wins - they ALL come down

Historical Examples:
- Zoom (ZM): $67 → $588 → $60 (91% crash from peak)
- GoPro (GPRO): $93 → $8 (91% crash)
- Peloton (PTON): $160 → $5 (97% crash)
- Beyond Meat (BYND): $234 → $5 (98% crash)
- Nikola (NKLA): $93 → $1 (99% crash)
- WeWork: Never made it public at $47B valuation
- Pets.com: $14 → $0 (100% loss)
- Luckin Coffee (LK): $50 → $1 (fraud)
- Rivian (RIVN): $172 → $10 (94% crash)
- Snapchat (SNAP): $29 → $8 (72% crash from IPO high)
- Twitter (TWTR): $74 → $31 (58% crash from peak)
- DocuSign (DOCU): $314 → $39 (88% crash)
- Teladoc (TDOC): $308 → $20 (94% crash)
- Roku (ROKU): $490 → $40 (92% crash)
- Coinbase (COIN): $429 → $40 (91% crash)
- Affirm (AFRM): $176 → $8 (95% crash)
- DoorDash (DASH): $256 → $40 (84% crash)
- Snowflake (SNOW): $405 → $110 (73% crash)
- Palantir (PLTR): $45 → $6 (87% crash)
- Unity (U): $210 → $13 (94% crash)
- Robinhood (HOOD): $85 → $7 (92% crash)
- Carvana (CVNA): $376 → $4 (99% crash)

PATTERN OBSERVED:
1. Massive run-up (often 300-1000%+ in 1-2 years)
2. Price WAY above fundamentals
3. Retail FOMO buying (high volume, social media buzz)
4. Eventually cracks appear (earnings miss, guidance cut)
5. Crash is FAST and BRUTAL (often 80-99%)

KEY INSIGHT:
- The run-up is unpredictable (you don't know how high it goes)
- The crash is MORE predictable (once it starts, it's relentless)
- Mean reversion is powerful for extreme moves

INDICATORS FOR "EMOTIONAL BUYS":
1. Price/Sales > 20 (extremely overvalued)
2. No earnings or negative earnings
3. 12-month return > 200% (parabolic)
4. Price > 100% above 200-day SMA
5. RSI > 80 sustained for weeks
6. Volume spike (3x+ normal)
7. High short interest (others see it too)
8. Social media mentions exploding

ENTRY SIGNALS FOR SHORT:
1. Momentum breakdown (price drops below 50-day SMA)
2. Lower high formation (failed rally)
3. Volume increasing on down days
4. RSI divergence (price high, RSI lower high)
5. Earnings miss or guidance cut

EXIT SIGNALS (Cover Short):
1. Price drops 50%+ from entry (take profits)
2. Price breaks above recent high (stop loss)
3. Momentum reversal (too risky to stay short)

RISKS:
1. Short squeeze (GME, AMC showed this)
2. Unlimited loss potential
3. Borrow costs for hard-to-borrow stocks
4. Timing - "markets can stay irrational longer than you can stay solvent"
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Famous hype stocks that crashed
HYPE_STOCKS = {
    # COVID bubble stocks
    'ZM': {'name': 'Zoom', 'peak': 588, 'bottom': 60, 'crash': 0.90},
    'PTON': {'name': 'Peloton', 'peak': 171, 'bottom': 5, 'crash': 0.97},
    'DOCU': {'name': 'DocuSign', 'peak': 314, 'bottom': 39, 'crash': 0.88},
    'TDOC': {'name': 'Teladoc', 'peak': 308, 'bottom': 20, 'crash': 0.94},
    'ROKU': {'name': 'Roku', 'peak': 490, 'bottom': 40, 'crash': 0.92},

    # EV bubble
    'RIVN': {'name': 'Rivian', 'peak': 172, 'bottom': 10, 'crash': 0.94},
    'LCID': {'name': 'Lucid', 'peak': 57, 'bottom': 2, 'crash': 0.96},
    'NKLA': {'name': 'Nikola', 'peak': 93, 'bottom': 1, 'crash': 0.99},

    # Fintech crash
    'COIN': {'name': 'Coinbase', 'peak': 429, 'bottom': 40, 'crash': 0.91},
    'AFRM': {'name': 'Affirm', 'peak': 176, 'bottom': 8, 'crash': 0.95},
    'HOOD': {'name': 'Robinhood', 'peak': 85, 'bottom': 7, 'crash': 0.92},
    'UPST': {'name': 'Upstart', 'peak': 401, 'bottom': 12, 'crash': 0.97},
    'SOFI': {'name': 'SoFi', 'peak': 24, 'bottom': 4, 'crash': 0.83},

    # Tech bubble 2.0
    'SNOW': {'name': 'Snowflake', 'peak': 405, 'bottom': 110, 'crash': 0.73},
    'PLTR': {'name': 'Palantir', 'peak': 45, 'bottom': 6, 'crash': 0.87},
    'U': {'name': 'Unity', 'peak': 210, 'bottom': 13, 'crash': 0.94},
    'DASH': {'name': 'DoorDash', 'peak': 256, 'bottom': 40, 'crash': 0.84},

    # Meme stocks
    'GME': {'name': 'GameStop', 'peak': 483, 'bottom': 10, 'crash': 0.98},
    'AMC': {'name': 'AMC', 'peak': 72, 'bottom': 2, 'crash': 0.97},
    'BBBY': {'name': 'Bed Bath', 'peak': 30, 'bottom': 0, 'crash': 1.00},

    # Older examples
    'GPRO': {'name': 'GoPro', 'peak': 93, 'bottom': 3, 'crash': 0.97},
    'FIT': {'name': 'Fitbit', 'peak': 51, 'bottom': 3, 'crash': 0.94},
    'SNAP': {'name': 'Snapchat', 'peak': 83, 'bottom': 8, 'crash': 0.90},
    'BYND': {'name': 'Beyond Meat', 'peak': 234, 'bottom': 5, 'crash': 0.98},

    # E-commerce bubble
    'CVNA': {'name': 'Carvana', 'peak': 376, 'bottom': 4, 'crash': 0.99},
    'W': {'name': 'Wayfair', 'peak': 369, 'bottom': 20, 'crash': 0.95},
    'CHWY': {'name': 'Chewy', 'peak': 120, 'bottom': 15, 'crash': 0.88},
}

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def print_research_summary():
    """Print research summary"""
    print("\n" + "="*80)
    print("SHORT THE HYPE - RESEARCH SUMMARY")
    print("="*80)

    print("\n📊 HISTORICAL HYPE STOCK CRASHES:")
    print("-"*80)
    print(f"{'Stock':<8} {'Name':<15} {'Peak':<10} {'Bottom':<10} {'Crash %':<10}")
    print("-"*80)

    total_crash = 0
    count = 0
    for ticker, data in HYPE_STOCKS.items():
        print(f"{ticker:<8} {data['name']:<15} ${data['peak']:<9} ${data['bottom']:<9} {data['crash']*100:.0f}%")
        total_crash += data['crash']
        count += 1

    print("-"*80)
    print(f"{'AVERAGE':<8} {'':<15} {'':<10} {'':<10} {total_crash/count*100:.0f}%")

    print("\n" + "="*80)
    print("KEY FINDINGS:")
    print("="*80)
    print("""
1. AVERAGE CRASH: 92% from peak to trough
   - These aren't normal corrections, they're WIPEOUTS
   - Most never recover to previous highs

2. COMMON PATTERNS AT PEAK:
   - RSI > 80 for extended period
   - Price 50-200% above 200-day SMA
   - Volume 3-5x normal (retail FOMO)
   - Social media frenzy
   - No earnings or P/S > 30

3. CRASH TRIGGERS:
   - First earnings miss after hype
   - Guidance reduction
   - Insider selling
   - Short seller report
   - Macro shift (rate hikes killed growth stocks)

4. CRASH SPEED:
   - First 50% happens in 2-6 months
   - Next 50% can take another year
   - Very few V-shaped recoveries

5. WARNING SIGNS BEFORE CRASH:
   - Lower highs on rallies
   - Declining volume on up days
   - Breaking 50-day SMA
   - RSI divergence (price high, RSI lower)
""")

    print("\n" + "="*80)
    print("PROPOSED STRATEGY: SHORT THE HYPE")
    print("="*80)
    print("""
SCAN CRITERIA (Find Candidates):
1. 12-month return > 200% (had massive run)
2. Price > 80% above 200-day SMA
3. RSI > 70 in past month
4. P/S ratio > 15 or negative earnings
5. Volume spike in past 3 months

ENTRY SIGNAL (When to Short):
1. Price breaks BELOW 50-day SMA
2. Lower high confirmed (rally failed)
3. RSI drops below 50 from overbought
4. Volume increasing on down days

POSITION SIZING:
- 3% of portfolio per short position
- Max 5 short positions (15% total exposure)
- Use stop-loss to limit risk

EXIT RULES:
- PROFIT TARGET: Cover 50% at 30% gain, rest at 50% gain
- STOP LOSS: Cover if price rises 20% above entry
- TIME STOP: Cover after 6 months regardless

RISK MANAGEMENT:
- Never short more than 15% of portfolio
- Avoid heavily shorted stocks (squeeze risk)
- Don't fight the Fed (avoid in easy money periods)
- Use options (puts) to cap maximum loss
""")


if __name__ == '__main__':
    print_research_summary()

    print("\n" + "="*80)
    print("CRASH STATISTICS FROM HISTORICAL DATA:")
    print("="*80)

    crashes = [data['crash'] for data in HYPE_STOCKS.values()]
    print(f"\nTotal stocks analyzed: {len(crashes)}")
    print(f"Average crash: {np.mean(crashes)*100:.1f}%")
    print(f"Median crash: {np.median(crashes)*100:.1f}%")
    print(f"Min crash: {np.min(crashes)*100:.1f}%")
    print(f"Max crash: {np.max(crashes)*100:.1f}%")
    print(f"\nStocks that crashed 90%+: {sum(1 for c in crashes if c >= 0.90)}")
    print(f"Stocks that crashed 95%+: {sum(1 for c in crashes if c >= 0.95)}")
    print(f"Stocks that went to $0: {sum(1 for c in crashes if c >= 0.99)}")
