from datetime import datetime, timedelta, timezone
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

import bcrypt
import jwt

from auth.validation import (
    normalize_email,
    normalize_username,
    validate_password,
    validate_registration,
)
from auth.login_throttle import LoginThrottle
from database.models import DatabaseManager, User as DBUser, get_db


logger = logging.getLogger(__name__)
_JWT_ISSUER = "ssm-quant"
_JWT_AUDIENCE = "ssm-web"


@dataclass
class User:
    """内部映射的模型"""

    id: str
    username: str
    email: str
    password_hash: str
    created_at: str
    last_login: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    is_active: bool = True
    is_admin: bool = False

    @classmethod
    def from_db(cls, db_user: Optional[DBUser]) -> Optional["User"]:
        if not db_user:
            return None
        return cls(
            id=db_user.id,
            username=db_user.username,
            email=db_user.email,
            password_hash=db_user.password_hash,
            created_at=db_user.created_at,
            last_login=db_user.last_login,
            preferences=db_user.preferences or {},
            is_active=db_user.is_active,
            is_admin=db_user.is_admin,
        )


class AuthManager:
    """用户认证管理器(PG支持版)"""

    def __init__(
        self,
        secret_key: str,
        data_dir: Optional[str] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        if not isinstance(secret_key, str) or len(secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        self.secret_key = secret_key
        self.db_manager = db_manager or get_db()
        self.login_throttle = LoginThrottle(self.db_manager)

    def hash_password(self, password: str) -> str:
        """密码哈希"""
        validate_password(password)
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    def create_user(
        self, username: str, email: str, password: str, is_admin: bool = False
    ) -> User:
        """创建用户"""
        username, email, password = validate_registration(username, email, password)
        session = self.db_manager.get_session()
        try:
            # 检查重复
            if session.query(DBUser).filter_by(username=username).first():
                raise ValueError("用户名已存在")
            if session.query(DBUser).filter_by(email=email).first():
                raise ValueError("邮箱已注册")

            user_id = f"user_{uuid4().hex}"
            password_hash = self.hash_password(password)

            new_user = DBUser(
                id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                created_at=datetime.now().isoformat(),
                preferences={
                    "theme": "dark",
                    "language": "zh",
                    "risk_tolerance": "medium",
                    "default_page": "market",
                },
                is_active=True,
                is_admin=is_admin,
            )
            session.add(new_user)
            session.commit()
            mapped_user = User.from_db(new_user)
            if mapped_user is None:
                raise RuntimeError("new user could not be mapped")
            return mapped_user
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """用户认证"""
        if not isinstance(username, str) or not isinstance(password, str):
            return None
        identity = username.strip()
        if not identity or len(identity) > 254 or len(password) > 128:
            return None
        if "@" in identity:
            try:
                identity = normalize_email(identity)
            except ValueError:
                return None
        else:
            try:
                identity = normalize_username(identity)
            except ValueError:
                return None
        if not self.login_throttle.is_allowed(identity):
            return None
        session = self.db_manager.get_session()
        try:
            user = (
                session.query(DBUser)
                .filter((DBUser.username == identity) | (DBUser.email == identity))
                .first()
            )
            if not user or not user.is_active:
                self.login_throttle.record_failure(identity)
                return None
            if not self.verify_password(password, user.password_hash):
                self.login_throttle.record_failure(identity)
                return None

            user.last_login = datetime.now().isoformat()
            session.commit()

            u_model = User.from_db(user)
            self.login_throttle.reset(identity)
        except Exception:
            logger.error("Authentication failed because the user store is unavailable")
            return None
        finally:
            session.close()

        if u_model is None:
            return None

        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "user_id": u_model.id,
                "username": u_model.username,
                "is_admin": u_model.is_admin,
                "iat": now,
                "exp": now + timedelta(hours=8),
                "iss": _JWT_ISSUER,
                "aud": _JWT_AUDIENCE,
                "jti": uuid4().hex,
            },
            self.secret_key,
            algorithm="HS256",
        )

        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证令牌"""
        if not isinstance(token, str) or not token or len(token) > 4096:
            return None
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
                issuer=_JWT_ISSUER,
                audience=_JWT_AUDIENCE,
                options={"require": ["exp", "iat", "iss", "aud", "jti", "user_id"]},
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def get_user(self, user_id: str) -> Optional[User]:
        session = self.db_manager.get_session()
        try:
            user = session.query(DBUser).filter_by(id=user_id).first()
            return User.from_db(user)
        finally:
            session.close()

    def get_user_by_username(self, username: str) -> Optional[User]:
        session = self.db_manager.get_session()
        try:
            user = session.query(DBUser).filter_by(username=username).first()
            return User.from_db(user)
        finally:
            session.close()

    def update_user(self, user_id: str, **kwargs):
        session = self.db_manager.get_session()
        try:
            user = session.query(DBUser).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"用户 {user_id} 不存在")
            if "email" in kwargs:
                user.email = kwargs["email"]
            if "preferences" in kwargs:
                # Merge dicts
                pref = user.preferences.copy() if user.preferences else {}
                pref.update(kwargs["preferences"])
                user.preferences = pref
            if "is_active" in kwargs:
                user.is_active = kwargs["is_active"]
            session.commit()
        finally:
            session.close()

    def change_password(self, user_id: str, old_password: str, new_password: str):
        validate_password(new_password)
        session = self.db_manager.get_session()
        try:
            user = session.query(DBUser).filter_by(id=user_id).first()
            if not user:
                raise ValueError("用户不存在")
            if not self.verify_password(old_password, user.password_hash):
                raise ValueError("原密码错误")
            user.password_hash = self.hash_password(new_password)
            session.commit()
        finally:
            session.close()

    def reset_password(self, user_id: str, new_password: str):
        validate_password(new_password)
        session = self.db_manager.get_session()
        try:
            user = session.query(DBUser).filter_by(id=user_id).first()
            if not user:
                raise ValueError("用户不存在")
            user.password_hash = self.hash_password(new_password)
            session.commit()
        finally:
            session.close()

    def deactivate_user(self, user_id: str):
        session = self.db_manager.get_session()
        try:
            user = session.query(DBUser).filter_by(id=user_id).first()
            if user:
                user.is_active = False
                session.commit()
        finally:
            session.close()

    def delete_user(self, user_id: str):
        session = self.db_manager.get_session()
        try:
            user = session.query(DBUser).filter_by(id=user_id).first()
            if user:
                session.delete(user)
                session.commit()
        finally:
            session.close()

    def list_users(self) -> list:
        session = self.db_manager.get_session()
        try:
            users = session.query(DBUser).all()
            return [User.from_db(u) for u in users]
        finally:
            session.close()
