"""
预警任务 — Celery 异步执行
通知渠道优先级: 企业微信 Webhook > 通用 Webhook > 日志降级
"""

from celery import shared_task
import sys
import os
import logging
import requests
from datetime import datetime, time as dtime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.alerts.alert_system import AlertManager
from core.cache import RedisCache
from core.url_security import validate_https_webhook
from database.models import get_db
from modules.alerts.delivery_ledger import DeliveryLedger

logger = logging.getLogger(__name__)

_WECOM_HOSTS = {"qyapi.weixin.qq.com"}
_LARK_HOSTS = {"open.feishu.cn", "open.larksuite.com"}


def _generic_webhook_hosts() -> set[str]:
    raw_hosts = os.getenv("ALERT_WEBHOOK_ALLOWED_HOSTS", "")
    return {host.strip() for host in raw_hosts.split(",") if host.strip()}


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
    url = validate_https_webhook(os.getenv("WECOM_WEBHOOK_URL", ""), _WECOM_HOSTS)
    if not url:
        return False
    try:
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": f"## {title}\n{content}"},
        }
        resp = requests.post(url, json=payload, timeout=(3, 5))
        resp.raise_for_status()
        result = resp.json()
        if result.get("errcode") == 0:
            logger.info("WeCom alert delivery succeeded")
            return True
        logger.warning("[Alert] 企业微信推送被远端拒绝")
        return False
    except (requests.RequestException, ValueError, TypeError):
        logger.warning("[Alert] 企业微信推送失败")
        return False


def _send_lark_webhook(title: str, content: str) -> bool:
    """
    飞书 Webhook 推送 (文本消息)
    配置方式: 环境变量 LARK_WEBHOOK_URL
    """
    url = validate_https_webhook(os.getenv("LARK_WEBHOOK_URL", ""), _LARK_HOSTS)
    if not url:
        return False
    try:
        payload = {"msg_type": "text", "content": {"text": f"{title}\n{content}"}}
        resp = requests.post(url, json=payload, timeout=(3, 5))
        resp.raise_for_status()
        result = resp.json()
        if result.get("StatusCode") == 0 or result.get("code") == 0:
            logger.info("Lark alert delivery succeeded")
            return True
        logger.warning("[Alert] 飞书推送被远端拒绝")
        return False
    except (requests.RequestException, ValueError, TypeError):
        logger.warning("[Alert] 飞书推送失败")
        return False


def _send_generic_webhook(alert_id: str, title: str, content: str) -> bool:
    """
    通用 Webhook 推送 (POST JSON)
    配置方式: 环境变量 ALERT_WEBHOOK_URL
    """
    url = validate_https_webhook(
        os.getenv("ALERT_WEBHOOK_URL", ""),
        _generic_webhook_hosts(),
    )
    if not url:
        return False
    try:
        payload = {
            "alert_id": alert_id,
            "title": title,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        resp = requests.post(url, json=payload, timeout=(3, 5))
        if 200 <= resp.status_code < 300:
            logger.info("Generic webhook alert delivery succeeded")
            return True
        logger.warning(
            "Generic webhook alert delivery was rejected",
            extra={"status_code": resp.status_code},
        )
        return False
    except requests.RequestException:
        logger.warning("[Alert] Webhook 推送失败")
        return False


def _deliver_notification(alert_id: str, message: str) -> str:
    """
    通知分发 (降级链: 企微 → 飞书 → 通用 Webhook → 日志)
    返回实际使用的渠道名称
    """
    if not isinstance(alert_id, str) or not alert_id or len(alert_id) > 100:
        raise ValueError("invalid alert id")
    if not isinstance(message, str) or len(message) > 500:
        raise ValueError("invalid alert message")
    title = f"📢 SSM 预警触发 [{alert_id}]"
    content = message

    if _send_wecom_webhook(title, content):
        return "wecom"
    if _send_lark_webhook(title, content):
        return "lark"
    if _send_generic_webhook(alert_id, title, content):
        return "webhook"

    # No remote channel: record metadata in the delivery ledger without persisting user content.
    logger.warning("No remote alert channel is configured")
    return "ledger"


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
        cache = RedisCache()
        user_ids = get_db().get_active_alert_user_ids()
        if not user_ids:
            return "No active alerts"

        managers = [AlertManager(user_id=user_id) for user_id in user_ids]
        alerts_by_manager = [
            (manager, manager.get_active_alerts()) for manager in managers
        ]
        active_alerts = [alert for _, alerts in alerts_by_manager for alert in alerts]

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
        triggered = []
        for manager, alerts in alerts_by_manager:
            owned_symbols = {alert.symbol for alert in alerts}
            owned_market_data = {
                symbol: data
                for symbol, data in market_data.items()
                if symbol in owned_symbols
            }
            triggered.extend(manager.check_all_alerts(owned_market_data))

        # 异步发送通知 (每条独立任务，失败不阻塞其他)
        for alert in triggered:
            event_key = f"{alert.id}:{alert.trigger_count}"
            send_alert_notification.delay(
                event_key,
                alert.user_id,
                alert.id,
                alert.message,
            )

        return f"Checked {len(active_alerts)} alerts, {len(triggered)} triggered"

    except Exception:
        logger.error("Alert checking failed")
        raise


@shared_task(bind=True, max_retries=2)
def send_alert_notification(
    self,
    event_key: str,
    user_id: str,
    alert_id: str,
    message: str,
):
    """
    发送预警通知 (多渠道降级链)
    渠道: 企业微信 Webhook → 通用 Webhook → 日志文件
    """
    ledger = DeliveryLedger()
    if not ledger.claim(event_key, alert_id, user_id):
        return "Notification already handled"
    try:
        channel = _deliver_notification(alert_id, message)
        ledger.mark_sent(event_key, channel)
        return f"Notification sent via [{channel}] for {alert_id}"
    except Exception:
        ledger.mark_failed(event_key)
        logger.error("Alert notification delivery failed")
        try:
            raise self.retry(exc=RuntimeError("alert delivery failed"), countdown=30)
        except self.MaxRetriesExceededError:
            logger.error("Alert notification reached its retry limit")
            return "Notification failed"


@shared_task
def cleanup_triggered_alerts(days: int = 7):
    """清理已触发的旧预警"""
    try:
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        removed = 0
        for user_id in get_db().get_triggered_alert_user_ids():
            alert_manager = AlertManager(user_id=user_id)
            for alert in alert_manager.get_triggered_alerts():
                if alert.triggered_at and alert.triggered_at < cutoff_date:
                    if alert_manager.remove_alert(alert.id):
                        removed += 1

        logger.info(
            f"[cleanup_triggered_alerts] Removed {removed} old alerts (>{days}d)"
        )
        return f"Removed {removed} old alerts"

    except Exception:
        logger.error("Triggered-alert cleanup failed")
        raise
