"""Authentication input validation and normalization."""

from __future__ import annotations

import re
import unicodedata


_USERNAME_RE = re.compile(r"^[\w.-]{3,20}$", re.UNICODE)
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_PASSWORD_MIN_LENGTH = 8
_PASSWORD_MAX_LENGTH = 128


def normalize_username(value: object) -> str:
    """Normalize and validate a username from an untrusted input."""
    if not isinstance(value, str):
        raise ValueError("用户名格式不正确")
    username = unicodedata.normalize("NFKC", value).strip()
    if not _USERNAME_RE.fullmatch(username):
        raise ValueError("用户名需为3-20个字符，仅可包含文字、数字、点、横线或下划线")
    return username


def normalize_email(value: object) -> str:
    """Normalize and validate an email address from an untrusted input."""
    if not isinstance(value, str):
        raise ValueError("邮箱格式不正确")
    email = unicodedata.normalize("NFKC", value).strip().lower()
    if len(email) > 254 or not _EMAIL_RE.fullmatch(email):
        raise ValueError("请输入有效的邮箱地址")
    return email


def validate_password(value: object) -> str:
    """Validate a password without modifying the user's secret."""
    if not isinstance(value, str):
        raise ValueError("密码格式不正确")
    if not _PASSWORD_MIN_LENGTH <= len(value) <= _PASSWORD_MAX_LENGTH:
        raise ValueError("密码长度需为8-128个字符")
    if _CONTROL_RE.search(value):
        raise ValueError("密码不能包含控制字符")
    if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
        raise ValueError("密码需同时包含字母和数字")
    return value


def validate_registration(
    username: object, email: object, password: object
) -> tuple[str, str, str]:
    """Validate all registration fields and return normalized values."""
    return (
        normalize_username(username),
        normalize_email(email),
        validate_password(password),
    )
