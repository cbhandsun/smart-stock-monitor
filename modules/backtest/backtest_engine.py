import pandas as pd
import numpy as np
try:
    import vectorbt as vbt
    VBT_AVAILABLE = True
except ImportError:
    VBT_AVAILABLE = False
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
        """运行向量化多标的/单标的回测"""
        if not data: return {}
        
        # 1. 对齐多只股票的价格时间序列
        close_df = pd.DataFrame()
        for sym, df in data.items():
            df_copy = df.copy()
            if '日期' in df_copy.columns:
                df_copy['日期'] = pd.to_datetime(df_copy['日期'])
                df_copy.set_index('日期', inplace=True)
            elif not isinstance(df_copy.index, pd.DatetimeIndex):
                df_copy.index = pd.to_datetime(df_copy.index)
                
            mask = (df_copy.index >= pd.to_datetime(start_date)) & (df_copy.index <= pd.to_datetime(end_date))
            df_copy = df_copy.loc[mask]
            if not df_copy.empty:
                close_df[sym] = df_copy['收盘']
                
        if close_df.empty: return {}
        
        # 时间序列按时间排序并向前/向后填充以应对停牌
        close_df.sort_index(inplace=True)
        close_df = close_df.ffill().bfill()
        
        # 2. 产生交易信号 (多列 DataFrame 向量化处理)
        if self.strategy_name == "ma_cross":
            fast_ma, slow_ma = self.params
            ma_fast = vbt.MA.run(close_df, window=fast_ma)
            ma_slow = vbt.MA.run(close_df, window=slow_ma)
            entries = ma_fast.ma.vbt.crossed_above(ma_slow.ma)
            exits = ma_fast.ma.vbt.crossed_below(ma_slow.ma)
            
        elif self.strategy_name == "rsi":
            oversold, overbought = self.params
            rsi = vbt.RSI.run(close_df, window=14)
            entries = rsi.rsi.vbt.crossed_below(oversold)
            exits = rsi.rsi.vbt.crossed_above(overbought)
        else:
            entries = pd.DataFrame(False, index=close_df.index, columns=close_df.columns)
            exits = pd.DataFrame(False, index=close_df.index, columns=close_df.columns)
            
        # 3. 运行投资组合回测 (启用资金共享与自动组合)
        pf = vbt.Portfolio.from_signals(
            close_df,
            entries,
            exits,
            init_cash=self.initial_cash,
            fees=self.commission_rate,
            cash_sharing=True, # 多标的资金共享
            group_by=True,     # 合并统计为一个组合
            freq='d'
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
            
            # 4. 每日组合净值与现金流提取
            daily_values = []
            values_series = pf.value()
            cash_series = pf.cash()
            for date_idx, val in values_series.items():
                daily_values.append({
                    'date': date_idx.strftime('%Y-%m-%d'),
                    'total_value': float(val),
                    'cash': float(cash_series.get(date_idx, 0.0))
                })
            
            # 5. 提取成交明细记录 (注意处理多标的多维索引)
            trades_records = pf.trades.records
            trades_list = []
            if not trades_records.empty:
                for _, trade_row in trades_records.iterrows():
                    entry_idx = int(trade_row['entry_idx'])
                    exit_idx = int(trade_row['exit_idx'])
                    entry_date = close_df.index[entry_idx].strftime('%Y-%m-%d')
                    exit_date = close_df.index[exit_idx].strftime('%Y-%m-%d')
                    
                    # 确定标的代码
                    col_idx = int(trade_row.get('col', 0))
                    sym = close_df.columns[col_idx] if col_idx < len(close_df.columns) else list(data.keys())[0]
                    
                    trades_list.append({
                        'symbol': sym,
                        'entry_date': entry_date,
                        'exit_date': exit_date,
                        'size': float(trade_row['size']),
                        'entry_price': float(trade_row['entry_price']),
                        'exit_price': float(trade_row['exit_price']),
                        'pnl': float(trade_row['pnl']),
                        'return_pct': float(trade_row['return'] * 100),
                        'direction': '做多' if trade_row['direction'] == 0 else '做空'
                    })
            
            # 6. 获取行指作为大盘 Benchmark 比较 (默认沪深 300)
            benchmark_close = None
            try:
                from modules.data_loader import fetch_kline
                bench_df = fetch_kline("sh000300")
                if not bench_df.empty:
                    if '日期' in bench_df.columns:
                        bench_df['日期'] = pd.to_datetime(bench_df['日期'])
                        bench_df.set_index('日期', inplace=True)
                    # 对齐并填充
                    benchmark_close = bench_df['收盘'].reindex(close_df.index).ffill().bfill()
            except Exception as bench_err:
                print("Failed to fetch CSI 300 benchmark data:", bench_err)
                
            # 7. 现代风险归因计算 (Alpha, Beta, Sortino, Info Ratio)
            portfolio_returns = pf.returns()
            
            # 索提诺比率 (Sortino Ratio) 计算
            sortino_ratio = pf.sortino_ratio()
            if pd.isna(sortino_ratio) or np.isinf(sortino_ratio):
                sortino_ratio = 0.0
                
            alpha = 0.0
            beta = 1.0
            info_ratio = 0.0
            tracking_error = 0.0
            
            if benchmark_close is not None:
                bench_returns = benchmark_close.vbt.returns()
                
                # 对齐收益率序列并计算协方差
                comb_df = pd.DataFrame({'port': portfolio_returns, 'bench': bench_returns}).dropna()
                if not comb_df.empty:
                    cov = np.cov(comb_df['port'], comb_df['bench'])
                    if cov[1, 1] > 0:
                        beta = cov[0, 1] / cov[1, 1]
                    else:
                        beta = 1.0
                        
                    rf_ann = 0.02 # 2% 风险无风险收益率
                    port_ann = portfolio_returns.vbt.returns.annualized()
                    bench_ann = bench_returns.vbt.returns.annualized()
                    alpha = port_ann - (rf_ann + beta * (bench_ann - rf_ann))
                    
                    active_returns = comb_df['port'] - comb_df['bench']
                    tracking_error = active_returns.std() * np.sqrt(244)
                    active_mean_ann = active_returns.mean() * 244
                    info_ratio = active_mean_ann / tracking_error if tracking_error > 0 else 0.0
            
            return {
                'initial_cash': self.initial_cash,
                'final_value': pf.final_value(),
                'total_return': total_return,
                'annual_return': annual_return,
                'max_drawdown': abs(max_drawdown),
                'sharpe_ratio': sharpe_ratio,
                'total_trades': total_trades,
                'win_rate': win_rate,
                'daily_values': daily_values,
                'trades_list': trades_list,
                'alpha': float(alpha) * 100 if not pd.isna(alpha) else 0.0,
                'beta': float(beta) if not pd.isna(beta) else 1.0,
                'sortino_ratio': float(sortino_ratio) if not pd.isna(sortino_ratio) else 0.0,
                'info_ratio': float(info_ratio) if not pd.isna(info_ratio) else 0.0,
                'tracking_error': float(tracking_error) * 100 if not pd.isna(tracking_error) else 0.0
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
