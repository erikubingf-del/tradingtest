# Running the Individual Stock Analysis Locally

Due to environment restrictions, this analysis script needs to be run on your local machine.

## Quick Start

```bash
# 1. Install dependencies
pip install yfinance pandas numpy

# 2. Run the analysis
python individual_stocks_analysis.py
```

## What the Script Does

1. **Fetches 10 years of data** for 70+ stocks (hype stocks, quality stocks, various sectors)
2. **Identifies extreme momentum events** (100%+ returns in 12 months)
3. **Calculates forward returns** (1m, 3m, 6m, 12m) after each event
4. **Groups by momentum bucket** (100-150%, 150-200%, 200-300%, etc.)
5. **Calculates crash probability** for each bucket
6. **Compares hype stocks vs quality stocks**

## Expected Output

The script will:
- Fetch data for ~70 stocks from Yahoo Finance
- Find all instances of 100%+ 12-month momentum
- Calculate what happened next (forward returns)
- Show probability of decline by momentum bucket
- Compare crashed stocks (ZM, PTON, etc.) vs quality stocks (AAPL, MSFT, etc.)

## Files Created

- `individual_stocks_momentum_events.csv` - All extreme momentum events with forward returns
- `individual_stocks_bucket_analysis.csv` - Summary statistics by momentum bucket

## Key Findings from Previous Analysis

Based on index/commodity analysis (12,682 events over 44 years):

| Momentum Bucket | 6-Month Decline Probability | Avg Forward Return |
|-----------------|-----------------------------|--------------------|
| 100-150%        | **70.3%**                   | -6.2%              |
| 150-200%        | 66.2%                       | -4.8%              |
| 200-300%        | 30.0%                       | +5.2%              |
| 300%+           | 31.5%                       | +7.1%              |

**Key Insight:** 100-150% momentum is the sweet spot for shorting (70% decline probability).
Higher momentum (200%+) tends to continue - avoid shorting these!

## Stock Categories

### Hype Stocks (Expected to crash hard):
- COVID bubble: ZM, PTON, DOCU, TDOC, ROKU
- EV bubble: RIVN, LCID, NKLA
- Fintech: COIN, AFRM, HOOD, UPST, SOFI
- Tech: SNOW, PLTR, U, DASH

### Quality Stocks (May dip but recover):
- Big tech: AAPL, MSFT, GOOGL, AMZN, META
- Semis: NVDA, AMD, TSM
- Finance: JPM, V, MA

## Related Files

- `hype_classifier_framework.py` - ML framework for classifying hype vs quality stocks
- `comprehensive_short_analysis.py` - Combined analysis using existing data
- `momentum_crash_probability.py` - Index/commodity probability analysis
- `PROBABILITY_ANALYSIS_RESULTS.md` - Summary of probability findings
