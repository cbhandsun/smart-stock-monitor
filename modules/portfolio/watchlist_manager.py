import logging
import math
from datetime import datetime
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, cast
from uuid import uuid4

from core.user_context import require_user_id
from database.models import DatabaseManager, UserPortfolio, get_db


logger = logging.getLogger(__name__)


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


def _parse_stock_position(value: object) -> StockPosition:
    """Validate a persisted JSON position before exposing it to the UI."""
    if isinstance(value, StockPosition):
        return value
    if not isinstance(value, dict):
        raise ValueError("invalid persisted stock position")
    symbol = value.get("symbol")
    name = value.get("name")
    quantity = value.get("quantity")
    avg_cost = value.get("avg_cost")
    tags = value.get("tags")
    notes = value.get("notes")
    added_date = value.get("added_date")
    if not isinstance(symbol, str) or not symbol.isdigit() or len(symbol) != 6:
        raise ValueError("invalid persisted stock symbol")
    if not isinstance(name, str) or len(name) > 100:
        raise ValueError("invalid persisted stock name")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValueError("invalid persisted stock quantity")
    if isinstance(avg_cost, bool) or not isinstance(avg_cost, (int, float)):
        raise ValueError("invalid persisted stock cost")
    normalized_cost = float(avg_cost)
    if not math.isfinite(normalized_cost) or normalized_cost < 0:
        raise ValueError("invalid persisted stock cost")
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("invalid persisted stock tags")
    if not isinstance(notes, str) or len(notes) > 500:
        raise ValueError("invalid persisted stock notes")
    if not isinstance(added_date, str) or len(added_date) > 50:
        raise ValueError("invalid persisted stock date")
    return StockPosition(
        symbol=symbol,
        name=name,
        quantity=quantity,
        avg_cost=normalized_cost,
        tags=tags,
        notes=notes,
        added_date=added_date,
    )


class WatchlistManager:
    """自选股组合管理器(PostgreSQL版)"""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        user_id: Optional[str] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.user_id = require_user_id(user_id)
        self.db_manager = db_manager or get_db()
        self.portfolios = self._load_all_portfolios()

    def _load_all_portfolios(self) -> Dict[str, Portfolio]:
        """从数据库加载用户的组合"""
        portfolios = {}
        try:
            db_portfolios = self.db_manager.get_user_portfolios(self.user_id)
            for db_p in db_portfolios:
                raw_stocks = cast(Optional[list[object]], db_p.stocks)
                stocks = [_parse_stock_position(stock) for stock in raw_stocks or []]
                created_at = cast(Optional[datetime], db_p.created_at)
                updated_at = cast(Optional[datetime], db_p.updated_at)

                p = Portfolio(
                    id=cast(str, db_p.id),
                    name=cast(str, db_p.name),
                    description=cast(Optional[str], db_p.description) or "",
                    stocks=stocks,
                    created_at=created_at.isoformat() if created_at else "",
                    updated_at=updated_at.isoformat() if updated_at else "",
                )
                portfolios[p.id] = p
        except Exception:
            logger.error("Failed to load portfolios")
            raise
        return portfolios

    def _map_portfolio(self, db_p: UserPortfolio) -> Portfolio:
        raw_stocks = cast(Optional[list[object]], db_p.stocks)
        stocks = [_parse_stock_position(stock) for stock in raw_stocks or []]
        created_at = cast(Optional[datetime], db_p.created_at)
        updated_at = cast(Optional[datetime], db_p.updated_at)
        return Portfolio(
            id=cast(str, db_p.id),
            name=cast(str, db_p.name),
            description=cast(Optional[str], db_p.description) or "",
            stocks=stocks,
            created_at=created_at.isoformat() if created_at else "",
            updated_at=updated_at.isoformat() if updated_at else "",
        )

    def list_by_state(self, state: str) -> List[Portfolio]:
        return [
            self._map_portfolio(row)
            for row in self.db_manager.get_portfolios_by_state(self.user_id, state)
        ]

    def archive_portfolio(self, portfolio_id: str) -> bool:
        changed = self.db_manager.set_portfolio_state(
            portfolio_id, self.user_id, "archived"
        )
        if changed:
            self.portfolios.pop(portfolio_id, None)
        return changed

    def restore_portfolio(self, portfolio_id: str) -> bool:
        changed = self.db_manager.set_portfolio_state(
            portfolio_id, self.user_id, "active"
        )
        if changed:
            row = self.db_manager.get_portfolio(portfolio_id, self.user_id)
            if row is not None:
                portfolio = self._map_portfolio(row)
                self.portfolios[portfolio.id] = portfolio
        return changed

    def create_portfolio(self, name: str, description: str = "") -> Portfolio:
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ValueError("组合名称长度需为1-100个字符")
        if not isinstance(description, str) or len(description) > 500:
            raise ValueError("组合描述不能超过500个字符")
        name = name.strip()
        if any(portfolio.name == name for portfolio in self.portfolios.values()):
            raise ValueError("组合名称已存在")
        portfolio_id = f"portfolio_{uuid4().hex}"
        portfolio = Portfolio(
            id=portfolio_id,
            name=name,
            description=description,
            stocks=[],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self.db_manager.create_user_portfolio(
            portfolio.id,
            self.user_id,
            portfolio.name,
            portfolio.description,
        )
        self.portfolios[portfolio_id] = portfolio
        return portfolio

    def add_stock(
        self,
        portfolio_id: str,
        symbol: str,
        name: str,
        quantity: int = 0,
        avg_cost: float = 0.0,
        tags: Optional[List[str]] = None,
        notes: str = "",
    ):
        """添加股票到组合"""
        if portfolio_id not in self.portfolios:
            raise ValueError(f"组合 {portfolio_id} 不存在")
        if not isinstance(symbol, str) or not symbol.isdigit() or len(symbol) != 6:
            raise ValueError("股票代码必须是6位数字")
        if not isinstance(name, str) or len(name) > 100:
            raise ValueError("股票名称不能超过100个字符")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
            raise ValueError("持仓数量必须是非负整数")
        if isinstance(avg_cost, bool) or not isinstance(avg_cost, (int, float)):
            raise ValueError("平均成本必须是非负数值")
        avg_cost = float(avg_cost)
        if not math.isfinite(avg_cost) or avg_cost < 0:
            raise ValueError("平均成本必须是有限的非负数值")
        if not isinstance(notes, str) or len(notes) > 500:
            raise ValueError("备注不能超过500个字符")
        position = StockPosition(
            symbol=symbol,
            name=name,
            quantity=quantity,
            avg_cost=avg_cost,
            tags=tags or [],
            notes=notes,
            added_date=datetime.now().isoformat(),
        )
        stocks = self.db_manager.add_portfolio_stock(
            portfolio_id,
            self.user_id,
            asdict(position),
        )
        self.portfolios[portfolio_id].stocks = [
            _parse_stock_position(stock) for stock in stocks
        ]
        self.portfolios[portfolio_id].updated_at = datetime.now().isoformat()

    def remove_stock(self, portfolio_id: str, symbol: str) -> bool:
        """从组合移除股票"""
        changed, stocks = self.db_manager.remove_portfolio_stock(
            portfolio_id,
            self.user_id,
            symbol,
        )
        if portfolio_id in self.portfolios:
            self.portfolios[portfolio_id].stocks = [
                _parse_stock_position(stock) for stock in stocks
            ]
            if changed:
                self.portfolios[portfolio_id].updated_at = datetime.now().isoformat()
        return changed

    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """获取组合详情"""
        return self.portfolios.get(portfolio_id)

    def list_portfolios(self) -> List[Portfolio]:
        """列出所有组合"""
        return list(self.portfolios.values())

    def delete_portfolio(self, portfolio_id: str):
        """删除组合"""
        if portfolio_id in self.portfolios:
            if not self.db_manager.delete_portfolio(portfolio_id, self.user_id):
                raise PermissionError("portfolio not found")
            del self.portfolios[portfolio_id]

    def update_portfolio(
        self,
        portfolio_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """更新组合信息"""
        if portfolio_id not in self.portfolios:
            raise ValueError(f"组合 {portfolio_id} 不存在")

        portfolio = self.portfolios[portfolio_id]
        updated_name = portfolio.name
        updated_description = portfolio.description
        if name is not None:
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
                raise ValueError("组合名称长度需为1-100个字符")
            normalized_name = name.strip()
            if any(
                portfolio.id != portfolio_id and portfolio.name == normalized_name
                for portfolio in self.portfolios.values()
            ):
                raise ValueError("组合名称已存在")
            updated_name = normalized_name
        if description is not None:
            if not isinstance(description, str) or len(description) > 500:
                raise ValueError("组合描述不能超过500个字符")
            updated_description = description

        self.db_manager.update_portfolio_metadata(
            portfolio_id,
            self.user_id,
            updated_name,
            updated_description,
        )
        portfolio.name = updated_name
        portfolio.description = updated_description
        portfolio.updated_at = datetime.now().isoformat()

    def get_portfolio_symbols(self, portfolio_id: str) -> List[str]:
        """获取组合中的所有股票代码"""
        portfolio = self.portfolios.get(portfolio_id)
        if portfolio:
            return [s.symbol for s in portfolio.stocks]
        return []
