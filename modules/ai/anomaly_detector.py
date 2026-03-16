"""
异常检测系统
实现股价异动检测、大宗交易监控、智能提醒生成
"""

import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import pandas as pd
import numpy as np

from modules.ai.multi_model import MultiModelAI, get_ai_manager


class AnomalyType(Enum):
    """异常类型"""
    PRICE_GAP_UP = "price_gap_up"  # 向上跳空
    PRICE_GAP_DOWN = "price_gap_down"  # 向下跳空
    VOLUME_SPIKE = "volume_spike"  # 成交量激增
    PRICE_BREAKOUT = "price_breakout"  # 价格突破
    PRICE_BREAKDOWN = "price_breakdown"  # 价格跌破
    VOLATILITY_SPIKE = "volatility_spike"  # 波动率激增
    BLOCK_TRADE = "block_trade"  # 大宗交易
    RAPID_CHANGE = "rapid_change"  # 快速变动
    UNUSUAL_PATTERN = "unusual_pattern"  # 异常形态


class AlertLevel(Enum):
    """提醒级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AnomalyEvent:
    """异常事件"""
    symbol: str
    anomaly_type: AnomalyType
    level: AlertLevel
    timestamp: datetime
    description: str
    metrics: Dict[str, float] = field(default_factory=dict)
    suggested_action: str = ""
    confidence: float = 0.0


@dataclass
class Alert:
    """智能提醒"""
    id: str
    symbol: str
    title: str
    message: str
    level: AlertLevel
    created_at: datetime
    expires_at: datetime
    is_read: bool = False
    actions: List[str] = field(default_factory=list)


class AnomalyDetector:
    """异常检测器"""
    
    # 默认阈值配置
    DEFAULT_THRESHOLDS = {
        'gap_up': 0.03,  # 跳空上涨3%
        'gap_down': -0.03,  # 跳空下跌3%
        'volume_spike': 3.0,  # 成交量是均量的3倍
        'breakout': 0.05,  # 突破5%
        'volatility_spike': 2.0,  # 波动率是平时的2倍
        'rapid_change': 0.05,  # 5分钟内变动5%
        'block_trade_threshold': 1000000,  # 大宗交易金额阈值（万元）
    }
    
    def __init__(self, thresholds: Dict[str, float] = None):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.price_history = defaultdict(lambda: deque(maxlen=100))
        self.volume_history = defaultdict(lambda: deque(maxlen=100))
        self.anomaly_history = defaultdict(list)
        self.alert_handlers = []
    
    def detect_price_gap(self, symbol: str, current_data: pd.Series, 
                         prev_close: float) -> Optional[AnomalyEvent]:
        """
        检测价格跳空
        
        Args:
            symbol: 股票代码
            current_data: 当前数据（开盘、最高、最低、收盘、成交量）
            prev_close: 昨日收盘价
            
        Returns:
            异常事件或None
        """
        if prev_close <= 0:
            return None
        
        open_price = current_data.get('open', current_data.get('开盘', 0))
        gap_pct = (open_price - prev_close) / prev_close
        
        if gap_pct >= self.thresholds['gap_up']:
            return AnomalyEvent(
                symbol=symbol,
                anomaly_type=AnomalyType.PRICE_GAP_UP,
                level=AlertLevel.INFO if gap_pct < 0.05 else AlertLevel.WARNING,
                timestamp=datetime.now(),
                description=f"向上跳空 {gap_pct * 100:.2f}%",
                metrics={'gap_pct': gap_pct, 'open': open_price, 'prev_close': prev_close},
                suggested_action="关注是否能站稳跳空缺口上方",
                confidence=min(abs(gap_pct) / 0.05, 1.0)
            )
        elif gap_pct <= self.thresholds['gap_down']:
            return AnomalyEvent(
                symbol=symbol,
                anomaly_type=AnomalyType.PRICE_GAP_DOWN,
                level=AlertLevel.WARNING if gap_pct > -0.05 else AlertLevel.CRITICAL,
                timestamp=datetime.now(),
                description=f"向下跳空 {gap_pct * 100:.2f}%",
                metrics={'gap_pct': gap_pct, 'open': open_price, 'prev_close': prev_close},
                suggested_action="关注是否能回补跳空缺口",
                confidence=min(abs(gap_pct) / 0.05, 1.0)
            )
        
        return None
    
    def detect_volume_spike(self, symbol: str, current_volume: float,
                           lookback: int = 20) -> Optional[AnomalyEvent]:
        """
        检测成交量激增
        
        Args:
            symbol: 股票代码
            current_volume: 当前成交量
            lookback: 回看周期
            
        Returns:
            异常事件或None
        """
        history = list(self.volume_history[symbol])
        
        if len(history) < lookback:
            self.volume_history[symbol].append(current_volume)
            return None
        
        avg_volume = np.mean(history[-lookback:])
        
        if avg_volume <= 0:
            self.volume_history[symbol].append(current_volume)
            return None
        
        volume_ratio = current_volume / avg_volume
        
        self.volume_history[symbol].append(current_volume)
        
        if volume_ratio >= self.thresholds['volume_spike']:
            return AnomalyEvent(
                symbol=symbol,
                anomaly_type=AnomalyType.VOLUME_SPIKE,
                level=AlertLevel.INFO if volume_ratio < 5 else AlertLevel.WARNING,
                timestamp=datetime.now(),
                description=f"成交量激增 {volume_ratio:.1f}倍",
                metrics={'volume_ratio': volume_ratio, 'current_volume': current_volume, 'avg_volume': avg_volume},
                suggested_action="放量突破或出货信号，需结合价格走势判断",
                confidence=min(volume_ratio / 5, 1.0)
            )
        
        return None
    
    def detect_breakout(self, symbol: str, current_price: float,
                       df: pd.DataFrame, window: int = 20) -> Optional[AnomalyEvent]:
        """
        检测价格突破
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            df: 历史数据
            window: 计算窗口
            
        Returns:
            异常事件或None
        """
        if len(df) < window:
            return None
        
        high_col = 'high' if 'high' in df.columns else '最高'
        low_col = 'low' if 'low' in df.columns else '最低'
        
        recent_high = df[high_col].tail(window).max()
        recent_low = df[low_col].tail(window).min()
        
        # 向上突破
        if current_price > recent_high * (1 + self.thresholds['breakout']):
            return AnomalyEvent(
                symbol=symbol,
                anomaly_type=AnomalyType.PRICE_BREAKOUT,
                level=AlertLevel.WARNING,
                timestamp=datetime.now(),
                description=f"向上突破 {window}日高点",
                metrics={'current_price': current_price, 'resistance': recent_high, 'breakout_pct': (current_price / recent_high - 1) * 100},
                suggested_action="突破阻力位，关注量能配合",
                confidence=0.8
            )
        
        # 向下突破
        if current_price < recent_low * (1 - self.thresholds['breakout']):
            return AnomalyEvent(
                symbol=symbol,
                anomaly_type=AnomalyType.PRICE_BREAKDOWN,
                level=AlertLevel.CRITICAL,
                timestamp=datetime.now(),
                description=f"向下跌破 {window}日低点",
                metrics={'current_price': current_price, 'support': recent_low, 'breakdown_pct': (1 - current_price / recent_low) * 100},
                suggested_action="跌破支撑位，注意止损",
                confidence=0.8
            )
        
        return None
    
    def detect_volatility_spike(self, symbol: str, df: pd.DataFrame,
                                lookback: int = 20) -> Optional[AnomalyEvent]:
        """
        检测波动率激增
        
        Args:
            symbol: 股票代码
            df: 历史数据
            lookback: 回看周期
            
        Returns:
            异常事件或None
        """
        if len(df) < lookback + 1:
            return None
        
        close_col = 'close' if 'close' in df.columns else '收盘'
        
        # 计算历史波动率
        returns = df[close_col].pct_change().dropna()
        hist_vol = returns.tail(lookback).std() * np.sqrt(252)
        
        # 计算当前波动率（最近5天）
        current_vol = returns.tail(5).std() * np.sqrt(252)
        
        if hist_vol <= 0:
            return None
        
        vol_ratio = current_vol / hist_vol
        
        if vol_ratio >= self.thresholds['volatility_spike']:
            return AnomalyEvent(
                symbol=symbol,
                anomaly_type=AnomalyType.VOLATILITY_SPIKE,
                level=AlertLevel.WARNING,
                timestamp=datetime.now(),
                description=f"波动率激增 {vol_ratio:.1f}倍",
                metrics={'vol_ratio': vol_ratio, 'current_vol': current_vol, 'hist_vol': hist_vol},
                suggested_action="市场不确定性增加，注意风险控制",
                confidence=min(vol_ratio / 3, 1.0)
            )
        
        return None
    
    def detect_block_trade(self, symbol: str, trade_data: Dict[str, Any]) -> Optional[AnomalyEvent]:
        """
        检测大宗交易
        
        Args:
            symbol: 股票代码
            trade_data: 交易数据
            
        Returns:
            异常事件或None
        """
        amount = trade_data.get('amount', 0)  # 万元
        volume = trade_data.get('volume', 0)
        price = trade_data.get('price', 0)
        buyer = trade_data.get('buyer', '')
        seller = trade_data.get('seller', '')
        
        if amount < self.thresholds['block_trade_threshold']:
            return None
        
        # 判断是溢价还是折价
        market_price = trade_data.get('market_price', price)
        discount = (market_price - price) / market_price if market_price > 0 else 0
        
        if discount > 0.05:
            description = f"大宗折价成交 {discount * 100:.1f}%，金额{amount:.0f}万元"
            level = AlertLevel.WARNING
        elif discount < -0.05:
            description = f"大宗溢价成交 {abs(discount) * 100:.1f}%，金额{amount:.0f}万元"
            level = AlertLevel.INFO
        else:
            description = f"大宗平价成交，金额{amount:.0f}万元"
            level = AlertLevel.INFO
        
        return AnomalyEvent(
            symbol=symbol,
            anomaly_type=AnomalyType.BLOCK_TRADE,
            level=level,
            timestamp=datetime.now(),
            description=description,
            metrics={'amount': amount, 'volume': volume, 'price': price, 'discount': discount},
            suggested_action="关注机构席位动向，可能是建仓或出货信号",
            confidence=min(amount / 5000000, 1.0)  # 5000万为最高置信度
        )
    
    def detect_rapid_change(self, symbol: str, price_changes: List[float],
                           time_window_minutes: int = 5) -> Optional[AnomalyEvent]:
        """
        检测快速变动
        
        Args:
            symbol: 股票代码
            price_changes: 价格变动列表
            time_window_minutes: 时间窗口（分钟）
            
        Returns:
            异常事件或None
        """
        if len(price_changes) < 2:
            return None
        
        total_change = sum(price_changes)
        
        if abs(total_change) >= self.thresholds['rapid_change']:
            direction = "上涨" if total_change > 0 else "下跌"
            return AnomalyEvent(
                symbol=symbol,
                anomaly_type=AnomalyType.RAPID_CHANGE,
                level=AlertLevel.WARNING if abs(total_change) < 0.07 else AlertLevel.CRITICAL,
                timestamp=datetime.now(),
                description=f"{time_window_minutes}分钟内快速{direction} {abs(total_change) * 100:.2f}%",
                metrics={'total_change': total_change, 'time_window': time_window_minutes},
                suggested_action="快速变动可能伴随重要消息，建议关注公告",
                confidence=min(abs(total_change) / 0.1, 1.0)
            )
        
        return None
    
    def analyze(self, symbol: str, current_data: Dict[str, Any],
               historical_df: pd.DataFrame = None) -> List[AnomalyEvent]:
        """
        综合分析异常
        
        Args:
            symbol: 股票代码
            current_data: 当前数据
            historical_df: 历史数据
            
        Returns:
            异常事件列表
        """
        anomalies = []
        
        # 价格跳空检测
        if 'open' in current_data and 'prev_close' in current_data:
            gap_event = self.detect_price_gap(
                symbol,
                pd.Series(current_data),
                current_data['prev_close']
            )
            if gap_event:
                anomalies.append(gap_event)
        
        # 成交量激增检测
        if 'volume' in current_data:
            volume_event = self.detect_volume_spike(symbol, current_data['volume'])
            if volume_event:
                anomalies.append(volume_event)
        
        # 突破检测
        if historical_df is not None and 'close' in current_data:
            breakout_event = self.detect_breakout(symbol, current_data['close'], historical_df)
            if breakout_event:
                anomalies.append(breakout_event)
        
        # 波动率检测
        if historical_df is not None:
            vol_event = self.detect_volatility_spike(symbol, historical_df)
            if vol_event:
                anomalies.append(vol_event)
        
        # 保存历史
        self.anomaly_history[symbol].extend(anomalies)
        
        return anomalies
    
    def get_anomaly_stats(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        """
        获取异常统计
        
        Args:
            symbol: 股票代码
            days: 统计天数
            
        Returns:
            统计信息
        """
        cutoff = datetime.now() - timedelta(days=days)
        history = [a for a in self.anomaly_history.get(symbol, []) if a.timestamp >= cutoff]
        
        if not history:
            return {
                'total_count': 0,
                'by_type': {},
                'by_level': {},
                'avg_confidence': 0
            }
        
        by_type = defaultdict(int)
        by_level = defaultdict(int)
        total_confidence = 0
        
        for event in history:
            by_type[event.anomaly_type.value] += 1
            by_level[event.level.value] += 1
            total_confidence += event.confidence
        
        return {
            'total_count': len(history),
            'by_type': dict(by_type),
            'by_level': dict(by_level),
            'avg_confidence': total_confidence / len(history)
        }


class SmartAlertSystem:
    """智能提醒系统"""
    
    def __init__(self, detector: AnomalyDetector = None):
        self.detector = detector or AnomalyDetector()
        self.alerts = []
        self.alert_id_counter = 0
        self.subscribers = defaultdict(list)  # symbol -> list of callbacks
        self.ai = get_ai_manager()
    
    def generate_alert(self, event: AnomalyEvent) -> Alert:
        """
        从异常事件生成智能提醒
        
        Args:
            event: 异常事件
            
        Returns:
            智能提醒
        """
        self.alert_id_counter += 1
        alert_id = f"ALT{self.alert_id_counter:06d}"
        
        # 生成标题和消息
        title = f"[{event.level.value.upper()}] {event.symbol} {event.description}"
        
        # 使用AI生成建议
        message = self._generate_smart_message(event)
        
        # 确定有效期
        if event.level == AlertLevel.CRITICAL:
            expires = datetime.now() + timedelta(hours=1)
        elif event.level == AlertLevel.WARNING:
            expires = datetime.now() + timedelta(hours=4)
        else:
            expires = datetime.now() + timedelta(days=1)
        
        alert = Alert(
            id=alert_id,
            symbol=event.symbol,
            title=title,
            message=message,
            level=event.level,
            created_at=datetime.now(),
            expires_at=expires,
            actions=self._suggest_actions(event)
        )
        
        self.alerts.append(alert)
        
        # 通知订阅者
        self._notify_subscribers(event.symbol, alert)
        
        return alert
    
    def _generate_smart_message(self, event: AnomalyEvent) -> str:
        """生成智能提醒消息"""
        # 构建提示
        prompt = f"""请为以下股票异常事件生成一条简洁的提醒消息（100字以内）：

股票：{event.symbol}
异常类型：{event.anomaly_type.value}
描述：{event.description}
建议：{event.suggested_action}
置信度：{event.confidence * 100:.0f}%

请用中文生成提醒消息，包含：
1. 发生了什么
2. 意味着什么
3. 建议采取的行动"""
        
        try:
            response = self.ai.generate_response(prompt)
            return response.strip()[:200]
        except:
            # 备用方案
            return f"{event.description}。{event.suggested_action}。置信度：{event.confidence * 100:.0f}%"
    
    def _suggest_actions(self, event: AnomalyEvent) -> List[str]:
        """建议行动"""
        actions = []
        
        if event.anomaly_type in [AnomalyType.PRICE_BREAKOUT, AnomalyType.PRICE_GAP_UP]:
            actions = ['查看详情', '加入观察', '设置止盈']
        elif event.anomaly_type in [AnomalyType.PRICE_BREAKDOWN, AnomalyType.PRICE_GAP_DOWN]:
            actions = ['查看详情', '设置止损', '减仓']
        elif event.anomaly_type == AnomalyType.VOLUME_SPIKE:
            actions = ['查看详情', '分析资金流向']
        elif event.anomaly_type == AnomalyType.BLOCK_TRADE:
            actions = ['查看详情', '查看席位']
        else:
            actions = ['查看详情', '加入观察']
        
        return actions
    
    def subscribe(self, symbol: str, callback: Callable):
        """订阅股票提醒"""
        self.subscribers[symbol].append(callback)
    
    def unsubscribe(self, symbol: str, callback: Callable):
        """取消订阅"""
        if callback in self.subscribers[symbol]:
            self.subscribers[symbol].remove(callback)
    
    def _notify_subscribers(self, symbol: str, alert: Alert):
        """通知订阅者"""
        for callback in self.subscribers.get(symbol, []):
            try:
                callback(alert)
            except Exception as e:
                print(f"通知订阅者失败: {e}")
    
    def get_active_alerts(self, symbol: str = None, 
                         level: AlertLevel = None) -> List[Alert]:
        """
        获取活跃提醒
        
        Args:
            symbol: 股票代码过滤
            level: 级别过滤
            
        Returns:
            提醒列表
        """
        now = datetime.now()
        active = [a for a in self.alerts if a.expires_at > now and not a.is_read]
        
        if symbol:
            active = [a for a in active if a.symbol == symbol]
        if level:
            active = [a for a in active if a.level == level]
        
        return sorted(active, key=lambda x: x.created_at, reverse=True)
    
    def mark_as_read(self, alert_id: str):
        """标记提醒为已读"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.is_read = True
                break
    
    def clear_expired(self):
        """清理过期提醒"""
        now = datetime.now()
        self.alerts = [a for a in self.alerts if a.expires_at > now]
    
    def process_market_data(self, symbol: str, data: Dict[str, Any],
                           historical_df: pd.DataFrame = None) -> List[Alert]:
        """
        处理市场数据并生成提醒
        
        Args:
            symbol: 股票代码
            data: 当前市场数据
            historical_df: 历史数据
            
        Returns:
            生成的提醒列表
        """
        # 检测异常
        anomalies = self.detector.analyze(symbol, data, historical_df)
        
        # 生成提醒
        alerts = []
        for event in anomalies:
            # 过滤低置信度
            if event.confidence >= 0.6:
                alert = self.generate_alert(event)
                alerts.append(alert)
        
        return alerts
    
    def get_alert_summary(self, symbol: str = None) -> Dict[str, Any]:
        """
        获取提醒摘要
        
        Args:
            symbol: 股票代码
            
        Returns:
            摘要信息
        """
        alerts = self.get_active_alerts(symbol)
        
        summary = {
            'total': len(alerts),
            'critical': len([a for a in alerts if a.level == AlertLevel.CRITICAL]),
            'warning': len([a for a in alerts if a.level == AlertLevel.WARNING]),
            'info': len([a for a in alerts if a.level == AlertLevel.INFO]),
            'unread': len([a for a in alerts if not a.is_read])
        }
        
        # 按股票分组
        by_symbol = defaultdict(list)
        for a in alerts:
            by_symbol[a.symbol].append(a.id)
        
        summary['by_symbol'] = dict(by_symbol)
        
        return summary
