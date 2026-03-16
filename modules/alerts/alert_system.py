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
    """预警管理器"""
    
    def __init__(self, data_dir: str = "./data/alerts"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.alerts: Dict[str, Alert] = {}
        self.callbacks: List[Callable] = []
        self._load_alerts()
    
    def _load_alerts(self):
        """加载预警规则"""
        alerts_file = os.path.join(self.data_dir, "alerts.json")
        if os.path.exists(alerts_file):
            with open(alerts_file, 'r') as f:
                data = json.load(f)
                for alert_data in data:
                    alert_data['alert_type'] = AlertType(alert_data['alert_type'])
                    alert_data['status'] = AlertStatus(alert_data['status'])
                    self.alerts[alert_data['id']] = Alert(**alert_data)
    
    def _save_alerts(self):
        """保存预警规则"""
        alerts_file = os.path.join(self.data_dir, "alerts.json")
        data = []
        for alert in self.alerts.values():
            alert_dict = alert.__dict__.copy()
            alert_dict['alert_type'] = alert.alert_type.value
            alert_dict['status'] = alert.status.value
            data.append(alert_dict)
        with open(alerts_file, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_alert(self, symbol: str, alert_type: AlertType, 
                  threshold: float, message: str = "") -> Alert:
        """添加预警规则"""
        alert_id = f"alert_{datetime.now().strftime('%Y%m%d%H%M%S')}_{symbol}"
        alert = Alert(
            id=alert_id,
            symbol=symbol,
            alert_type=alert_type,
            threshold=threshold,
            message=message or f"{symbol} {alert_type.value} {threshold}",
            status=AlertStatus.ACTIVE,
            created_at=datetime.now().isoformat()
        )
        self.alerts[alert_id] = alert
        self._save_alerts()
        return alert
    
    def remove_alert(self, alert_id: str):
        """删除预警规则"""
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            self._save_alerts()
    
    def enable_alert(self, alert_id: str):
        """启用预警"""
        if alert_id in self.alerts:
            self.alerts[alert_id].status = AlertStatus.ACTIVE
            self._save_alerts()
    
    def disable_alert(self, alert_id: str):
        """禁用预警"""
        if alert_id in self.alerts:
            self.alerts[alert_id].status = AlertStatus.DISABLED
            self._save_alerts()
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """根据ID获取预警"""
        return self.alerts.get(alert_id)
    
    def reset_alert(self, alert_id: str):
        """重置预警状态为活跃"""
        if alert_id in self.alerts:
            self.alerts[alert_id].status = AlertStatus.ACTIVE
            self.alerts[alert_id].triggered_at = None
            self._save_alerts()
    
    def check_alerts(self, symbol: str, current_data: Dict) -> List[Alert]:
        """检查触发的预警"""
        triggered = []
        for alert in self.alerts.values():
            if alert.symbol != symbol or alert.status != AlertStatus.ACTIVE:
                continue
            
            should_trigger = False
            
            if alert.alert_type == AlertType.PRICE_ABOVE:
                should_trigger = current_data.get('price', 0) > alert.threshold
            elif alert.alert_type == AlertType.PRICE_BELOW:
                should_trigger = current_data.get('price', 0) < alert.threshold
            elif alert.alert_type == AlertType.CHANGE_PCT_ABOVE:
                should_trigger = current_data.get('change_pct', 0) > alert.threshold
            elif alert.alert_type == AlertType.CHANGE_PCT_BELOW:
                should_trigger = current_data.get('change_pct', 0) < alert.threshold
            elif alert.alert_type == AlertType.RSI_ABOVE:
                should_trigger = current_data.get('rsi', 0) > alert.threshold
            elif alert.alert_type == AlertType.RSI_BELOW:
                should_trigger = current_data.get('rsi', 0) < alert.threshold
            elif alert.alert_type == AlertType.VOLUME_SPIKE:
                should_trigger = current_data.get('volume', 0) > alert.threshold
            
            if should_trigger:
                alert.status = AlertStatus.TRIGGERED
                alert.triggered_at = datetime.now().isoformat()
                alert.trigger_count += 1
                triggered.append(alert)
                self._notify(alert, current_data)
        
        if triggered:
            self._save_alerts()
        
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
        return [a for a in self.alerts.values() if a.symbol == symbol]
    
    def get_active_alerts(self) -> List[Alert]:
        """获取所有活跃预警"""
        return [a for a in self.alerts.values() if a.status == AlertStatus.ACTIVE]
    
    def get_triggered_alerts(self) -> List[Alert]:
        """获取所有已触发预警"""
        return [a for a in self.alerts.values() if a.status == AlertStatus.TRIGGERED]
    
    def list_all_alerts(self) -> List[Alert]:
        """列出所有预警"""
        return list(self.alerts.values())
    
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
