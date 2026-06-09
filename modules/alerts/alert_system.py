import json
import os
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class AlertType(Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    CHANGE_PCT_ABOVE = "change_pct_above"
    CHANGE_PCT_BELOW = "change_pct_below"
    RSI_ABOVE = "rsi_above"
    RSI_BELOW = "rsi_below"
    MA_CROSS = "ma_cross"
    VOLUME_SPIKE = "volume_spike"

class AlertStatus(Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    DISABLED = "disabled"

@dataclass
class Alert:
    """预警规则"""
    id: str
    symbol: str
    alert_type: AlertType
    threshold: float
    message: str
    status: AlertStatus
    created_at: str
    triggered_at: Optional[str] = None
    trigger_count: int = 0

class AlertManager:
    """预警管理器 (PostgreSQL版)"""
    
    def __init__(self, data_dir: str = None, user_id: str = None):
        if not user_id:
            try:
                import streamlit as st
                if st.runtime.exists():
                    user_id = st.session_state.get('user_id', 'default_user')
                else:
                    user_id = 'default_user'
            except Exception:
                user_id = 'default_user'
        self.user_id = user_id
        self.callbacks: List[Callable] = []
        try:
            from database.models import get_db
            self.db = get_db()
        except Exception as e:
            self.db = None
            print("Failed to initialize database in AlertManager:", e)

    def _get_session(self):
        if self.db:
            return self.db.get_session()
        raise ConnectionError("Database not connected in AlertManager")

    def _db_to_dataclass(self, rule) -> Alert:
        return Alert(
            id=rule.id,
            symbol=rule.symbol,
            alert_type=AlertType(rule.alert_type),
            threshold=rule.threshold,
            message=rule.message or "",
            status=AlertStatus(rule.status),
            created_at=rule.created_at.isoformat() if rule.created_at else "",
            triggered_at=rule.triggered_at.isoformat() if rule.triggered_at else None,
            trigger_count=rule.trigger_count or 0
        )

    def list_all_alerts(self) -> List[Alert]:
        """列出所有预警"""
        try:
            from database.models import AlertRule
            session = self._get_session()
            rules = session.query(AlertRule).filter_by(user_id=self.user_id).all()
            result = [self._db_to_dataclass(r) for r in rules]
            session.close()
            return result
        except Exception as e:
            print("Failed to list alerts from DB:", e)
            return []

    def add_alert(self, symbol: str, alert_type: AlertType, 
                  threshold: float, message: str = "") -> Alert:
        """添加预警规则"""
        try:
            from database.models import AlertRule
            import uuid
            alert_id = f"alert_{uuid.uuid4().hex[:12]}_{symbol}"
            session = self._get_session()
            
            rule = AlertRule(
                id=alert_id,
                user_id=self.user_id,
                symbol=symbol,
                alert_type=alert_type.value,
                threshold=float(threshold),
                message=message or f"{symbol} {alert_type.value} {threshold}",
                status=AlertStatus.ACTIVE.value,
                created_at=datetime.now(),
                trigger_count=0
            )
            session.add(rule)
            session.commit()
            
            # Map back to dataclass
            alert = self._db_to_dataclass(rule)
            session.close()
            return alert
        except Exception as e:
            print("Failed to add alert to DB:", e)
            return Alert(
                id=f"alert_dummy_{symbol}",
                symbol=symbol,
                alert_type=alert_type,
                threshold=threshold,
                message=message,
                status=AlertStatus.ACTIVE,
                created_at=datetime.now().isoformat()
            )

    def remove_alert(self, alert_id: str):
        """删除预警规则"""
        try:
            from database.models import AlertRule
            session = self._get_session()
            rule = session.query(AlertRule).filter_by(id=alert_id).first()
            if rule:
                session.delete(rule)
                session.commit()
            session.close()
        except Exception as e:
            print("Failed to remove alert from DB:", e)

    def enable_alert(self, alert_id: str):
        """启用预警"""
        try:
            from database.models import AlertRule
            session = self._get_session()
            rule = session.query(AlertRule).filter_by(id=alert_id).first()
            if rule:
                rule.status = AlertStatus.ACTIVE.value
                session.commit()
            session.close()
        except Exception as e:
            print("Failed to enable alert in DB:", e)

    def disable_alert(self, alert_id: str):
        """禁用预警"""
        try:
            from database.models import AlertRule
            session = self._get_session()
            rule = session.query(AlertRule).filter_by(id=alert_id).first()
            if rule:
                rule.status = AlertStatus.DISABLED.value
                session.commit()
            session.close()
        except Exception as e:
            print("Failed to disable alert in DB:", e)

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """根据ID获取预警"""
        try:
            from database.models import AlertRule
            session = self._get_session()
            rule = session.query(AlertRule).filter_by(id=alert_id).first()
            result = self._db_to_dataclass(rule) if rule else None
            session.close()
            return result
        except Exception as e:
            print("Failed to get alert from DB:", e)
            return None

    def reset_alert(self, alert_id: str):
        """重置预警状态为活跃"""
        try:
            from database.models import AlertRule
            session = self._get_session()
            rule = session.query(AlertRule).filter_by(id=alert_id).first()
            if rule:
                rule.status = AlertStatus.ACTIVE.value
                rule.triggered_at = None
                session.commit()
            session.close()
        except Exception as e:
            print("Failed to reset alert in DB:", e)

    def get_active_alerts(self) -> List[Alert]:
        """获取所有活跃预警"""
        try:
            from database.models import AlertRule
            session = self._get_session()
            rules = session.query(AlertRule).filter_by(user_id=self.user_id, status=AlertStatus.ACTIVE.value).all()
            result = [self._db_to_dataclass(r) for r in rules]
            session.close()
            return result
        except Exception as e:
            print("Failed to get active alerts from DB:", e)
            return []

    def get_triggered_alerts(self) -> List[Alert]:
        """获取所有已触发预警"""
        try:
            from database.models import AlertRule
            session = self._get_session()
            rules = session.query(AlertRule).filter_by(user_id=self.user_id, status=AlertStatus.TRIGGERED.value).all()
            result = [self._db_to_dataclass(r) for r in rules]
            session.close()
            return result
        except Exception as e:
            print("Failed to get triggered alerts from DB:", e)
            return []

    def check_alerts(self, symbol: str, current_data: Dict) -> List[Alert]:
        """检查触发的预警"""
        triggered = []
        try:
            from database.models import AlertRule
            session = self._get_session()
            rules = session.query(AlertRule).filter_by(
                user_id=self.user_id, 
                symbol=symbol, 
                status=AlertStatus.ACTIVE.value
            ).all()
            
            for rule in rules:
                should_trigger = False
                
                price = current_data.get('price', 0)
                change_pct = current_data.get('change_pct', 0)
                rsi = current_data.get('rsi', 0)
                volume = current_data.get('volume', 0)
                
                alert_type_enum = AlertType(rule.alert_type)
                
                if alert_type_enum == AlertType.PRICE_ABOVE:
                    should_trigger = price > rule.threshold
                elif alert_type_enum == AlertType.PRICE_BELOW:
                    should_trigger = price < rule.threshold
                elif alert_type_enum == AlertType.CHANGE_PCT_ABOVE:
                    should_trigger = change_pct > rule.threshold
                elif alert_type_enum == AlertType.CHANGE_PCT_BELOW:
                    should_trigger = change_pct < rule.threshold
                elif alert_type_enum == AlertType.RSI_ABOVE:
                    should_trigger = rsi > rule.threshold
                elif alert_type_enum == AlertType.RSI_BELOW:
                    should_trigger = rsi < rule.threshold
                elif alert_type_enum == AlertType.VOLUME_SPIKE:
                    should_trigger = volume > rule.threshold
                
                if should_trigger:
                    rule.status = AlertStatus.TRIGGERED.value
                    rule.triggered_at = datetime.now()
                    rule.trigger_count = (rule.trigger_count or 0) + 1
                    
                    alert_dc = self._db_to_dataclass(rule)
                    triggered.append(alert_dc)
                    self._notify(alert_dc, current_data)
                    
            if triggered:
                session.commit()
            session.close()
        except Exception as e:
            print("Failed to check alerts in DB:", e)
            
        return triggered

    def check_all_alerts(self, market_data: Dict[str, Dict]) -> List[Alert]:
        """检查所有股票的预警"""
        all_triggered = []
        for symbol, data in market_data.items():
            triggered = self.check_alerts(symbol, data)
            all_triggered.extend(triggered)
        return all_triggered

    def get_alerts_for_symbol(self, symbol: str) -> List[Alert]:
        """获取某只股票的所有预警"""
        try:
            from database.models import AlertRule
            session = self._get_session()
            rules = session.query(AlertRule).filter_by(user_id=self.user_id, symbol=symbol).all()
            result = [self._db_to_dataclass(r) for r in rules]
            session.close()
            return result
        except Exception as e:
            print("Failed to get alerts for symbol from DB:", e)
            return []

    def _notify(self, alert: Alert, data: Dict):
        """通知回调"""
        for callback in self.callbacks:
            try:
                callback(alert, data)
            except Exception as e:
                print(f"通知回调失败: {e}")

    def register_callback(self, callback: Callable):
        """注册通知回调"""
        self.callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        """取消注册通知回调"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
