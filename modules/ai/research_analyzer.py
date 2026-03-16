"""
智能研报分析模块
实现研报自动总结、多研报对比分析等功能
"""

import re
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import pandas as pd

from modules.ai.multi_model import MultiModelAI, AIModel, get_ai_manager


@dataclass
class ResearchReport:
    """研报数据结构"""
    id: str
    title: str
    stock_symbol: str
    stock_name: str
    author: str
    institution: str
    publish_date: datetime
    rating: str = ""  # 评级：买入、增持、中性、减持
    target_price: Optional[float] = None
    current_price: Optional[float] = None
    content: str = ""
    summary: str = ""
    investment_points: List[str] = field(default_factory=list)
    risk_warnings: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    pages: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'stock_symbol': self.stock_symbol,
            'stock_name': self.stock_name,
            'author': self.author,
            'institution': self.institution,
            'publish_date': self.publish_date.isoformat(),
            'rating': self.rating,
            'target_price': self.target_price,
            'current_price': self.current_price,
            'summary': self.summary,
            'investment_points': self.investment_points,
            'risk_warnings': self.risk_warnings,
            'keywords': self.keywords,
            'pages': self.pages
        }


@dataclass
class ReportComparison:
    """研报对比结果"""
    stock_symbol: str
    reports_analyzed: int
    consensus_rating: str
    rating_consistency: float  # 评级一致性 (0-1)
    avg_target_price: Optional[float]
    target_price_range: tuple
    price_upside: Optional[float]  # 上涨空间
    common_points: List[str]
    divergent_points: List[str]
    risk_consensus: List[str]
    confidence_score: float  # 综合置信度


class ResearchAnalyzer:
    """研报智能分析器"""
    
    # 评级映射
    RATING_MAP = {
        '买入': 5,
        '增持': 4,
        '推荐': 4,
        '中性': 3,
        '持有': 3,
        '减持': 2,
        '卖出': 1,
        'buy': 5,
        'overweight': 4,
        'outperform': 4,
        'hold': 3,
        'neutral': 3,
        'underweight': 2,
        'sell': 1
    }
    
    def __init__(self, ai_manager: MultiModelAI = None):
        self.ai = ai_manager or get_ai_manager()
        self.analysis_cache = {}
        self.cache_ttl = 3600  # 缓存1小时
    
    def analyze_report(self, report: ResearchReport, 
                       use_ai: bool = True) -> ResearchReport:
        """
        分析单篇研报
        
        Args:
            report: 研报数据
            use_ai: 是否使用AI进行分析
            
        Returns:
            分析后的研报
        """
        if not use_ai or not report.content:
            return self._rule_based_analysis(report)
        
        # 使用AI进行分析
        system_prompt = """你是一位专业的金融分析师，擅长分析股票研究报告。
请从以下研报中提取关键信息，并以JSON格式返回：
{
    "summary": "研报核心观点总结（200字以内）",
    "investment_points": ["投资要点1", "投资要点2", ...],
    "risk_warnings": ["风险提示1", "风险提示2", ...],
    "rating": "评级（买入/增持/中性/减持/卖出）",
    "target_price": 目标价（数字，没有则填null）,
    "keywords": ["关键词1", "关键词2", ...]
}"""
        
        prompt = f"""请分析以下研报：

标题：{report.title}
股票：{report.stock_name} ({report.stock_symbol})
机构：{report.institution}
作者：{report.author}
发布日期：{report.publish_date.strftime('%Y-%m-%d')}

研报内容：
{report.content[:8000]}  # 限制长度

请提取关键信息并以JSON格式返回。"""
        
        try:
            response = self.ai.generate_response(prompt, system_prompt)
            
            # 解析JSON响应
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                
                report.summary = analysis.get('summary', '')
                report.investment_points = analysis.get('investment_points', [])
                report.risk_warnings = analysis.get('risk_warnings', [])
                report.rating = analysis.get('rating', '')
                report.target_price = analysis.get('target_price')
                report.keywords = analysis.get('keywords', [])
            else:
                report = self._rule_based_analysis(report)
                
        except Exception as e:
            print(f"AI分析失败，使用规则分析: {e}")
            report = self._rule_based_analysis(report)
        
        return report
    
    def _rule_based_analysis(self, report: ResearchReport) -> ResearchReport:
        """基于规则的分析（备用方案）"""
        content = report.content
        
        # 提取投资要点
        investment_patterns = [
            r'投资要点[：:]\s*([^\n]+)',
            r'核心观点[：:]\s*([^\n]+)',
            r'推荐理由[：:]\s*([^\n]+)',
        ]
        
        for pattern in investment_patterns:
            matches = re.findall(pattern, content)
            if matches:
                report.investment_points = matches[:5]
                break
        
        # 提取风险提示
        risk_patterns = [
            r'风险提示[：:]\s*([^\n]+)',
            r'风险因素[：:]\s*([^\n]+)',
            r'主要风险[：:]\s*([^\n]+)',
        ]
        
        for pattern in risk_patterns:
            matches = re.findall(pattern, content)
            if matches:
                report.risk_warnings = matches[:5]
                break
        
        # 提取目标价
        price_patterns = [
            r'目标价[：:]\s*(\d+\.?\d*)',
            r'目标价格[：:]\s*(\d+\.?\d*)',
            r'target price[：:]\s*(\d+\.?\d*)',
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                report.target_price = float(match.group(1))
                break
        
        # 提取评级
        for rating, _ in self.RATING_MAP.items():
            if rating in content:
                report.rating = rating
                break
        
        # 生成摘要
        lines = content.split('\n')
        report.summary = lines[0][:200] if lines else ""
        
        return report
    
    def compare_reports(self, reports: List[ResearchReport]) -> ReportComparison:
        """
        对比多篇研报
        
        Args:
            reports: 研报列表
            
        Returns:
            对比结果
        """
        if not reports:
            return None
        
        stock_symbol = reports[0].stock_symbol
        
        # 收集评级
        ratings = [r.rating for r in reports if r.rating]
        rating_scores = [self.RATING_MAP.get(r.lower(), 3) for r in ratings]
        
        # 计算评级一致性
        if rating_scores:
            avg_rating = sum(rating_scores) / len(rating_scores)
            variance = sum((s - avg_rating) ** 2 for s in rating_scores) / len(rating_scores)
            rating_consistency = max(0, 1 - variance / 4)  # 归一化到0-1
            
            # 确定共识评级
            consensus_rating = self._get_rating_text(round(avg_rating))
        else:
            rating_consistency = 0
            consensus_rating = "未知"
        
        # 目标价统计
        target_prices = [r.target_price for r in reports if r.target_price]
        if target_prices:
            avg_target_price = sum(target_prices) / len(target_prices)
            price_range = (min(target_prices), max(target_prices))
            
            # 计算上涨空间
            current_price = reports[0].current_price
            if current_price and current_price > 0:
                price_upside = (avg_target_price - current_price) / current_price * 100
            else:
                price_upside = None
        else:
            avg_target_price = None
            price_range = (None, None)
            price_upside = None
        
        # 收集共同观点
        all_points = []
        for r in reports:
            all_points.extend(r.investment_points)
        
        common_points = self._find_common_themes(all_points)
        
        # 收集分歧点
        divergent_points = self._find_divergent_points(reports)
        
        # 风险共识
        all_risks = []
        for r in reports:
            all_risks.extend(r.risk_warnings)
        risk_consensus = self._find_common_themes(all_risks, min_count=2)
        
        # 计算置信度
        confidence = self._calculate_confidence(
            len(reports), rating_consistency, len(common_points), len(target_prices)
        )
        
        return ReportComparison(
            stock_symbol=stock_symbol,
            reports_analyzed=len(reports),
            consensus_rating=consensus_rating,
            rating_consistency=round(rating_consistency, 2),
            avg_target_price=round(avg_target_price, 2) if avg_target_price else None,
            target_price_range=price_range,
            price_upside=round(price_upside, 2) if price_upside else None,
            common_points=common_points,
            divergent_points=divergent_points,
            risk_consensus=risk_consensus,
            confidence_score=round(confidence, 2)
        )
    
    def _get_rating_text(self, score: int) -> str:
        """将评分转换为评级文本"""
        rating_map = {
            5: '买入',
            4: '增持',
            3: '中性',
            2: '减持',
            1: '卖出'
        }
        return rating_map.get(score, '中性')
    
    def _find_common_themes(self, points: List[str], min_count: int = 2) -> List[str]:
        """找出共同主题"""
        if not points:
            return []
        
        # 简单的关键词匹配
        keyword_counts = defaultdict(int)
        keyword_to_points = defaultdict(list)
        
        for point in points:
            # 提取关键词（简单实现）
            words = re.findall(r'[\u4e00-\u9fa5]{2,}', point)
            for word in words:
                if len(word) >= 4:  # 至少4个字符
                    keyword_counts[word] += 1
                    keyword_to_points[word].append(point)
        
        # 返回高频主题
        common = []
        for keyword, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True):
            if count >= min_count:
                # 选择最短的包含该关键词的句子
                shortest = min(keyword_to_points[keyword], key=len)
                if shortest not in common:
                    common.append(shortest)
        
        return common[:5]
    
    def _find_divergent_points(self, reports: List[ResearchReport]) -> List[str]:
        """找出分歧点"""
        divergent = []
        
        # 评级分歧
        ratings = [r.rating for r in reports if r.rating]
        if len(set(ratings)) > 1:
            divergent.append(f"评级存在分歧：{', '.join(set(ratings))}")
        
        # 目标价分歧
        target_prices = [r.target_price for r in reports if r.target_price]
        if len(target_prices) >= 2:
            max_price = max(target_prices)
            min_price = min(target_prices)
            if max_price / min_price > 1.2:  # 差异超过20%
                divergent.append(f"目标价分歧较大：{min_price:.2f} - {max_price:.2f}元")
        
        return divergent
    
    def _calculate_confidence(self, report_count: int, rating_consistency: float,
                             common_points_count: int, target_price_count: int) -> float:
        """计算综合置信度"""
        # 基于研报数量
        count_score = min(report_count / 5, 1.0) * 30  # 最多5篇，权重30%
        
        # 基于评级一致性
        consistency_score = rating_consistency * 30  # 权重30%
        
        # 基于观点共识
        points_score = min(common_points_count / 3, 1.0) * 20  # 权重20%
        
        # 基于目标价覆盖
        price_score = min(target_price_count / 3, 1.0) * 20  # 权重20%
        
        return count_score + consistency_score + points_score + price_score
    
    def generate_summary_report(self, comparison: ReportComparison) -> str:
        """
        生成研报总结报告
        
        Args:
            comparison: 研报对比结果
            
        Returns:
            总结报告文本
        """
        lines = [
            f"# {comparison.stock_symbol} 研报综合分析",
            "",
            f"**分析研报数量**: {comparison.reports_analyzed}篇",
            f"**综合评级**: {comparison.consensus_rating}",
            f"**评级一致性**: {comparison.rating_consistency * 100:.0f}%",
            "",
            "## 目标价分析",
        ]
        
        if comparison.avg_target_price:
            lines.extend([
                f"- 平均目标价: {comparison.avg_target_price:.2f}元",
                f"- 目标价区间: {comparison.target_price_range[0]:.2f} - {comparison.target_price_range[1]:.2f}元",
            ])
            if comparison.price_upside:
                lines.append(f"- 上涨空间: {comparison.price_upside:+.2f}%")
        else:
            lines.append("- 暂无目标价数据")
        
        lines.extend([
            "",
            "## 投资要点共识",
        ])
        
        if comparison.common_points:
            for point in comparison.common_points:
                lines.append(f"- {point}")
        else:
            lines.append("- 暂无明确共识")
        
        if comparison.divergent_points:
            lines.extend([
                "",
                "## 观点分歧",
            ])
            for point in comparison.divergent_points:
                lines.append(f"- ⚠️ {point}")
        
        lines.extend([
            "",
            "## 风险提示",
        ])
        
        if comparison.risk_consensus:
            for risk in comparison.risk_consensus:
                lines.append(f"- {risk}")
        else:
            lines.append("- 请查看具体研报了解风险")
        
        lines.extend([
            "",
            f"**综合置信度**: {comparison.confidence_score:.0f}/100",
            "",
            "*免责声明：以上分析仅供参考，不构成投资建议。*"
        ])
        
        return '\n'.join(lines)
    
    def batch_analyze(self, reports_data: List[Dict[str, Any]]) -> List[ResearchReport]:
        """
        批量分析研报
        
        Args:
            reports_data: 研报原始数据列表
            
        Returns:
            分析后的研报列表
        """
        results = []
        
        for data in reports_data:
            report = ResearchReport(
                id=data.get('id', ''),
                title=data.get('title', ''),
                stock_symbol=data.get('stock_symbol', ''),
                stock_name=data.get('stock_name', ''),
                author=data.get('author', ''),
                institution=data.get('institution', ''),
                publish_date=data.get('publish_date', datetime.now()),
                current_price=data.get('current_price'),
                content=data.get('content', '')
            )
            
            analyzed = self.analyze_report(report)
            results.append(analyzed)
        
        return results
    
    def get_rating_trend(self, reports: List[ResearchReport]) -> pd.DataFrame:
        """
        获取评级趋势
        
        Args:
            reports: 研报列表
            
        Returns:
            评级趋势DataFrame
        """
        if not reports:
            return pd.DataFrame()
        
        # 按日期排序
        sorted_reports = sorted(reports, key=lambda x: x.publish_date)
        
        data = []
        for r in sorted_reports:
            if r.rating:
                data.append({
                    'date': r.publish_date,
                    'institution': r.institution,
                    'rating': r.rating,
                    'rating_score': self.RATING_MAP.get(r.rating.lower(), 3),
                    'target_price': r.target_price
                })
        
        return pd.DataFrame(data)
