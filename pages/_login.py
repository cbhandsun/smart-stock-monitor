"""
🔐 用户认证 UI 页面
集成 auth/user_auth.py 的 AuthManager 到 Streamlit
"""
import streamlit as st
import os
import logging

logger = logging.getLogger(__name__)

# 条件导入
try:
    from auth.user_auth import AuthManager
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _SECRET = os.environ.get("JWT_SECRET_KEY", "ssm-default-secret-key-change-me")
    auth_manager = AuthManager(secret_key=_SECRET, data_dir=os.path.join(_BASE_DIR, "data", "users"))
    AUTH_AVAILABLE = True
except ImportError as e:
    AUTH_AVAILABLE = False
    auth_manager = None
    logger.warning(f"Auth module not available: {e}")


def check_auth() -> bool:
    """检查用户是否已登录，返回 True 表示已认证"""
    if not AUTH_AVAILABLE:
        return True  # 如果auth模块不可用，默认放行

    return st.session_state.get('authenticated', False)


def get_current_user() -> dict:
    """获取当前登录用户信息"""
    return st.session_state.get('user_info', {})


def logout():
    """登出"""
    st.session_state['authenticated'] = False
    st.session_state['auth_token'] = None
    st.session_state['user_info'] = {}


def render_login_page():
    """渲染登录/注册页面"""
    if not AUTH_AVAILABLE:
        st.warning("认证模块未安装，请安装 bcrypt 和 pyjwt")
        return True

    st.markdown("""
    <style>
    /* Hide Streamlit native sidebar navigation on login page */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
    </style>
    <div style='text-align:center; padding: 40px 0 20px 0;'>
        <h1 style='color:#3b82f6; font-size:2.5rem;'>⚛️ SSM Quantum Pro</h1>
        <p style='color:#94a3b8; font-size:1.1rem;'>Smart Stock Monitor v7.0</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔑 登录", "📝 注册"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("用户名 / 邮箱", placeholder="输入用户名或邮箱")
            password = st.text_input("密码", type="password", placeholder="输入密码")
            remember = st.checkbox("记住我", value=True)
            submitted = st.form_submit_button("登 录", type="primary", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("请填写用户名和密码")
                else:
                    token = auth_manager.authenticate(username, password)
                    if token:
                        payload = auth_manager.verify_token(token)
                        st.session_state['authenticated'] = True
                        st.session_state['auth_token'] = token
                        st.session_state['user_info'] = payload
                        st.session_state['user_id'] = payload.get('user_id', 'default_user')
                        st.success("✅ 登录成功！")
                        st.rerun()
                    else:
                        st.error("❌ 用户名或密码错误")

    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("用户名", placeholder="3-20个字符", key="reg_user")
            new_email = st.text_input("邮箱", placeholder="your@email.com", key="reg_email")
            new_password = st.text_input("密码", type="password", placeholder="至少6个字符", key="reg_pass")
            confirm_password = st.text_input("确认密码", type="password", placeholder="再次输入密码", key="reg_confirm")
            submitted = st.form_submit_button("注 册", type="primary", use_container_width=True)

            if submitted:
                if not all([new_username, new_email, new_password, confirm_password]):
                    st.error("请填写所有字段")
                elif len(new_password) < 6:
                    st.error("密码至少需要6个字符")
                elif new_password != confirm_password:
                    st.error("两次输入的密码不一致")
                else:
                    try:
                        user = auth_manager.create_user(new_username, new_email, new_password)
                        st.success(f"✅ 注册成功！欢迎 {user.username}，请切换到登录标签页登录")
                    except ValueError as e:
                        st.error(f"❌ {str(e)}")

    return st.session_state.get('authenticated', False)


def render_user_menu():
    """在侧边栏渲染用户菜单"""
    user_info = get_current_user()
    if user_info:
        username = user_info.get('username', '用户')
        st.markdown(f"👤 **{username}**")
        if st.button("🚪 登出", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()
