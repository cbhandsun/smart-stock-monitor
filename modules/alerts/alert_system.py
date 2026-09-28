import logging
import math
from uuid import uuid4
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.user_context import require_user_id
from database.models import DatabaseManager, get_db


logger = logging.getLogger(__name__)


def _finite_number(value: object, default: float = 0.0) -> float:
    """Coerce untrusted market data to a finite float."""
    if isinstance(value, bool):
        return default
    if not isinstance(value, (str, int, float)):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


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
    user_id: str
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

    def __init__(
        self,
        data_dir: Optional[str] = None,
        user_id: Optional[str] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.user_id = require_user_id(user_id)
        self.callbacks: List[Callable] = []
        self.db = db_manager or get_db()

    def _get_session(self):
        return self.db.get_session()

    def _get_owned_rule(self, session, alert_id: str):
        from database.models import AlertRule

        if not isinstance(alert_id, str) or not alert_id or len(alert_id) > 100:
            raise ValueError("invalid alert id")
        return (
            session.query(AlertRule)
            .filter_by(
                id=alert_id,
                user_id=self.user_id,
            )
            .first()
        )

    def _db_to_dataclass(self, rule) -> Alert:
        return Alert(
            id=rule.id,
            user_id=rule.user_id,
            symbol=rule.symbol,
            alert_type=AlertType(rule.alert_type),
            threshold=rule.threshold,
            message=rule.message or "",
            status=AlertStatus(rule.status),
            created_at=rule.created_at.isoformat() if rule.created_at else "",
            triggered_at=rule.triggered_at.isoformat() if rule.triggered_at else None,
            trigger_count=rule.trigger_count or 0,
        )

    def list_all_alerts(self) -> List[Alert]:
        """列出所有预警"""
        from database.models import AlertRule

        session = self._get_session()
        try:
            rules = session.query(AlertRule).filter_by(user_id=self.user_id).all()
            return [self._db_to_dataclass(r) for r in rules]
        finally:
            session.close()

    def add_alert(
        self, symbol: str, alert_type: AlertType, threshold: float, message: str = ""
    ) -> Alert:
        """添加预警规则"""
        from database.models import AlertRule

        if not isinstance(symbol, str) or not symbol.isdigit() or len(symbol) != 6:
            raise ValueError("股票代码必须是6位数字")
        if not isinstance(alert_type, AlertType):
            raise ValueError("预警类型无效")
        threshold = float(threshold)
        if not math.isfinite(threshold):
            raise ValueError("预警阈值必须是有限数值")
        if (
            alert_type
            in {AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW, AlertType.VOLUME_SPIKE}
            and threshold < 0
        ):
            raise ValueError("价格或成交量阈值不能为负数")
        if (
            alert_type in {AlertType.RSI_ABOVE, AlertType.RSI_BELOW}
            and not 0 <= threshold <= 100
        ):
            raise ValueError("RSI 阈值必须在0-100之间")
        if (
            alert_type in {AlertType.CHANGE_PCT_ABOVE, AlertType.CHANGE_PCT_BELOW}
            and not 0 <= threshold <= 100
        ):
            raise ValueError("涨跌幅阈值必须在0-100之间")
        if not isinstance(message, str) or len(message) > 500:
            raise ValueError("预警消息不能超过500个字符")
        alert_id = f"alert_{uuid4().hex}"
        session = self._get_session()
        try:
            rule = AlertRule(
                id=alert_id,
                user_id=self.user_id,
                symbol=symbol,
                alert_type=alert_type.value,
                threshold=float(threshold),
                message=message or f"{symbol} {alert_type.value} {threshold}",
                status=AlertStatus.ACTIVE.value,
                created_at=datetime.now(),
                trigger_count=0,
            )
            session.add(rule)
            session.commit()
            return self._db_to_dataclass(rule)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def remove_alert(self, alert_id: str) -> bool:
        """Delete an alert only when it belongs to the requesting user."""
        session = self._get_session()
        try:
            rule = self._get_owned_rule(session, alert_id)
            if not rule:
                return False
            session.delete(rule)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def enable_alert(self, alert_id: str) -> bool:
        """启用预警"""
        session = self._get_session()
        try:
            rule = self._get_owned_rule(session, alert_id)
            if not rule:
                return False
            rule.status = AlertStatus.ACTIVE.value
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def disable_alert(self, alert_id: str) -> bool:
        """禁用预警"""
        session = self._get_session()
        try:
            rule = self._get_owned_rule(session, alert_id)
            if not rule:
                return False
            rule.status = AlertStatus.DISABLED.value
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """根据ID获取预警"""
        session = self._get_session()
        try:
            rule = self._get_owned_rule(session, alert_id)
            return self._db_to_dataclass(rule) if rule else None
        finally:
            session.close()

    def reset_alert(self, alert_id: str) -> bool:
        """重置预警状态为活跃"""
        session = self._get_session()
        try:
            rule = self._get_owned_rule(session, alert_id)
            if not rule:
                return False
            rule.status = AlertStatus.ACTIVE.value
            rule.triggered_at = None
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_active_alerts(self) -> List[Alert]:
        """获取所有活跃预警"""
        from database.models import AlertRule

        session = self._get_session()
        try:
            rules = (
                session.query(AlertRule)
                .filter_by(user_id=self.user_id, status=AlertStatus.ACTIVE.value)
                .all()
            )
            return [self._db_to_dataclass(r) for r in rules]
        finally:
            session.close()

    def get_triggered_alerts(self) -> List[Alert]:
        """获取所有已触发预警"""
        from database.models import AlertRule

        session = self._get_session()
        try:
            rules = (
                session.query(AlertRule)
                .filter_by(user_id=self.user_id, status=AlertStatus.TRIGGERED.value)
                .all()
            )
            return [self._db_to_dataclass(r) for r in rules]
        finally:
            session.close()

    def check_alerts(self, symbol: str, current_data: Dict) -> List[Alert]:
        """检查触发的预警"""
        from database.models import AlertRule

        if not isinstance(symbol, str) or not isinstance(current_data, dict):
            raise ValueError("invalid market data")
        triggered = []
        session = self._get_session()
        try:
            rules = (
                session.query(AlertRule)
                .filter_by(
                    user_id=self.user_id, symbol=symbol, status=AlertStatus.ACTIVE.value
                )
                .all()
            )

            for rule in rules:
                should_trigger = False

                price = _finite_number(current_data.get("price"))
                change_pct = _finite_number(current_data.get("change_pct"))
                rsi = _finite_number(current_data.get("rsi"))
                volume = _finite_number(current_data.get("volume"))

                alert_type_enum = AlertType(rule.alert_type)

                if alert_type_enum == AlertType.PRICE_ABOVE:
                    should_trigger = price >= rule.threshold
                elif alert_type_enum == AlertType.PRICE_BELOW:
                    should_trigger = price <= rule.threshold
                elif alert_type_enum == AlertType.CHANGE_PCT_ABOVE:
                    should_trigger = change_pct >= rule.threshold
                elif alert_type_enum == AlertType.CHANGE_PCT_BELOW:
                    should_trigger = change_pct <= -abs(rule.threshold)
                elif alert_type_enum == AlertType.RSI_ABOVE:
                    should_trigger = rsi >= rule.threshold
                elif alert_type_enum == AlertType.RSI_BELOW:
                    should_trigger = rsi <= rule.threshold
                elif alert_type_enum == AlertType.VOLUME_SPIKE:
                    should_trigger = volume >= rule.threshold

                if should_trigger:
                    rule.status = AlertStatus.TRIGGERED.value
                    rule.triggered_at = datetime.now()
                    rule.trigger_count = (rule.trigger_count or 0) + 1

                    alert_dc = self._db_to_dataclass(rule)
                    triggered.append(alert_dc)

            if triggered:
                session.commit()
            for alert in triggered:
                self._notify(alert, current_data)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

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
        from database.models import AlertRule

        session = self._get_session()
        try:
            rules = (
                session.query(AlertRule)
                .filter_by(user_id=self.user_id, symbol=symbol)
                .all()
            )
            return [self._db_to_dataclass(r) for r in rules]
        finally:
            session.close()

    def _notify(self, alert: Alert, data: Dict):
        """通知回调"""
        for callback in self.callbacks:
            try:
                callback(alert, data)
            except Exception:
                logger.error("Alert callback failed")

    def register_callback(self, callback: Callable):
        """注册通知回调"""
        self.callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        """取消注册通知回调"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
