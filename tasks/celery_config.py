from celery import Celery
from celery.schedules import crontab
import os

# Celery应用配置
celery_app = Celery(
    'stock_monitor',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2'),
    include=['tasks.market_data', 'tasks.alerts', 'tasks.reports']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# 定时任务配置
celery_app.conf.beat_schedule = {
    'update-market-data': {
        'task': 'tasks.market_data.update_all_stocks',
        'schedule': 60.0,  # 每分钟
    },
    'check-alerts': {
        'task': 'tasks.alerts.check_all_alerts',
        'schedule': 30.0,  # 每30秒
    },
    'daily-report': {
        'task': 'tasks.reports.generate_daily_report',
        'schedule': crontab(hour=16, minute=0),  # 每天16:00
    },
    'weekly-report': {
        'task': 'tasks.reports.generate_weekly_report',
        'schedule': crontab(day_of_week=5, hour=18, minute=0),  # 每周五18:00
    },
    'prewarm-market-snapshot': {
        'task': 'tasks.market_data.prewarm_market_snapshot',
        'schedule': 300.0,  # 每5分钟
    },
    'sync-market-valuation': {
        'task': 'tasks.market_data.sync_market_valuation',
        'schedule': crontab(hour=16, minute=30),  # 每交易日16:30全屏同步
    },
}
