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
                        # 将 stocks 中的 dict 转为 StockPosition 对象
                        if 'stocks' in data and data['stocks']:
                            data['stocks'] = [
                                StockPosition(**s) if isinstance(s, dict) else s
                                for s in data['stocks']
                            ]
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
    
    def delete_portfolio(self, portfolio_id: str):
        """删除组合"""
        if portfolio_id in self.portfolios:
            filepath = os.path.join(self.data_dir, f"{portfolio_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
            del self.portfolios[portfolio_id]
    
    def update_portfolio(self, portfolio_id: str, name: str = None, description: str = None):
        """更新组合信息"""
        if portfolio_id not in self.portfolios:
            raise ValueError(f"组合 {portfolio_id} 不存在")
        
        if name:
            self.portfolios[portfolio_id].name = name
        if description:
            self.portfolios[portfolio_id].description = description
        
        self.portfolios[portfolio_id].updated_at = datetime.now().isoformat()
        self._save_portfolio(self.portfolios[portfolio_id])
    
    def get_portfolio_symbols(self, portfolio_id: str) -> List[str]:
        """获取组合中的所有股票代码"""
        portfolio = self.portfolios.get(portfolio_id)
        if portfolio:
            return [s.symbol for s in portfolio.stocks]
        return []
    
    def _save_portfolio(self, portfolio: Portfolio):
        """保存组合到文件"""
        filepath = os.path.join(self.data_dir, f"{portfolio.id}.json")
        with open(filepath, 'w') as f:
            json.dump(asdict(portfolio), f, ensure_ascii=False, indent=2)
