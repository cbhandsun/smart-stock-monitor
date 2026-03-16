"""
AI智能投顾模块
实现基于用户画像的个性化建议、资产配置建议、风险评估和仓位管理
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict
import pandas as pd
import numpy as np

from modules.ai.multi_model import MultiModelAI, get_ai_manager


class RiskTolerance(Enum):
    """风险承受能力"""
    CONSERVATIVE = "conservative"  # 保守型
    MODERATE = "moderate"  # 稳健型
    BALANCED = "balanced"  # 平衡型
    AGGRESSIVE = "aggressive"  # 进取型
    SPECULATIVE = "speculative"  # 激进型


class InvestmentStyle(Enum):
    """投资风格"""
    VALUE = "value"  # 价值投资
    GROWTH = "growth"  # 成长投资
    INDEX = "index"  # 指数投资
    DIVIDEND = "dividend"  # 股息投资
    MOMENTUM = "momentum"  # 动量投资
    BALANCED = "balanced"  # 平衡型


class InvestmentHorizon(Enum):
    """投资期限"""
    SHORT = "short"  # 短期 (< 1年)
    MEDIUM = "medium"  # 中期 (1-3年)
    LONG = "long"  # 长期 (> 3年)


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    risk_tolerance: RiskTolerance = RiskTolerance.BALANCED
    investment_style: InvestmentStyle = InvestmentStyle.BALANCED
    horizon: InvestmentHorizon = InvestmentHorizon.MEDIUM
    age: int = 35
    annual_income: float = 0  # 年收入（万元）
    investable_assets: float = 0  # 可投资资产（万元）
    investment_experience: str = "intermediate"  # novice, intermediate, expert
    existing_holdings: Dict[str, float] = field(default_factory=dict)  # 现有持仓
    preferred_sectors: List[str] = field(default_factory=list)
    excluded_sectors: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)  # 投资目标
    constraints: List[str] = field(default_factory=list)  # 投资限制
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AssetAllocation:
    """资产配置建议"""
    stocks_pct: float  # 股票占比
    bonds_pct: float  # 债券占比
    cash_pct: float  # 现金占比
    alternatives_pct: float  # 另类投资占比
    
    # 细分配置
    large_cap_pct: float = 0  # 大盘股
    mid_cap_pct: float = 0  # 中盘股
    small_cap_pct: float = 0  # 小盘股
    
    domestic_pct: float = 0  # 国内
    international_pct: float = 0  # 国际
    
    rebalancing_frequency: str = "quarterly"  # 再平衡频率
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'stocks': self.stocks_pct,
            'bonds': self.bonds_pct,
            'cash': self.cash_pct,
            'alternatives': self.alternatives_pct,
            'large_cap': self.large_cap_pct,
            'mid_cap': self.mid_cap_pct,
            'small_cap': self.small_cap_pct,
            'domestic': self.domestic_pct,
            'international': self.international_pct
        }


@dataclass
class PositionAdvice:
    """仓位管理建议"""
    symbol: str
    current_position: float  # 当前仓位（%）
    suggested_position: float  # 建议仓位（%）
    action: str  # 建议操作：buy, sell, hold, add, reduce
    action_pct: float  # 操作比例
    confidence: float  # 置信度
    reasoning: str  # 理由


@dataclass
class RiskAssessment:
    """风险评估结果"""
    overall_risk_score: float  # 0-100
    risk_level: str  # Low, Medium, High
    portfolio_volatility: float  # 组合波动率
    max_drawdown_estimate: float  # 预估最大回撤
    var_95: float  # 95% VaR
    concentration_risk: float  # 集中度风险
    sector_risk: Dict[str, float] = field(default_factory=dict)
    stress_test_results: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


class InvestmentAdvisor:
    """AI智能投顾"""
    
    # 风险承受能力与资产配置映射
    RISK_ALLOCATION = {
        RiskTolerance.CONSERVATIVE: AssetAllocation(
            stocks_pct=20, bonds_pct=60, cash_pct=15, alternatives_pct=5,
            large_cap_pct=15, mid_cap_pct=3, small_cap_pct=2,
            domestic_pct=18, international_pct=2
        ),
        RiskTolerance.MODERATE: AssetAllocation(
            stocks_pct=40, bonds_pct=45, cash_pct=10, alternatives_pct=5,
            large_cap_pct=25, mid_cap_pct=10, small_cap_pct=5,
            domestic_pct=32, international_pct=8
        ),
        RiskTolerance.BALANCED: AssetAllocation(
            stocks_pct=60, bonds_pct=30, cash_pct=5, alternatives_pct=5,
            large_cap_pct=35, mid_cap_pct=15, small_cap_pct=10,
            domestic_pct=48, international_pct=12
        ),
        RiskTolerance.AGGRESSIVE: AssetAllocation(
            stocks_pct=80, bonds_pct=15, cash_pct=2, alternatives_pct=3,
            large_cap_pct=40, mid_cap_pct=25, small_cap_pct=15,
            domestic_pct=64, international_pct=16
        ),
        RiskTolerance.SPECULATIVE: AssetAllocation(
            stocks_pct=90, bonds_pct=5, cash_pct=2, alternatives_pct=3,
            large_cap_pct=35, mid_cap_pct=30, small_cap_pct=25,
            domestic_pct=72, international_pct=18
        ),
    }
    
    def __init__(self, ai_manager: MultiModelAI = None):
        self.ai = ai_manager or get_ai_manager()
        self.user_profiles: Dict[str, UserProfile] = {}
        self.advice_history: Dict[str, List[Dict]] = defaultdict(list)
    
    def create_profile(self, user_id: str, **kwargs) -> UserProfile:
        """
        创建用户画像
        
        Args:
            user_id: 用户ID
            **kwargs: 画像参数
            
        Returns:
            用户画像
        """
        profile = UserProfile(user_id=user_id, **kwargs)
        self.user_profiles[user_id] = profile
        return profile
    
    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像"""
        return self.user_profiles.get(user_id)
    
    def update_profile(self, user_id: str, **kwargs) -> Optional[UserProfile]:
        """更新用户画像"""
        profile = self.user_profiles.get(user_id)
        if profile:
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            profile.updated_at = datetime.now()
        return profile
    
    def assess_risk_tolerance(self, answers: Dict[str, Any]) -> RiskTolerance:
        """
        评估风险承受能力
        
        Args:
            answers: 问卷答案
            
        Returns:
            风险承受能力等级
        """
        score = 0
        
        # 年龄评分（越年轻风险承受能力越高）
        age = answers.get('age', 35)
        if age < 30:
            score += 20
        elif age < 40:
            score += 15
        elif age < 50:
            score += 10
        elif age < 60:
            score += 5
        
        # 收入稳定性
        income_stability = answers.get('income_stability', 'stable')
        score += {'very_stable': 15, 'stable': 10, 'unstable': 5}.get(income_stability, 10)
        
        # 投资经验
        experience = answers.get('investment_experience', 'intermediate')
        score += {'novice': 5, 'intermediate': 10, 'expert': 20}.get(experience, 10)
        
        # 可承受损失
        loss_tolerance = answers.get('max_loss_tolerance', 10)
        score += min(loss_tolerance, 30)
        
        # 投资期限
        horizon = answers.get('investment_horizon', 'medium')
        score += {'short': 5, 'medium': 10, 'long': 20}.get(horizon, 10)
        
        # 映射到风险等级
        if score >= 70:
            return RiskTolerance.SPECULATIVE
        elif score >= 55:
            return RiskTolerance.AGGRESSIVE
        elif score >= 40:
            return RiskTolerance.BALANCED
        elif score >= 25:
            return RiskTolerance.MODERATE
        else:
            return RiskTolerance.CONSERVATIVE
    
    def recommend_allocation(self, user_id: str) -> AssetAllocation:
        """
        推荐资产配置
        
        Args:
            user_id: 用户ID
            
        Returns:
            资产配置建议
        """
        profile = self.user_profiles.get(user_id)
        if not profile:
            return self.RISK_ALLOCATION[RiskTolerance.BALANCED]
        
        base_allocation = self.RISK_ALLOCATION.get(
            profile.risk_tolerance, 
            self.RISK_ALLOCATION[RiskTolerance.BALANCED]
        )
        
        # 根据投资风格调整
        allocation = self._adjust_for_style(base_allocation, profile.investment_style)
        
        # 根据投资期限调整
        allocation = self._adjust_for_horizon(allocation, profile.horizon)
        
        return allocation
    
    def _adjust_for_style(self, allocation: AssetAllocation, 
                          style: InvestmentStyle) -> AssetAllocation:
        """根据投资风格调整配置"""
        if style == InvestmentStyle.VALUE:
            # 价值型：增加大盘股比例
            allocation.large_cap_pct += 10
            allocation.small_cap_pct -= 10
        elif style == InvestmentStyle.GROWTH:
            # 成长型：增加中小盘比例
            allocation.large_cap_pct -= 10
            allocation.mid_cap_pct += 5
            allocation.small_cap_pct += 5
        elif style == InvestmentStyle.DIVIDEND:
            # 股息型：增加债券和大盘股
            allocation.bonds_pct += 10
            allocation.stocks_pct -= 10
            allocation.large_cap_pct += 5
        elif style == InvestmentStyle.MOMENTUM:
            # 动量型：增加股票比例
            allocation.stocks_pct += 10
            allocation.bonds_pct -= 10
        
        return allocation
    
    def _adjust_for_horizon(self, allocation: AssetAllocation,
                           horizon: InvestmentHorizon) -> AssetAllocation:
        """根据投资期限调整配置"""
        if horizon == InvestmentHorizon.SHORT:
            # 短期：增加现金和债券
            allocation.cash_pct += 10
            allocation.stocks_pct -= 10
        elif horizon == InvestmentHorizon.LONG:
            # 长期：增加股票
            allocation.stocks_pct += 10
            allocation.bonds_pct -= 10
        
        return allocation
    
    def assess_portfolio_risk(self, user_id: str, 
                              holdings: Dict[str, float] = None) -> RiskAssessment:
        """
        评估组合风险
        
        Args:
            user_id: 用户ID
            holdings: 持仓数据（代码->权重）
            
        Returns:
            风险评估结果
        """
        profile = self.user_profiles.get(user_id)
        if not holdings and profile:
            holdings = profile.existing_holdings
        
        if not holdings:
            return RiskAssessment(
                overall_risk_score=0,
                risk_level="Unknown",
                portfolio_volatility=0,
                max_drawdown_estimate=0,
                var_95=0,
                concentration_risk=0
            )
        
        # 计算集中度风险
        weights = list(holdings.values())
        max_weight = max(weights)
        concentration_risk = max_weight * 100  # 最大持仓占比
        
        # 估算组合波动率（简化计算）
        estimated_vol = self._estimate_portfolio_volatility(holdings)
        
        # 估算最大回撤
        max_dd = estimated_vol * 2.5  # 简化估算
        
        # 计算VaR
        total_value = sum(weights)
        var_95 = total_value * estimated_vol * 1.645 / 100  # 95%置信度
        
        # 综合风险评分
        risk_score = (
            estimated_vol * 0.4 +
            concentration_risk * 0.3 +
            (max_dd / 3) * 0.3
        )
        
        # 风险等级
        if risk_score < 20:
            risk_level = "Low"
        elif risk_score < 50:
            risk_level = "Medium"
        else:
            risk_level = "High"
        
        # 生成建议
        recommendations = self._generate_risk_recommendations(
            risk_score, concentration_risk, holdings
        )
        
        return RiskAssessment(
            overall_risk_score=round(risk_score, 2),
            risk_level=risk_level,
            portfolio_volatility=round(estimated_vol, 2),
            max_drawdown_estimate=round(max_dd, 2),
            var_95=round(var_95, 2),
            concentration_risk=round(concentration_risk, 2),
            recommendations=recommendations
        )
    
    def _estimate_portfolio_volatility(self, holdings: Dict[str, float]) -> float:
        """估算组合波动率"""
        # 简化估算：假设个股波动率20%，相关性0.5
        n = len(holdings)
        if n == 0:
            return 0
        
        avg_weight = 100 / n
        # 分散化效应
        diversification_factor = 1 / np.sqrt(n) if n > 1 else 1
        estimated_vol = 20 * diversification_factor  # 假设个股波动率20%
        
        return estimated_vol
    
    def _generate_risk_recommendations(self, risk_score: float,
                                       concentration_risk: float,
                                       holdings: Dict[str, float]) -> List[str]:
        """生成风险建议"""
        recommendations = []
        
        if risk_score > 50:
            recommendations.append("组合风险较高，建议降低股票仓位或增加防御性资产")
        
        if concentration_risk > 30:
            recommendations.append(f"持仓集中度较高（{concentration_risk:.1f}%），建议分散投资")
        
        if len(holdings) < 5:
            recommendations.append("持仓过于集中，建议至少持有5-10只股票以分散风险")
        
        if not recommendations:
            recommendations.append("组合风险控制在合理范围内")
        
        return recommendations
    
    def advise_position(self, user_id: str, symbol: str,
                       current_data: Dict[str, Any]) -> PositionAdvice:
        """
        仓位管理建议
        
        Args:
            user_id: 用户ID
            symbol: 股票代码
            current_data: 当前数据
            
        Returns:
            仓位建议
        """
        profile = self.user_profiles.get(user_id)
        current_position = profile.existing_holdings.get(symbol, 0) if profile else 0
        
        # 基于AI生成建议
        prompt = f"""作为投资顾问，请为以下情况提供仓位管理建议：

用户画像：
- 风险承受能力：{profile.risk_tolerance.value if profile else 'balanced'}
- 投资风格：{profile.investment_style.value if profile else 'balanced'}
- 投资期限：{profile.horizon.value if profile else 'medium'}

股票信息：
- 代码：{symbol}
- 当前价格：{current_data.get('price', 'N/A')}
- 当前仓位：{current_position}%
- 近期涨跌幅：{current_data.get('change_pct', 'N/A')}%
- 成交量变化：{current_data.get('volume_change', 'N/A')}

请给出：
1. 建议仓位（%）
2. 建议操作（buy/sell/hold/add/reduce）
3. 操作比例（%）
4. 简要理由

以JSON格式返回：
{{
    "suggested_position": 0,
    "action": "hold",
    "action_pct": 0,
    "reasoning": ""
}}"""
        
        try:
            response = self.ai.generate_response(prompt)
            
            # 解析JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                return PositionAdvice(
                    symbol=symbol,
                    current_position=current_position,
                    suggested_position=result.get('suggested_position', current_position),
                    action=result.get('action', 'hold'),
                    action_pct=result.get('action_pct', 0),
                    confidence=0.75,
                    reasoning=result.get('reasoning', '')
                )
        except Exception as e:
            print(f"AI仓位建议生成失败: {e}")
        
        # 备用方案：基于规则
        return self._rule_based_position_advice(user_id, symbol, current_position, current_data)
    
    def _rule_based_position_advice(self, user_id: str, symbol: str,
                                    current_position: float,
                                    current_data: Dict[str, Any]) -> PositionAdvice:
        """基于规则的仓位建议"""
        profile = self.user_profiles.get(user_id)
        
        # 基于风险承受能力确定最大仓位
        max_position = {
            RiskTolerance.CONSERVATIVE: 10,
            RiskTolerance.MODERATE: 20,
            RiskTolerance.BALANCED: 30,
            RiskTolerance.AGGRESSIVE: 50,
            RiskTolerance.SPECULATIVE: 70
        }.get(profile.risk_tolerance if profile else RiskTolerance.BALANCED, 30)
        
        change_pct = current_data.get('change_pct', 0)
        
        # 简单规则
        if current_position == 0:
            if change_pct > 5:
                action = 'buy'
                suggested = min(10, max_position)
            else:
                action = 'hold'
                suggested = 0
        elif current_position > max_position:
            action = 'reduce'
            suggested = max_position
        elif change_pct < -10:
            action = 'add'
            suggested = min(current_position + 5, max_position)
        else:
            action = 'hold'
            suggested = current_position
        
        action_pct = abs(suggested - current_position)
        
        reasoning = f"基于您的风险承受能力（{profile.risk_tolerance.value if profile else 'balanced'}），"
        reasoning += f"建议该股票最大仓位不超过{max_position}%。"
        
        return PositionAdvice(
            symbol=symbol,
            current_position=current_position,
            suggested_position=suggested,
            action=action,
            action_pct=action_pct,
            confidence=0.6,
            reasoning=reasoning
        )
    
    def generate_investment_plan(self, user_id: str) -> str:
        """
        生成投资计划书
        
        Args:
            user_id: 用户ID
            
        Returns:
            投资计划书文本
        """
        profile = self.user_profiles.get(user_id)
        if not profile:
            return "请先创建用户画像"
        
        allocation = self.recommend_allocation(user_id)
        risk = self.assess_portfolio_risk(user_id)
        
        lines = [
            f"# {profile.user_id} 个性化投资计划书",
            "",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 用户画像",
            "",
            f"- **风险承受能力**: {profile.risk_tolerance.value}",
            f"- **投资风格**: {profile.investment_style.value}",
            f"- **投资期限**: {profile.horizon.value}",
            f"- **投资经验**: {profile.investment_experience}",
            "",
            "## 资产配置建议",
            "",
            "### 大类资产配置",
            f"- 股票类资产: **{allocation.stocks_pct}%**",
            f"- 债券类资产: **{allocation.bonds_pct}%**",
            f"- 现金及等价物: **{allocation.cash_pct}%**",
            f"- 另类投资: **{allocation.alternatives_pct}%**",
            "",
            "### 股票类细分配置",
            f"- 大盘股: {allocation.large_cap_pct}%",
            f"- 中盘股: {allocation.mid_cap_pct}%",
            f"- 小盘股: {allocation.small_cap_pct}%",
            "",
            "### 地域配置",
            f"- 国内市场: {allocation.domestic_pct}%",
            f"- 国际市场: {allocation.international_pct}%",
            "",
            "## 风险评估",
            "",
            f"- **综合风险评分**: {risk.overall_risk_score}/100",
            f"- **风险等级**: {risk.risk_level}",
            f"- **预估组合波动率**: {risk.portfolio_volatility}%",
            f"- **预估最大回撤**: {risk.max_drawdown_estimate}%",
            "",
            "### 风险提示",
        ]
        
        for rec in risk.recommendations:
            lines.append(f"- {rec}")
        
        lines.extend([
            "",
            "## 投资建议",
            "",
            "1. **定期再平衡**: 建议每季度检查并调整资产配置",
            "2. **分散投资**: 单只股票仓位不宜超过总资产的10%",
            "3. **长期持有**: 避免频繁交易，降低交易成本",
            "4. **持续学习**: 关注市场动态，提升投资能力",
            "",
            "---",
            "*免责声明：本投资计划仅供参考，不构成投资建议。投资有风险，入市需谨慎。*"
        ])
        
        return '\n'.join(lines)
    
    def get_personalized_recommendations(self, user_id: str, 
                                         market_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        获取个性化推荐
        
        Args:
            user_id: 用户ID
            market_data: 市场数据
            
        Returns:
            推荐列表
        """
        profile = self.user_profiles.get(user_id)
        if not profile:
            return []
        
        recommendations = []
        
        # 基于投资风格的推荐
        if profile.investment_style == InvestmentStyle.VALUE:
            recommendations.append({
                'type': 'strategy',
                'title': '价值投资关注',
                'content': '关注低PE、低PB的优质蓝筹股',
                'priority': 'high'
            })
        elif profile.investment_style == InvestmentStyle.GROWTH:
            recommendations.append({
                'type': 'strategy',
                'title': '成长投资关注',
                'content': '关注高成长性的科技和创新企业',
                'priority': 'high'
            })
        
        # 基于风险承受能力的提醒
        if profile.risk_tolerance == RiskTolerance.CONSERVATIVE:
            recommendations.append({
                'type': 'risk',
                'title': '风险控制提醒',
                'content': '建议保持较高的现金比例，关注低风险债券',
                'priority': 'medium'
            })
        
        # 基于投资期限的建议
        if profile.horizon == InvestmentHorizon.LONG:
            recommendations.append({
                'type': 'time',
                'title': '长期投资优势',
                'content': '可利用定投策略平摊成本，享受复利效应',
                'priority': 'medium'
            })
        
        return recommendations


# 便捷函数
def get_advisor() -> InvestmentAdvisor:
    """获取投顾单例"""
    if not hasattr(get_advisor, '_instance'):
        get_advisor._instance = InvestmentAdvisor()
    return get_advisor._instance
