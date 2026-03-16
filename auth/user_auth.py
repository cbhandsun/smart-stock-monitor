from datetime import datetime, timedelta
import jwt
import bcrypt
from dataclasses import dataclass, asdict
from typing import Dict, Optional
import json
import os

@dataclass
class User:
    """用户模型"""
    id: str
    username: str
    email: str
    password_hash: str
    created_at: str
    last_login: Optional[str] = None
    preferences: Dict = None
    is_active: bool = True
    is_admin: bool = False

class AuthManager:
    """用户认证管理器"""
    
    def __init__(self, secret_key: str, data_dir: str = "./data/users"):
        self.secret_key = secret_key
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.users: Dict[str, User] = {}
        self._load_users()
    
    def _load_users(self):
        """加载用户数据"""
        users_file = os.path.join(self.data_dir, "users.json")
        if os.path.exists(users_file):
            with open(users_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for user_data in data:
                    self.users[user_data['id']] = User(**user_data)
    
    def _save_users(self):
        """保存用户数据"""
        users_file = os.path.join(self.data_dir, "users.json")
        data = [asdict(user) for user in self.users.values()]
        with open(users_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
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
        # 检查用户名是否已存在
        if any(u.username == username for u in self.users.values()):
            raise ValueError(f"用户名 {username} 已存在")
        
        if any(u.email == email for u in self.users.values()):
            raise ValueError(f"邮箱 {email} 已注册")
        
        user_id = f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        password_hash = self.hash_password(password)
        
        user = User(
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
        
        self.users[user_id] = user
        self._save_users()
        
        return user
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """用户认证"""
        user = None
        for u in self.users.values():
            if u.username == username or u.email == username:
                user = u
                break
        
        if not user or not user.is_active:
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        # 更新最后登录时间
        user.last_login = datetime.now().isoformat()
        self._save_users()
        
        # 生成JWT令牌
        token = jwt.encode(
            {
                'user_id': user.id,
                'username': user.username,
                'is_admin': user.is_admin,
                'exp': datetime.utcnow() + timedelta(days=7)
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
        """获取用户信息"""
        return self.users.get(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    def update_user(self, user_id: str, **kwargs):
        """更新用户信息"""
        if user_id not in self.users:
            raise ValueError(f"用户 {user_id} 不存在")
        
        user = self.users[user_id]
        
        if 'email' in kwargs:
            user.email = kwargs['email']
        if 'preferences' in kwargs:
            user.preferences.update(kwargs['preferences'])
        if 'is_active' in kwargs:
            user.is_active = kwargs['is_active']
        
        self._save_users()
    
    def change_password(self, user_id: str, old_password: str, new_password: str):
        """修改密码"""
        user = self.users.get(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        if not self.verify_password(old_password, user.password_hash):
            raise ValueError("原密码错误")
        
        user.password_hash = self.hash_password(new_password)
        self._save_users()
    
    def reset_password(self, user_id: str, new_password: str):
        """重置密码（管理员使用）"""
        user = self.users.get(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        user.password_hash = self.hash_password(new_password)
        self._save_users()
    
    def deactivate_user(self, user_id: str):
        """停用用户"""
        if user_id in self.users:
            self.users[user_id].is_active = False
            self._save_users()
    
    def delete_user(self, user_id: str):
        """删除用户"""
        if user_id in self.users:
            del self.users[user_id]
            self._save_users()
    
    def list_users(self) -> list:
        """列出所有用户"""
        return list(self.users.values())
