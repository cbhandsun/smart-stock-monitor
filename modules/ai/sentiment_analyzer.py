"""
情绪分析模块
实现新闻情绪分析、社交媒体情绪监控、情绪指数计算和可视化
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import pandas as pd
import numpy as np

from modules.ai.multi_model import MultiModelAI, AIModel, get_ai_manager


@dataclass
class SentimentResult:
    """情绪分析结果"""
    text: str
    sentiment: str  # positive, negative, neutral
    confidence: float  # 0-1
    score: float  # -1 to 1
    keywords: List[str] = field(default_factory=list)
    aspects: Dict[str, str] = field(default_factory=dict)  # 方面级情绪
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""  # 来源


@dataclass
class SentimentIndex:
    """情绪指数"""
    symbol: str
    overall_sentiment: float  # -100 to 100
    bullish_ratio: float  # 0-1
    bearish_ratio: float  # 0-1
    neutral_ratio: float  # 0-1
    volume: int  # 分析样本数
    trend: str  # rising, falling, stable
    timestamp: datetime = field(default_factory=datetime.now)
    components: Dict[str, float] = field(default_factory=dict)  # 各维度情绪


class SentimentAnalyzer:
    """情绪分析器"""
    
    # 情感词典
    POSITIVE_WORDS = [
        '涨', '上涨', '大涨', '暴涨', '涨停', '利好', '突破', '创新高', '强势',
        '看好', '推荐', '买入', '增持', '超预期', '改善', '增长', '盈利',
        '反弹', '回升', '复苏', '景气', '繁荣', '优势', '领先', '龙头',
        'rise', 'surge', 'rally', 'breakout', 'strong', 'bullish', 'buy',
        'growth', 'profit', 'recovery', 'boom', 'outperform'
    ]
    
    NEGATIVE_WORDS = [
        '跌', '下跌', '大跌', '暴跌', '跌停', '利空', '跌破', '创新低', '弱势',
        '看空', '卖出', '减持', '不及预期', '恶化', '下滑', '亏损', '暴雷',
        '回调', '回落', '衰退', '萧条', '风险', '劣势', '落后', '垫底',
        'fall', 'drop', 'crash', 'breakdown', 'weak', 'bearish', 'sell',
        'decline', 'loss', 'recession', 'risk', 'underperform'
    ]
    
    # 社交媒体特定表达
    SOCIAL_EXPRESSIONS = {
        'positive': ['🚀', '💰', '📈', '👍', '牛', '666', '给力', '稳了'],
        'negative': ['💸', '📉', '👎', '熊', '完了', '割肉', '跌停', '踩雷']
    }
    
    def __init__(self, ai_manager: MultiModelAI = None):
        self.ai = ai_manager or get_ai_manager()
        self.history = defaultdict(lambda: deque(maxlen=1000))  # 历史数据
        self.index_history = defaultdict(list)  # 指数历史
    
    def analyze_text(self, text: str, source: str = "", 
                     use_ai: bool = True) -> SentimentResult:
        """
        分析单条文本情绪
        
        Args:
            text: 文本内容
            source: 来源标识
            use_ai: 是否使用AI分析
            
        Returns:
            情绪分析结果
        """
        if use_ai:
            return self._ai_sentiment_analysis(text, source)
        else:
            return self._rule_based_sentiment(text, source)
    
    def _ai_sentiment_analysis(self, text: str, source: str) -> SentimentResult:
        """使用AI进行情绪分析"""
        system_prompt = """你是一位专业的金融情绪分析师。请分析以下文本的情绪倾向。
以JSON格式返回：
{
    "sentiment": "positive/negative/neutral",
    "score": 0.0,  // -1到1之间，越接近1越正面
    "confidence": 0.0,  // 0到1之间
    "keywords": ["关键词1", "关键词2"],
    "aspects": {
        "价格": "positive/negative/neutral",
        "业绩": "positive/negative/neutral"
    }
}"""
        
        prompt = f"请分析以下金融相关文本的情绪：\n\n{text[:2000]}"
        
        try:
            response = self.ai.generate_response(prompt, system_prompt)
            
            # 解析JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                return SentimentResult(
                    text=text,
                    sentiment=result.get('sentiment', 'neutral'),
                    confidence=result.get('confidence', 0.5),
                    score=result.get('score', 0.0),
                    keywords=result.get('keywords', []),
                    aspects=result.get('aspects', {}),
                    source=source
                )
        except Exception as e:
            print(f"AI情绪分析失败: {e}")
        
        # 失败时回退到规则分析
        return self._rule_based_sentiment(text, source)
    
    def _rule_based_sentiment(self, text: str, source: str) -> SentimentResult:
        """基于规则的情绪分析"""
        text_lower = text.lower()
        
        # 统计正负向词
        pos_count = sum(1 for word in self.POSITIVE_WORDS if word in text)
        neg_count = sum(1 for word in self.NEGATIVE_WORDS if word in text)
        
        # 社交媒体表情
        for emoji in self.SOCIAL_EXPRESSIONS['positive']:
            if emoji in text:
                pos_count += 2
        for emoji in self.SOCIAL_EXPRESSIONS['negative']:
            if emoji in text:
                neg_count += 2
        
        # 计算分数
        total = pos_count + neg_count
        if total == 0:
            sentiment = 'neutral'
            score = 0.0
            confidence = 0.3
        else:
            score = (pos_count - neg_count) / total
            if score > 0.2:
                sentiment = 'positive'
            elif score < -0.2:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            confidence = min(total / 5, 1.0)
        
        # 提取关键词
        keywords = self._extract_keywords(text)
        
        return SentimentResult(
            text=text,
            sentiment=sentiment,
            confidence=confidence,
            score=score,
            keywords=keywords,
            source=source
        )
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        words = re.findall(r'[\u4e00-\u9fa5]{2,6}', text)
        
        # 过滤停用词
        stop_words = {'我们', '你们', '他们', '今天', '明天', '公司', '股票', '市场'}
        keywords = [w for w in words if w not in stop_words]
        
        # 统计频率
        word_freq = defaultdict(int)
        for w in keywords:
            word_freq[w] += 1
        
        # 返回高频词
        return [w for w, _ in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]]
    
    def analyze_news(self, news_items: List[Dict[str, Any]]) -> List[SentimentResult]:
        """
        批量分析新闻情绪
        
        Args:
            news_items: 新闻列表，每项包含title, content, source等
            
        Returns:
            情绪分析结果列表
        """
        results = []
        
        for item in news_items:
            text = f"{item.get('title', '')} {item.get('content', '')}"
            result = self.analyze_text(text, item.get('source', 'news'))
            results.append(result)
        
        return results
    
    def analyze_social_media(self, posts: List[Dict[str, Any]], 
                            platform: str = "xueqiu") -> List[SentimentResult]:
        """
        分析社交媒体帖子
        
        Args:
            posts: 帖子列表
            platform: 平台名称 (xueqiu, guba, weibo等)
            
        Returns:
            情绪分析结果列表
        """
        results = []
        
        for post in posts:
            text = post.get('content', '')
            result = self.analyze_text(text, f"{platform}:{post.get('author', '')}")
            results.append(result)
        
        return results
    
    def calculate_sentiment_index(self, symbol: str, 
                                  results: List[SentimentResult],
                                  time_window: timedelta = None) -> SentimentIndex:
        """
        计算情绪指数
        
        Args:
            symbol: 股票代码
            results: 情绪分析结果列表
            time_window: 时间窗口
            
        Returns:
            情绪指数
        """
        if not results:
            return SentimentIndex(
                symbol=symbol,
                overall_sentiment=0,
                bullish_ratio=0,
                bearish_ratio=0,
                neutral_ratio=0,
                volume=0,
                trend='stable'
            )
        
        # 过滤时间窗口
        if time_window:
            cutoff = datetime.now() - time_window
            results = [r for r in results if r.timestamp >= cutoff]
        
        total = len(results)
        if total == 0:
            return SentimentIndex(
                symbol=symbol,
                overall_sentiment=0,
                bullish_ratio=0,
                bearish_ratio=0,
                neutral_ratio=0,
                volume=0,
                trend='stable'
            )
        
        # 统计比例
        positive_count = sum(1 for r in results if r.sentiment == 'positive')
        negative_count = sum(1 for r in results if r.sentiment == 'negative')
        neutral_count = total - positive_count - negative_count
        
        bullish_ratio = positive_count / total
        bearish_ratio = negative_count / total
        neutral_ratio = neutral_count / total
        
        # 计算综合情绪分数 (-100 to 100)
        overall_sentiment = (bullish_ratio - bearish_ratio) * 100
        
        # 计算趋势
        trend = self._calculate_trend(symbol, overall_sentiment)
        
        # 计算各维度情绪
        components = {}
        
        # 按来源分组
        source_groups = defaultdict(list)
        for r in results:
            source = r.source.split(':')[0] if ':' in r.source else r.source
            source_groups[source].append(r)
        
        for source, group in source_groups.items():
            if group:
                avg_score = sum(r.score for r in group) / len(group)
                components[source] = avg_score * 100
        
        index = SentimentIndex(
            symbol=symbol,
            overall_sentiment=round(overall_sentiment, 2),
            bullish_ratio=round(bullish_ratio, 2),
            bearish_ratio=round(bearish_ratio, 2),
            neutral_ratio=round(neutral_ratio, 2),
            volume=total,
            trend=trend,
            components=components
        )
        
        # 保存历史
        self.index_history[symbol].append(index)
        
        return index
    
    def _calculate_trend(self, symbol: str, current_sentiment: float) -> str:
        """计算情绪趋势"""
        history = self.index_history.get(symbol, [])
        
        if len(history) < 2:
            return 'stable'
        
        # 比较最近几次的情绪
        recent = [h.overall_sentiment for h in history[-5:]]
        avg_recent = sum(recent) / len(recent)
        
        diff = current_sentiment - avg_recent
        
        if diff > 10:
            return 'rising'
        elif diff < -10:
            return 'falling'
        else:
            return 'stable'
    
    def get_sentiment_visualization_data(self, symbol: str, 
                                         days: int = 30) -> Dict[str, Any]:
        """
        获取情绪可视化数据
        
        Args:
            symbol: 股票代码
            days: 天数
            
        Returns:
            可视化数据
        """
        history = self.index_history.get(symbol, [])
        
        # 过滤最近N天
        cutoff = datetime.now() - timedelta(days=days)
        recent_history = [h for h in history if h.timestamp >= cutoff]
        
        if not recent_history:
            return {
                'dates': [],
                'sentiment': [],
                'bullish': [],
                'bearish': [],
                'volume': []
            }
        
        dates = [h.timestamp.strftime('%Y-%m-%d') for h in recent_history]
        sentiments = [h.overall_sentiment for h in recent_history]
        bullish = [h.bullish_ratio * 100 for h in recent_history]
        bearish = [h.bearish_ratio * 100 for h in recent_history]
        volumes = [h.volume for h in recent_history]
        
        return {
            'dates': dates,
            'sentiment': sentiments,
            'bullish': bullish,
            'bearish': bearish,
            'volume': volumes,
            'current': {
                'sentiment': recent_history[-1].overall_sentiment,
                'trend': recent_history[-1].trend,
                'components': recent_history[-1].components
            }
        }
    
    def detect_sentiment_anomaly(self, symbol: str, 
                                 threshold: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        检测情绪异常
        
        Args:
            symbol: 股票代码
            threshold: 异常阈值（标准差倍数）
            
        Returns:
            异常信息或None
        """
        history = self.index_history.get(symbol, [])
        
        if len(history) < 10:
            return None
        
        sentiments = [h.overall_sentiment for h in history]
        mean = np.mean(sentiments)
        std = np.std(sentiments)
        
        current = sentiments[-1]
        z_score = (current - mean) / std if std > 0 else 0
        
        if abs(z_score) > threshold:
            return {
                'symbol': symbol,
                'type': 'sentiment_spike' if z_score > 0 else 'sentiment_drop',
                'current_value': current,
                'mean': mean,
                'z_score': z_score,
                'severity': 'high' if abs(z_score) > 3 else 'medium',
                'timestamp': datetime.now()
            }
        
        return None
    
    def generate_sentiment_report(self, symbol: str) -> str:
        """
        生成情绪分析报告
        
        Args:
            symbol: 股票代码
            
        Returns:
            报告文本
        """
        history = self.index_history.get(symbol, [])
        
        if not history:
            return f"暂无 {symbol} 的情绪数据"
        
        latest = history[-1]
        
        lines = [
            f"# {symbol} 市场情绪分析报告",
            "",
            f"**报告时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 情绪指数概览",
            "",
            f"- **综合情绪**: {latest.overall_sentiment:+.1f} (-100到100)",
            f"- **看多比例**: {latest.bullish_ratio * 100:.1f}%",
            f"- **看空比例**: {latest.bearish_ratio * 100:.1f}%",
            f"- **中性比例**: {latest.neutral_ratio * 100:.1f}%",
            f"- **分析样本**: {latest.volume}条",
            f"- **情绪趋势**: {'上升📈' if latest.trend == 'rising' else '下降📉' if latest.trend == 'falling' else '平稳➡️'}",
            "",
            "## 分来源情绪",
            "",
        ]
        
        for source, score in latest.components.items():
            emoji = '📈' if score > 20 else '📉' if score < -20 else '➡️'
            lines.append(f"- **{source}**: {score:+.1f} {emoji}")
        
        # 异常检测
        anomaly = self.detect_sentiment_anomaly(symbol)
        if anomaly:
            lines.extend([
                "",
                "## ⚠️ 情绪异常提醒",
                "",
                f"检测到情绪{'激增' if anomaly['type'] == 'sentiment_spike' else '骤降'}！",
                f"- 当前Z值: {anomaly['z_score']:.2f}",
                f"- 严重程度: {anomaly['severity']}",
            ])
        
        lines.extend([
            "",
            "## 解读",
            "",
        ])
        
        if latest.overall_sentiment > 50:
            lines.append("市场情绪极度乐观，需警惕回调风险。")
        elif latest.overall_sentiment > 20:
            lines.append("市场情绪偏乐观，短期可能继续上涨。")
        elif latest.overall_sentiment > -20:
            lines.append("市场情绪中性，建议观望。")
        elif latest.overall_sentiment > -50:
            lines.append("市场情绪偏悲观，可能存在超卖机会。")
        else:
            lines.append("市场情绪极度悲观，需警惕进一步下跌。")
        
        lines.append("\n*免责声明：情绪分析仅供参考，不构成投资建议。*")
        
        return '\n'.join(lines)
    
    def batch_analyze_texts(self, texts: List[str], sources: List[str] = None) -> List[SentimentResult]:
        """
        批量分析文本
        
        Args:
            texts: 文本列表
            sources: 来源列表
            
        Returns:
            情绪分析结果列表
        """
        if sources is None:
            sources = [''] * len(texts)
        
        results = []
        for text, source in zip(texts, sources):
            result = self.analyze_text(text, source, use_ai=False)  # 批量使用规则分析
            results.append(result)
        
        return results


class SocialMediaMonitor:
    """社交媒体监控器"""
    
    def __init__(self, analyzer: SentimentAnalyzer = None):
        self.analyzer = analyzer or SentimentAnalyzer()
        self.monitored_symbols = set()
        self.alert_threshold = 0.7  # 情绪变化阈值
    
    def add_symbol(self, symbol: str):
        """添加监控股票"""
        self.monitored_symbols.add(symbol)
    
    def remove_symbol(self, symbol: str):
        """移除监控股票"""
        self.monitored_symbols.discard(symbol)
    
    def process_stream(self, symbol: str, posts: List[Dict[str, Any]], 
                       platform: str) -> Dict[str, Any]:
        """
        处理实时流数据
        
        Args:
            symbol: 股票代码
            posts: 帖子列表
            platform: 平台
            
        Returns:
            处理结果
        """
        # 分析情绪
        results = self.analyzer.analyze_social_media(posts, platform)
        
        # 计算指数
        index = self.analyzer.calculate_sentiment_index(symbol, results)
        
        # 检测异常
        anomaly = self.analyzer.detect_sentiment_anomaly(symbol)
        
        # 检测热点关键词
        all_keywords = []
        for r in results:
            all_keywords.extend(r.keywords)
        
        keyword_freq = defaultdict(int)
        for kw in all_keywords:
            keyword_freq[kw] += 1
        
        hot_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'symbol': symbol,
            'platform': platform,
            'sentiment_index': index,
            'anomaly': anomaly,
            'hot_keywords': hot_keywords,
            'post_count': len(posts),
            'processed_at': datetime.now()
        }
