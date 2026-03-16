import pandas as pd
import numpy as np
from typing import Dict, List
from collections import defaultdict

class RecommendationEngine:
    """个性化推荐引擎"""
    
    def __init__(self):
        self.user_preferences = {}
        self.stock_features = {}
        self.user_history = defaultdict(list)
        self.stock_ratings = defaultdict(dict)
    
    def set_user_preferences(self, user_id: str, preferences: Dict):
        """
        设置用户偏好
        
        Args:
            user_id: 用户ID
            preferences: 偏好设置
                - risk_tolerance: 风险承受能力 (low/medium/high)
                - preferred_sectors: 偏好行业列表
                - market_cap_pref: 市值偏好 (large/mid/small)
                - investment_style: 投资风格 (value/growth/balanced)
                - holding_period: 持仓周期 (short/medium/long)
        """
        self.user_preferences[user_id] = preferences
    
    def get_user_preferences(self, user_id: str) -> Dict:
        """获取用户偏好"""
        return self.user_preferences.get(user_id, {})
    
    def update_stock_features(self, symbol: str, features: Dict):
        """
        更新股票特征
        
        Args:
            symbol: 股票代码
            features: 股票特征
                - sector: 所属行业
                - market_cap: 市值
                - pe_ratio: 市盈率
                - pb_ratio: 市净率
                - volatility: 波动率
                - momentum: 动量
                - growth_rate: 增长率
                - dividend_yield: 股息率
        """
        self.stock_features[symbol] = features
    
    def calculate_similarity(self, stock_features: Dict, user_prefs: Dict) -> float:
        """
        计算股票与用户偏好的相似度
        
        Args:
            stock_features: 股票特征
            user_prefs: 用户偏好
        
        Returns:
            相似度得分 (0-1)
        """
        score = 0.0
        weights = 0.0
        
        # 风险匹配
        if 'risk_tolerance' in user_prefs and 'volatility' in stock_features:
            weights += 0.25
            volatility = stock_features.get('volatility', 0)
            risk_tolerance = user_prefs.get('risk_tolerance', 'medium')
            
            if risk_tolerance == 'high' and volatility > 0.3:
                score += 0.25
            elif risk_tolerance == 'medium' and 0.2 <= volatility <= 0.3:
                score += 0.25
            elif risk_tolerance == 'low' and volatility < 0.2:
                score += 0.25
        
        # 行业偏好
        if 'preferred_sectors' in user_prefs and 'sector' in stock_features:
            weights += 0.25
            if stock_features['sector'] in user_prefs['preferred_sectors']:
                score += 0.25
        
        # 市值偏好
        if 'market_cap_pref' in user_prefs and 'market_cap' in stock_features:
            weights += 0.2
            market_cap = stock_features.get('market_cap', 0)
            market_cap_pref = user_prefs.get('market_cap_pref', 'mid')
            
            if market_cap_pref == 'large' and market_cap > 100e9:
                score += 0.2
            elif market_cap_pref == 'mid' and 10e9 <= market_cap <= 100e9:
                score += 0.2
            elif market_cap_pref == 'small' and market_cap < 10e9:
                score += 0.2
        
        # 投资风格
        if 'investment_style' in user_prefs:
            weights += 0.3
            style = user_prefs.get('investment_style', 'balanced')
            pe = stock_features.get('pe_ratio', 0)
            growth = stock_features.get('growth_rate', 0)
            
            if style == 'value' and pe < 15:
                score += 0.3
            elif style == 'growth' and growth > 0.2:
                score += 0.3
            elif style == 'balanced' and 15 <= pe <= 30:
                score += 0.3
        
        return score / weights if weights > 0 else 0
    
    def get_recommendations(self, user_id: str, top_n: int = 10, 
                           exclude_symbols: List[str] = None) -> List[Dict]:
        """
        获取个性化推荐
        
        Args:
            user_id: 用户ID
            top_n: 推荐数量
            exclude_symbols: 排除的股票代码
        
        Returns:
            推荐列表
        """
        user_prefs = self.user_preferences.get(user_id, {})
        exclude = set(exclude_symbols or [])
        
        recommendations = []
        for symbol, features in self.stock_features.items():
            if symbol in exclude:
                continue
            
            similarity = self.calculate_similarity(features, user_prefs)
            
            # 添加历史交互分数
            history_score = self._get_history_score(user_id, symbol)
            
            # 综合得分
            final_score = similarity * 0.7 + history_score * 0.3
            
            recommendations.append({
                'symbol': symbol,
                'score': round(final_score, 4),
                'similarity': round(similarity, 4),
                'history_score': round(history_score, 4),
                'features': features,
                'reason': self._generate_reason(features, user_prefs)
            })
        
        # 按得分排序
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:top_n]
    
    def _get_history_score(self, user_id: str, symbol: str) -> float:
        """获取历史交互分数"""
        history = self.user_history.get(user_id, [])
        if not history:
            return 0.5
        
        # 计算该股票在历史中的出现频率
        symbol_count = sum(1 for h in history if h.get('symbol') == symbol)
        total = len(history)
        
        return min(symbol_count / total, 1.0) if total > 0 else 0.5
    
    def _generate_reason(self, features: Dict, user_prefs: Dict) -> str:
        """生成推荐理由"""
        reasons = []
        
        if 'sector' in features and 'preferred_sectors' in user_prefs:
            if features['sector'] in user_prefs['preferred_sectors']:
                reasons.append(f"属于您关注的{features['sector']}行业")
        
        if 'volatility' in features and 'risk_tolerance' in user_prefs:
            vol = features['volatility']
            risk = user_prefs['risk_tolerance']
            if risk == 'low' and vol < 0.2:
                reasons.append("波动率较低，符合您的风险偏好")
            elif risk == 'high' and vol > 0.3:
                reasons.append("波动率较高，符合您的风险偏好")
        
        if 'pe_ratio' in features and 'investment_style' in user_prefs:
            pe = features['pe_ratio']
            style = user_prefs['investment_style']
            if style == 'value' and pe < 15:
                reasons.append("估值较低，符合价值投资风格")
            elif style == 'growth' and pe > 30:
                reasons.append("成长性强，符合成长投资风格")
        
        return "；".join(reasons) if reasons else "综合评分较高"
    
    def record_interaction(self, user_id: str, symbol: str, action: str, rating: float = None):
        """
        记录用户交互
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            action: 交互类型 (view/click/buy/sell)
            rating: 评分 (1-5)
        """
        self.user_history[user_id].append({
            'symbol': symbol,
            'action': action,
            'rating': rating,
            'timestamp': pd.Timestamp.now().isoformat()
        })
        
        if rating:
            self.stock_ratings[user_id][symbol] = rating
    
    def get_similar_users(self, user_id: str, n: int = 5) -> List[str]:
        """
        查找相似用户（基于协同过滤）
        
        Args:
            user_id: 目标用户ID
            n: 返回相似用户数量
        
        Returns:
            相似用户ID列表
        """
        target_prefs = self.user_preferences.get(user_id, {})
        if not target_prefs:
            return []
        
        similarities = []
        for other_id, other_prefs in self.user_preferences.items():
            if other_id == user_id:
                continue
            
            # 计算偏好相似度
            common_keys = set(target_prefs.keys()) & set(other_prefs.keys())
            if not common_keys:
                continue
            
            match_count = sum(1 for k in common_keys if target_prefs[k] == other_prefs[k])
            similarity = match_count / len(common_keys)
            
            similarities.append((other_id, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [uid for uid, _ in similarities[:n]]
    
    def get_collaborative_recommendations(self, user_id: str, top_n: int = 10) -> List[Dict]:
        """
        基于协同过滤的推荐
        
        Args:
            user_id: 用户ID
            top_n: 推荐数量
        
        Returns:
            推荐列表
        """
        similar_users = self.get_similar_users(user_id, n=5)
        if not similar_users:
            return []
        
        # 收集相似用户喜欢的股票
        stock_scores = defaultdict(float)
        for similar_user in similar_users:
            for symbol, rating in self.stock_ratings.get(similar_user, {}).items():
                stock_scores[symbol] += rating
        
        # 排除已持有的
        user_history_symbols = set(
            h['symbol'] for h in self.user_history.get(user_id, [])
        )
        
        recommendations = []
        for symbol, score in sorted(stock_scores.items(), key=lambda x: x[1], reverse=True):
            if symbol not in user_history_symbols:
                recommendations.append({
                    'symbol': symbol,
                    'score': score,
                    'source': 'collaborative',
                    'reason': '相似用户关注'
                })
                
                if len(recommendations) >= top_n:
                    break
        
        return recommendations
    
    def get_hybrid_recommendations(self, user_id: str, top_n: int = 10) -> List[Dict]:
        """
        混合推荐（结合基于内容和协同过滤）
        
        Args:
            user_id: 用户ID
            top_n: 推荐数量
        
        Returns:
            推荐列表
        """
        content_recs = self.get_recommendations(user_id, top_n=top_n * 2)
        collab_recs = self.get_collaborative_recommendations(user_id, top_n=top_n)
        
        # 合并并去重
        seen = set()
        hybrid_recs = []
        
        # 优先内容推荐
        for rec in content_recs:
            if rec['symbol'] not in seen:
                seen.add(rec['symbol'])
                rec['source'] = 'content'
                hybrid_recs.append(rec)
        
        # 添加协同过滤推荐
        for rec in collab_recs:
            if rec['symbol'] not in seen:
                seen.add(rec['symbol'])
                hybrid_recs.append(rec)
        
        return hybrid_recs[:top_n]
