#!/usr/bin/env python3
"""
Quick test to verify all components work correctly.
"""

import sys


def test_imports():
    """Test all modules can be imported."""
    print("Testing imports...")
    try:
        from config import BacktestConfig, ASSET_UNIVERSE, get_full_universe
        from indicators import TrendIndicators, calculate_all_indicators
        from position_sizing import PositionSizer, VolatilityTargeting
        from strategies import TurtleStrategy, MomentumStrategy, CombinedStrategy
        from backtester import Backtester
        print("✓ Core imports successful")

        # Data fetcher may fail if yfinance dependencies not fully installed
        try:
            from data_fetcher import DataFetcher
            print("✓ Data fetcher available")
        except ImportError as e:
            print(f"⚠ Data fetcher import warning (optional): {e}")

        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_config():
    """Test configuration."""
    print("\nTesting configuration...")
    from config import BacktestConfig, get_full_universe

    config = BacktestConfig()
    assert config.target_cagr == 0.20, "Target CAGR should be 20%"

    universe = get_full_universe()
    print(f"✓ Asset universe: {len(universe)} tickers")
    return True


def test_indicators():
    """Test indicators with sample data."""
    print("\nTesting indicators...")
    import pandas as pd
    import numpy as np

    # Create sample data
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=300, freq='D')
    close = 100 * np.cumprod(1 + np.random.normal(0.0005, 0.02, 300))
    high = close * (1 + np.abs(np.random.normal(0, 0.01, 300)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, 300)))

    df = pd.DataFrame({
        'open': close * 0.999,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000000, 5000000, 300)
    }, index=dates)

    from indicators import TrendIndicators, calculate_all_indicators

    # Test ATR
    atr = TrendIndicators.atr(df['high'], df['low'], df['close'], 20)
    assert not atr.isna().all(), "ATR should have values"

    # Test Donchian
    upper, lower, mid = TrendIndicators.donchian_channel(df['high'], df['low'], 20)
    # Skip NaN values at the start
    valid_mask = ~(upper.isna() | lower.isna())
    assert (upper[valid_mask] >= lower[valid_mask]).all(), "Upper channel should be >= lower"

    # Test momentum
    mom = TrendIndicators.momentum(df['close'], 20)
    assert len(mom) == len(df), "Momentum length should match"

    # Test all indicators
    result = calculate_all_indicators(df)
    assert 'atr_20' in result.columns, "Should have ATR column"
    assert 'mom_12m' in result.columns, "Should have momentum column"

    print("✓ All indicators working")
    return True


def test_position_sizing():
    """Test position sizing calculations."""
    print("\nTesting position sizing...")
    from position_sizing import PositionSizer, ScaleInManager

    sizer = PositionSizer(risk_per_trade=0.01)

    # Test unit calculation
    shares = sizer.calculate_unit_size(
        account_value=100000,
        atr=2.50,
        price=50.0
    )
    assert shares > 0, "Should calculate positive shares"
    print(f"  Sample position: {shares} shares at $50")

    # Test scale-in manager
    scale_mgr = ScaleInManager(initial_pct=0.02, max_pct=0.10)
    initial_weight = scale_mgr.get_initial_weight()
    assert initial_weight == 0.02, "Initial weight should be 2%"

    should_scale, new_weight = scale_mgr.should_scale_up(
        entry_price=100, current_price=106, current_weight=0.02, direction=1
    )
    assert should_scale, "Should scale up after 5% profit"
    assert new_weight == 0.04, "New weight should be 4%"

    print("✓ Position sizing working")
    return True


def test_strategies():
    """Test strategy signal generation."""
    print("\nTesting strategies...")
    import pandas as pd
    import numpy as np

    # Create trending sample data
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=300, freq='D')
    # Uptrend with noise
    trend = np.linspace(100, 150, 300)
    noise = np.random.normal(0, 2, 300)
    close = trend + noise

    df = pd.DataFrame({
        'open': close * 0.999,
        'high': close * 1.01,
        'low': close * 0.99,
        'close': close,
        'volume': np.random.randint(1000000, 5000000, 300)
    }, index=dates)

    from strategies import TurtleStrategy, MomentumStrategy, CombinedStrategy

    # Test Turtle
    turtle = TurtleStrategy()
    turtle_signals = turtle.generate_signals(df, "TEST")
    assert 'signal' in turtle_signals.columns
    print(f"  Turtle: {(turtle_signals['signal'] != 0).sum()} signals")

    # Test Momentum
    momentum = MomentumStrategy()
    mom_signals = momentum.generate_signals(df, "TEST")
    assert 'signal' in mom_signals.columns
    print(f"  Momentum: {(mom_signals['signal'] != 0).sum()} signals")

    # Test Combined
    combined = CombinedStrategy()
    combined_signals = combined.generate_signals(df, "TEST")
    assert 'signal' in combined_signals.columns
    print(f"  Combined: {(combined_signals['signal'] != 0).sum()} signals")

    print("✓ All strategies working")
    return True


def test_backtester():
    """Test backtester with sample data."""
    print("\nTesting backtester...")
    import pandas as pd
    import numpy as np

    from config import BacktestConfig
    from backtester import Backtester

    # Create sample data for 2 assets
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=500, freq='D')

    data = {}
    for i, ticker in enumerate(['ASSET1', 'ASSET2']):
        trend = np.linspace(100, 100 + 50 * (i + 1), 500)
        noise = np.random.normal(0, 2, 500)
        close = trend + noise

        df = pd.DataFrame({
            'open': close * 0.999,
            'high': close * 1.01,
            'low': close * 0.99,
            'close': close,
            'volume': np.random.randint(1000000, 5000000, 500)
        }, index=dates)
        data[ticker] = df

    config = BacktestConfig(
        start_date="2020-01-01",
        end_date="2021-06-01",
        initial_capital=100000
    )

    bt = Backtester(config, strategy_name="combined")
    results = bt.run(data, show_progress=False)

    assert 'cagr' in results, "Should have CAGR"
    assert 'sharpe_ratio' in results, "Should have Sharpe"
    assert 'max_drawdown' in results, "Should have max drawdown"

    print(f"  CAGR: {results['cagr']:.2%}")
    print(f"  Sharpe: {results['sharpe_ratio']:.2f}")
    print(f"  Max DD: {results['max_drawdown']:.2%}")
    print(f"  Trades: {results['total_trades']}")

    print("✓ Backtester working")
    return True


def run_all_tests():
    """Run all tests."""
    print("="*60)
    print("TREND FOLLOWING SYSTEM - TEST SUITE")
    print("="*60)

    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Indicators", test_indicators),
        ("Position Sizing", test_position_sizing),
        ("Strategies", test_strategies),
        ("Backtester", test_backtester),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
