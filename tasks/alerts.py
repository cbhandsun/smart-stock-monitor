from celery import shared_task
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.alerts.alert_system import AlertManager, AlertType
from core.cache import RedisCache

@shared_task
def check_all_alerts():
    """检查所有预警"""
    try:
        alert_manager = AlertManager()
        cache = RedisCache()
        
        # 获取所有活跃预警
        active_alerts = alert_manager.get_active_alerts()
        
        if not active_alerts:
            return "No active alerts"
        
        # 获取需要检查的股票列表
        symbols = set(a.symbol for a in active_alerts)
        
        # 获取最新行情
        market_data = {}
        for symbol in symbols:
            data = cache.get_stock_data(symbol, "quote")
            if data:
                market_data[symbol] = data
        
        # 检查预警
        triggered = alert_manager.check_all_alerts(market_data)
        
        # 发送通知（可以集成邮件、短信、推送等）
        for alert in triggered:
            send_alert_notification.delay(alert.id, alert.message)
        
        return f"Checked {len(active_alerts)} alerts, {len(triggered)} triggered"
        
    except Exception as e:
        return f"Error: {str(e)}"

@shared_task
def send_alert_notification(alert_id: str, message: str):
    """发送预警通知"""
    # 这里可以集成各种通知渠道
    # 例如：邮件、短信、推送、Webhook等
    
    print(f"[ALERT] {alert_id}: {message}")
    
    # TODO: 实现具体的通知逻辑
    # - 发送邮件
    # - 发送短信
    # - 发送推送通知
    # - 调用Webhook
    
    return f"Notification sent for {alert_id}"

@shared_task
def cleanup_triggered_alerts(days: int = 7):
    """清理已触发的旧预警"""
    try:
        from datetime import datetime, timedelta
        
        alert_manager = AlertManager()
        triggered = alert_manager.get_triggered_alerts()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        removed = 0
        for alert in triggered:
            if alert.triggered_at and alert.triggered_at < cutoff_date:
                alert_manager.remove_alert(alert.id)
                removed += 1
        
        return f"Removed {removed} old alerts"
        
    except Exception as e:
        return f"Error: {str(e)}"
