from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, JSON, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os

Base = declarative_base()

class StockData(Base):
    """股票数据表"""
    __tablename__ = 'stock_data'
    
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

class UserPortfolio(Base):
    """用户投资组合表"""
    __tablename__ = 'user_portfolios'
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    stocks = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class AlertRule(Base):
    """预警规则表"""
    __tablename__ = 'alert_rules'
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), index=True, nullable=False)
    symbol = Column(String(10), index=True, nullable=False)
    alert_type = Column(String(20), nullable=False)
    threshold = Column(Float, nullable=False)
    message = Column(String(500))
    status = Column(String(20), default='active')
    created_at = Column(DateTime, default=datetime.now)
    triggered_at = Column(DateTime)
    trigger_count = Column(Integer, default=0)

class UserActivity(Base):
    """用户活动日志表"""
    __tablename__ = 'user_activities'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), index=True, nullable=False)
    action = Column(String(50), nullable=False)
    details = Column(JSON)
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)

class ResearchReport(Base):
    """研报数据表"""
    __tablename__ = 'research_reports'
    
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
    __tablename__ = 'backtest_results'
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), index=True)
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
    
    def __init__(self, database_url: str = None):
        if not database_url:
            # 默认使用SQLite
            database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/stock_monitor.db')
        
        self.engine = create_engine(database_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()
    
    def close(self):
        """关闭数据库连接"""
        self.engine.dispose()
    
    def save_stock_data(self, symbol: str, data: dict):
        """保存股票数据"""
        session = self.get_session()
        try:
            stock_data = StockData(
                symbol=symbol,
                date=data.get('date'),
                open_price=data.get('open'),
                high_price=data.get('high'),
                low_price=data.get('low'),
                close_price=data.get('close'),
                volume=data.get('volume'),
                turnover=data.get('turnover')
            )
            session.add(stock_data)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_stock_data(self, symbol: str, start_date: datetime = None, end_date: datetime = None):
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
            session.close()
    
    def save_portfolio(self, portfolio_id: str, user_id: str, name: str, 
                       description: str, stocks: list):
        """保存投资组合"""
        session = self.get_session()
        try:
            portfolio = session.query(UserPortfolio).filter_by(id=portfolio_id).first()
            
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
                    stocks=stocks
                )
                session.add(portfolio)
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_portfolio(self, portfolio_id: str):
        """获取投资组合"""
        session = self.get_session()
        try:
            return session.query(UserPortfolio).filter_by(id=portfolio_id).first()
        finally:
            session.close()
    
    def get_user_portfolios(self, user_id: str):
        """获取用户的所有投资组合"""
        session = self.get_session()
        try:
            return session.query(UserPortfolio).filter_by(user_id=user_id).all()
        finally:
            session.close()
    
    def save_alert(self, alert_id: str, user_id: str, symbol: str, 
                   alert_type: str, threshold: float, message: str):
        """保存预警规则"""
        session = self.get_session()
        try:
            alert = AlertRule(
                id=alert_id,
                user_id=user_id,
                symbol=symbol,
                alert_type=alert_type,
                threshold=threshold,
                message=message
            )
            session.add(alert)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_user_alerts(self, user_id: str):
        """获取用户的所有预警"""
        session = self.get_session()
        try:
            return session.query(AlertRule).filter_by(user_id=user_id).all()
        finally:
            session.close()
    
    def log_activity(self, user_id: str, action: str, details: dict = None, ip_address: str = None):
        """记录用户活动"""
        session = self.get_session()
        try:
            activity = UserActivity(
                user_id=user_id,
                action=action,
                details=details or {},
                ip_address=ip_address
            )
            session.add(activity)
            session.commit()
        except Exception as e:
            session.rollback()
        finally:
            session.close()
    
    def save_backtest_result(self, result_id: str, user_id: str, strategy_name: str,
                            symbols: list, start_date: datetime, end_date: datetime,
                            initial_cash: float, final_value: float, total_return: float,
                            annual_return: float, max_drawdown: float, sharpe_ratio: float,
                            total_trades: int, daily_values: list):
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
                daily_values=daily_values
            )
            session.add(result)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_backtest_results(self, user_id: str = None, limit: int = 100):
        """获取回测结果"""
        session = self.get_session()
        try:
            query = session.query(BacktestResult)
            if user_id:
                query = query.filter_by(user_id=user_id)
            return query.order_by(BacktestResult.created_at.desc()).limit(limit).all()
        finally:
            session.close()

# 全局数据库实例
db_manager = None

def init_db(database_url: str = None) -> DatabaseManager:
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
