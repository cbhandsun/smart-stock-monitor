"""
统一的日志和错误处理系统
"""

import logging
import sys
import traceback
from datetime import datetime
from typing import Optional, Any, Dict
import json
import os
import re


_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "cookies",
    "headers",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}
_REDACTION_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*"),
    re.compile(
        r"(?i)((?:api[_-]?key|token|secret|password|cookie|authorization)\s*[:=]\s*)[^\s,;]+"
    ),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
)


def redact_text(value: object) -> str:
    """Redact common credentials from data before it reaches a log handler."""
    text = str(value)
    for pattern in _REDACTION_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]" if pattern.groups else "[REDACTED]", text)
    return text


def sanitize_log_data(value: object) -> object:
    """Recursively remove sensitive fields from structured logging metadata."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if str(key).lower() in _SENSITIVE_KEYS
            else sanitize_log_data(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_log_data(item) for item in value]
    return redact_text(value)


class SensitiveDataFilter(logging.Filter):
    """Final defense that redacts credentials from every emitted record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


class RedactingFormatter(logging.Formatter):
    """Formatter that also redacts exception text produced after filters run."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))

    def formatException(self, exc_info) -> str:
        return redact_text(super().formatException(exc_info))


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
        "RESET": "\033[0m",  # 重置
    }

    def format(self, record):
        record.message = record.getMessage()
        # 添加颜色
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # 格式化时间
        record.asctime = datetime.fromtimestamp(record.created).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # 构建日志消息
        msg = f"{color}[{record.asctime}] [{record.levelname}]{reset} {record.message}"

        # 如果有异常信息，添加堆栈跟踪
        if record.exc_info:
            exc_text = traceback.format_exception(*record.exc_info)
            msg += f"\n{''.join(exc_text)}"

        return redact_text(msg)


class StructuredLogger:
    """
    结构化日志记录器
    支持 JSON 格式输出，便于日志分析
    """

    def __init__(self, name: str, log_dir: str = "./logs"):
        self.name = name
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        # 创建标准 logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 避免重复添加 handler
        if self.logger.handlers:
            return

        # 控制台输出（带颜色）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredFormatter())
        console_handler.addFilter(SensitiveDataFilter())
        self.logger.addHandler(console_handler)

        # 文件输出（详细日志）
        log_file = os.path.join(
            log_dir, f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            RedactingFormatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
            )
        )
        file_handler.addFilter(SensitiveDataFilter())
        self.logger.addHandler(file_handler)

        # 错误日志单独文件
        error_file = os.path.join(
            log_dir, f"{name}_error_{datetime.now().strftime('%Y%m%d')}.log"
        )
        error_handler = logging.FileHandler(error_file, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            RedactingFormatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s\n%(exc_info)s"
            )
        )
        error_handler.addFilter(SensitiveDataFilter())
        self.logger.addHandler(error_handler)

    def _log(
        self,
        level: str,
        message: str,
        extra: Optional[Dict] = None,
        exc_info: bool = False,
    ):
        """内部日志方法"""
        # 构建结构化数据
        log_data: dict[str, object] = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "logger": self.name,
            "message": message,
        }

        if extra:
            log_data["extra"] = extra

        # 记录到标准 logger
        method = getattr(self.logger, level.lower())

        if extra:
            # 如果有额外数据，添加到消息中
            extra_str = json.dumps(
                sanitize_log_data(extra), ensure_ascii=False, default=str
            )
            full_message = f"{message} | {extra_str}"
        else:
            full_message = message

        method(full_message, exc_info=exc_info)

    def debug(self, message: str, extra: Optional[Dict] = None):
        self._log("DEBUG", message, extra)

    def info(self, message: str, extra: Optional[Dict] = None):
        self._log("INFO", message, extra)

    def warning(self, message: str, extra: Optional[Dict] = None):
        self._log("WARNING", message, extra)

    def error(self, message: str, extra: Optional[Dict] = None, exc_info: bool = True):
        self._log("ERROR", message, extra, exc_info=exc_info)

    def critical(
        self, message: str, extra: Optional[Dict] = None, exc_info: bool = True
    ):
        self._log("CRITICAL", message, extra, exc_info=exc_info)


# 全局日志记录器
_logger = None


def get_logger(name: str = "smart_stock") -> StructuredLogger:
    """获取全局日志记录器"""
    global _logger
    if _logger is None:
        _logger = StructuredLogger(name)
    return _logger


class ErrorHandler:
    """
    统一的错误处理器
    提供友好的错误信息和恢复建议
    """

    ERROR_MESSAGES = {
        "DATA_SOURCE_ERROR": {
            "message": "数据源连接失败",
            "suggestions": [
                "检查网络连接",
                "查看数据源状态: python data_router.py",
                "稍后重试",
            ],
        },
        "API_RATE_LIMIT": {
            "message": "API 调用频率超限",
            "suggestions": ["等待 60 秒后重试", "降低查询频率", "考虑升级 API 套餐"],
        },
        "INVALID_SYMBOL": {
            "message": "股票代码无效",
            "suggestions": ["检查股票代码格式（如：sh000001）", "确认股票代码是否存在"],
        },
        "CALCULATION_ERROR": {
            "message": "计算出错",
            "suggestions": ["检查输入数据是否完整", "查看日志了解详情"],
        },
        "AI_SERVICE_ERROR": {
            "message": "AI 服务调用失败",
            "suggestions": [
                "检查 API Key 是否有效",
                "确认网络连接正常",
                "尝试切换 AI 模型",
            ],
        },
    }

    @staticmethod
    def handle(
        exception: Exception, context: str = "", raise_error: bool = False
    ) -> Dict[str, Any]:
        """
        处理异常并返回结构化错误信息

        Args:
            exception: 异常对象
            context: 错误上下文
            raise_error: 是否重新抛出异常

        Returns:
            错误信息字典
        """
        logger = get_logger()

        # 获取异常类型
        exc_type = type(exception).__name__
        # Record the exception type and stack without adding user-controlled values.
        logger.error(
            f"错误发生: {exc_type}",
            extra={
                "context": context,
                "exception_type": exc_type,
            },
        )

        # 构建用户友好的错误信息
        error_info = {
            "success": False,
            "error_type": exc_type,
            "error_message": "操作失败，请稍后重试",
            "context": context,
            "timestamp": datetime.now().isoformat(),
        }

        # 添加建议
        if exc_type in ErrorHandler.ERROR_MESSAGES:
            template = ErrorHandler.ERROR_MESSAGES[exc_type]
            error_info["user_message"] = template["message"]
            error_info["suggestions"] = template["suggestions"]
        else:
            error_info["user_message"] = "操作失败，请稍后重试"
            error_info["suggestions"] = ["请稍后重试", "查看系统日志了解详情"]

        if raise_error:
            raise exception

        return error_info

    @staticmethod
    def safe_call(func, *args, default_return=None, context: str = "", **kwargs):
        """
        安全调用函数，自动处理异常

        Args:
            func: 要调用的函数
            args, kwargs: 函数参数
            default_return: 异常时的默认返回值
            context: 错误上下文

        Returns:
            函数返回值或 default_return
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            ErrorHandler.handle(e, context)
            return default_return


def setup_logging():
    """设置全局日志配置"""
    # 创建 logs 目录
    os.makedirs("./logs", exist_ok=True)

    # 配置根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 清除现有 handler
    root_logger.handlers = []

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(ColoredFormatter())
    console.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console)

    return get_logger()


# 装饰器：自动记录函数调用和异常
def log_call(level: str = "info"):
    """装饰器：记录函数调用"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger()
            func_name = func.__name__

            getattr(logger, level)(f"调用 {func_name}")

            try:
                result = func(*args, **kwargs)
                getattr(logger, level)(f"{func_name} 成功")
                return result
            except Exception:
                logger.error(f"{func_name} 失败", extra={"function": func_name})
                raise

        return wrapper

    return decorator


if __name__ == "__main__":
    # 测试日志系统
    setup_logging()
    logger = get_logger()

    print("\n" + "=" * 60)
    print("日志系统测试")
    print("=" * 60 + "\n")

    logger.debug("调试信息", extra={"detail": "some debug info"})
    logger.info("普通信息")
    logger.warning("警告信息")

    # 测试错误处理
    try:
        _ = 1 / 0
    except Exception as e:
        error_info = ErrorHandler.handle(e, "测试错误处理")
        print(f"\n错误信息: {json.dumps(error_info, indent=2, ensure_ascii=False)}")
