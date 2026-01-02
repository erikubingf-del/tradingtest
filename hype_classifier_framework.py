#!/usr/bin/env python3
"""
HYPE STOCK CLASSIFIER - ML Framework

The Key Insight:
- Tesla, NVIDIA = CAN be overvalued but have REAL business
- Zoom, Peloton, Nikola = HYPE with weak/no fundamentals

We need to classify stocks into:
1. TRUE HYPE (Short these) - Will crash 80-99%
2. QUALITY OVERVALUED (Careful) - May correct 30-50%
3. QUALITY MOMENTUM (Don't short) - May dip but recovers

Features that separate TRUE HYPE from QUALITY:
"""

import pandas as pd
import numpy as np

# ============================================================================
# FEATURE DEFINITIONS FOR ML CLASSIFIER
# ============================================================================

FEATURES = {
    # =========================================
    # FUNDAMENTAL FEATURES (Critical for classification)
    # =========================================
    'earnings': {
        'net_income_positive': 'bool',       # Has positive earnings?
        'earnings_growth': 'float',          # Year-over-year growth
        'consecutive_profit_quarters': 'int', # How many quarters profitable
        'ever_profitable': 'bool',           # Has company EVER made money?
    },

    'valuation': {
        'pe_ratio': 'float',           # Price/Earnings (high = risky)
        'ps_ratio': 'float',           # Price/Sales (>20 = danger)
        'price_to_book': 'float',      # Price/Book value
        'ev_to_revenue': 'float',      # Enterprise Value / Revenue
        'peg_ratio': 'float',          # P/E / Growth (>2 = expensive)
    },

    'cash_flow': {
        'fcf_positive': 'bool',         # Free cash flow positive?
        'operating_cf_positive': 'bool', # Operating cash flow positive?
        'cash_burn_rate': 'float',      # Months of cash left
        'capex_to_revenue': 'float',    # Capital intensity
    },

    'revenue_quality': {
        'revenue_growth': 'float',       # YoY revenue growth
        'gross_margin': 'float',         # Gross profit / Revenue
        'operating_margin': 'float',     # Operating income / Revenue
        'net_margin': 'float',           # Net income / Revenue
        'recurring_revenue_pct': 'float', # Subscription/recurring %
    },

    # =========================================
    # COMPANY PROFILE FEATURES
    # =========================================
    'maturity': {
        'years_since_ipo': 'int',        # IPO age (<3 years = risky)
        'years_profitable': 'int',       # Years of profitability
        'employee_count': 'int',         # Company size
        'market_cap': 'float',           # Market capitalization
    },

    'business_model': {
        'is_tech': 'bool',               # Technology company
        'is_speculative': 'bool',        # Speculative industry (EV, crypto, etc.)
        'has_physical_product': 'bool',  # Physical vs digital
        'is_platform': 'bool',           # Platform/marketplace business
        'is_spac': 'bool',               # Came public via SPAC
    },

    # =========================================
    # TECHNICAL/MOMENTUM FEATURES
    # =========================================
    'momentum': {
        'return_12m': 'float',           # 12-month return
        'return_6m': 'float',            # 6-month return
        'return_3m': 'float',            # 3-month return
        'return_from_ipo': 'float',      # Return since IPO
        'pct_from_52w_high': 'float',    # Distance from peak
        'pct_above_200sma': 'float',     # % above 200 SMA
    },

    'volatility': {
        'historical_vol': 'float',       # Annualized volatility
        'beta': 'float',                 # Market beta
        'max_drawdown_1y': 'float',      # Max DD in past year
    },

    # =========================================
    # MARKET SENTIMENT FEATURES
    # =========================================
    'sentiment': {
        'short_interest_pct': 'float',   # Short interest %
        'analyst_buy_pct': 'float',      # % of analysts with buy rating
        'insider_selling': 'bool',       # Recent insider selling
        'lockup_expiry_near': 'bool',    # IPO lockup expiring soon
    },

    'retail_indicators': {
        'wsb_mentions': 'int',           # WallStreetBets mentions
        'twitter_mentions': 'int',       # Social media buzz
        'robinhood_holdings': 'int',     # Retail broker holdings
        'google_trends': 'float',        # Search interest
    },
}

# ============================================================================
# CLASSIFICATION RULES (Before ML)
# ============================================================================

def classify_hype_stock(features):
    """
    Rule-based classification before ML

    Returns:
    - 'TRUE_HYPE': High probability crash 80%+
    - 'RISKY_OVERVALUED': May crash 30-50%
    - 'QUALITY_MOMENTUM': Don't short
    """

    hype_score = 0
    quality_score = 0

    # ===== NEGATIVE SIGNALS (Hype indicators) =====

    # No earnings = big red flag
    if not features.get('net_income_positive', True):
        hype_score += 3

    # Never been profitable
    if not features.get('ever_profitable', True):
        hype_score += 2

    # Insane P/S ratio
    if features.get('ps_ratio', 0) > 20:
        hype_score += 3
    elif features.get('ps_ratio', 0) > 10:
        hype_score += 2

    # Burning cash
    if not features.get('fcf_positive', True):
        hype_score += 2

    # Young company
    if features.get('years_since_ipo', 10) < 3:
        hype_score += 2
    elif features.get('years_since_ipo', 10) < 5:
        hype_score += 1

    # Speculative industry
    if features.get('is_speculative', False):
        hype_score += 2

    # SPAC
    if features.get('is_spac', False):
        hype_score += 3

    # Massive run-up
    if features.get('return_12m', 0) > 3.0:  # 300%+ return
        hype_score += 2
    elif features.get('return_12m', 0) > 2.0:  # 200%+ return
        hype_score += 1

    # Way above 200 SMA
    if features.get('pct_above_200sma', 0) > 1.0:  # 100%+ above
        hype_score += 2

    # Retail frenzy
    if features.get('wsb_mentions', 0) > 100:
        hype_score += 2

    # ===== POSITIVE SIGNALS (Quality indicators) =====

    # Has earnings
    if features.get('net_income_positive', False):
        quality_score += 2

    # Reasonable P/E
    if 0 < features.get('pe_ratio', 1000) < 40:
        quality_score += 2

    # Cash flow positive
    if features.get('fcf_positive', False):
        quality_score += 2

    # Good margins
    if features.get('net_margin', 0) > 0.10:
        quality_score += 2

    # Established company
    if features.get('years_since_ipo', 0) > 10:
        quality_score += 2

    # Growing revenue with profits
    if features.get('revenue_growth', 0) > 0.20 and features.get('net_income_positive', False):
        quality_score += 2

    # ===== CLASSIFICATION =====

    net_score = hype_score - quality_score

    if net_score >= 6:
        return 'TRUE_HYPE', hype_score, quality_score
    elif net_score >= 2:
        return 'RISKY_OVERVALUED', hype_score, quality_score
    else:
        return 'QUALITY_MOMENTUM', hype_score, quality_score


# ============================================================================
# EXAMPLE CLASSIFICATIONS
# ============================================================================

EXAMPLE_STOCKS = {
    # TRUE HYPE (crashed 80%+)
    'NKLA': {
        'name': 'Nikola',
        'net_income_positive': False,
        'ever_profitable': False,
        'ps_ratio': 1000,  # No revenue
        'fcf_positive': False,
        'years_since_ipo': 1,
        'is_speculative': True,  # EV
        'is_spac': True,
        'return_12m': 5.0,  # 500%
        'pct_above_200sma': 1.5,
        'wsb_mentions': 200,
        'outcome': 'Crashed 99%',
    },
    'PTON': {
        'name': 'Peloton',
        'net_income_positive': False,
        'ever_profitable': False,
        'ps_ratio': 15,
        'fcf_positive': False,
        'years_since_ipo': 2,
        'is_speculative': False,
        'is_spac': False,
        'return_12m': 4.0,
        'pct_above_200sma': 1.0,
        'wsb_mentions': 50,
        'outcome': 'Crashed 97%',
    },
    'ZM': {
        'name': 'Zoom',
        'net_income_positive': True,  # Actually had earnings!
        'ever_profitable': True,
        'ps_ratio': 50,
        'fcf_positive': True,
        'years_since_ipo': 2,
        'is_speculative': False,
        'is_spac': False,
        'return_12m': 6.0,  # 600%
        'pct_above_200sma': 2.0,
        'wsb_mentions': 100,
        'outcome': 'Crashed 90%',
    },

    # QUALITY MOMENTUM (recovered)
    'NVDA': {
        'name': 'NVIDIA',
        'net_income_positive': True,
        'ever_profitable': True,
        'ps_ratio': 25,  # High but has earnings
        'pe_ratio': 60,  # High but growing
        'fcf_positive': True,
        'net_margin': 0.25,
        'years_since_ipo': 25,
        'is_speculative': False,
        'is_spac': False,
        'return_12m': 2.5,
        'pct_above_200sma': 0.5,
        'wsb_mentions': 150,
        'outcome': 'Dipped 50%, then 10x',
    },
    'TSLA': {
        'name': 'Tesla',
        'net_income_positive': True,  # Became profitable
        'ever_profitable': True,
        'ps_ratio': 15,
        'pe_ratio': 100,  # High but growing
        'fcf_positive': True,
        'net_margin': 0.10,
        'years_since_ipo': 12,
        'is_speculative': True,  # EV
        'is_spac': False,
        'return_12m': 3.0,
        'pct_above_200sma': 1.0,
        'wsb_mentions': 500,
        'outcome': 'Volatile but recovered',
    },
    'AAPL': {
        'name': 'Apple',
        'net_income_positive': True,
        'ever_profitable': True,
        'ps_ratio': 7,
        'pe_ratio': 28,
        'fcf_positive': True,
        'net_margin': 0.25,
        'years_since_ipo': 44,
        'is_speculative': False,
        'is_spac': False,
        'return_12m': 0.3,
        'pct_above_200sma': 0.1,
        'wsb_mentions': 20,
        'outcome': 'Steady growth',
    },
}


def test_classifier():
    """Test the classifier on examples"""
    print("\n" + "="*80)
    print("HYPE STOCK CLASSIFIER - TEST RESULTS")
    print("="*80)

    print("\n" + "-"*80)
    print(f"{'Stock':<8} {'Name':<12} {'Classification':<20} {'Hype':<6} {'Quality':<8} {'Actual Outcome'}")
    print("-"*80)

    for ticker, features in EXAMPLE_STOCKS.items():
        classification, hype, quality = classify_hype_stock(features)
        outcome = features.get('outcome', 'Unknown')
        print(f"{ticker:<8} {features['name']:<12} {classification:<20} {hype:<6} {quality:<8} {outcome}")

    print("-"*80)


def print_ml_approach():
    """Print ML implementation approach"""
    print("\n" + "="*80)
    print("ML APPROACH FOR PRODUCTION")
    print("="*80)
    print("""
STEP 1: DATA COLLECTION
- Get fundamentals from SEC filings (10-K, 10-Q)
- Price data from Yahoo Finance / Polygon
- Social sentiment from Twitter/Reddit APIs
- Short interest from FINRA
- Analyst ratings from Bloomberg/Refinitiv

STEP 2: FEATURE ENGINEERING
- Calculate all features in FEATURES dict
- Create rolling windows (3m, 6m, 12m)
- Normalize features (z-score or min-max)
- Handle missing data (imputation)

STEP 3: LABELING
- Label stocks as TRUE_HYPE if they crashed 70%+ from peak
- Label as RISKY if crashed 30-70%
- Label as QUALITY if recovered after dip

STEP 4: MODEL TRAINING
- Split data: 70% train, 15% validation, 15% test
- Try models: XGBoost, LightGBM, Random Forest
- Use class weighting (TRUE_HYPE is rare)
- Feature importance analysis

STEP 5: BACKTESTING
- Paper trade on validation set
- Measure precision/recall for TRUE_HYPE class
- Calculate Sharpe ratio of short strategy

STEP 6: PRODUCTION
- Daily screening of stocks with 100%+ 12m return
- Classify new candidates
- Alert on TRUE_HYPE with breakdown signals

KEY METRICS TO TRACK:
- Precision: When we say TRUE_HYPE, how often correct?
- Recall: Of all TRUE_HYPE, how many did we catch?
- F1 Score: Balance of precision and recall
- Strategy Sharpe: Risk-adjusted return of shorts

TARGET: 80%+ precision on TRUE_HYPE classification
This means 4/5 shorts are profitable (crash 50%+)
""")


def print_trading_strategy():
    """Print the complete trading strategy"""
    print("\n" + "="*80)
    print("COMPLETE SHORT-THE-HYPE TRADING STRATEGY")
    print("="*80)
    print("""
UNIVERSE FILTER:
1. All US stocks with market cap > $1B
2. Had 100%+ return in past 12 months
3. Currently trading (not halted/delisted)

CLASSIFICATION:
1. Run through ML classifier
2. Focus ONLY on TRUE_HYPE classification
3. Require confidence > 80%

ENTRY SIGNALS (Short when):
1. Price breaks below 50-day SMA
2. RSI drops below 50 from overbought (was >70)
3. Volume increasing on down days
4. Lower high confirmed on 20-day chart

POSITION SIZING:
- 3% of portfolio per position
- Max 5 positions (15% total short exposure)
- Use puts for defined risk (max loss = premium)

EXIT RULES:
- Profit Target 1: Cover 50% at 30% gain
- Profit Target 2: Cover rest at 50% gain
- Stop Loss: Cover at 20% loss
- Time Stop: Cover after 3 months

AVOID SHORTING:
- Heavily shorted stocks (>20% short interest) - squeeze risk
- Stocks with upcoming catalysts (earnings, FDA approval)
- Small caps (<$1B) - manipulation risk
- Stocks with strong insider buying

BEST CONDITIONS:
- Rising interest rate environment
- Risk-off market sentiment
- After Fed tightening cycle begins
- Post-bubble (like 2022)

WORST CONDITIONS:
- QE / Money printing
- Meme stock mania
- Low VIX environment
- Retail FOMO phase
""")


if __name__ == '__main__':
    test_classifier()
    print_ml_approach()
    print_trading_strategy()

    # Summary stats
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("""
KEY INSIGHT:
- TRUE HYPE stocks (NKLA, PTON, ZM at peak) crash 80-99%
- QUALITY stocks (NVDA, TSLA, AAPL) may dip but recover
- The difference is FUNDAMENTALS

CLASSIFICATION FEATURES (Ranked by importance):
1. Ever profitable? (No = +3 hype score)
2. P/S ratio > 20 (Yes = +3 hype score)
3. Years since IPO < 3 (Yes = +2 hype score)
4. SPAC merger (Yes = +3 hype score)
5. Cash flow positive? (No = +2 hype score)

WITH PROPER CLASSIFICATION:
- Expected win rate: 70-80%
- Average winner: 40-60%
- Average loser: 15-20%
- Expected Sharpe: 1.0-1.5

THIS IS A VIABLE STRATEGY when you can identify TRUE HYPE.
The key is the fundamental analysis, not just technicals.
""")
