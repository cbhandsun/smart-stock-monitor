"""
预警任务 — Celery 异步执行
通知渠道优先级: 企业微信 Webhook > 通用 Webhook > 日志降级
"""
from celery import shared_task
import sys
import os
import logging
import json
import requests
from datetime import datetime, time as dtime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.alerts.alert_system import AlertManager, AlertType
from core.cache import RedisCache

logger = logging.getLogger(__name__)


def is_trading_hours() -> bool:
    """判断是否为 A 股交易时段 (工作日 09:25~15:05)"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 25) <= t <= dtime(15, 5)


# ============================================================
#  通知发送核心 (多渠道降级链)
# ============================================================

def _send_wecom_webhook(title: str, content: str) -> bool:
    """
    企业微信 Webhook 推送 (Markdown 消息)
    配置方式: 环境变量 WECOM_WEBHOOK_URL
    """
    url = os.getenv('WECOM_WEBHOOK_URL', '')
    if not url:
        return False
    try:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n{content}"
            }
        }
        resp = requests.post(url, json=payload, timeout=5)
        result = resp.json()
        if result.get('errcode') == 0:
            logger.info(f"[Alert] 企业微信推送成功: {title}")
            return True
        else:
            logger.warning(f"[Alert] 企业微信推送失败: {result}")
            return False
    except Exception as e:
        logger.warning(f"[Alert] 企业微信推送异常: {e}")
        return False


def _send_generic_webhook(alert_id: str, title: str, content: str) -> bool:
    """
    通用 Webhook 推送 (POST JSON)
    配置方式: 环境变量 ALERT_WEBHOOK_URL
    """
    url = os.getenv('ALERT_WEBHOOK_URL', '')
    if not url:
        return False
    try:
        payload = {
            "alert_id": alert_id,
            "title": title,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            logger.info(f"[Alert] Webhook 推送成功: {alert_id}")
            return True
        logger.warning(f"[Alert] Webhook 推送失败 HTTP {resp.status_code}: {alert_id}")
        return False
    except Exception as e:
        logger.warning(f"[Alert] Webhook 推送异常: {e}")
        return False


def _deliver_notification(alert_id: str, message: str) -> str:
    """
    通知分发 (降级链: 企微 → 通用 Webhook → 日志)
    返回实际使用的渠道名称
    """
    title = f"📢 SSM 预警触发 [{alert_id}]"
    content = message

    if _send_wecom_webhook(title, content):
        return "wecom"
    if _send_generic_webhook(alert_id, title, content):
        return "webhook"

    # 兜底: 写入持久化告警日志
    log_dir = './logs/alerts'
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"alerts_{datetime.now().strftime('%Y-%m-%d')}.log")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().isoformat()}] {alert_id}: {message}\n")
    logger.info(f"[Alert] 已写入日志降级: {alert_id}")
    return "log"


# ============================================================
#  Celery 任务
# ============================================================

@shared_task
def check_all_alerts():
    """检查所有预警 (仅交易时段 + 非交易时段收盘后触发一次)"""
    if not is_trading_hours():
        logger.debug("[check_all_alerts] 非交易时段，跳过")
        return "Skipped: outside trading hours"

    try:
        alert_manager = AlertManager()
        cache = RedisCache()

        # 获取所有活跃预警
        active_alerts = alert_manager.get_active_alerts()
        if not active_alerts:
            return "No active alerts"

        # 获取需要检查的股票列表
        symbols = set(a.symbol for a in active_alerts)

        # 从 Redis 获取最新行情 (由 update_all_stocks 每分钟刷新)
        market_data = {}
        for symbol in symbols:
            data = cache.get_stock_data(symbol, "quote")
            if data:
                market_data[symbol] = data

        if not market_data:
            logger.debug("[check_all_alerts] 行情缓存为空，跳过本次检查")
            return "No market data in cache"

        # 检查预警触发
        triggered = alert_manager.check_all_alerts(market_data)

        # 异步发送通知 (每条独立任务，失败不阻塞其他)
        for alert in triggered:
            send_alert_notification.delay(alert.id, alert.message)

        return f"Checked {len(active_alerts)} alerts, {len(triggered)} triggered"

    except Exception as e:
        logger.error(f"[check_all_alerts] error: {e}")
        return f"Error: {str(e)}"


@shared_task(bind=True, max_retries=2)
def send_alert_notification(self, alert_id: str, message: str):
    """
    发送预警通知 (多渠道降级链)
    渠道: 企业微信 Webhook → 通用 Webhook → 日志文件
    """
    try:
        channel = _deliver_notification(alert_id, message)
        return f"Notification sent via [{channel}] for {alert_id}"
    except Exception as exc:
        logger.error(f"[send_alert_notification] fatal error: {exc}")
        try:
            raise self.retry(exc=exc, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error(f"[send_alert_notification] max retries reached for {alert_id}")
            return f"Failed to notify: {alert_id}"


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

        logger.info(f"[cleanup_triggered_alerts] Removed {removed} old alerts (>{days}d)")
        return f"Removed {removed} old alerts"

    except Exception as e:
        logger.error(f"[cleanup_triggered_alerts] error: {e}")
        return f"Error: {str(e)}"
