import pandas as pd
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _get_ak():
    """Lazy import akshare"""
    import akshare as ak

    return ak


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

    def __init__(self):
        self.cache = {}

    def get_stock_reports(self, symbol: str, limit: int = 10) -> pd.DataFrame:
        """获取个股研报"""
        try:
            code = symbol[2:] if symbol.startswith(("sh", "sz")) else symbol
            df = _get_ak().stock_zyjs_report_em(symbol=code)
            return df.head(limit)
        except Exception:
            logger.warning("Stock research request failed")
            return pd.DataFrame()

    def get_industry_reports(self, industry: str, limit: int = 10) -> pd.DataFrame:
        """获取行业研报"""
        try:
            df = _get_ak().stock_research_report_em(symbol=industry)
            return df.head(limit)
        except Exception:
            logger.warning("Industry research request failed")
            return pd.DataFrame()

    def get_latest_reports(self, limit: int = 20) -> pd.DataFrame:
        """获取最新研报"""
        try:
            df = _get_ak().stock_research_report_em()
            return df.head(limit)
        except Exception:
            logger.warning("Recent research request failed")
            return pd.DataFrame()

    def get_analyst_reports(self, analyst: str, limit: int = 10) -> pd.DataFrame:
        """获取分析师研报"""
        try:
            df = _get_ak().stock_research_report_em()
            if "分析师" in df.columns:
                df = df[df["分析师"].str.contains(analyst, na=False)]
            return df.head(limit)
        except Exception:
            logger.warning("Analyst research request failed")
            return pd.DataFrame()

    def get_institution_reports(
        self, institution: str, limit: int = 10
    ) -> pd.DataFrame:
        """获取机构研报"""
        try:
            df = _get_ak().stock_research_report_em()
            if "机构" in df.columns:
                df = df[df["机构"].str.contains(institution, na=False)]
            return df.head(limit)
        except Exception:
            logger.warning("Institutional research request failed")
            return pd.DataFrame()

    def get_rating_distribution(self, symbol: str) -> Dict:
        """获取评级分布"""
        try:
            reports = self.get_stock_reports(symbol, limit=50)
            if reports.empty or "评级" not in reports.columns:
                return {}

            rating_counts = reports["评级"].value_counts().to_dict()
            total = len(reports)

            return {
                "distribution": rating_counts,
                "total": total,
                "latest_rating": reports.iloc[0]["评级"] if len(reports) > 0 else None,
                "latest_target": reports.iloc[0].get("目标价", None)
                if len(reports) > 0
                else None,
            }
        except Exception:
            logger.warning("Rating distribution request failed")
            return {}

    def get_consensus_rating(self, symbol: str) -> str:
        """获取一致评级"""
        distribution = self.get_rating_distribution(symbol)
        if not distribution or "distribution" not in distribution:
            return "暂无评级"

        dist = distribution["distribution"]
        if not dist:
            return "暂无评级"

        rating_scores = {
            "买入": 5,
            "增持": 4,
            "中性": 3,
            "减持": 2,
            "卖出": 1,
            "强烈推荐": 5,
            "推荐": 4,
            "谨慎推荐": 3,
            "回避": 1,
        }

        total_score = 0
        total_count = 0
        for rating, count in dist.items():
            score = rating_scores.get(rating, 3)
            total_score += score * count
            total_count += count

        if total_count == 0:
            return "暂无评级"

        avg_score = total_score / total_count

        if avg_score >= 4.5:
            return "强烈买入"
        elif avg_score >= 4:
            return "买入"
        elif avg_score >= 3:
            return "增持"
        elif avg_score >= 2:
            return "中性"
        else:
            return "减持"

    def search_reports(self, keyword: str, limit: int = 20) -> pd.DataFrame:
        """搜索研报"""
        try:
            df = _get_ak().stock_research_report_em()

            mask = pd.Series([False] * len(df))
            for col in df.columns:
                if df[col].dtype == "object":
                    mask = mask | df[col].str.contains(keyword, na=False, case=False)

            return df[mask].head(limit)
        except Exception:
            logger.warning("Research search failed")
            return pd.DataFrame()
