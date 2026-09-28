"""Secure, session-scoped authentication UI."""

import logging
import os

import streamlit as st

logger = logging.getLogger(__name__)

# ── AuthManager 初始化 ─────────────────────────────────────────────
try:
    from auth.user_auth import AuthManager

    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _SECRET = os.environ.get("JWT_SECRET_KEY")
    if not _SECRET:
        raise RuntimeError("JWT_SECRET_KEY is required")
    auth_manager = AuthManager(
        secret_key=_SECRET, data_dir=os.path.join(_BASE_DIR, "data", "users")
    )
    AUTH_AVAILABLE = True
    AUTH_CONFIGURATION_ERROR = None
except (ImportError, RuntimeError, ValueError) as exc:
    AUTH_AVAILABLE = False
    auth_manager = None
    AUTH_CONFIGURATION_ERROR = str(exc)
    logger.error(
        "Authentication is disabled because required configuration is unavailable"
    )


# ─────────────────────────────────────────────────────────────────
#  认证核心函数
# ─────────────────────────────────────────────────────────────────


def _restore_from_token(token: str) -> bool:
    """验证 token 并恢复 session，返回是否成功"""
    if not token or not auth_manager:
        return False
    payload = auth_manager.verify_token(token)
    if payload:
        user_id = payload.get("user_id")
        if not isinstance(user_id, str):
            return False
        user = auth_manager.get_user(user_id)
        if not user or not user.is_active:
            return False
        st.session_state["authenticated"] = True
        st.session_state["auth_token"] = token
        st.session_state["user_info"] = payload
        st.session_state["user_id"] = user_id
        return True
    return False


def check_auth() -> bool:
    """Validate the token held only in the current Streamlit session."""
    if not AUTH_AVAILABLE:
        return False

    token = st.session_state.get("auth_token")
    if st.session_state.get("authenticated", False) and isinstance(token, str):
        if _restore_from_token(token):
            return True
    logout()
    return False


def get_current_user() -> dict:
    return st.session_state.get("user_info", {})


def logout():
    st.session_state["authenticated"] = False
    st.session_state["auth_token"] = None
    st.session_state["user_info"] = {}
    st.session_state["user_id"] = None


# ─────────────────────────────────────────────────────────────────
#  登录页面渲染
# ─────────────────────────────────────────────────────────────────


def render_login_page():
    if not AUTH_AVAILABLE:
        st.error(
            "🚨 **系统配置错误**：认证服务未安全配置，访问已中止。请联系管理员检查 `JWT_SECRET_KEY` 和数据库连接。"
        )
        st.stop()

    # 精品登录页
    st.html("""
    <style>
    [data-testid="stSidebarNav"] { display: none !important; }
    .login-header {
        text-align: center;
        padding: 48px 0 24px;
    }
    .login-logo {
        font-size: 2.8rem;
        font-weight: 900;
        letter-spacing: -0.04em;
        background: linear-gradient(135deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1;
        margin-bottom: 8px;
    }
    .login-sub {
        font-size: 0.85rem;
        color: #475569;
        letter-spacing: 0.15em;
    }
    </style>
    <div class="login-header">
        <div class="login-logo">⚛️ SSM QUANT</div>
        <div class="login-sub">INSTITUTIONAL QUANTUM PRO · v8.0</div>
    </div>
    """)

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        tab1, tab2 = st.tabs(["🔑 登录", "📝 注册"])

        with tab1:
            with st.form("login_form"):
                username = st.text_input(
                    "用户名 / 邮箱", placeholder="输入用户名或邮箱"
                )
                password = st.text_input(
                    "密码", type="password", placeholder="输入密码"
                )
                submitted = st.form_submit_button(
                    "登 录", type="primary", use_container_width=True
                )
                st.caption("为保护账户安全，登录状态仅保留在当前安全会话中。")

            if submitted:
                if not username or not password:
                    st.error("请填写用户名和密码")
                else:
                    with st.spinner("验证中..."):
                        token = auth_manager.authenticate(username, password)
                    if token:
                        payload = auth_manager.verify_token(token)
                        if not payload or not isinstance(payload.get("user_id"), str):
                            st.error("❌ 登录会话创建失败，请重试")
                            return False
                        st.session_state["authenticated"] = True
                        st.session_state["auth_token"] = token
                        st.session_state["user_info"] = payload
                        st.session_state["user_id"] = payload["user_id"]

                        st.success(
                            f"✅ 欢迎回来，{payload.get('username', username)}！"
                        )
                        st.rerun()
                    else:
                        st.error("❌ 用户名或密码错误")

        with tab2:
            with st.form("register_form"):
                new_username = st.text_input(
                    "用户名",
                    placeholder="3-20个字符，可使用文字、数字、点、横线或下划线",
                    key="reg_user",
                )
                new_email = st.text_input(
                    "邮箱", placeholder="your@email.com", key="reg_email"
                )
                new_password = st.text_input(
                    "密码",
                    type="password",
                    placeholder="8-128个字符，需包含字母和数字",
                    key="reg_pass",
                )
                confirm_pass = st.text_input(
                    "确认密码", type="password", key="reg_confirm"
                )
                reg_submit = st.form_submit_button(
                    "注 册", type="primary", use_container_width=True
                )

            if reg_submit:
                if not all([new_username, new_email, new_password, confirm_pass]):
                    st.error("请填写所有字段")
                elif new_password != confirm_pass:
                    st.error("两次密码不一致")
                else:
                    try:
                        user = auth_manager.create_user(
                            new_username, new_email, new_password
                        )
                        st.success(
                            f"✅ 注册成功！欢迎 {user.username}，请切换到登录标签页"
                        )
                    except ValueError as e:
                        st.error(f"❌ {e}")

    return st.session_state.get("authenticated", False)


def render_user_menu():
    user_info = get_current_user()
    if user_info:
        username = user_info.get("username", "用户")
        st.markdown(
            f'<div style="font-size:0.82rem;color:#64748b;padding:4px 0;">'
            f'👤 <strong style="color:#94a3b8;">{username}</strong>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button("🚪 登出", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()
