"""
GLOBAL ROTATIONAL STRATEGY - INTERACTIVE BROKERS LIVE TRADING
=============================================================

This script connects to IBKR TWS/Gateway and executes the Global Rotational
strategy with the optimal configuration:

- 21 Asset Universe
- 45-day Lookback
- Daily Rebalancing
- Top 3 Holdings (equally weighted)
- Regime Filter (cash when all negative)

USAGE:
1. Open TWS or IB Gateway
2. Enable API (port 7497 for paper, 7496 for live)
3. Run: python ibkr_live_trading.py

Author: Claude Code Assistant
Strategy: Global Rotational Momentum
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

CONFIG = {
    # Strategy Parameters (Optimal from backtest)
    'lookback_days': 45,
    'top_n': 3,
    'use_regime_filter': True,

    # IBKR Connection
    'host': '127.0.0.1',
    'port': 7497,  # 7497 for paper, 7496 for live
    'client_id': 1,

    # Position Sizing
    'max_position_pct': 0.33,  # 33% per position
    'cash_buffer': 0.02,  # Keep 2% cash for fees
}

# Asset Universe (21 assets)
UNIVERSE = {
    # Crypto - IBKR symbols
    'BTC': {'type': 'CRYPTO', 'exchange': 'PAXOS', 'name': 'Bitcoin'},
    'ETH': {'type': 'CRYPTO', 'exchange': 'PAXOS', 'name': 'Ethereum'},

    # Use COIN as SOL proxy since IBKR doesn't have SOL
    'COIN': {'type': 'STK', 'exchange': 'SMART', 'name': 'Coinbase (SOL proxy)'},

    # US Indices
    'SPY': {'type': 'STK', 'exchange': 'SMART', 'name': 'S&P 500'},
    'QQQ': {'type': 'STK', 'exchange': 'SMART', 'name': 'Nasdaq 100'},
    'IWM': {'type': 'STK', 'exchange': 'SMART', 'name': 'Russell 2000'},

    # Sector ETFs
    'XLK': {'type': 'STK', 'exchange': 'SMART', 'name': 'Technology'},
    'XLF': {'type': 'STK', 'exchange': 'SMART', 'name': 'Financials'},
    'XLE': {'type': 'STK', 'exchange': 'SMART', 'name': 'Energy'},
    'XLV': {'type': 'STK', 'exchange': 'SMART', 'name': 'Healthcare'},

    # Individual Stocks
    'NVDA': {'type': 'STK', 'exchange': 'SMART', 'name': 'NVIDIA'},
    'AAPL': {'type': 'STK', 'exchange': 'SMART', 'name': 'Apple'},
    'MSFT': {'type': 'STK', 'exchange': 'SMART', 'name': 'Microsoft'},
    'AMZN': {'type': 'STK', 'exchange': 'SMART', 'name': 'Amazon'},

    # International
    'EFA': {'type': 'STK', 'exchange': 'SMART', 'name': 'Developed Markets'},
    'EEM': {'type': 'STK', 'exchange': 'SMART', 'name': 'Emerging Markets'},

    # Commodities
    'GLD': {'type': 'STK', 'exchange': 'SMART', 'name': 'Gold'},
    'USO': {'type': 'STK', 'exchange': 'SMART', 'name': 'Oil'},
    'DBA': {'type': 'STK', 'exchange': 'SMART', 'name': 'Agriculture'},

    # Bonds/Safe Haven
    'TLT': {'type': 'STK', 'exchange': 'SMART', 'name': 'Long Treasury'},
    'UUP': {'type': 'STK', 'exchange': 'SMART', 'name': 'US Dollar'},
}


class GlobalRotationalIBKR:
    """
    Live trading implementation for Global Rotational Strategy on IBKR
    """

    def __init__(self):
        self.ib = None
        self.connected = False
        self.positions = {}
        self.prices = {}

    def connect(self):
        """Connect to IBKR TWS/Gateway"""
        try:
            from ib_insync import IB

            self.ib = IB()
            self.ib.connect(
                CONFIG['host'],
                CONFIG['port'],
                clientId=CONFIG['client_id']
            )
            self.connected = True
            logger.info("Connected to IBKR")
            return True

        except ImportError:
            logger.error("ib_insync not installed. Run: pip install ib_insync")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib:
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IBKR")

    def get_historical_data(self, symbol, days=60):
        """Get historical price data for momentum calculation"""
        from ib_insync import Stock, Crypto

        info = UNIVERSE[symbol]

        if info['type'] == 'CRYPTO':
            contract = Crypto(symbol, 'PAXOS', 'USD')
        else:
            contract = Stock(symbol, 'SMART', 'USD')

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr=f'{days} D',
            barSizeSetting='1 day',
            whatToShow='TRADES' if info['type'] != 'CRYPTO' else 'MIDPOINT',
            useRTH=True,
            formatDate=1
        )

        if bars:
            df = pd.DataFrame(bars)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            return df['close']

        return None

    def calculate_momentum_scores(self):
        """Calculate risk-adjusted momentum for all assets"""
        logger.info("Calculating momentum scores...")

        scores = {}
        lookback = CONFIG['lookback_days']

        for symbol in UNIVERSE:
            try:
                prices = self.get_historical_data(symbol, days=lookback + 10)

                if prices is None or len(prices) < lookback:
                    logger.warning(f"Insufficient data for {symbol}")
                    continue

                # Calculate momentum score
                returns = (prices.iloc[-1] / prices.iloc[-lookback]) - 1
                volatility = prices.pct_change().std() * np.sqrt(252)

                score = returns / (volatility + 1e-9)
                scores[symbol] = {
                    'score': score,
                    'return': returns * 100,
                    'volatility': volatility * 100,
                    'price': prices.iloc[-1]
                }

                logger.info(f"  {symbol}: Score={score:.2f}, Return={returns*100:.1f}%, Vol={volatility*100:.1f}%")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.error(f"Error calculating {symbol}: {e}")

        return scores

    def get_current_positions(self):
        """Get current portfolio positions"""
        positions = {}

        for pos in self.ib.positions():
            symbol = pos.contract.symbol
            if symbol in UNIVERSE:
                positions[symbol] = {
                    'shares': pos.position,
                    'avg_cost': pos.avgCost,
                    'value': pos.position * pos.avgCost
                }

        return positions

    def get_account_value(self):
        """Get total account value"""
        account = self.ib.accountSummary()

        for item in account:
            if item.tag == 'NetLiquidation':
                return float(item.value)

        return 0

    def rank_assets(self, scores):
        """Rank assets by momentum score and select top N"""

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)

        # Apply regime filter
        if CONFIG['use_regime_filter']:
            positive_assets = [s for s in ranked if s[1]['score'] > 0]
            if len(positive_assets) == 0:
                logger.warning("All assets have negative momentum - going to CASH")
                return []
            ranked = positive_assets

        # Select top N
        top_n = ranked[:CONFIG['top_n']]

        logger.info("\nTOP RANKED ASSETS:")
        for i, (symbol, data) in enumerate(top_n, 1):
            logger.info(f"  {i}. {symbol} ({UNIVERSE[symbol]['name']}): "
                       f"Score={data['score']:.2f}, Return={data['return']:.1f}%")

        return [s[0] for s in top_n]

    def calculate_target_positions(self, target_symbols, account_value):
        """Calculate target position sizes"""

        if not target_symbols:
            return {}

        # Equal weight with cash buffer
        available_capital = account_value * (1 - CONFIG['cash_buffer'])
        per_position = available_capital / len(target_symbols)

        targets = {}
        for symbol in target_symbols:
            targets[symbol] = per_position

        return targets

    def execute_rebalance(self, target_positions, scores):
        """Execute trades to rebalance portfolio"""
        from ib_insync import Stock, Crypto, MarketOrder

        current_positions = self.get_current_positions()

        # Calculate what to sell
        sells = []
        for symbol, pos in current_positions.items():
            if symbol not in target_positions:
                sells.append((symbol, pos['shares'], 'CLOSE'))

        # Calculate what to buy
        buys = []
        for symbol, target_value in target_positions.items():
            current_value = current_positions.get(symbol, {}).get('value', 0)
            price = scores.get(symbol, {}).get('price', 0)

            if price > 0:
                target_shares = int(target_value / price)
                current_shares = current_positions.get(symbol, {}).get('shares', 0)

                if target_shares > current_shares:
                    buys.append((symbol, target_shares - current_shares, price))
                elif target_shares < current_shares:
                    sells.append((symbol, current_shares - target_shares, 'REDUCE'))

        # Execute sells first (to free up capital)
        for symbol, shares, reason in sells:
            logger.info(f"SELL {shares} {symbol} ({reason})")

            info = UNIVERSE[symbol]
            if info['type'] == 'CRYPTO':
                contract = Crypto(symbol, 'PAXOS', 'USD')
            else:
                contract = Stock(symbol, 'SMART', 'USD')

            order = MarketOrder('SELL', abs(shares))

            try:
                trade = self.ib.placeOrder(contract, order)
                logger.info(f"  Order placed: {trade.order.orderId}")
            except Exception as e:
                logger.error(f"  Error placing sell order: {e}")

        # Wait for sells to settle
        time.sleep(2)

        # Execute buys
        for symbol, shares, price in buys:
            logger.info(f"BUY {shares} {symbol} @ ~${price:.2f}")

            info = UNIVERSE[symbol]
            if info['type'] == 'CRYPTO':
                contract = Crypto(symbol, 'PAXOS', 'USD')
            else:
                contract = Stock(symbol, 'SMART', 'USD')

            order = MarketOrder('BUY', shares)

            try:
                trade = self.ib.placeOrder(contract, order)
                logger.info(f"  Order placed: {trade.order.orderId}")
            except Exception as e:
                logger.error(f"  Error placing buy order: {e}")

    def run_daily_check(self, execute=False):
        """
        Run daily momentum check and rebalance

        Args:
            execute: If True, actually execute trades. If False, just show what would happen.
        """
        logger.info("="*60)
        logger.info("GLOBAL ROTATIONAL STRATEGY - DAILY CHECK")
        logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60)

        if not self.connected:
            if not self.connect():
                return

        # 1. Calculate momentum scores
        scores = self.calculate_momentum_scores()

        if not scores:
            logger.error("Failed to calculate scores")
            return

        # 2. Rank and select top assets
        target_symbols = self.rank_assets(scores)

        # 3. Get account value
        account_value = self.get_account_value()
        logger.info(f"\nAccount Value: ${account_value:,.2f}")

        # 4. Calculate target positions
        target_positions = self.calculate_target_positions(target_symbols, account_value)

        logger.info("\nTARGET POSITIONS:")
        for symbol, value in target_positions.items():
            pct = (value / account_value) * 100
            logger.info(f"  {symbol}: ${value:,.2f} ({pct:.1f}%)")

        # 5. Get current positions
        current_positions = self.get_current_positions()

        logger.info("\nCURRENT POSITIONS:")
        for symbol, pos in current_positions.items():
            logger.info(f"  {symbol}: {pos['shares']} shares @ ${pos['avg_cost']:.2f}")

        # 6. Determine if rebalance needed
        current_symbols = set(current_positions.keys())
        target_symbol_set = set(target_symbols)

        if current_symbols == target_symbol_set:
            logger.info("\nNo rebalance needed - holdings match targets")
        else:
            logger.info("\nREBALANCE REQUIRED:")
            logger.info(f"  Exit: {current_symbols - target_symbol_set}")
            logger.info(f"  Enter: {target_symbol_set - current_symbols}")

            if execute:
                logger.info("\nEXECUTING TRADES...")
                self.execute_rebalance(target_positions, scores)
            else:
                logger.info("\n[DRY RUN] Set execute=True to place orders")


def main():
    """Main entry point"""

    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║      GLOBAL ROTATIONAL STRATEGY - INTERACTIVE BROKERS            ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║  Configuration:                                                  ║
    ║    - Lookback: 45 days                                          ║
    ║    - Rebalance: Daily                                           ║
    ║    - Holdings: Top 3 assets                                     ║
    ║    - Universe: 21 assets (Crypto, Stocks, ETFs, Commodities)    ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    strategy = GlobalRotationalIBKR()

    try:
        # Run daily check (dry run by default)
        strategy.run_daily_check(execute=False)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        strategy.disconnect()


if __name__ == "__main__":
    main()
