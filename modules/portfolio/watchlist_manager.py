import json
import os
import streamlit as st
from database.models import get_db, UserPortfolio
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
    """自选股组合管理器(PostgreSQL版)"""
    
    def __init__(self, data_dir: str = None, user_id: str = None):
        if not user_id:
            try:
                # 尝试从 Streamlit 拿
                import streamlit as st
                # check if st context exists
                if st.runtime.exists():
                    user_id = st.session_state.get('user_id', 'default_user')
                else:
                    user_id = 'default_user'
            except Exception:
                user_id = 'default_user'
                
        self.user_id = user_id
        try:
            self.db_manager = get_db()
        except:
            pass
        self.portfolios = self._load_all_portfolios()
    
    def _load_all_portfolios(self) -> Dict[str, Portfolio]:
        """从数据库加载用户的组合"""
        portfolios = {}
        try:
            db_portfolios = self.db_manager.get_user_portfolios(self.user_id)
            for db_p in db_portfolios:
                stocks_data = db_p.stocks or []
                stocks = [StockPosition(**s) if isinstance(s, dict) else s for s in stocks_data]
                
                p = Portfolio(
                    id=db_p.id,
                    name=db_p.name,
                    description=db_p.description or "",
                    stocks=stocks,
                    created_at=db_p.created_at.isoformat() if db_p.created_at else "",
                    updated_at=db_p.updated_at.isoformat() if db_p.updated_at else ""
                )
                portfolios[p.id] = p
        except Exception as e:
            print("DB Load Portfolio Error:", e)
        return portfolios
    
    def create_portfolio(self, name: str, description: str = "") -> Portfolio:
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
            del self.portfolios[portfolio_id]
            try:
                session = self.db_manager.get_session()
                pf = session.query(UserPortfolio).filter_by(id=portfolio_id).first()
                if pf:
                    session.delete(pf)
                    session.commit()
                session.close()
            except Exception as e:
                pass
    
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
        """保存组合到数据库"""
        try:
            stocks_dict = [asdict(s) for s in portfolio.stocks]
            self.db_manager.save_portfolio(
                portfolio_id=portfolio.id,
                user_id=self.user_id,
                name=portfolio.name,
                description=portfolio.description,
                stocks=stocks_dict
            )
        except Exception as e:
            print("DB Save Portfolio Error:", e)
