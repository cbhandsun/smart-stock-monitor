"""
PostgreSQL 数据库管理模块
提供连接池、自动建表、增量读写工具
"""

import os
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# ---- 连接管理 (单例) ----

_engine = None


def get_engine():
    """获取 SQLAlchemy 引擎 (单例, 带连接池)"""
    global _engine
    if _engine is not None:
        return _engine

    host = os.getenv('PG_HOST', 'postgres')
    port = os.getenv('PG_PORT', '5432')
    user = os.getenv('PG_USER', 'ssm')
    password = os.getenv('PG_PASSWORD', 'ssm_secure_2026')
    database = os.getenv('PG_DATABASE', 'stock_data')

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

    try:
        _engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,    # 自动检测断连
            pool_recycle=1800,     # 30分钟回收连接
            echo=False,
        )
        # 验证连接
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL 连接成功")
        return _engine
    except Exception as e:
        logger.warning(f"⚠️ PostgreSQL 连接失败: {e}")
        _engine = None
        return None


def init_tables():
    """自动建表 (幂等)"""
    engine = get_engine()
    if not engine:
        return False

    ddl = """
    -- 股票基础信息
    CREATE TABLE IF NOT EXISTS stock_basic (
        ts_code     VARCHAR(16) PRIMARY KEY,  -- 000001.SZ
        symbol      VARCHAR(10) NOT NULL,      -- 000001
        name        VARCHAR(32),
        area        VARCHAR(16),
        industry    VARCHAR(32),
        market      VARCHAR(16),
        list_date   VARCHAR(10),
        updated_at  TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_stock_basic_symbol ON stock_basic(symbol);

    -- 日线行情
    CREATE TABLE IF NOT EXISTS kline_daily (
        ts_code     VARCHAR(16) NOT NULL,
        trade_date  VARCHAR(10) NOT NULL,
        open        NUMERIC(12,4),
        high        NUMERIC(12,4),
        low         NUMERIC(12,4),
        close       NUMERIC(12,4),
        vol         NUMERIC(18,2),  -- 成交量(手)
        amount      NUMERIC(18,2),  -- 成交额(千元)
        pct_chg     NUMERIC(8,4),
        PRIMARY KEY (ts_code, trade_date)
    );
    CREATE INDEX IF NOT EXISTS idx_kline_daily_date ON kline_daily(trade_date);

    -- 周线行情
    CREATE TABLE IF NOT EXISTS kline_weekly (
        ts_code     VARCHAR(16) NOT NULL,
        trade_date  VARCHAR(10) NOT NULL,
        open        NUMERIC(12,4),
        high        NUMERIC(12,4),
        low         NUMERIC(12,4),
        close       NUMERIC(12,4),
        vol         NUMERIC(18,2),
        amount      NUMERIC(18,2),
        pct_chg     NUMERIC(8,4),
        PRIMARY KEY (ts_code, trade_date)
    );

    -- 月线行情
    CREATE TABLE IF NOT EXISTS kline_monthly (
        ts_code     VARCHAR(16) NOT NULL,
        trade_date  VARCHAR(10) NOT NULL,
        open        NUMERIC(12,4),
        high        NUMERIC(12,4),
        low         NUMERIC(12,4),
        close       NUMERIC(12,4),
        vol         NUMERIC(18,2),
        amount      NUMERIC(18,2),
        pct_chg     NUMERIC(8,4),
        PRIMARY KEY (ts_code, trade_date)
    );

    -- 财务指标
    CREATE TABLE IF NOT EXISTS fina_indicator (
        ts_code         VARCHAR(16) NOT NULL,
        end_date        VARCHAR(10) NOT NULL,
        eps             NUMERIC(12,4),
        roe             NUMERIC(8,4),
        roa             NUMERIC(8,4),
        debt_to_assets  NUMERIC(8,4),
        current_ratio   NUMERIC(8,4),
        gross_margin    NUMERIC(8,4),
        netprofit_yoy   NUMERIC(12,4),
        revenue_yoy     NUMERIC(12,4),
        updated_at      TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (ts_code, end_date)
    );
    """

    try:
        with engine.connect() as conn:
            conn.execute(text(ddl))
            conn.commit()
        logger.info("✅ 数据库表初始化完成")
        return True
    except Exception as e:
        logger.error(f"❌ 建表失败: {e}")
        return False


# ---- 读写工具 ----

def read_kline(ts_code: str, table: str = 'kline_daily',
               limit: int = 200) -> Optional[pd.DataFrame]:
    """从 PG 读取 K 线数据"""
    engine = get_engine()
    if not engine:
        return None
    try:
        sql = text(f"""
            SELECT trade_date, open, high, low, close, vol, amount, pct_chg
            FROM {table}
            WHERE ts_code = :code
            ORDER BY trade_date DESC
            LIMIT :limit
        """)
        df = pd.read_sql(sql, engine, params={'code': ts_code, 'limit': limit})
        if df.empty:
            return None
        # 反转为时间升序
        df = df.iloc[::-1].reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"PG read_kline error: {e}")
        return None


def write_kline(df: pd.DataFrame, ts_code: str,
                table: str = 'kline_daily'):
    """写入 K 线数据 (UPSERT)"""
    engine = get_engine()
    if not engine or df is None or df.empty:
        return

    try:
        # 确保有 ts_code 列
        df = df.copy()
        if 'ts_code' not in df.columns:
            df['ts_code'] = ts_code

        # 需要的列
        cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount', 'pct_chg']
        available = [c for c in cols if c in df.columns]
        df_write = df[available].dropna(subset=['trade_date'])

        if df_write.empty:
            return

        # 使用 ON CONFLICT 做 UPSERT
        with engine.connect() as conn:
            for _, row in df_write.iterrows():
                vals = {c: (row[c] if c in row.index else None) for c in available}
                upsert_sql = text(f"""
                    INSERT INTO {table} ({', '.join(available)})
                    VALUES ({', '.join(':' + c for c in available)})
                    ON CONFLICT (ts_code, trade_date) DO UPDATE SET
                    {', '.join(f'{c} = EXCLUDED.{c}' for c in available if c not in ('ts_code', 'trade_date'))}
                """)
                conn.execute(upsert_sql, vals)
            conn.commit()
        logger.debug(f"PG write_kline: {ts_code} {len(df_write)} rows → {table}")
    except Exception as e:
        logger.error(f"PG write_kline error: {e}")


def read_stock_basic(symbol: str = None) -> Optional[pd.DataFrame]:
    """读取股票基础信息"""
    engine = get_engine()
    if not engine:
        return None
    try:
        if symbol:
            sql = text("SELECT * FROM stock_basic WHERE symbol = :sym")
            return pd.read_sql(sql, engine, params={'sym': symbol})
        else:
            return pd.read_sql("SELECT * FROM stock_basic", engine)
    except Exception:
        return None


def write_stock_basic(df: pd.DataFrame):
    """写入股票基础信息 (UPSERT)"""
    engine = get_engine()
    if not engine or df is None or df.empty:
        return
    try:
        cols = ['ts_code', 'symbol', 'name', 'area', 'industry', 'market', 'list_date']
        available = [c for c in cols if c in df.columns]
        df_write = df[available].copy()
        df_write['updated_at'] = datetime.now()

        with engine.connect() as conn:
            for _, row in df_write.iterrows():
                vals = {c: row[c] for c in available}
                vals['updated_at'] = datetime.now()
                upsert_sql = text(f"""
                    INSERT INTO stock_basic ({', '.join(available)}, updated_at)
                    VALUES ({', '.join(':' + c for c in available)}, :updated_at)
                    ON CONFLICT (ts_code) DO UPDATE SET
                    {', '.join(f'{c} = EXCLUDED.{c}' for c in available if c != 'ts_code')},
                    updated_at = EXCLUDED.updated_at
                """)
                conn.execute(upsert_sql, vals)
            conn.commit()
        logger.info(f"PG write_stock_basic: {len(df_write)} rows")
    except Exception as e:
        logger.error(f"PG write_stock_basic error: {e}")
