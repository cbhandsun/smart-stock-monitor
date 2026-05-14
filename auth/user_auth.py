from datetime import datetime, timedelta
import jwt
import bcrypt
from dataclasses import dataclass, asdict
from typing import Dict, Optional
import json
import os

from database.models import get_db, User as DBUser

@dataclass
class User:
    """内部映射的模型"""
    id: str
    username: str
    email: str
    password_hash: str
    created_at: str
    last_login: Optional[str] = None
    preferences: Dict = None
    is_active: bool = True
    is_admin: bool = False
    
    @classmethod
    def from_db(cls, db_user):
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
            is_admin=db_user.is_admin
        )

class AuthManager:
    """用户认证管理器(PG支持版)"""
    
    def __init__(self, secret_key: str, data_dir: str = None):
        self.secret_key = secret_key
        # no internal cache needed
        try:
            self.db_manager = get_db()
        except Exception as e:
            print("DB not available at init:", e)
    
    def hash_password(self, password: str) -> str:
        """密码哈希"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    
    def create_user(self, username: str, email: str, password: str, 
                    is_admin: bool = False) -> User:
        """创建用户"""
        session = self.db_manager.get_session()
        try:
            # 检查重复
            if session.query(DBUser).filter_by(username=username).first():
                raise ValueError(f"用户名 {username} 已存在")
            if session.query(DBUser).filter_by(email=email).first():
                raise ValueError(f"邮箱 {email} 已注册")
                
            user_id = f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            password_hash = self.hash_password(password)
            
            new_user = DBUser(
                id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                created_at=datetime.now().isoformat(),
                preferences={
                    'theme': 'dark',
                    'language': 'zh',
                    'risk_tolerance': 'medium',
                    'default_page': 'market'
                },
                is_active=True,
                is_admin=is_admin
            )
            session.add(new_user)
            session.commit()
            return User.from_db(new_user)
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """用户认证"""
        session = self.db_manager.get_session()
        try:
            user = session.query(DBUser).filter(
                (DBUser.username == username) | (DBUser.email == username)
            ).first()
            if not user or not user.is_active:
                return None
            if not self.verify_password(password, user.password_hash):
                return None
                
            user.last_login = datetime.now().isoformat()
            session.commit()
            
            u_model = User.from_db(user)
        except Exception:
            return None
        finally:
            session.close()
            
        # 生成JWT令牌（30天有效，配合"记住我"功能）
        token = jwt.encode(
            {
                'user_id': u_model.id,
                'username': u_model.username,
                'is_admin': u_model.is_admin,
                'exp': datetime.utcnow() + timedelta(days=30)
            },
            self.secret_key,
            algorithm='HS256'
        )
        
        return token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """验证令牌"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
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
            if 'email' in kwargs:
                user.email = kwargs['email']
            if 'preferences' in kwargs:
                # Merge dicts
                pref = user.preferences.copy() if user.preferences else {}
                pref.update(kwargs['preferences'])
                user.preferences = pref
            if 'is_active' in kwargs:
                user.is_active = kwargs['is_active']
            session.commit()
        finally:
            session.close()
    
    def change_password(self, user_id: str, old_password: str, new_password: str):
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
