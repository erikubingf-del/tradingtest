import sys
from hftbacktest import HftBacktest, BacktestAsset, ConstantLatency, Linear
import numpy as np
from strategy import grid_strategy

def main():
    print("Initializing Backtest...")
    
    # Configuration
    latency = ConstantLatency(10_000_000) # 10ms (in nanoseconds)
    asset_model = Linear(fee=0.0002) # 0.02% Maker fee (Standard)
    
    # Load Data
    # Ideally, we load the .npz files created by data_loader
    # data = np.load('data/btcusdt_20230101.npz')['data']
    
    # Initialize Engine
    # hbt = HftBacktest(data, tick_size=0.1, lot_size=0.001, maker_fee=0.0002, taker_fee=0.0004, order_latency=latency, asset_model=asset_model)
    
    # Run Strategy
    # fast_strategy = grid_strategy(hbt, stat_recorder)
    
    print("Backtest Complete. (Mock run - Data needed)")

if __name__ == '__main__':
    main()
