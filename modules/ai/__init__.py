"""
AI模块 - Smart Stock Monitor
包含多模型AI、智能问答、预测分析、推荐引擎、研报分析、情绪分析、异常检测、智能投顾
"""

from modules.ai.multi_model import (
    MultiModelAI, 
    AIModel, 
    ModelPerformance, 
    ModelConfig,
    get_ai_manager
)

from modules.ai.intelligent_qa import IntelligentQA

from modules.ai.predictive_analysis import PredictiveAnalyzer

from modules.ai.recommendation_engine import RecommendationEngine

from modules.ai.research_analyzer import (
    ResearchAnalyzer,
    ResearchReport,
    ReportComparison
)

from modules.ai.sentiment_analyzer import (
    SentimentAnalyzer,
    SentimentResult,
    SentimentIndex,
    SocialMediaMonitor
)

from modules.ai.anomaly_detector import (
    AnomalyDetector,
    AnomalyEvent,
    AnomalyType,
    Alert,
    AlertLevel,
    SmartAlertSystem
)

from modules.ai.investment_advisor import (
    InvestmentAdvisor,
    UserProfile,
    AssetAllocation,
    PositionAdvice,
    RiskAssessment,
    RiskTolerance,
    InvestmentStyle,
    InvestmentHorizon,
    get_advisor
)

__all__ = [
    # 多模型AI
    'MultiModelAI',
    'AIModel',
    'ModelPerformance',
    'ModelConfig',
    'get_ai_manager',
    
    # 智能问答
    'IntelligentQA',
    
    # 预测分析
    'PredictiveAnalyzer',
    
    # 推荐引擎
    'RecommendationEngine',
    
    # 研报分析
    'ResearchAnalyzer',
    'ResearchReport',
    'ReportComparison',
    
    # 情绪分析
    'SentimentAnalyzer',
    'SentimentResult',
    'SentimentIndex',
    'SocialMediaMonitor',
    
    # 异常检测
    'AnomalyDetector',
    'AnomalyEvent',
    'AnomalyType',
    'Alert',
    'AlertLevel',
    'SmartAlertSystem',
    
    # 智能投顾
    'InvestmentAdvisor',
    'UserProfile',
    'AssetAllocation',
    'PositionAdvice',
    'RiskAssessment',
    'RiskTolerance',
    'InvestmentStyle',
    'InvestmentHorizon',
    'get_advisor',
]
