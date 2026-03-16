import pandas as pd
import numpy as np
import vectorbt as vbt
from typing import Dict, List, Callable, Optional

class BacktestEngine:
    """基于 vectorbt 的机构级向量化回测引擎"""
    
    def __init__(self, initial_cash: float = 100000.0, commission_rate: float = 0.0003):
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.strategy_name = "ma_cross"
        self.params = (5, 20)
    
    def set_strategy(self, strategy_name: str, *args):
        """设置策略参数"""
        self.strategy_name = strategy_name
        self.params = args
    
    def run(self, data: Dict[str, pd.DataFrame], start_date: str, end_date: str) -> Dict:
        """运行向量化回测"""
        # 准备数据 (这里只取一个主标的)
        if not data: return {}
        symbol = list(data.keys())[0]
        df = data[symbol].copy()
        
        # 确保日期索引并筛选范围
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'])
            df.set_index('日期', inplace=True)
            
        mask = (df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))
        df = df.loc[mask]
        
        if df.empty: return {}

        close = df['收盘']
        
        # 产生交易信号
        if self.strategy_name == "ma_cross":
            fast_ma, slow_ma = self.params
            ma_fast = vbt.MA.run(close, window=fast_ma)
            ma_slow = vbt.MA.run(close, window=slow_ma)
            entries = ma_fast.ma.vbt.crossed_above(ma_slow.ma)
            exits = ma_fast.ma.vbt.crossed_below(ma_slow.ma)
            
        elif self.strategy_name == "rsi":
            oversold, overbought = self.params
            rsi = vbt.RSI.run(close, window=14)
            entries = rsi.rsi.vbt.crossed_below(oversold)
            exits = rsi.rsi.vbt.crossed_above(overbought)
        else:
            entries = pd.Series(False, index=close.index)
            exits = pd.Series(False, index=close.index)
            
        # 运行投资组合回测
        pf = vbt.Portfolio.from_signals(
            close,
            entries,
            exits,
            init_cash=self.initial_cash,
            fees=self.commission_rate,
            freq='d' # 假设日频率
        )
        
        # 提取统计指标
        stats = pf.stats()
        
        try:
            total_return = stats.get('Total Return [%]', 0.0)
            annual_return = stats.get('Ann. Return [%]', 0.0)
            max_drawdown = stats.get('Max Drawdown [%]', 0.0)
            sharpe_ratio = stats.get('Sharpe Ratio', 0.0)
            win_rate = stats.get('Win Rate [%]', 0.0)
            total_trades = int(stats.get('Total Trades', 0))
            
            if pd.isna(sharpe_ratio): sharpe_ratio = 0.0
            if pd.isna(annual_return): annual_return = total_return
            
            # 每日净值提取, 补齐格式给旧的性能走势图用
            daily_values = []
            values_series = pf.value()
            cash_series = pf.cash()
            for date_idx, val in values_series.items():
                daily_values.append({
                    'date': date_idx.strftime('%Y-%m-%d'),
                    'total_value': float(val),
                    'cash': float(cash_series.get(date_idx, 0.0))
                })
                
            return {
                'initial_cash': self.initial_cash,
                'final_value': pf.final_value(),
                'total_return': total_return,
                'annual_return': annual_return,
                'max_drawdown': abs(max_drawdown), # 用绝对值显示
                'sharpe_ratio': sharpe_ratio,
                'total_trades': total_trades,
                'win_rate': win_rate,
                'daily_values': daily_values
            }
        except Exception as e:
            print(f"VectorBT Error: {e}")
            return {}

class StrategyTemplate:
    """为兼容保留前置名称"""
    @staticmethod
    def ma_cross_strategy(short_period: int = 5, long_period: int = 20):
        return ("ma_cross", short_period, long_period)
    
    @staticmethod
    def rsi_strategy(oversold: float = 30, overbought: float = 70):
        return ("rsi", oversold, overbought)
