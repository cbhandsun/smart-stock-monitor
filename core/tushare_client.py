"""
Tushare Pro API 封装
单例客户端，带限频控制和 PostgreSQL 写入
"""

import os
import time
import logging
from typing import Optional
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

# ---- 单例客户端 ----

_client = None


class TushareClient:
    """Tushare Pro 客户端 (带限频 + PG 存储)"""

    def __init__(self, token: str = None):
        self.token = token or os.getenv('TUSHARE_TOKEN', '')
        self._pro = None
        self._call_count = 0
        self._minute_start = time.time()
        self._max_calls_per_min = 480  # 留 20 余量

    @property
    def pro(self):
        """懒加载 tushare pro api"""
        if self._pro is None and self.token:
            import tushare as ts
            ts.set_token(self.token)
            self._pro = ts.pro_api()
        return self._pro

    @property
    def available(self) -> bool:
        return bool(self.token and self.pro)

    def _rate_limit(self):
        """限频: 500次/分钟"""
        now = time.time()
        if now - self._minute_start > 60:
            self._call_count = 0
            self._minute_start = now

        if self._call_count >= self._max_calls_per_min:
            wait = 60 - (now - self._minute_start)
            if wait > 0:
                logger.info(f"Tushare 限频等待 {wait:.1f}s")
                time.sleep(wait)
            self._call_count = 0
            self._minute_start = time.time()

        self._call_count += 1

    # ---- 股票基础信息 ----

    def get_stock_basic(self) -> Optional[pd.DataFrame]:
        """获取全部 A 股基础信息，写入 PG"""
        if not self.available:
            return None
        try:
            self._rate_limit()
            df = self.pro.stock_basic(
                exchange='',
                list_status='L',
                fields='ts_code,symbol,name,area,industry,market,list_date'
            )
            if df is not None and not df.empty:
                # 写入 PG
                try:
                    from core.database import write_stock_basic
                    write_stock_basic(df)
                except Exception as e:
                    logger.warning(f"PG write stock_basic failed: {e}")
                return df
            return None
        except Exception as e:
            logger.error(f"Tushare get_stock_basic error: {e}")
            return None

    def get_stock_company(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取上市公司基本信息（公司简介、主营业务、董事长等）"""
        if not self.available:
            return None
        ts_code = self._symbol_to_ts_code(symbol)
        try:
            self._rate_limit()
            df = self.pro.stock_company(
                ts_code=ts_code,
                fields='ts_code,chairman,manager,secretary,reg_capital,setup_date,'
                       'province,city,introduction,website,email,employees,'
                       'main_business,business_scope'
            )
            if df is not None and not df.empty:
                return df.iloc[0:1]
            return None
        except Exception as e:
            logger.error(f"Tushare stock_company error: {e}")
            return None

    def get_name_map(self) -> dict:
        """获取 symbol -> name 映射 (优先 PG, 缺失拉 Tushare)"""
        # 优先从 PG 读
        try:
            from core.database import read_stock_basic
            df = read_stock_basic()
            if df is not None and len(df) > 100:
                return dict(zip(df['symbol'], df['name']))
        except Exception:
            pass

        # PG 无数据则从 Tushare 拉取
        df = self.get_stock_basic()
        if df is not None and not df.empty:
            return dict(zip(df['symbol'], df['name']))
        return {}

    # ---- 日线 K 线 ----

    def _symbol_to_ts_code(self, symbol: str) -> str:
        """转换代码格式: 000001/sz000001 -> 000001.SZ"""
        if '.' in symbol:
            return symbol
        code = symbol
        if code.startswith(('sh', 'sz')):
            prefix = code[:2]
            code = code[2:]
        else:
            prefix = 'sh' if code.startswith('6') else 'sz'
        exchange = 'SH' if prefix == 'sh' else 'SZ'
        return f"{code}.{exchange}"

    def get_daily(self, symbol: str, start_date: str = None,
                  limit: int = 200) -> Optional[pd.DataFrame]:
        """
        获取日线数据: PG → Tushare → PG
        返回统一格式 DataFrame (日期,开盘,最高,最低,收盘,成交量)
        """
        ts_code = self._symbol_to_ts_code(symbol)

        # 1. 尝试从 PG 读取
        try:
            from core.database import read_kline, write_kline
            pg_df = read_kline(ts_code, 'kline_daily', limit * 2)
            if pg_df is not None and len(pg_df) >= limit:
                return self._format_kline(pg_df, limit)
        except Exception:
            pass

        # 2. 从 Tushare 拉取
        if not self.available:
            return None

        try:
            self._rate_limit()
            if not start_date:
                start_date = (datetime.now() - timedelta(days=limit * 2)).strftime('%Y%m%d')
            df = self.pro.daily(ts_code=ts_code, start_date=start_date)
            if df is None or df.empty:
                return None

            # 写入 PG
            try:
                from core.database import write_kline
                write_kline(df, ts_code, 'kline_daily')
            except Exception as e:
                logger.warning(f"PG write daily failed: {e}")

            return self._format_kline(df, limit)
        except Exception as e:
            logger.error(f"Tushare get_daily error for {symbol}: {e}")
            return None

    def get_weekly(self, symbol: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """获取周线数据"""
        ts_code = self._symbol_to_ts_code(symbol)

        # PG 先读
        try:
            from core.database import read_kline, write_kline
            pg_df = read_kline(ts_code, 'kline_weekly', limit * 2)
            if pg_df is not None and len(pg_df) >= limit:
                return self._format_kline(pg_df, limit)
        except Exception:
            pass

        if not self.available:
            return None
        try:
            self._rate_limit()
            start = (datetime.now() - timedelta(days=limit * 10)).strftime('%Y%m%d')
            df = self.pro.weekly(ts_code=ts_code, start_date=start)
            if df is None or df.empty:
                return None
            try:
                from core.database import write_kline
                write_kline(df, ts_code, 'kline_weekly')
            except Exception:
                pass
            return self._format_kline(df, limit)
        except Exception as e:
            logger.error(f"Tushare get_weekly error: {e}")
            return None

    def get_monthly(self, symbol: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """获取月线数据"""
        ts_code = self._symbol_to_ts_code(symbol)

        try:
            from core.database import read_kline, write_kline
            pg_df = read_kline(ts_code, 'kline_monthly', limit * 2)
            if pg_df is not None and len(pg_df) >= limit:
                return self._format_kline(pg_df, limit)
        except Exception:
            pass

        if not self.available:
            return None
        try:
            self._rate_limit()
            start = (datetime.now() - timedelta(days=limit * 35)).strftime('%Y%m%d')
            df = self.pro.monthly(ts_code=ts_code, start_date=start)
            if df is None or df.empty:
                return None
            try:
                from core.database import write_kline
                write_kline(df, ts_code, 'kline_monthly')
            except Exception:
                pass
            return self._format_kline(df, limit)
        except Exception as e:
            logger.error(f"Tushare get_monthly error: {e}")
            return None

    def _format_kline(self, df: pd.DataFrame, limit: int) -> pd.DataFrame:
        """将 Tushare/PG 格式统一为应用格式"""
        df = df.copy()

        # 列名映射
        col_map = {
            'trade_date': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'vol': '成交量',
            'pct_chg': '涨跌幅',
        }
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

        # 确保日期格式 YYYY-MM-DD
        if '日期' in df.columns:
            date_str = df['日期'].astype(str)
            if len(date_str.iloc[0]) == 8:  # 20260316 -> 2026-03-16
                df['日期'] = date_str.str[:4] + '-' + date_str.str[4:6] + '-' + date_str.str[6:]

        # 数值类型
        for col in ['开盘', '最高', '最低', '收盘', '成交量']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 按日期升序排列
        if '日期' in df.columns:
            df = df.sort_values('日期').reset_index(drop=True)

        # 均线
        if '收盘' in df.columns:
            df['MA5'] = df['收盘'].rolling(5).mean()
            df['MA20'] = df['收盘'].rolling(20).mean()
            df['MA60'] = df['收盘'].rolling(60).mean()

        return df.tail(limit).reset_index(drop=True)

    # ---- 财务数据 ----

    def get_fina_indicator(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取财务指标"""
        if not self.available:
            return None
        ts_code = self._symbol_to_ts_code(symbol)
        try:
            self._rate_limit()
            df = self.pro.fina_indicator(
                ts_code=ts_code,
                fields='ts_code,end_date,eps,roe,roa,debt_to_assets,current_ratio,grossprofit_margin,netprofit_yoy,or_yoy'
            )
            if df is not None and not df.empty:
                return df.head(4)  # 最近4个季度
            return None
        except Exception as e:
            logger.error(f"Tushare fina_indicator error: {e}")
            return None

    # ---- 盈利预测 ----

    def get_forecast(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取业绩预告"""
        if not self.available:
            return None
        ts_code = self._symbol_to_ts_code(symbol)
        try:
            self._rate_limit()
            df = self.pro.forecast(ts_code=ts_code)
            return df if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare forecast error: {e}")
            return None

    # ---- 资金流向 ----

    def get_moneyflow(self, trade_date: str = None) -> Optional[pd.DataFrame]:
        """获取个股资金流向"""
        if not self.available:
            return None
        try:
            self._rate_limit()
            if not trade_date:
                trade_date = datetime.now().strftime('%Y%m%d')
            df = self.pro.moneyflow(trade_date=trade_date)
            return df if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare moneyflow error: {e}")
            return None

    # ---- 当日全市场行情 ----

    def get_daily_snapshot(self, trade_date: str = None) -> Optional[pd.DataFrame]:
        """获取全市场当日行情 (替代 fetch_sina_market_snapshot)"""
        if not self.available:
            return None
        try:
            self._rate_limit()
            if not trade_date:
                trade_date = datetime.now().strftime('%Y%m%d')
            df = self.pro.daily(trade_date=trade_date)
            if df is None or df.empty:
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
                self._rate_limit()
                df = self.pro.daily(trade_date=yesterday)
            return df if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare daily_snapshot error: {e}")
            return None

    # ---- 北向资金 (沪深港通) ----

    def get_hsgt_flow(self, days: int = 10) -> Optional[pd.DataFrame]:
        """获取沪深港通资金流向 (近 N 日)"""
        if not self.available:
            return None
        try:
            self._rate_limit()
            start = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')
            df = self.pro.moneyflow_hsgt(start_date=start)
            if df is not None and not df.empty:
                df = df.sort_values('trade_date').tail(days)
                return df
            return None
        except Exception as e:
            logger.error(f"Tushare hsgt_flow error: {e}")
            return None

    # ---- 个股资金流向 ----

    def get_moneyflow_single(self, symbol: str, days: int = 20) -> Optional[pd.DataFrame]:
        """获取单只股票资金流向明细 (超大单/大单/中单/小单)"""
        if not self.available:
            return None
        ts_code = self._symbol_to_ts_code(symbol)
        try:
            self._rate_limit()
            start = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')
            df = self.pro.moneyflow(
                ts_code=ts_code, start_date=start,
                fields='ts_code,trade_date,buy_elg_vol,sell_elg_vol,buy_lg_vol,sell_lg_vol,buy_md_vol,sell_md_vol,buy_sm_vol,sell_sm_vol,net_mf_vol'
            )
            if df is not None and not df.empty:
                return df.sort_values('trade_date').tail(days).reset_index(drop=True)
            return None
        except Exception as e:
            logger.error(f"Tushare moneyflow_single error: {e}")
            return None

    # ---- 融资融券 ----

    def get_margin(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """获取个股融资融券数据"""
        if not self.available:
            return None
        ts_code = self._symbol_to_ts_code(symbol)
        try:
            self._rate_limit()
            start = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')
            df = self.pro.margin_detail(
                ts_code=ts_code, start_date=start,
                fields='trade_date,ts_code,rzye,rzmre,rzche,rqye,rqmcl,rqchl'
            )
            if df is not None and not df.empty:
                return df.sort_values('trade_date').tail(days).reset_index(drop=True)
            return None
        except Exception as e:
            logger.error(f"Tushare margin_detail error: {e}")
            return None

    # ---- 龙虎榜 ----

    def get_top_list(self, symbol: str = None, trade_date: str = None) -> Optional[pd.DataFrame]:
        """获取龙虎榜 (按股票或按日期)"""
        if not self.available:
            return None
        try:
            ts_code = self._symbol_to_ts_code(symbol) if symbol else None

            if trade_date:
                self._rate_limit()
                df = self.pro.top_list(trade_date=trade_date)
                if ts_code and df is not None and not df.empty:
                    df = df[df['ts_code'] == ts_code]
                return df if df is not None and not df.empty else None

            # 按股票查询: 遍历最近 30 个交易日
            results = []
            for i in range(30):
                d = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                self._rate_limit()
                try:
                    df = self.pro.top_list(trade_date=d)
                    if df is not None and not df.empty:
                        if ts_code:
                            matched = df[df['ts_code'] == ts_code]
                            if not matched.empty:
                                results.append(matched)
                        else:
                            return df  # 无 symbol 就返回当日全部
                except Exception:
                    continue
                if len(results) >= 3:
                    break
            if results:
                return pd.concat(results, ignore_index=True)
            return None
        except Exception as e:
            logger.error(f"Tushare top_list error: {e}")
            return None

    def get_top_inst(self, symbol: str = None, trade_date: str = None) -> Optional[pd.DataFrame]:
        """获取龙虎榜营业部明细"""
        if not self.available:
            return None
        try:
            self._rate_limit()
            params = {}
            if symbol:
                params['ts_code'] = self._symbol_to_ts_code(symbol)
            if trade_date:
                params['trade_date'] = trade_date
            df = self.pro.top_inst(**params)
            return df if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare top_inst error: {e}")
            return None

    # ---- 大宗交易 ----

    def get_block_trade(self, symbol: str = None, days: int = 30) -> Optional[pd.DataFrame]:
        """获取大宗交易"""
        if not self.available:
            return None
        try:
            self._rate_limit()
            params = {}
            if symbol:
                params['ts_code'] = self._symbol_to_ts_code(symbol)
            start = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')
            params['start_date'] = start
            df = self.pro.block_trade(**params)
            if df is not None and not df.empty:
                return df.sort_values('trade_date', ascending=False).head(20)
            return None
        except Exception as e:
            logger.error(f"Tushare block_trade error: {e}")
            return None

    # ---- 概念板块 ----

    def get_concept_list(self) -> Optional[pd.DataFrame]:
        """获取概念板块列表"""
        if not self.available:
            return None
        try:
            self._rate_limit()
            df = self.pro.concept()
            return df if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare concept error: {e}")
            return None

    def get_concept_stocks(self, concept_id: str) -> Optional[pd.DataFrame]:
        """获取概念板块成分股"""
        if not self.available:
            return None
        try:
            self._rate_limit()
            df = self.pro.concept_detail(id=concept_id)
            return df if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare concept_detail error: {e}")
            return None

    # ---- 利润表 / 资产负债表 ----

    def get_income(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取利润表 (最近 4 期)"""
        if not self.available:
            return None
        ts_code = self._symbol_to_ts_code(symbol)
        try:
            self._rate_limit()
            df = self.pro.income(
                ts_code=ts_code,
                fields='ts_code,end_date,revenue,operate_profit,total_profit,n_income,basic_eps'
            )
            return df.head(4) if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare income error: {e}")
            return None

    def get_balancesheet(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取资产负债表 (最近 4 期)"""
        if not self.available:
            return None
        ts_code = self._symbol_to_ts_code(symbol)
        try:
            self._rate_limit()
            df = self.pro.balancesheet(
                ts_code=ts_code,
                fields='ts_code,end_date,total_assets,total_liab,total_hldr_eqy_exc_min_int,money_cap'
            )
            return df.head(4) if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare balancesheet error: {e}")
            return None

    # ---- 股东增减持 / 股东人数 ----

    def get_holder_trade(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取股东增减持"""
        if not self.available:
            return None
        ts_code = self._symbol_to_ts_code(symbol)
        try:
            self._rate_limit()
            df = self.pro.stk_holdertrade(ts_code=ts_code)
            return df.head(10) if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare stk_holdertrade error: {e}")
            return None

    def get_holder_number(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取股东人数变化"""
        if not self.available:
            return None
        ts_code = self._symbol_to_ts_code(symbol)
        try:
            self._rate_limit()
            df = self.pro.stk_holdernumber(ts_code=ts_code)
            return df.head(8) if df is not None and not df.empty else None
        except Exception as e:
            logger.error(f"Tushare stk_holdernumber error: {e}")
            return None


def get_ts_client() -> TushareClient:
    """获取 Tushare 客户端单例"""
    global _client
    if _client is None:
        _client = TushareClient()
    return _client


# ============================================================
#  缓存包装器 — st.cache_data 加速 (避免重复 API 请求)
# ============================================================
try:
    import streamlit as st

    @st.cache_data(ttl=14400, show_spinner=False)  # 4h — 财报季度更新
    def cached_fina_indicator(symbol: str):
        return get_ts_client().get_fina_indicator(symbol)

    @st.cache_data(ttl=14400, show_spinner=False)
    def cached_income(symbol: str):
        return get_ts_client().get_income(symbol)

    @st.cache_data(ttl=14400, show_spinner=False)
    def cached_balancesheet(symbol: str):
        return get_ts_client().get_balancesheet(symbol)

    @st.cache_data(ttl=14400, show_spinner=False)
    def cached_forecast(symbol: str):
        return get_ts_client().get_forecast(symbol)

    @st.cache_data(ttl=86400, show_spinner=False)  # 24h — 公司简介极少变
    def cached_stock_company(symbol: str):
        return get_ts_client().get_stock_company(symbol)

    @st.cache_data(ttl=600, show_spinner=False)  # 10min — 资金流盘中变化
    def cached_moneyflow_single(symbol: str, days: int = 20):
        return get_ts_client().get_moneyflow_single(symbol, days)

    @st.cache_data(ttl=600, show_spinner=False)
    def cached_margin(symbol: str, days: int = 30):
        return get_ts_client().get_margin(symbol, days)

    @st.cache_data(ttl=3600, show_spinner=False)  # 1h — 股东数据日更
    def cached_holder_number(symbol: str):
        return get_ts_client().get_holder_number(symbol)

    @st.cache_data(ttl=3600, show_spinner=False)
    def cached_holder_trade(symbol: str):
        return get_ts_client().get_holder_trade(symbol)

except ImportError:
    # 非 Streamlit 环境 (测试 / 脚本) — 无缓存直通
    def cached_fina_indicator(symbol): return get_ts_client().get_fina_indicator(symbol)
    def cached_income(symbol): return get_ts_client().get_income(symbol)
    def cached_balancesheet(symbol): return get_ts_client().get_balancesheet(symbol)
    def cached_forecast(symbol): return get_ts_client().get_forecast(symbol)
    def cached_stock_company(symbol): return get_ts_client().get_stock_company(symbol)
    def cached_moneyflow_single(symbol, days=20): return get_ts_client().get_moneyflow_single(symbol, days)
    def cached_margin(symbol, days=30): return get_ts_client().get_margin(symbol, days)
    def cached_holder_number(symbol): return get_ts_client().get_holder_number(symbol)
    def cached_holder_trade(symbol): return get_ts_client().get_holder_trade(symbol)
