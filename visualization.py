"""
Visualization Module for Trend Following Backtester

Creates charts for:
- Equity curves
- Drawdown analysis
- Return distributions
- Strategy comparisons
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, List, Optional
import warnings

warnings.filterwarnings('ignore')


def set_style():
    """Set matplotlib style for consistent charts."""
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams['figure.figsize'] = (12, 6)
    plt.rcParams['font.size'] = 10
    plt.rcParams['axes.titlesize'] = 12
    plt.rcParams['axes.labelsize'] = 10


def plot_equity_curve(
    equity_df: pd.DataFrame,
    title: str = "Portfolio Equity Curve",
    benchmark_df: Optional[pd.DataFrame] = None,
    save_path: Optional[str] = None
):
    """
    Plot equity curve with optional benchmark comparison.
    """
    set_style()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), height_ratios=[3, 1])

    # Equity curve
    ax1.plot(equity_df.index, equity_df['equity'], label='Strategy', color='blue', linewidth=1.5)

    if benchmark_df is not None:
        # Normalize benchmark to same starting value
        start_val = equity_df['equity'].iloc[0]
        bench_normalized = benchmark_df['close'] / benchmark_df['close'].iloc[0] * start_val
        ax1.plot(bench_normalized.index, bench_normalized, label='Benchmark', color='gray', alpha=0.7)

    ax1.set_title(title)
    ax1.set_ylabel('Portfolio Value ($)')
    ax1.legend(loc='upper left')
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Drawdown
    running_max = equity_df['equity'].cummax()
    drawdown = (equity_df['equity'] - running_max) / running_max * 100

    ax2.fill_between(drawdown.index, drawdown, 0, color='red', alpha=0.3)
    ax2.plot(drawdown.index, drawdown, color='red', linewidth=1)
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Date')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved chart to {save_path}")

    plt.show()


def plot_annual_returns(
    annual_returns: pd.Series,
    target_cagr: float = 0.20,
    save_path: Optional[str] = None
):
    """
    Plot annual returns as bar chart.
    """
    set_style()
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = ['green' if r >= target_cagr else ('lightgreen' if r >= 0 else 'red')
              for r in annual_returns]

    bars = ax.bar(annual_returns.index, annual_returns * 100, color=colors, edgecolor='black')

    # Add target line
    ax.axhline(y=target_cagr * 100, color='blue', linestyle='--', label=f'Target ({target_cagr:.0%})')
    ax.axhline(y=0, color='black', linewidth=0.5)

    ax.set_title('Annual Returns')
    ax.set_xlabel('Year')
    ax.set_ylabel('Return (%)')
    ax.legend()

    # Add value labels on bars
    for bar, val in zip(bars, annual_returns):
        height = bar.get_height()
        ax.annotate(f'{val:.1%}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3 if height >= 0 else -10),
                    textcoords="offset points",
                    ha='center', va='bottom' if height >= 0 else 'top',
                    fontsize=8)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')

    plt.show()


def plot_rolling_returns(
    equity_df: pd.DataFrame,
    windows: List[int] = [252, 756, 2520],  # 1, 3, 10 years
    target_cagr: float = 0.20,
    save_path: Optional[str] = None
):
    """
    Plot rolling CAGR for different time windows.
    """
    set_style()
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = ['blue', 'green', 'purple']
    labels = ['1-Year', '3-Year', '10-Year']

    for window, color, label in zip(windows, colors, labels):
        if len(equity_df) < window:
            continue

        # Calculate rolling CAGR
        rolling_return = equity_df['equity'].pct_change(periods=window)
        years = window / 252
        rolling_cagr = (1 + rolling_return) ** (1 / years) - 1

        ax.plot(rolling_cagr.index, rolling_cagr * 100, label=label, color=color, alpha=0.8)

    ax.axhline(y=target_cagr * 100, color='red', linestyle='--', label=f'Target ({target_cagr:.0%})')
    ax.axhline(y=0, color='black', linewidth=0.5)

    ax.set_title('Rolling CAGR')
    ax.set_xlabel('Date')
    ax.set_ylabel('CAGR (%)')
    ax.legend()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')

    plt.show()


def plot_return_distribution(
    daily_returns: pd.Series,
    save_path: Optional[str] = None
):
    """
    Plot distribution of daily returns.
    """
    set_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram
    ax1.hist(daily_returns * 100, bins=50, color='blue', alpha=0.7, edgecolor='black')
    ax1.axvline(x=daily_returns.mean() * 100, color='red', linestyle='--', label='Mean')
    ax1.axvline(x=daily_returns.median() * 100, color='green', linestyle='--', label='Median')
    ax1.set_title('Daily Return Distribution')
    ax1.set_xlabel('Daily Return (%)')
    ax1.set_ylabel('Frequency')
    ax1.legend()

    # QQ plot (check for normality)
    from scipy import stats
    stats.probplot(daily_returns.dropna(), dist="norm", plot=ax2)
    ax2.set_title('Q-Q Plot (Normal)')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')

    plt.show()


def plot_strategy_comparison(
    results_dict: Dict[str, Dict],
    save_path: Optional[str] = None
):
    """
    Compare multiple strategy results.
    """
    set_style()
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    strategies = list(results_dict.keys())
    metrics = ['cagr', 'sharpe_ratio', 'max_drawdown', 'win_rate']
    titles = ['CAGR', 'Sharpe Ratio', 'Max Drawdown', 'Win Rate']

    for ax, metric, title in zip(axes.flatten(), metrics, titles):
        values = [results_dict[s][metric] for s in strategies]

        if metric == 'max_drawdown':
            values = [abs(v) for v in values]

        if metric in ['cagr', 'max_drawdown', 'win_rate']:
            values = [v * 100 for v in values]

        bars = ax.bar(strategies, values, color='steelblue', edgecolor='black')
        ax.set_title(title)
        ax.set_ylabel('%' if metric != 'sharpe_ratio' else 'Ratio')

        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(f'{val:.1f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')

    plt.show()


def plot_position_analysis(
    trades: List,
    save_path: Optional[str] = None
):
    """
    Analyze trade distribution and holding periods.
    """
    if not trades:
        print("No trades to analyze")
        return

    set_style()
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    trade_df = pd.DataFrame([{
        'pnl': t.pnl,
        'pnl_pct': t.pnl_pct,
        'holding_days': t.holding_days,
        'ticker': t.ticker
    } for t in trades])

    # PnL distribution
    ax = axes[0, 0]
    winners = trade_df[trade_df['pnl'] > 0]['pnl']
    losers = trade_df[trade_df['pnl'] <= 0]['pnl']
    ax.hist([winners, losers], bins=30, color=['green', 'red'], alpha=0.7, label=['Winners', 'Losers'])
    ax.set_title('Trade PnL Distribution')
    ax.set_xlabel('PnL ($)')
    ax.legend()

    # Holding period distribution
    ax = axes[0, 1]
    ax.hist(trade_df['holding_days'], bins=30, color='blue', alpha=0.7)
    ax.set_title('Holding Period Distribution')
    ax.set_xlabel('Days')

    # Cumulative PnL
    ax = axes[1, 0]
    trade_df['cum_pnl'] = trade_df['pnl'].cumsum()
    ax.plot(trade_df['cum_pnl'], color='blue')
    ax.set_title('Cumulative Trade PnL')
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('Cumulative PnL ($)')

    # Win/Loss by ticker
    ax = axes[1, 1]
    ticker_stats = trade_df.groupby('ticker')['pnl'].agg(['sum', 'count']).sort_values('sum', ascending=True)
    colors = ['green' if x > 0 else 'red' for x in ticker_stats['sum']]
    ax.barh(ticker_stats.index[-15:], ticker_stats['sum'][-15:], color=colors[-15:])
    ax.set_title('PnL by Ticker (Top 15)')
    ax.set_xlabel('Total PnL ($)')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')

    plt.show()


def plot_monte_carlo_results(
    mc_results: pd.DataFrame,
    target_cagr: float = 0.20,
    save_path: Optional[str] = None
):
    """
    Plot Monte Carlo simulation results.
    """
    set_style()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # CAGR distribution
    ax = axes[0]
    ax.hist(mc_results['cagr'] * 100, bins=50, color='blue', alpha=0.7, edgecolor='black')
    ax.axvline(x=target_cagr * 100, color='red', linestyle='--', linewidth=2, label=f'Target ({target_cagr:.0%})')
    ax.axvline(x=mc_results['cagr'].median() * 100, color='green', linestyle='--', label='Median')

    # Shade area above target
    ax.axvspan(target_cagr * 100, mc_results['cagr'].max() * 100, alpha=0.2, color='green')

    prob_above = (mc_results['cagr'] >= target_cagr).mean() * 100
    ax.set_title(f'CAGR Distribution (P(>20%) = {prob_above:.1f}%)')
    ax.set_xlabel('CAGR (%)')
    ax.legend()

    # Sharpe vs MaxDD scatter
    ax = axes[1]
    ax.scatter(mc_results['max_dd'] * 100, mc_results['sharpe'], alpha=0.5, c='blue')
    ax.set_title('Risk-Return Trade-off')
    ax.set_xlabel('Max Drawdown (%)')
    ax.set_ylabel('Sharpe Ratio')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')

    plt.show()


def create_performance_report(
    metrics: Dict,
    equity_df: pd.DataFrame,
    trades: List,
    save_dir: str = "."
):
    """
    Create a complete performance report with multiple charts.
    """
    import os

    os.makedirs(save_dir, exist_ok=True)

    print("Generating performance report...")

    # 1. Equity curve
    plot_equity_curve(
        equity_df,
        title=f"Portfolio Performance (CAGR: {metrics['cagr']:.2%})",
        save_path=os.path.join(save_dir, "equity_curve.png")
    )

    # 2. Annual returns
    annual = equity_df.groupby(equity_df.index.year)['equity'].agg(['first', 'last'])
    annual_returns = pd.Series(
        (annual['last'] - annual['first']) / annual['first'],
        index=annual.index
    )
    plot_annual_returns(
        annual_returns,
        save_path=os.path.join(save_dir, "annual_returns.png")
    )

    # 3. Rolling returns
    plot_rolling_returns(
        equity_df,
        save_path=os.path.join(save_dir, "rolling_cagr.png")
    )

    # 4. Trade analysis
    if trades:
        plot_position_analysis(
            trades,
            save_path=os.path.join(save_dir, "trade_analysis.png")
        )

    print(f"Report saved to {save_dir}/")


if __name__ == "__main__":
    # Test visualization with sample data
    import numpy as np

    # Generate sample equity curve
    dates = pd.date_range(start='2010-01-01', end='2024-01-01', freq='D')
    np.random.seed(42)
    returns = np.random.normal(0.0003, 0.01, len(dates))
    equity = 100000 * np.cumprod(1 + returns)

    equity_df = pd.DataFrame({
        'equity': equity,
        'cash': equity * 0.1,
        'positions': np.random.randint(0, 10, len(dates))
    }, index=dates)

    print("Testing equity curve plot...")
    plot_equity_curve(equity_df, "Sample Equity Curve")

    print("\nTesting annual returns plot...")
    annual = equity_df.groupby(equity_df.index.year)['equity'].agg(['first', 'last'])
    annual_returns = pd.Series(
        (annual['last'] - annual['first']) / annual['first'],
        index=annual.index
    )
    plot_annual_returns(annual_returns)
