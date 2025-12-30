from hftbacktest import HftBacktest, hftbacktest, Linear, ConstantLatency, BacktestAsset
from numba import njit
import numpy as np

@njit
def grid_strategy(hbt, stat):
    # Parameters
    # Grid spacing in ticks (e.g., 0.1% or fixed pip amount)
    # Using a simple fixed pip grid for this example
    grid_interval = 10.0 # Price ticks
    half_spread = 5.0    # Distance from mid price
    order_qty = 0.001    # Quantity per grid level
    
    while hbt.elapse(100_000): # Check every 100ms
        # Get current best bid/ask
        mid_price = (hbt.best_bid + hbt.best_ask) / 2.0
        
        # Simple Logic: Maintain orders around mid_price
        # Clear existing orders (simplification for HFT: usually we modify)
        hbt.clear_inactive_orders()
        
        # Place Buy LO
        buy_price = mid_price - half_spread
        # Round to tick size logic would go here
        hbt.submit_buy_order(0, buy_price, order_qty, 0) # 0 = TimeInForce.GTC
        
        # Place Sell LO
        sell_price = mid_price + half_spread
        hbt.submit_sell_order(1, sell_price, order_qty, 0)
        
        # Record stats
        # stat.record(hbt.current_timestamp, hbt.equity)
        
    return True
