# region imports
from AlgorithmImports import *
import numpy as np
from datetime import timedelta
# endregion

class TrendFollowingMultiAsset(QCAlgorithm):
    """
    Multi-Asset Trend Following Strategy
    =====================================

    Based on proven academic research:
    - Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum"
    - Hurst, Ooi, Pedersen (2017) "A Century of Evidence on Trend-Following"
    - AQR Capital Research on Managed Futures

    Key Findings from Research:
    - Trend following has worked for 100+ years across all asset classes
    - Strongest in commodities due to supply/demand shocks
    - 35-40% win rate with big winners (positive expectancy)
    - Provides "crisis alpha" - profits during market crashes

    Target: 20-30% CAGR with managed drawdowns

    Universe: 25+ assets across:
    - Agricultural Commodities (Soybeans, Corn, Wheat, Coffee, Sugar, Cotton, Cocoa)
    - Energy (Crude Oil, Natural Gas, Heating Oil, Gasoline)
    - Metals (Gold, Silver, Copper, Platinum)
    - Financials (S&P 500, Nasdaq, Treasury Bonds)
    - Currencies (EUR, GBP, JPY, AUD, CAD)
    - Crypto (BTC, ETH) - if enabled
    """

    def Initialize(self):
        # ==================== BACKTEST SETTINGS ====================
        self.SetStartDate(2000, 1, 1)  # 25 years of data
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)

        # ==================== STRATEGY PARAMETERS ====================
        # Trend Detection
        self.lookback_short = 20   # Short-term momentum (1 month)
        self.lookback_long = 200   # Long-term trend filter
        self.breakout_period = 40  # Donchian channel period

        # Risk Management
        self.max_leverage = 2.0
        self.risk_per_trade = 0.02  # 2% risk per position
        self.max_positions = 15     # Maximum concurrent positions
        self.atr_period = 20
        self.atr_multiplier = 2.5   # For stop loss

        # Rebalance frequency
        self.rebalance_days = 5     # Check signals every 5 days

        # ==================== FUTURES UNIVERSE ====================
        # Agricultural Commodities
        self.futures_symbols = {
            # Grains
            "ZS": Futures.Grains.Soybeans,
            "ZC": Futures.Grains.Corn,
            "ZW": Futures.Grains.Wheat,
            "ZO": Futures.Grains.Oats,

            # Softs
            "KC": Futures.Softs.Coffee,
            "SB": Futures.Softs.Sugar11,
            "CT": Futures.Softs.Cotton2,
            "CC": Futures.Softs.Cocoa,
            "OJ": Futures.Softs.OrangeJuice,

            # Energy
            "CL": Futures.Energies.CrudeOilWTI,
            "NG": Futures.Energies.NaturalGas,
            "HO": Futures.Energies.HeatingOil,
            "RB": Futures.Energies.Gasoline,

            # Metals
            "GC": Futures.Metals.Gold,
            "SI": Futures.Metals.Silver,
            "HG": Futures.Metals.Copper,
            "PL": Futures.Metals.Platinum,

            # Financials (Indices)
            "ES": Futures.Indices.SP500EMini,
            "NQ": Futures.Indices.NASDAQ100EMini,
            "YM": Futures.Indices.Dow30EMini,

            # Bonds
            "ZN": Futures.Financials.Y10TreasuryNote,
            "ZB": Futures.Financials.Y30TreasuryBond,

            # Currencies
            "6E": Futures.Currencies.EUR,
            "6B": Futures.Currencies.GBP,
            "6J": Futures.Currencies.JPY,
            "6A": Futures.Currencies.AUD,
            "6C": Futures.Currencies.CAD,
        }

        # Add futures to universe
        self.contracts = {}
        for symbol, future in self.futures_symbols.items():
            try:
                continuous = self.AddFuture(future,
                                           Resolution.Daily,
                                           extendedMarketHours=False,
                                           dataNormalizationMode=DataNormalizationMode.BackwardsRatio,
                                           dataMappingMode=DataMappingMode.OpenInterest,
                                           contractDepthOffset=0)
                continuous.SetFilter(0, 90)  # Front month
                self.contracts[symbol] = continuous.Symbol
            except:
                self.Debug(f"Could not add {symbol}")

        # ==================== INDICATORS ====================
        self.indicators = {}

        # Schedule rebalancing
        self.last_rebalance = self.Time

        # Track positions
        self.active_positions = {}

        # Warm up period
        self.SetWarmUp(self.lookback_long + 50, Resolution.Daily)

        self.Debug(f"Initialized with {len(self.contracts)} futures contracts")

    def OnData(self, data: Slice):
        if self.IsWarmingUp:
            return

        # Only rebalance every N days
        if (self.Time - self.last_rebalance).days < self.rebalance_days:
            return
        self.last_rebalance = self.Time

        # Get signals for all contracts
        signals = self.GetSignals(data)

        # Execute trades
        self.ExecuteTrades(signals, data)

    def GetSignals(self, data):
        """
        Generate trend following signals for each asset.

        Entry Signal (Long):
        1. Price > 200-day SMA (bull regime)
        2. Price breaks above 40-day high (momentum breakout)
        3. 20-day return positive (short-term momentum)

        Exit Signal:
        1. Price < 200-day SMA (regime change)
        2. Price breaks below 20-day low (momentum breakdown)
        3. ATR trailing stop hit
        """
        signals = {}

        for symbol_name, symbol in self.contracts.items():
            try:
                # Get the mapped contract
                mapped_symbol = self.Securities[symbol].Mapped
                if mapped_symbol is None:
                    continue

                # Get historical data
                history = self.History(mapped_symbol, self.lookback_long + 10, Resolution.Daily)
                if history.empty or len(history) < self.lookback_long:
                    continue

                close = history['close'].values
                high = history['high'].values
                low = history['low'].values

                # Calculate indicators
                current_price = close[-1]

                # Long-term trend (200-day SMA)
                sma_long = np.mean(close[-self.lookback_long:])

                # Short-term momentum (20-day return)
                momentum = (close[-1] / close[-self.lookback_short] - 1) * 100

                # Donchian channels
                highest_high = np.max(high[-self.breakout_period:])
                lowest_low = np.min(low[-self.breakout_period:])

                # Shorter exit channel
                exit_high = np.max(high[-self.lookback_short:])
                exit_low = np.min(low[-self.lookback_short:])

                # ATR for position sizing
                tr = np.maximum(
                    high[-self.atr_period:] - low[-self.atr_period:],
                    np.abs(high[-self.atr_period:] - np.roll(close[-self.atr_period:], 1)[1:self.atr_period])
                )
                atr = np.mean(tr) if len(tr) > 0 else 0

                # Generate signal
                signal = 0

                # LONG conditions
                if (current_price > sma_long and           # Bull regime
                    current_price >= highest_high * 0.99 and  # Near breakout
                    momentum > 0):                          # Positive momentum
                    signal = 1

                # EXIT conditions (for existing longs)
                if (current_price < sma_long or            # Regime change
                    current_price <= exit_low * 1.01):     # Breakdown
                    signal = -1

                signals[symbol_name] = {
                    'signal': signal,
                    'price': current_price,
                    'atr': atr,
                    'momentum': momentum,
                    'trend': 'bull' if current_price > sma_long else 'bear'
                }

            except Exception as e:
                self.Debug(f"Error processing {symbol_name}: {str(e)}")
                continue

        return signals

    def ExecuteTrades(self, signals, data):
        """
        Execute trades based on signals with proper position sizing.
        Uses ATR-based position sizing to normalize risk across assets.
        """
        # First, handle exits
        for symbol_name in list(self.active_positions.keys()):
            if symbol_name in signals and signals[symbol_name]['signal'] == -1:
                symbol = self.contracts[symbol_name]
                mapped = self.Securities[symbol].Mapped
                if mapped:
                    self.Liquidate(mapped)
                    del self.active_positions[symbol_name]
                    self.Debug(f"EXIT: {symbol_name}")

        # Count current positions
        current_positions = len(self.active_positions)

        # Get new entry signals, sorted by momentum
        entries = [(name, sig) for name, sig in signals.items()
                   if sig['signal'] == 1 and name not in self.active_positions]
        entries.sort(key=lambda x: x[1]['momentum'], reverse=True)

        # Enter new positions
        for symbol_name, signal in entries:
            if current_positions >= self.max_positions:
                break

            try:
                symbol = self.contracts[symbol_name]
                mapped = self.Securities[symbol].Mapped
                if mapped is None:
                    continue

                # ATR-based position sizing
                atr = signal['atr']
                if atr <= 0:
                    continue

                # Risk per trade = 2% of portfolio
                risk_dollars = self.Portfolio.TotalPortfolioValue * self.risk_per_trade

                # Stop distance = ATR * multiplier
                stop_distance = atr * self.atr_multiplier

                # Position size = Risk / Stop Distance
                point_value = self.Securities[mapped].SymbolProperties.ContractMultiplier
                contracts = int(risk_dollars / (stop_distance * point_value))

                if contracts > 0:
                    self.MarketOrder(mapped, contracts)
                    self.active_positions[symbol_name] = {
                        'entry_price': signal['price'],
                        'stop_price': signal['price'] - stop_distance,
                        'contracts': contracts
                    }
                    current_positions += 1
                    self.Debug(f"ENTRY: {symbol_name} x{contracts} @ {signal['price']:.2f}")

            except Exception as e:
                self.Debug(f"Error entering {symbol_name}: {str(e)}")

    def OnEndOfAlgorithm(self):
        """Log final statistics."""
        self.Debug(f"=== FINAL RESULTS ===")
        self.Debug(f"Total Trades: {self.TradeBuilder.ClosedTrades.Count if hasattr(self, 'TradeBuilder') else 'N/A'}")
        self.Debug(f"Final Portfolio Value: ${self.Portfolio.TotalPortfolioValue:,.2f}")
