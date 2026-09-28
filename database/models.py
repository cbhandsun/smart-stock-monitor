from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    DateTime,
    Integer,
    JSON,
    Boolean,
    Text,
    ForeignKey,
    event,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, scoped_session
from datetime import datetime
import os
from typing import Optional

Base = declarative_base()


class StockData(Base):
    """股票数据表"""

    __tablename__ = "stock_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), index=True, nullable=False)
    date = Column(DateTime, index=True, nullable=False)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Integer)
    turnover = Column(Float)
    created_at = Column(DateTime, default=datetime.now)


class User(Base):
    """用户认证与配置表"""

    __tablename__ = "users"

    id = Column(String(50), primary_key=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    created_at = Column(
        String(50), nullable=False
    )  # keeping string matching dict format or datetime
    last_login = Column(String(50), nullable=True)
    preferences = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)


class UserPortfolio(Base):
    """用户投资组合表"""

    __tablename__ = "user_portfolios"

    id = Column(String(50), primary_key=True)
    user_id = Column(
        String(50),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    stocks = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    archived_at = Column(DateTime)
    deleted_at = Column(DateTime)


class AlertRule(Base):
    """预警规则表"""

    __tablename__ = "alert_rules"

    id = Column(String(50), primary_key=True)
    user_id = Column(
        String(50),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    symbol = Column(String(10), index=True, nullable=False)
    alert_type = Column(String(20), nullable=False)
    threshold = Column(Float, nullable=False)
    message = Column(String(500))
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.now)
    triggered_at = Column(DateTime)
    trigger_count = Column(Integer, default=0)


class NotificationDelivery(Base):
    """Durable, tenant-owned notification delivery ledger."""

    __tablename__ = "notification_deliveries"

    event_key = Column(String(120), primary_key=True)
    alert_id = Column(String(50), index=True, nullable=False)
    user_id = Column(
        String(50),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status = Column(String(20), nullable=False, default="pending")
    channel = Column(String(20))
    attempts = Column(Integer, nullable=False, default=1)
    error_code = Column(String(50))
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
    sent_at = Column(DateTime)


class LoginThrottleState(Base):
    """Hashed login-identity throttle state shared across web replicas."""

    __tablename__ = "login_throttle_states"

    identity_hash = Column(String(64), primary_key=True)
    failure_count = Column(Integer, nullable=False, default=0)
    blocked_until = Column(DateTime)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)


class UserActivity(Base):
    """用户活动日志表"""

    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(50),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action = Column(String(50), nullable=False)
    details = Column(JSON)
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)


class ResearchReport(Base):
    """研报数据表"""

    __tablename__ = "research_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), index=True)
    title = Column(String(500))
    author = Column(String(100))
    institution = Column(String(100))
    rating = Column(String(20))
    target_price = Column(Float)
    content = Column(Text)
    report_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)


class BacktestResult(Base):
    """回测结果表"""

    __tablename__ = "backtest_results"

    id = Column(String(50), primary_key=True)
    user_id = Column(
        String(50),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    strategy_name = Column(String(100))
    symbols = Column(JSON)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    initial_cash = Column(Float)
    final_value = Column(Float)
    total_return = Column(Float)
    annual_return = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    total_trades = Column(Integer)
    daily_values = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)


class DatabaseManager:
    """数据库管理器"""

    def __init__(
        self, database_url: Optional[str] = None, *, create_schema: bool = False
    ):
        if not database_url:
            # 默认使用SQLite
            database_url = os.getenv(
                "DATABASE_URL", "sqlite:///./data/stock_monitor.db"
            )

        if database_url.startswith("postgresql"):
            self.engine = create_engine(
                database_url,
                pool_size=15,
                max_overflow=25,
                pool_recycle=1800,
                pool_pre_ping=True,
                echo=False,
            )
        else:
            self.engine = create_engine(database_url, echo=False)
            if database_url.startswith("sqlite"):

                @event.listens_for(self.engine, "connect")
                def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()

        if create_schema:
            Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.SessionLocal = scoped_session(self.session_factory)

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    def close(self):
        """关闭数据库连接"""
        self.SessionLocal.remove()
        self.engine.dispose()

    def save_stock_data(self, symbol: str, data: dict):
        """保存股票数据"""
        session = self.get_session()
        try:
            stock_data = StockData(
                symbol=symbol,
                date=data.get("date"),
                open_price=data.get("open"),
                high_price=data.get("high"),
                low_price=data.get("low"),
                close_price=data.get("close"),
                volume=data.get("volume"),
                turnover=data.get("turnover"),
            )
            session.add(stock_data)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def get_stock_data(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """获取股票数据"""
        session = self.get_session()
        try:
            query = session.query(StockData).filter(StockData.symbol == symbol)

            if start_date:
                query = query.filter(StockData.date >= start_date)
            if end_date:
                query = query.filter(StockData.date <= end_date)

            return query.order_by(StockData.date).all()
        finally:
            self.SessionLocal.remove()

    def save_portfolio(
        self, portfolio_id: str, user_id: str, name: str, description: str, stocks: list
    ):
        """保存投资组合"""
        if not portfolio_id or not user_id:
            raise ValueError("portfolio_id and user_id are required")
        session = self.get_session()
        try:
            portfolio = session.query(UserPortfolio).filter_by(id=portfolio_id).first()
            if portfolio and portfolio.user_id != user_id:
                raise PermissionError("portfolio not found")

            if portfolio:
                portfolio.name = name
                portfolio.description = description
                portfolio.stocks = stocks
                portfolio.updated_at = datetime.now()
            else:
                portfolio = UserPortfolio(
                    id=portfolio_id,
                    user_id=user_id,
                    name=name,
                    description=description,
                    stocks=stocks,
                )
                session.add(portfolio)

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def _begin_serialized_write(self, session: Session) -> None:
        """Serialize SQLite writes; PostgreSQL callers use row locks below."""
        if self.engine.dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))

    def create_user_portfolio(
        self,
        portfolio_id: str,
        user_id: str,
        name: str,
        description: str,
    ) -> None:
        """Create one active portfolio while serializing name checks per owner."""
        session = self.get_session()
        try:
            self._begin_serialized_write(session)
            owner = session.query(User).filter_by(id=user_id).with_for_update().first()
            if owner is None:
                raise PermissionError("portfolio owner not found")
            duplicate = (
                session.query(UserPortfolio)
                .filter_by(
                    user_id=user_id,
                    name=name,
                    archived_at=None,
                    deleted_at=None,
                )
                .first()
            )
            if duplicate is not None:
                raise ValueError("组合名称已存在")
            session.add(
                UserPortfolio(
                    id=portfolio_id,
                    user_id=user_id,
                    name=name,
                    description=description,
                    stocks=[],
                )
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def update_portfolio_metadata(
        self,
        portfolio_id: str,
        user_id: str,
        name: str,
        description: str,
    ) -> None:
        """Update metadata without overwriting concurrently changed positions."""
        session = self.get_session()
        try:
            self._begin_serialized_write(session)
            owner = session.query(User).filter_by(id=user_id).with_for_update().first()
            if owner is None:
                raise PermissionError("portfolio owner not found")
            portfolio = (
                session.query(UserPortfolio)
                .filter_by(
                    id=portfolio_id,
                    user_id=user_id,
                    archived_at=None,
                    deleted_at=None,
                )
                .with_for_update()
                .first()
            )
            if portfolio is None:
                raise PermissionError("portfolio not found")
            duplicate = (
                session.query(UserPortfolio)
                .filter(
                    UserPortfolio.user_id == user_id,
                    UserPortfolio.name == name,
                    UserPortfolio.id != portfolio_id,
                    UserPortfolio.archived_at.is_(None),
                    UserPortfolio.deleted_at.is_(None),
                )
                .first()
            )
            if duplicate is not None:
                raise ValueError("组合名称已存在")
            portfolio.name = name
            portfolio.description = description
            portfolio.updated_at = datetime.now()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def add_portfolio_stock(
        self,
        portfolio_id: str,
        user_id: str,
        stock: dict[str, object],
    ) -> list[dict[str, object]]:
        """Atomically append one unique stock position to an active portfolio."""
        symbol = stock.get("symbol") if isinstance(stock, dict) else None
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("stock symbol is required")
        session = self.get_session()
        try:
            self._begin_serialized_write(session)
            portfolio = (
                session.query(UserPortfolio)
                .filter_by(
                    id=portfolio_id,
                    user_id=user_id,
                    archived_at=None,
                    deleted_at=None,
                )
                .with_for_update()
                .first()
            )
            if portfolio is None:
                raise PermissionError("portfolio not found")
            stocks = [
                item for item in (portfolio.stocks or []) if isinstance(item, dict)
            ]
            if any(item.get("symbol") == symbol for item in stocks):
                raise ValueError("该股票已在组合中")
            stocks.append(dict(stock))
            portfolio.stocks = stocks
            portfolio.updated_at = datetime.now()
            session.commit()
            return stocks
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def remove_portfolio_stock(
        self,
        portfolio_id: str,
        user_id: str,
        symbol: str,
    ) -> tuple[bool, list[dict[str, object]]]:
        """Atomically remove a stock and return the latest position snapshot."""
        session = self.get_session()
        try:
            self._begin_serialized_write(session)
            portfolio = (
                session.query(UserPortfolio)
                .filter_by(
                    id=portfolio_id,
                    user_id=user_id,
                    archived_at=None,
                    deleted_at=None,
                )
                .with_for_update()
                .first()
            )
            if portfolio is None:
                return False, []
            stocks = [
                item for item in (portfolio.stocks or []) if isinstance(item, dict)
            ]
            retained = [item for item in stocks if item.get("symbol") != symbol]
            changed = len(retained) != len(stocks)
            if changed:
                portfolio.stocks = retained
                portfolio.updated_at = datetime.now()
                session.commit()
            return changed, retained
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def get_portfolio(self, portfolio_id: str, user_id: str):
        """获取投资组合"""
        if not portfolio_id or not user_id:
            raise ValueError("portfolio_id and user_id are required")
        session = self.get_session()
        try:
            return (
                session.query(UserPortfolio)
                .filter_by(id=portfolio_id, user_id=user_id, deleted_at=None)
                .first()
            )
        finally:
            self.SessionLocal.remove()

    def delete_portfolio(self, portfolio_id: str, user_id: str) -> bool:
        """Delete a portfolio only when it belongs to the requesting user."""
        if not portfolio_id or not user_id:
            raise ValueError("portfolio_id and user_id are required")
        session = self.get_session()
        try:
            portfolio = (
                session.query(UserPortfolio)
                .filter_by(
                    id=portfolio_id,
                    user_id=user_id,
                )
                .first()
            )
            if not portfolio:
                return False
            portfolio.deleted_at = datetime.now()
            portfolio.updated_at = datetime.now()
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def get_user_portfolios(self, user_id: str):
        """Return active, non-deleted portfolios for one owner."""
        session = self.get_session()
        try:
            return (
                session.query(UserPortfolio)
                .filter_by(user_id=user_id, archived_at=None, deleted_at=None)
                .all()
            )
        finally:
            self.SessionLocal.remove()

    def get_portfolios_by_state(self, user_id: str, state: str):
        if state not in {"archived", "deleted"}:
            raise ValueError("invalid portfolio state")
        session = self.get_session()
        try:
            query = session.query(UserPortfolio).filter_by(user_id=user_id)
            if state == "archived":
                query = query.filter(
                    UserPortfolio.archived_at.is_not(None),
                    UserPortfolio.deleted_at.is_(None),
                )
            else:
                query = query.filter(UserPortfolio.deleted_at.is_not(None))
            return query.order_by(UserPortfolio.updated_at.desc()).all()
        finally:
            self.SessionLocal.remove()

    def set_portfolio_state(self, portfolio_id: str, user_id: str, state: str) -> bool:
        if state not in {"active", "archived", "deleted"}:
            raise ValueError("invalid portfolio state")
        session = self.get_session()
        try:
            portfolio = (
                session.query(UserPortfolio)
                .filter_by(id=portfolio_id, user_id=user_id)
                .first()
            )
            if portfolio is None:
                return False
            now = datetime.now()
            if state == "active":
                portfolio.archived_at = None
                portfolio.deleted_at = None
            elif state == "archived":
                portfolio.archived_at = now
                portfolio.deleted_at = None
            else:
                portfolio.deleted_at = now
            portfolio.updated_at = now
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def get_all_portfolio_symbols(self) -> list[str]:
        """Return unique symbols across all users for background quote refresh."""
        session = self.get_session()
        try:
            symbols: set[str] = set()
            for portfolio in (
                session.query(UserPortfolio)
                .filter_by(archived_at=None, deleted_at=None)
                .all()
            ):
                for stock in portfolio.stocks or []:
                    if isinstance(stock, dict):
                        symbol = stock.get("symbol")
                        if isinstance(symbol, str) and symbol:
                            symbols.add(symbol)
            return sorted(symbols)
        finally:
            self.SessionLocal.remove()

    def get_active_alert_user_ids(self) -> list[str]:
        """Return owners that currently have active alert rules."""
        session = self.get_session()
        try:
            rows = (
                session.query(AlertRule.user_id)
                .filter_by(status="active")
                .distinct()
                .all()
            )
            return sorted(user_id for (user_id,) in rows if user_id)
        finally:
            self.SessionLocal.remove()

    def get_triggered_alert_user_ids(self) -> list[str]:
        """Return owners that currently have triggered alert rules."""
        session = self.get_session()
        try:
            rows = (
                session.query(AlertRule.user_id)
                .filter_by(status="triggered")
                .distinct()
                .all()
            )
            return sorted(user_id for (user_id,) in rows if user_id)
        finally:
            self.SessionLocal.remove()

    def save_alert(
        self,
        alert_id: str,
        user_id: str,
        symbol: str,
        alert_type: str,
        threshold: float,
        message: str,
    ):
        """保存预警规则"""
        session = self.get_session()
        try:
            alert = AlertRule(
                id=alert_id,
                user_id=user_id,
                symbol=symbol,
                alert_type=alert_type,
                threshold=threshold,
                message=message,
            )
            session.add(alert)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def get_user_alerts(self, user_id: str):
        """获取用户的所有预警"""
        session = self.get_session()
        try:
            return session.query(AlertRule).filter_by(user_id=user_id).all()
        finally:
            self.SessionLocal.remove()

    def log_activity(
        self,
        user_id: str,
        action: str,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ):
        """记录用户活动"""
        session = self.get_session()
        try:
            activity = UserActivity(
                user_id=user_id,
                action=action,
                details=details or {},
                ip_address=ip_address,
            )
            session.add(activity)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            self.SessionLocal.remove()

    def save_backtest_result(
        self,
        result_id: str,
        user_id: str,
        strategy_name: str,
        symbols: list,
        start_date: datetime,
        end_date: datetime,
        initial_cash: float,
        final_value: float,
        total_return: float,
        annual_return: float,
        max_drawdown: float,
        sharpe_ratio: float,
        total_trades: int,
        daily_values: list,
    ):
        """保存回测结果"""
        session = self.get_session()
        try:
            result = BacktestResult(
                id=result_id,
                user_id=user_id,
                strategy_name=strategy_name,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                final_value=final_value,
                total_return=total_return,
                annual_return=annual_return,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                total_trades=total_trades,
                daily_values=daily_values,
            )
            session.add(result)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.SessionLocal.remove()

    def get_backtest_results(self, user_id: str, limit: int = 100):
        """获取回测结果"""
        if not user_id:
            raise ValueError("user_id is required")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 500
        ):
            raise ValueError("limit must be between 1 and 500")
        session = self.get_session()
        try:
            query = session.query(BacktestResult).filter_by(user_id=user_id)
            return query.order_by(BacktestResult.created_at.desc()).limit(limit).all()
        finally:
            self.SessionLocal.remove()


# 全局数据库实例
db_manager = None


def init_db(database_url: Optional[str] = None) -> DatabaseManager:
    """初始化数据库"""
    global db_manager
    db_manager = DatabaseManager(database_url)
    return db_manager


def get_db() -> DatabaseManager:
    """获取数据库管理器实例"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager
