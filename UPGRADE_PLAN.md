# Smart Stock Monitor 全面升级方案

> 参考行业先进做法：Bloomberg Terminal、Wind 万得、TradingView、雪球、同花顺
> 版本：v5.0 Quantum Pro
> 日期：2026-03-05

---

## 📋 目录

1. [数据维度扩展](#1-数据维度扩展)
2. [功能模块增强](#2-功能模块增强)
3. [UI/UX 设计提升](#3-uiux-设计提升)
4. [AI 能力升级](#4-ai-能力升级)
5. [工程架构优化](#5-工程架构优化)
6. [实施路线图](#6-实施路线图)

---

## 1. 数据维度扩展

### 1.1 多市场数据支持

#### 1.1.1 港股数据接入

```python
# modules/market_data/hk_stock.py
import akshare as ak
import pandas as pd
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class HKStockQuote:
    """港股行情数据模型"""
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: int
    turnover: float
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    market_cap: float
    timestamp: datetime

class HKStockDataProvider:
    """港股数据提供者"""
    
    def __init__(self):
        self.cache = {}
    
    def get_realtime_quotes(self) -> pd.DataFrame:
        """获取港股实时行情"""
        try:
            df = ak.stock_hk_ggt_components_em()
            df.rename(columns={
                '代码': 'symbol',
                '名称': 'name',
                '最新价': 'price',
                '涨跌额': 'change',
                '涨跌幅': 'change_pct',
                '成交量': 'volume',
                '成交额': 'turnover',
                '市盈率': 'pe_ratio',
                '市净率': 'pb_ratio',
                '总市值': 'market_cap'
            }, inplace=True)
            return df
        except Exception as e:
            print(f"港股数据获取失败: {e}")
            return pd.DataFrame()
```

#### 1.1.2 美股数据接入

```python
# modules/market_data/us_stock.py
import yfinance as yf
import pandas as pd

class USStockDataProvider:
    """美股数据提供者 (使用 yfinance)"""
    
    def get_ticker_info(self, symbol: str) -> dict:
        """获取美股基本信息"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                'symbol': symbol,
                'name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE'),
                'pb_ratio': info.get('priceToBook'),
                'dividend_yield': info.get('dividendYield', 0),
                '52w_high': info.get('fiftyTwoWeekHigh'),
                '52w_low': info.get('fiftyTwoWeekLow'),
                'avg_volume': info.get('averageVolume'),
                'beta': info.get('beta')
            }
        except Exception as e:
            print(f"美股信息获取失败: {e}")
            return {}
```

#### 1.1.3 期货与外汇数据

```python
# modules/market_data/futures_forex.py
import akshare as ak
import pandas as pd

class FuturesDataProvider:
    """期货数据提供者"""
    
    def get_domestic_futures(self) -> pd.DataFrame:
        """获取国内期货主力合约"""
        try:
            df = ak.futures_zh_realtime(symbol="主力")
            return df
        except Exception as e:
            print(f"期货数据获取失败: {e}")
            return pd.DataFrame()

class ForexDataProvider:
    """外汇数据提供者"""
    
    def get_usd_cnh_kline(self) -> pd.DataFrame:
        """获取美元兑离岸人民币K线"""
        try:
            df = ak.currency_hist(symbol="USD/CNH")
            return df
        except Exception as e:
            print(f"USD/CNH K线获取失败: {e}")
            return pd.DataFrame()
```

### 1.2 基本面数据扩展

```python
# modules/fundamentals/enhanced.py
import akshare as ak
import pandas as pd

class EnhancedFundamentals:
    """增强版基本面分析模块"""
    
    def get_income_statement(self, symbol: str) -> pd.DataFrame:
        """获取利润表"""
        try:
            code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            df = ak.stock_financial_report_sina(stock=code, symbol="利润表")
            return df
        except Exception as e:
            print(f"利润表获取失败: {e}")
            return pd.DataFrame()
    
    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        """获取资产负债表"""
        try:
            code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            df = ak.stock_financial_report_sina(stock=code, symbol="资产负债表")
            return df
        except Exception as e:
            print(f"资产负债表获取失败: {e}")
            return pd.DataFrame()
    
    def get_cash_flow(self, symbol: str) -> pd.DataFrame:
        """获取现金流量表"""
        try:
            code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            df = ak.stock_financial_report_sina(stock=code, symbol="现金流量表")
            return df
        except Exception as e:
            print(f"现金流量表获取失败: {e}")
            return pd.DataFrame()
    
    def get_profit_forecast(self, symbol: str) -> pd.DataFrame:
        """获取业绩预告"""
        try:
            code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            df = ak.stock_profit_forecast_em(symbol=code)
            return df
        except Exception as e:
            print(f"业绩预告获取失败: {e}")
            return pd.DataFrame()
    
    def get_institutional_holdings(self, symbol: str) -> pd.DataFrame:
        """获取机构持仓数据"""
        try:
            code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            df = ak.stock_institute_hold_detail(stock=code)
            return df
        except Exception as e:
            print(f"机构持仓获取失败: {e}")
            return pd.DataFrame()
    
    def get_fund_holdings(self, symbol: str) -> pd.DataFrame:
        """获取基金持仓数据"""
        try:
            code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            df = ak.stock_report_fund_hold(symbol=code)
            return df
        except Exception as e:
            print(f"基金持仓获取失败: {e}")
            return pd.DataFrame()
    
    def get_northbound_holding(self, symbol: str) -> pd.DataFrame:
        """获取北向资金持仓"""
        try:
            code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            df = ak.stock_hsgt_stock_em(symbol=code)
            return df
        except Exception as e:
            print(f"北向持仓获取失败: {e}")
            return pd.DataFrame()
```

### 1.3 技术面指标扩展

```python
# modules/technical/indicators.py
import pandas as pd
import numpy as np
from typing import Dict, List
from dataclasses import dataclass
from enum import Enum

class SignalType(Enum):
    BUY = "买入"
    SELL = "卖出"
    HOLD = "持有"

@dataclass
class TechnicalSignal:
    """技术信号"""
    indicator: str
    signal: SignalType
    strength: float
    description: str

class TechnicalIndicators:
    """技术指标计算库"""
    
    @staticmethod
    def calculate_ma(df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60, 120, 250]) -> pd.DataFrame:
        """计算多周期移动平均线"""
        for period in periods:
            df[f'MA{period}'] = df['close'].rolling(window=period).mean()
        return df
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算MACD指标"""
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        df['MACD'] = ema_fast - ema_slow
        df['MACD_signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
        df['MACD_hist'] = df['MACD'] - df['MACD_signal']
        return df
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算RSI指标"""
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        return df
    
    @staticmethod
    def calculate_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """计算KDJ指标"""
        low_list = df['low'].rolling(window=n, min_periods=n).min()
        high_list = df['high'].rolling(window=n, min_periods=n).max()
        rsv = (df['close'] - low_list) / (high_list - low_list) * 100
        df['K'] = rsv.ewm(alpha=1/m1, adjust=False).mean()
        df['D'] = df['K'].ewm(alpha=1/m2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        return df
    
    @staticmethod
    def calculate_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """计算布林带"""
        df['BOLL_mid'] = df['close'].rolling(window=period).mean()
        df['BOLL_std'] = df['close'].rolling(window=period).std()
        df['BOLL_upper'] = df['BOLL_mid'] + std_dev * df['BOLL_std']
        df['BOLL_lower'] = df['BOLL_mid'] - std_dev * df['BOLL_std']
        return df
```

### 1.4 市场情绪数据

```python
# modules/sentiment/market_sentiment.py
import akshare as ak
import pandas as pd

class MarketSentimentAnalyzer:
    """市场情绪分析器"""
    
    def get_northbound_flow(self) -> Dict:
        """获取北向资金流向"""
        try:
            sh_df = ak.stock_hsgt_hist_em(symbol="沪股通")
            sz_df = ak.stock_hsgt_hist_em(symbol="深股通")
            sh_df['net_flow'] = pd.to_numeric(sh_df['当日资金流入'], errors='coerce')
            sz_df['net_flow'] = pd.to_numeric(sz_df['当日资金流入'], errors='coerce')
            return {
                'shanghai': sh_df,
                'shenzhen': sz_df,
                'total_today': sh_df.iloc[0]['net_flow'] + sz_df.iloc[0]['net_flow'] if len(sh_df) > 0 and len(sz_df) > 0 else 0
            }
        except Exception as e:
            print(f"北向资金获取失败: {e}")
            return {}
    
    def get_sector_fund_flow(self) -> pd.DataFrame:
        """获取板块资金流向"""
        try:
            df = ak.stock_sector_fund_flow_rank(indicator="今日")
            return df
        except Exception as e:
            print(f"板块资金流向获取失败: {e}")
            return pd.DataFrame()
    
    def get_dragon_tiger(self, date: str = None) -> pd.DataFrame:
        """获取龙虎榜数据"""
        try:
            if date is None:
                from datetime import datetime
                date = datetime.now().strftime("%Y%m%d")
            df = ak.stock_lhb_detail_daily_sina(start_date=date, end_date=date)
            return df
        except Exception as e:
            print(f"龙虎榜获取失败: {e}")
            return pd.DataFrame()
```

---

## 2. 功能模块增强

### 2.1 自选股组合管理

```python
# modules/portfolio/watchlist_manager.py
import json
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class StockPosition:
    """股票持仓"""
    symbol: str
    name: str
    quantity: int
    avg_cost: float
    tags: List[str]
    notes: str
    added_date: str

@dataclass
class Portfolio:
    """投资组合"""
    id: str
    name: str
    description: str
    stocks: List[StockPosition]
    created_at: str
    updated_at: str
    total_value: float = 0.0
    total_return: float = 0.0

class WatchlistManager:
    """自选股组合管理器"""
    
    def __init__(self, data_dir: str = "./data/portfolios"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.portfolios = self._load_all_portfolios()
    
    def _load_all_portfolios(self) -> Dict[str, Portfolio]:
        """加载所有组合"""
        portfolios = {}
        if os.path.exists(self.data_dir):
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.json'):
                    with open(os.path.join(self.data_dir, filename), 'r') as f:
                        data = json.load(f)
                        portfolios[data['id']] = Portfolio(**data)
        return portfolios
    
    def create_portfolio(self, name: str, description: str = "") -> Portfolio:
        """创建新组合"""
        portfolio_id = f"portfolio_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        portfolio = Portfolio(
            id=portfolio_id,
            name=name,
            description=description,
            stocks=[],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self.portfolios[portfolio_id] = portfolio
        self._save_portfolio(portfolio)
        return portfolio
    
    def add_stock(self, portfolio_id: str, symbol: str, name: str, 
                  quantity: int = 0, avg_cost: float = 0.0, 
                  tags: List[str] = None, notes: str = ""):
        """添加股票到组合"""
        if portfolio_id not in self.portfolios:
            raise ValueError(f"组合 {portfolio_id} 不存在")
        
        position = StockPosition(
            symbol=symbol,
            name=name,
            quantity=quantity,
            avg_cost=avg_cost,
            tags=tags or [],
            notes=notes,
            added_date=datetime.now().isoformat()
        )
        
        self.portfolios[portfolio_id].stocks.append(position)
        self.portfolios[portfolio_id].updated_at = datetime.now().isoformat()
        self._save_portfolio(self.portfolios[portfolio_id])
    
    def remove_stock(self, portfolio_id: str, symbol: str):
        """从组合移除股票"""
        if portfolio_id in self.portfolios:
            self.portfolios[portfolio_id].stocks = [
                s for s in self.portfolios[portfolio_id].stocks if s.symbol != symbol
            ]
            self.portfolios[portfolio_id].updated_at = datetime.now().isoformat()
            self._save_portfolio(self.portfolios[portfolio_id])
    
    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """获取组合详情"""
        return self.portfolios.get(portfolio_id)
    
    def list_portfolios(self) -> List[Portfolio]:
        """列出所有组合"""
        return list(self.portfolios.values())
    
    def _save_portfolio(self, portfolio: Portfolio):
        """保存组合到文件"""
        filepath = os.path.join(self.data_dir, f"{portfolio.id}.json")
        with open(filepath, 'w') as f:
            json.dump(asdict(portfolio), f, ensure_ascii=False, indent=2)
```

### 2.2 预警提醒功能

```python
# modules/alerts/alert_system.py
import json
import os
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class AlertType(Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    CHANGE_PCT_ABOVE = "change_pct_above"
    CHANGE_PCT_BELOW = "change_pct_below"
    RSI_ABOVE = "rsi_above"
    RSI_BELOW = "rsi_below"
    MA_CROSS = "ma_cross"
    VOLUME_SPIKE = "volume_spike"

class AlertStatus(Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    DISABLED = "disabled"

@dataclass
class Alert:
    """预警规则"""
    id: str
    symbol: str
    alert_type: AlertType
    threshold: float
    message: str
    status: AlertStatus
    created_at: str
    triggered_at: Optional[str] = None
    trigger_count: int = 0

class AlertManager:
    """预警管理器"""
    
    def __init__(self, data_dir: str = "./data/alerts"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.alerts: Dict[str, Alert] = {}
        self.callbacks: List[Callable] = []
        self._load_alerts()
    
    def _load_alerts(self):
        """加载预警规则"""
        alerts_file = os.path.join(self.data_dir, "alerts.json")
        if os.path.exists(alerts_file):
            with open(alerts_file, 'r') as f:
                data = json.load(f)
                for alert_data in data:
                    alert_data['alert_type'] = AlertType(alert_data['alert_type'])
                    alert_data['status'] = AlertStatus(alert_data['status'])
                    self.alerts[alert_data['id']] = Alert(**alert_data)
    
    def _save_alerts(self):
        """保存预警规则"""
        alerts_file = os.path.join(self.data_dir, "alerts.json")
        data = []
        for alert in self.alerts.values():
            alert_dict = alert.__dict__.copy()
            alert_dict['alert_type'] = alert.alert_type.value
            alert_dict['status'] = alert.status.value
            data.append(alert_dict)
        with open(alerts_file, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_alert(self, symbol: str, alert_type: AlertType, 
                  threshold: float, message: str = "") -> Alert:
        """添加预警规则"""
        alert_id = f"alert_{datetime.now().strftime('%Y%m%d%H%M%S')}_{symbol}"
        alert = Alert(
            id=alert_id,
            symbol=symbol,
            alert_type=alert_type,
            threshold=threshold,
            message=message or f"{symbol} {alert_type.value} {threshold}",
            status=AlertStatus.ACTIVE,
            created_at=datetime.now().isoformat()
        )
        self.alerts[alert_id] = alert
        self._save_alerts()
        return alert
    
    def remove_alert(self, alert_id: str):
        """删除预警规则"""
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            self._save_alerts()
    
    def check_alerts(self, symbol: str, current_data: Dict) -> List[Alert]:
        """检查触发的预警"""
        triggered = []
        for alert in self.alerts.values():
            if alert.symbol != symbol or alert.status != AlertStatus.ACTIVE:
                continue
            
            should_trigger = False
            
            if alert.alert_type == AlertType.PRICE_ABOVE:
                should_trigger = current_data.get('price', 0) > alert.threshold
            elif alert.alert_type == AlertType.PRICE_BELOW:
                should_trigger = current_data.get('price', 0) < alert.threshold
            elif alert.alert_type == AlertType.CHANGE_PCT_ABOVE:
                should_trigger = current_data.get('change_pct', 0) > alert.threshold
            elif alert.alert_type == AlertType.CHANGE_PCT_BELOW:
                should_trigger = current_data.get('change_pct', 0) < alert.threshold
            elif alert.alert_type == AlertType.RSI_ABOVE:
                should_trigger = current_data.get('rsi', 0) > alert.threshold
            elif alert.alert_type == AlertType.RSI_BELOW:
                should_trigger = current_data.get('rsi', 0) < alert.threshold
            
            if should_trigger:
                alert.status = AlertStatus.TRIGGERED
                alert.triggered_at = datetime.now().isoformat()
                alert.trigger_count += 1
                triggered.append(alert)
                self._notify(alert, current_data)
        
        if triggered:
            self._save_alerts()
        
        return triggered
    
    def _notify(self, alert: Alert, data: Dict):
        """通知回调"""
        for callback in self.callbacks:
            try:
                callback(alert, data)
            except Exception as e:
                print(f"通知回调失败: {e}")
    
    def register_callback(self, callback: Callable):
        """注册通知回调"""
        self.callbacks.append(callback)
```

### 2.3 回测功能

```python
# modules/backtest/backtest_engine.py
import pandas as pd
import numpy as np
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

@dataclass
class Order:
    """订单"""
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    price: Optional[float] = None
    timestamp: datetime = None

@dataclass
class Trade:
    """成交记录"""
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime
    commission: float

@dataclass
class Position:
    """持仓"""
    symbol: str
    quantity: int
    avg_cost: float
    market_value: float
    unrealized_pnl: float

@dataclass
class PortfolioState:
    """组合状态"""
    cash: float
    positions: Dict[str, Position]
    total_value: float
    trades: List[Trade]

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_cash: float = 100000.0, 
                 commission_rate: float = 0.0003):
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.daily_values: List[Dict] = []
        self.strategy: Optional[Callable] = None
    
    def set_strategy(self, strategy: Callable):
        """设置策略"""
        self.strategy = strategy
    
    def run(self, data: Dict[str, pd.DataFrame], start_date: str, end_date: str) -> Dict:
        """运行回测"""
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        
        for date in dates:
            date_str = date.strftime('%Y-%m-%d')
            
            day_data = {}
            for symbol, df in data.items():
                day_df = df[df['date'] == date_str]
                if not day_df.empty:
                    day_data[symbol] = day_df.iloc[0]
            
            if not day_data:
                continue
            
            if self.strategy:
                orders = self.strategy(date_str, day_data, self.get_state())
                for order in orders:
                    self._execute_order(order, day_data.get(order.symbol))
            
            self._record_daily_value(date_str, day_data)
        
        return self._generate_report()
    
    def _execute_order(self, order: Order, bar: pd.Series):
        """执行订单"""
        if bar is None or bar.empty:
            return
        
        price = bar['close']
        amount = price * order.quantity
        commission = amount * self.commission_rate
        
        if order.side == OrderSide.BUY:
            if amount + commission > self.cash:
                return
            
            self.cash -= (amount + commission)
            
            if order.symbol in self.positions:
                pos = self.positions[order.symbol]
                total_cost = pos.avg_cost * pos.quantity + amount
                pos.quantity += order.quantity
                pos.avg_cost = total_cost / pos.quantity
            else:
                self.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    avg_cost=price,
                    market_value=amount,
                    unrealized_pnl=0.0
                )
        
        elif order.side == OrderSide.SELL:
            if order.symbol not in self.positions:
                return
            
            pos = self.positions[order.symbol]
            if pos.quantity < order.quantity:
                return
            
            self.cash += (amount - commission)
            
            pos.quantity -= order.quantity
            if pos.quantity == 0:
                del self.positions[order.symbol]
        
        trade = Trade(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=price,
            timestamp=datetime.now(),
            commission=commission
        )
        self.trades.append(trade)
    
    def get_state(self) -> PortfolioState:
        """获取当前状态"""
        total_value = self.cash + sum(
            pos.market_value for pos in self.positions.values()
        )
        return PortfolioState(
            cash=self.cash,
            positions=self.positions.copy(),
            total_value=total_value,
            trades=self.trades.copy()
        )
    
    def _record_daily_value(self, date: str, day_data: Dict):
        """记录每日净值"""
        positions_value = 0
        for symbol, pos in self.positions.items():
            if symbol in day_data:
                price = day_data[symbol]['close']
                pos.market_value = price * pos.quantity
                pos.unrealized_pnl = (price - pos.avg_cost) * pos.quantity
                positions_value += pos.market_value
        
        total_value = self.cash + positions_value
        self.daily_values.append({
            'date': date,
            'cash': self.cash,
            'positions_value': positions_value,
            'total_value': total_value,
            'return_pct': (total_value - self.initial_cash) / self.initial_cash * 100
        })
    
    def _generate_report(self) -> Dict:
        """生成回测报告"""
        if not self.daily_values:
            return {}
        
        values_df = pd.DataFrame(self.daily_values)
        
        total_return = (values_df['total_value'].iloc[-1] - self.initial_cash) / self.initial_cash
        days = len(values_df)
        annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
        
        values_df['cummax'] = values_df['total_value'].cummax()
        values_df['drawdown'] = (values_df['total_value'] - values_df['cummax']) / values_df['cummax']
        max_drawdown = values_df['drawdown'].min()
        
        daily_returns = values_df['total_value'].pct_change().dropna()
        sharpe_ratio = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if len(daily_returns) > 0 else 0
        
        return {
            'initial_cash': self.initial_cash,
            'final_value': values_df['total_value'].iloc[-1],
            'total_return': total_return * 100,
            'annual_return': annual_return * 100,
            'max_drawdown': max_drawdown * 100,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(self.trades),
            'daily_values': values_df.to_dict('records'),
            'trades': [t.__dict__ for t in self.trades]
        }
```

### 2.4 研报中心

```python
# modules/research/research_center.py
import akshare as ak
import pandas as pd
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ResearchReport:
    """研究报告"""
    title: str
    author: str
    institution: str
    date: str
    symbol: str
    rating: str
    target_price: Optional[float]
    summary: str
    url: str

class ResearchCenter:
    """研报中心"""
    
    def get_stock_reports(self, symbol: str, limit: int = 10) -> pd.DataFrame:
        """获取个股研报"""
        try:
            code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            df = ak.stock_zyjs_report_em(symbol=code)
            return df.head(limit)
        except Exception as e:
            print(f"个股研报获取失败: {e}")
            return pd.DataFrame()
    
    def get_industry_reports(self, industry: str, limit: int = 10) -> pd.DataFrame:
        """获取行业研报"""
        try:
            df = ak.stock_research_report_em(symbol=industry)
            return df.head(limit)
        except Exception as e:
            print(f"行业研报获取失败: {e}")
            return pd.DataFrame()
    
    def get_latest_reports(self, limit: int = 20) -> pd.DataFrame:
        """获取最新研报"""
        try:
            df = ak.stock_research_report_em()
            return df.head(limit)
        except Exception as e:
            print(f"最新研报获取失败: {e}")
            return pd.DataFrame()
```

---

## 3. UI/UX 设计提升

### 3.1 专业金融终端布局

```python
# app_enhanced.py
import streamlit as st

def setup_page():
    st.set_page_config(
        page_title="SSM Quantum Pro",
        layout="wide",
        page_icon="⚛️",
        initial_sidebar_state="expanded"
    )

def render_header():
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        st.markdown("### SSM Quantum")
    with col2:
        st.markdown("#### Real-time Market Data")
    with col3:
        st.button("Settings")

def render_market_overview():
    st.markdown("## Market Overview")
    cols = st.columns(4)
    indices = ["上证指数", "深证成指", "创业板指", "科创50"]
    for i, idx in enumerate(indices):
        with cols[i]:
            st.metric(idx, "3,000.00", "+1.2%")
```

### 3.2 暗黑/亮色主题切换

```python
# themes.py
DARK_THEME = """
:root {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --accent: #3b82f6;
}
"""

LIGHT_THEME = """
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f1f5f9;
    --text-primary: #0f172a;
    --text-secondary: #64748b;
    --accent: #2563eb;
}
"""

def apply_theme(theme: str):
    if theme == "dark":
        st.markdown(f"<style>{DARK_THEME}</style>", unsafe_allow_html=True)
    else:
        st.markdown(f"<style>{LIGHT_THEME}</style>", unsafe_allow_html=True)
```

### 3.3 数据可视化优化

```python
# visualization.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_candlestick_chart(df, indicators=None):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                       vertical_spacing=0.03, row_heights=[0.7, 0.3])
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df['date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name="Price"
    ), row=1, col=1)
    
    # Volume
    colors = ['red' if c < o else 'green' for c, o in zip(df['close'], df['open'])]
    fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors), row=2, col=1)
    
    # Add indicators
    if indicators:
        for indicator in indicators:
            if indicator in df.columns:
                fig.add_trace(go.Scatter(x=df['date'], y=df[indicator], 
                                        name=indicator), row=1, col=1)
    
    fig.update_layout(template="plotly_dark", height=600)
    return fig
```

### 3.4 响应式设计

```python
# responsive.py
import streamlit as st

def get_screen_size():
    return st.session_state.get('screen_width', 1200)

def responsive_columns(items, min_col_width=300):
    screen_width = get_screen_size()
    num_cols = max(1, screen_width // min_col_width)
    return st.columns(num_cols)
```

---

## 4. AI 能力升级

### 4.1 多模型支持

```python
# ai/multi_model.py
from enum import Enum
import os

class AIModel(Enum):
    GPT4 = "gpt-4"
    CLAUDE = "claude-3"
    GEMINI = "gemini-pro"
    KIMI = "kimi"

class MultiModelAI:
    def __init__(self):
        self.models = {}
        self.current_model = AIModel.GEMINI
    
    def set_model(self, model: AIModel):
        self.current_model = model
    
    def generate_response(self, prompt: str) -> str:
        if self.current_model == AIModel.GPT4:
            return self._call_openai(prompt)
        elif self.current_model == AIModel.CLAUDE:
            return self._call_anthropic(prompt)
        elif self.current_model == AIModel.GEMINI:
            return self._call_gemini(prompt)
        elif self.current_model == AIModel.KIMI:
            return self._call_kimi(prompt)
    
    def _call_openai(self, prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    
    def _call_gemini(self, prompt: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text
```

### 4.2 智能问答

```python
# ai/intelligent_qa.py
import re

class IntelligentQA:
    def __init__(self, data_provider):
        self.data_provider = data_provider
        self.query_patterns = {
            'price': r'.*?(价格|股价|多少钱).*?',
            'pe': r'.*?(PE|市盈率).*?',
            'news': r'.*?(新闻|消息|公告).*?',
            'recommendation': r'.*?(推荐|建议|怎么看).*?'
        }
    
    def parse_query(self, query: str) -> Dict:
        query_type = None
        symbol = None
        
        for qtype, pattern in self.query_patterns.items():
            if re.match(pattern, query):
                query_type = qtype
                break
        
        symbol_match = re.search(r'(\d{6})', query)
        if symbol_match:
            symbol = symbol_match.group(1)
        
        return {'type': query_type, 'symbol': symbol}
    
    def answer(self, query: str) -> str:
        parsed = self.parse_query(query)
        
        if parsed['type'] == 'price':
            data = self.data_provider.get_price(parsed['symbol'])
            return f"{parsed['symbol']} 当前价格: {data['price']}"
        elif parsed['type'] == 'pe':
            data = self.data_provider.get_fundamentals(parsed['symbol'])
            return f"{parsed['symbol']} 市盈率: {data['pe']}"
        else:
            return "抱歉，我暂时无法回答这个问题。"
```

### 4.3 预测分析

```python
# ai/predictive_analysis.py
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

class PredictiveAnalyzer:
    def __init__(self):
        self.models = {}
    
    def trend_prediction(self, df: pd.DataFrame, days: int = 5) -> Dict:
        X = np.arange(len(df)).reshape(-1, 1)
        y = df['close'].values
        
        poly = PolynomialFeatures(degree=2)
        X_poly = poly.fit_transform(X)
        
        model = LinearRegression()
        model.fit(X_poly, y)
        
        future_X = np.arange(len(df), len(df) + days).reshape(-1, 1)
        future_X_poly = poly.transform(future_X)
        predictions = model.predict(future_X_poly)
        
        return {
            'predictions': predictions.tolist(),
            'trend': 'up' if predictions[-1] > y[-1] else 'down',
            'confidence': 0.7
        }
    
    def risk_assessment(self, df: pd.DataFrame) -> Dict:
        returns = df['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252)
        max_drawdown = ((df['close'] / df['close'].cummax()) - 1).min()
        
        risk_score = 0
        if volatility > 0.3:
            risk_score += 40
        elif volatility > 0.2:
            risk_score += 25
        
        if max_drawdown < -0.3:
            risk_score += 40
        elif max_drawdown < -0.2:
            risk_score += 25
        
        risk_level = "High" if risk_score > 60 else "Medium" if risk_score > 30 else "Low"
        
        return {
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'risk_score': risk_score,
            'risk_level': risk_level
        }
```

### 4.4 个性化推荐

```python
# ai/recommendation_engine.py
import pandas as pd
import numpy as np

class RecommendationEngine:
    def __init__(self):
        self.user_preferences = {}
        self.stock_features = {}
    
    def set_user_preferences(self, user_id: str, preferences: Dict):
        self.user_preferences[user_id] = preferences
    
    def calculate_similarity(self, stock_features: Dict, user_prefs: Dict) -> float:
        score = 0
        
        if user_prefs.get('risk_tolerance') == 'high' and stock_features.get('volatility', 0) > 0.3:
            score += 0.3
        elif user_prefs.get('risk_tolerance') == 'low' and stock_features.get('volatility', 0) < 0.2:
            score += 0.3
        
        if stock_features.get('sector') in user_prefs.get('preferred_sectors', []):
            score += 0.4
        
        market_cap = stock_features.get('market_cap', 0)
        if user_prefs.get('market_cap_pref') == 'large' and market_cap > 100e9:
            score += 0.3
        elif user_prefs.get('market_cap_pref') == 'small' and market_cap < 10e9:
            score += 0.3
        
        return score
    
    def get_recommendations(self, user_id: str, top_n: int = 10) -> List[Dict]:
        user_prefs = self.user_preferences.get(user_id, {})
        
        recommendations = []
        for symbol, features in self.stock_features.items():
            similarity = self.calculate_similarity(features, user_prefs)
            recommendations.append({
                'symbol': symbol,
                'score': similarity,
                'features': features
            })
        
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:top_n]
```

---

## 5. 工程架构优化

### 5.1 Redis 缓存层

```python
# cache/redis_cache.py
import redis
import pickle
from typing import Optional, Any

class RedisCache:
    def __init__(self, host='localhost', port=6379, db=0):
        self.client = redis.Redis(host=host, port=port, db=db)
    
    def get(self, key: str) -> Optional[Any]:
        data = self.client.get(key)
        if data:
            return pickle.loads(data)
        return None
    
    def set(self, key: str, value: Any, expire: int = 300):
        self.client.setex(key, expire, pickle.dumps(value))
    
    def delete(self, key: str):
        self.client.delete(key)
    
    def get_stock_data(self, symbol: str, data_type: str = "quote") -> Optional[Dict]:
        key = f"stock:{symbol}:{data_type}"
        return self.get(key)
    
    def set_stock_data(self, symbol: str, data: Dict, data_type: str = "quote", expire: int = 60):
        key = f"stock:{symbol}:{data_type}"
        self.set(key, data, expire)
```

### 5.2 Celery 异步任务队列

```python
# tasks/celery_config.py
from celery import Celery
from celery.schedules import crontab

app = Celery('stock_monitor')
app.config_from_object({
    'broker_url': 'redis://localhost:6379/1',
    'result_backend': 'redis://localhost:6379/2',
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'Asia/Shanghai',
    'enable_utc': True,
})

app.conf.beat_schedule = {
    'update-market-data': {
        'task': 'tasks.market_data.update_all_stocks',
        'schedule': 60.0,
    },
    'check-alerts': {
        'task': 'tasks.alerts.check_all_alerts',
        'schedule': 30.0,
    },
    'daily-report': {
        'task': 'tasks.reports.generate_daily_report',
        'schedule': crontab(hour=16, minute=0),
    },
}
```

```python
# tasks/market_data.py
from .celery_config import app
from cache.redis_cache import RedisCache

@app.task
def update_stock_quote(symbol: str):
    from modules.data_loader import fetch_kline
    
    cache = RedisCache()
    data = fetch_kline(symbol)
    
    if not data.empty:
        cache.set_stock_data(symbol, data.to_dict(), "kline", expire=300)
    
    return f"Updated {symbol}"

@app.task
def update_all_stocks():
    from modules.portfolio.watchlist_manager import WatchlistManager
    
    manager = WatchlistManager()
    portfolios = manager.list_portfolios()
    
    symbols = set()
    for portfolio in portfolios:
        for stock in portfolio.stocks:
            symbols.add(stock.symbol)
    
    for symbol in symbols:
        update_stock_quote.delay(symbol)
    
    return f"Queued updates for {len(symbols)} stocks"
```

### 5.3 用户认证系统

```python
# auth/user_auth.py
from datetime import datetime, timedelta
import jwt
import bcrypt
from dataclasses import dataclass

@dataclass
class User:
    id: str
    username: str
    email: str
    password_hash: str
    created_at: datetime
    last_login: Optional[datetime] = None
    preferences: Dict = None

class AuthManager:
    def __init__(self, secret_key: str, db_session):
        self.secret_key = secret_key
        self.db = db_session
    
    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    
    def create_user(self, username: str, email: str, password: str) -> User:
        user_id = f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        password_hash = self.hash_password(password)
        
        user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            created_at=datetime.now(),
            preferences={}
        )
        
        self.db.add(user)
        self.db.commit()
        
        return user
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        user = self.db.query(User).filter_by(username=username).first()
        
        if not user or not self.verify_password(password, user.password_hash):
            return None
        
        user.last_login = datetime.now()
        self.db.commit()
        
        token = jwt.encode(
            {
                'user_id': user.id,
                'username': user.username,
                'exp': datetime.utcnow() + timedelta(days=7)
            },
            self.secret_key,
            algorithm='HS256'
        )
        
        return token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
```

### 5.4 数据库持久化

```python
# database/models.py
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class StockData(Base):
    __tablename__ = 'stock_data'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), index=True)
    date = Column(DateTime, index=True)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

class UserPortfolio(Base):
    __tablename__ = 'user_portfolios'
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), index=True)
    name = Column(String(100))
    description = Column(String(500))
    stocks = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class AlertRule(Base):
    __tablename__ = 'alert_rules'
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), index=True)
    symbol = Column(String(10), index=True)
    alert_type = Column(String(20))
    threshold = Column(Float)
    message = Column(String(500))
    status = Column(String(20), default='active')
    created_at = Column(DateTime, default=datetime.now)
    triggered_at = Column(DateTime)
    trigger_count = Column(Integer, default=0)

def init_db(database_url: str):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session
```

---

## 6. 实施路线图

### Phase 1: 数据层扩展 (Week 1-2)
- [ ] 实现港股数据接入
- [ ] 实现美股数据接入
- [ ] 实现期货外汇数据接入
- [ ] 扩展基本面数据模块
- [ ] 扩展技术面指标库
- [ ] 实现市场情绪数据模块

### Phase 2: 功能增强 (Week 3-4)
- [ ] 实现自选股组合管理
- [ ] 实现预警提醒系统
- [ ] 实现回测引擎
- [ ] 实现研报中心

### Phase 3: UI/UX 升级 (Week 5-6)
- [ ] 设计专业金融终端布局
- [ ] 实现暗黑/亮色主题切换
- [ ] 优化数据可视化图表
- [ ] 实现响应式设计

### Phase 4: AI 能力 (Week 7-8)
- [ ] 实现多模型支持
- [ ] 实现智能问答系统
- [ ] 实现预测分析模块
- [ ] 实现个性化推荐引擎

### Phase 5: 架构优化 (Week 9-10)
- [ ] 部署 Redis 缓存层
- [ ] 配置 Celery 任务队列
- [ ] 实现用户认证系统
- [ ] 配置数据库持久化

### Phase 6: 集成测试 (Week 11-12)
- [ ] 端到端功能测试
- [ ] 性能测试与优化
- [ ] 安全审计
- [ ] 文档完善

---

## 附录

### A. 依赖安装

```bash
# 基础依赖
pip install akshare pandas numpy streamlit plotly

# AI 模型支持
pip install openai google-generativeai

# 缓存与队列
pip install redis celery

# 数据库
pip install sqlalchemy psycopg2-binary

# 用户认证
pip install bcrypt pyjwt

# 机器学习
pip install scikit-learn
```

### B. 配置文件示例

```yaml
# config.yaml
app:
  name: "SSM Quantum Pro"
  version: "5.0.0"
  debug: false

data:
  cache_ttl: 300
  default_market: "A"

ai:
  default_model: "gemini-pro"
  models:
    - name: "gpt-4"
      api_key: "${OPENAI_API_KEY}"
    - name: "gemini-pro"
      api_key: "${GEMINI_API_KEY}"

redis:
  host: "localhost"
  port: 6379
  db: 0

database:
  url: "postgresql://user:pass@localhost/stock_monitor"

auth:
  secret_key: "${JWT_SECRET_KEY}"
  token_expire_days: 7
```

### C. 目录结构

```
smart-stock-monitor/
├── app.py                    # 主应用入口
├── config.yaml              # 配置文件
├── modules/
│   ├── __init__.py
│   ├── data_loader.py       # 数据加载
│   ├── market_data/         # 市场数据模块
│   │   ├── hk_stock.py
│   │   ├── us_stock.py
│   │   └── futures_forex.py
│   ├── fundamentals/        # 基本面模块
│   │   └── enhanced.py
│   ├── technical/           # 技术面模块
│   │   └── indicators.py
│   ├── sentiment/           # 情绪面模块
│   │   └── market_sentiment.py
│   ├── portfolio/           # 组合管理
│   │   └── watchlist_manager.py
│   ├── alerts/              # 预警系统
│   │   └── alert_system.py
│   ├── backtest/            # 回测引擎
│   │   └── backtest_engine.py
│   ├── research/            # 研报中心
│   │   └── research_center.py
│   └── ai/                  # AI 模块
│       ├── multi_model.py
│       ├── intelligent_qa.py
│       ├── predictive_analysis.py
│       └── recommendation_engine.py
├── cache/                   # 缓存模块
│   └── redis_cache.py
├── tasks/                   # 异步任务
│   ├── celery_config.py
│   ├── market_data.py
│   └── alerts.py
├── auth/                    # 认证模块
│   └── user_auth.py
├── database/                # 数据库模块
│   ├── models.py
│   └── repository.py
├── visualization/           # 可视化模块
│   └── charts.py
├── themes/                  # 主题配置
│   └── themes.py
├── tests/                   # 测试用例
├── data/                    # 数据存储
│   ├── portfolios/
│   ├── alerts/
│   └── cache/
└── reports/                 # 报告输出
```

---

*文档版本: v5.0.0*
*最后更新: 2026-03-05*
