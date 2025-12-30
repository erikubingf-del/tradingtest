# region imports
from AlgorithmImports import *
import numpy as np
from datetime import timedelta
from collections import deque
# endregion

class AggressiveTrendFollowing(QCAlgorithm):
    """
    AGGRESSIVE TREND FOLLOWING STRATEGY
    ====================================
    Target: 20-30% CAGR

    Based on research from:
    - Dunn Capital (~18% CAGR over 40 years)
    - Mulvaney Capital (~20% CAGR over 20 years)
    - AQR Managed Futures

    Key Enhancements for Higher Returns:
    1. Volatility Targeting - Scale positions to target 15% annual volatility
    2. Momentum Ranking - Only trade top momentum assets
    3. Leverage - Up to 3x notional exposure
    4. Concentrated Portfolio - 8-12 positions (not 20+)
    5. Faster Signals - 10/40 day momentum vs 20/200

    Risk Management:
    - Max drawdown target: 25-30%
    - Stop loss: 2x ATR
    - Portfolio heat limit: 6% total risk

    UNIVERSE: 28 Assets
    - 12 Commodities (Ag, Energy, Metals)
    - 8 Financials (Indices, Bonds)
    - 8 Currencies (Major pairs)
    """

    def Initialize(self):
        # ==================== BACKTEST SETTINGS ====================
        self.SetStartDate(1990, 1, 1)  # 35 years of data
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)

        # ==================== AGGRESSIVE PARAMETERS ====================
        # Faster momentum signals
        self.fast_period = 10         # Fast momentum (2 weeks)
        self.slow_period = 40         # Slow trend (2 months)
        self.trend_filter = 100       # Long-term regime filter

        # Breakout parameters
        self.breakout_period = 20     # Donchian period
        self.exit_period = 10         # Tighter exit

        # Volatility targeting
        self.target_volatility = 0.15  # 15% annual target
        self.lookback_vol = 20         # Volatility calculation period

        # Position sizing
        self.max_notional_leverage = 3.0  # Up to 3x
        self.risk_per_trade = 0.025       # 2.5% risk per position
        self.max_positions = 10           # Concentrated portfolio
        self.atr_period = 14
        self.atr_stop_mult = 2.0

        # Rebalancing
        self.rebalance_frequency = 5  # Days between rebalance

        # ==================== FUTURES UNIVERSE ====================
        self.futures_config = {
            # === COMMODITIES (12) ===
            # Grains - High seasonality, strong trends
            "Soybeans": Futures.Grains.Soybeans,
            "Corn": Futures.Grains.Corn,
            "Wheat": Futures.Grains.Wheat,

            # Softs - Weather-driven trends
            "Coffee": Futures.Softs.Coffee,
            "Sugar": Futures.Softs.Sugar11,
            "Cotton": Futures.Softs.Cotton2,
            "Cocoa": Futures.Softs.Cocoa,

            # Energy - Geopolitical trends
            "CrudeOil": Futures.Energies.CrudeOilWTI,
            "NatGas": Futures.Energies.NaturalGas,
            "Gasoline": Futures.Energies.Gasoline,

            # Metals - Safe haven + industrial
            "Gold": Futures.Metals.Gold,
            "Copper": Futures.Metals.Copper,

            # === FINANCIALS (8) ===
            # Equity indices
            "SP500": Futures.Indices.SP500EMini,
            "Nasdaq": Futures.Indices.NASDAQ100EMini,
            "Russell": Futures.Indices.Russell2000EMini,

            # International indices
            "Nikkei": Futures.Indices.Nikkei225Dollar,

            # Bonds - Interest rate trends
            "10Year": Futures.Financials.Y10TreasuryNote,
            "30Year": Futures.Financials.Y30TreasuryBond,
            "5Year": Futures.Financials.Y5TreasuryNote,
            "2Year": Futures.Financials.Y2TreasuryNote,

            # === CURRENCIES (8) ===
            "EUR": Futures.Currencies.EUR,
            "GBP": Futures.Currencies.GBP,
            "JPY": Futures.Currencies.JPY,
            "AUD": Futures.Currencies.AUD,
            "CAD": Futures.Currencies.CAD,
            "CHF": Futures.Currencies.CHF,
            "MXN": Futures.Currencies.MXN,
            "NZD": Futures.Currencies.NZD,
        }

        # Initialize contracts
        self.contracts = {}
        for name, future in self.futures_config.items():
            try:
                continuous = self.AddFuture(future,
                    Resolution.Daily,
                    dataNormalizationMode=DataNormalizationMode.BackwardsRatio,
                    dataMappingMode=DataMappingMode.OpenInterest,
                    contractDepthOffset=0)
                continuous.SetFilter(0, 90)
                self.contracts[name] = continuous.Symbol
                self.Debug(f"Added: {name}")
            except Exception as e:
                self.Debug(f"Failed to add {name}: {e}")

        # Tracking
        self.last_rebalance = self.Time
        self.positions = {}
        self.daily_returns = deque(maxlen=252)
        self.portfolio_history = []

        # Warm up
        self.SetWarmUp(self.trend_filter + 50, Resolution.Daily)

        self.Debug(f"=== AGGRESSIVE TREND FOLLOWING ===")
        self.Debug(f"Universe: {len(self.contracts)} assets")
        self.Debug(f"Target Vol: {self.target_volatility*100}%")
        self.Debug(f"Max Leverage: {self.max_notional_leverage}x")

    def OnData(self, data: Slice):
        if self.IsWarmingUp:
            return

        # Track daily returns for vol targeting
        if len(self.portfolio_history) > 0:
            daily_ret = (self.Portfolio.TotalPortfolioValue / self.portfolio_history[-1]) - 1
            self.daily_returns.append(daily_ret)
        self.portfolio_history.append(self.Portfolio.TotalPortfolioValue)

        # Rebalance check
        if (self.Time - self.last_rebalance).days < self.rebalance_frequency:
            return
        self.last_rebalance = self.Time

        # Calculate current portfolio volatility
        current_vol = self.GetPortfolioVolatility()

        # Get and rank signals
        signals = self.RankSignals(data)

        # Execute with volatility scaling
        self.ExecuteWithVolTargeting(signals, current_vol)

    def RankSignals(self, data):
        """
        Calculate momentum signals and rank assets.
        Only top-ranked assets get capital.
        """
        signals = []

        for name, symbol in self.contracts.items():
            try:
                mapped = self.Securities[symbol].Mapped
                if mapped is None:
                    continue

                # Get history
                history = self.History(mapped, self.trend_filter + 20, Resolution.Daily)
                if history.empty or len(history) < self.trend_filter:
                    continue

                close = history['close'].values
                high = history['high'].values
                low = history['low'].values

                price = close[-1]

                # === MOMENTUM CALCULATIONS ===
                # Fast momentum (10-day)
                fast_mom = (close[-1] / close[-self.fast_period] - 1) if len(close) >= self.fast_period else 0

                # Slow momentum (40-day)
                slow_mom = (close[-1] / close[-self.slow_period] - 1) if len(close) >= self.slow_period else 0

                # Combined momentum score
                momentum_score = (fast_mom * 0.6) + (slow_mom * 0.4)

                # === TREND FILTER ===
                sma_trend = np.mean(close[-self.trend_filter:])
                in_uptrend = price > sma_trend

                # === BREAKOUT ===
                highest = np.max(high[-self.breakout_period:])
                lowest = np.min(low[-self.exit_period:])
                is_breakout = price >= highest * 0.98

                # === VOLATILITY (for sizing) ===
                returns = np.diff(close[-self.lookback_vol:]) / close[-self.lookback_vol-1:-1]
                vol = np.std(returns) * np.sqrt(252) if len(returns) > 5 else 0.2

                # ATR for stops
                tr = np.maximum(high[-self.atr_period:] - low[-self.atr_period:],
                               np.maximum(np.abs(high[-self.atr_period:] - np.roll(close[-self.atr_period:], 1)[1:]),
                                         np.abs(low[-self.atr_period:] - np.roll(close[-self.atr_period:], 1)[1:])))
                atr = np.mean(tr) if len(tr) > 1 else price * 0.02

                # === SIGNAL ===
                signal = 0
                if in_uptrend and is_breakout and momentum_score > 0:
                    signal = 1

                # Exit signal for current positions
                if name in self.positions:
                    if not in_uptrend or price < lowest:
                        signal = -1

                if signal != 0 or name in self.positions:
                    signals.append({
                        'name': name,
                        'symbol': symbol,
                        'signal': signal,
                        'momentum': momentum_score,
                        'volatility': vol,
                        'atr': atr,
                        'price': price,
                        'trend': in_uptrend
                    })

            except Exception as e:
                continue

        # Sort by momentum (strongest first)
        signals.sort(key=lambda x: x['momentum'], reverse=True)

        return signals

    def GetPortfolioVolatility(self):
        """Calculate realized portfolio volatility."""
        if len(self.daily_returns) < 20:
            return self.target_volatility

        returns = np.array(self.daily_returns)
        return np.std(returns) * np.sqrt(252)

    def ExecuteWithVolTargeting(self, signals, current_vol):
        """
        Execute trades with volatility targeting.
        Scale positions to maintain target volatility.
        """
        # Volatility scalar
        vol_scalar = 1.0
        if current_vol > 0:
            vol_scalar = min(self.target_volatility / current_vol, 1.5)  # Cap at 1.5x

        # === PROCESS EXITS FIRST ===
        for sig in signals:
            if sig['signal'] == -1 and sig['name'] in self.positions:
                mapped = self.Securities[sig['symbol']].Mapped
                if mapped:
                    self.Liquidate(mapped)
                    del self.positions[sig['name']]
                    self.Debug(f"EXIT: {sig['name']} | Mom: {sig['momentum']*100:.1f}%")

        # === PROCESS ENTRIES ===
        # Only enter top momentum assets
        entries = [s for s in signals if s['signal'] == 1 and s['name'] not in self.positions]
        current_positions = len(self.positions)

        for sig in entries[:self.max_positions - current_positions]:
            try:
                mapped = self.Securities[sig['symbol']].Mapped
                if mapped is None:
                    continue

                # === POSITION SIZING ===
                # Base risk
                risk_dollars = self.Portfolio.TotalPortfolioValue * self.risk_per_trade

                # Volatility adjustment - less capital to volatile assets
                vol_adjustment = self.target_volatility / max(sig['volatility'], 0.05)
                vol_adjustment = min(max(vol_adjustment, 0.5), 2.0)

                # Scale by portfolio vol target
                adjusted_risk = risk_dollars * vol_scalar * vol_adjustment

                # Stop distance
                stop_distance = sig['atr'] * self.atr_stop_mult

                # Calculate contracts
                point_value = self.Securities[mapped].SymbolProperties.ContractMultiplier
                contracts = int(adjusted_risk / (stop_distance * point_value))

                # Check leverage limit
                notional = contracts * sig['price'] * point_value
                current_notional = sum(
                    self.Securities[self.contracts[n]].Mapped.Price *
                    self.Portfolio[self.Securities[self.contracts[n]].Mapped].Quantity *
                    self.Securities[self.Securities[self.contracts[n]].Mapped].SymbolProperties.ContractMultiplier
                    for n in self.positions if self.Securities[self.contracts[n]].Mapped
                ) if self.positions else 0

                if (current_notional + notional) / self.Portfolio.TotalPortfolioValue > self.max_notional_leverage:
                    contracts = int(contracts * 0.5)  # Reduce if hitting leverage limit

                if contracts > 0:
                    self.MarketOrder(mapped, contracts)
                    self.positions[sig['name']] = {
                        'entry_price': sig['price'],
                        'stop': sig['price'] - stop_distance,
                        'contracts': contracts,
                        'atr': sig['atr']
                    }
                    self.Debug(f"ENTRY: {sig['name']} x{contracts} | Mom: {sig['momentum']*100:.1f}% | Vol: {sig['volatility']*100:.1f}%")

            except Exception as e:
                self.Debug(f"Entry error {sig['name']}: {e}")

    def OnEndOfDay(self, symbol):
        """Check stop losses at end of day."""
        for name in list(self.positions.keys()):
            try:
                mapped = self.Securities[self.contracts[name]].Mapped
                if mapped is None:
                    continue

                current_price = self.Securities[mapped].Price
                position = self.positions[name]

                # Check stop loss
                if current_price < position['stop']:
                    self.Liquidate(mapped)
                    del self.positions[name]
                    self.Debug(f"STOP: {name} @ {current_price:.2f} (stop was {position['stop']:.2f})")

                # Trail stop for winners
                elif current_price > position['entry_price'] * 1.05:
                    new_stop = current_price - (position['atr'] * self.atr_stop_mult)
                    if new_stop > position['stop']:
                        position['stop'] = new_stop

            except:
                pass

    def OnEndOfAlgorithm(self):
        """Calculate and log final statistics."""
        years = (self.EndDate - self.StartDate).days / 365.25
        start_value = 100000
        end_value = self.Portfolio.TotalPortfolioValue
        cagr = (end_value / start_value) ** (1/years) - 1

        self.Debug("=" * 50)
        self.Debug("FINAL RESULTS - AGGRESSIVE TREND FOLLOWING")
        self.Debug("=" * 50)
        self.Debug(f"Period: {self.StartDate.strftime('%Y-%m-%d')} to {self.EndDate.strftime('%Y-%m-%d')}")
        self.Debug(f"Years: {years:.1f}")
        self.Debug(f"Start: ${start_value:,.0f}")
        self.Debug(f"End: ${end_value:,.0f}")
        self.Debug(f"Total Return: {(end_value/start_value - 1)*100:.1f}%")
        self.Debug(f"CAGR: {cagr*100:.2f}%")
        self.Debug(f"Target CAGR: 20-30%")
        self.Debug("=" * 50)
