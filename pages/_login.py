"""
🔐 用户认证 UI 页面 v2.0
修复「记住我」失效问题：
- 改用 localStorage 持久化 token（比 Cookie 更可靠，不受 iframe 沙盒限制）
- 通过 st.query_params 在页面加载时传递 token
- 服务端 session 文件兜底（容器重启后依然有效）
"""
import streamlit as st
import streamlit.components.v1 as components
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── AuthManager 初始化 ─────────────────────────────────────────────
try:
    from auth.user_auth import AuthManager
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _SECRET = os.environ.get("JWT_SECRET_KEY", "ssm-quantum-pro-persistent-key-2026")
    auth_manager = AuthManager(secret_key=_SECRET, data_dir=os.path.join(_BASE_DIR, "data", "users"))
    AUTH_AVAILABLE = True
except ImportError as e:
    AUTH_AVAILABLE = False
    auth_manager = None
    logger.warning(f"Auth module not available: {e}")

# ── Session 持久化目录 ─────────────────────────────────────────────
_SESSION_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data" / "sessions"
_SESSION_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────
#  localStorage 读写组件（Streamlit 与浏览器双向通信标准方案）
# ─────────────────────────────────────────────────────────────────

_READ_TOKEN_JS = """
<script>
(function() {
    var token = localStorage.getItem('ssm_auth_token');
    if (token) {
        // 通过修改 URL query param 把 token 传回 Streamlit
        var url = new URL(window.parent.location.href);
        if (!url.searchParams.get('_auth_token')) {
            url.searchParams.set('_auth_token', token);
            window.parent.history.replaceState({}, '', url);
            // 触发 Streamlit 重新解析 query params
            window.parent.location.href = url.toString();
        }
    }
})();
</script>
"""

_WRITE_TOKEN_JS_TPL = """
<script>
(function() {{
    var token = "{token}";
    var remember = {remember};
    if (remember && token) {{
        localStorage.setItem('ssm_auth_token', token);
    }} else {{
        localStorage.removeItem('ssm_auth_token');
    }}
    // 清理 URL 中的 _auth_token 参数
    var url = new URL(window.parent.location.href);
    url.searchParams.delete('_auth_token');
    window.parent.history.replaceState({{}}, '', url);
}})();
</script>
"""

_CLEAR_TOKEN_JS = """
<script>
(function() {
    localStorage.removeItem('ssm_auth_token');
    var url = new URL(window.parent.location.href);
    url.searchParams.delete('_auth_token');
    window.parent.history.replaceState({}, '', url);
})();
</script>
"""


def _inject_js(js: str):
    """注入 JS 到父页面（height>0 才能在部分浏览器执行）"""
    components.html(f"<html><body>{js}</body></html>", height=1)


def _save_server_session(token: str, user_id: str):
    """服务端 session 文件持久化（容器重启兜底）"""
    try:
        session_file = _SESSION_DIR / f"{user_id}.json"
        session_file.write_text(json.dumps({"token": token, "user_id": user_id}))
    except Exception as e:
        logger.warning(f"Session file save failed: {e}")


def _load_server_session_by_token(token: str) -> dict | None:
    """按 token 反查 session 文件"""
    try:
        for f in _SESSION_DIR.glob("*.json"):
            data = json.loads(f.read_text())
            if data.get("token") == token:
                return data
    except Exception:
        pass
    return None


def _clear_server_session(user_id: str):
    """清除服务端 session"""
    try:
        session_file = _SESSION_DIR / f"{user_id}.json"
        if session_file.exists():
            session_file.unlink()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────
#  认证核心函数
# ─────────────────────────────────────────────────────────────────

def _restore_from_token(token: str) -> bool:
    """验证 token 并恢复 session，返回是否成功"""
    if not token or not auth_manager:
        return False
    payload = auth_manager.verify_token(token)
    if payload:
        st.session_state['authenticated'] = True
        st.session_state['auth_token'] = token
        st.session_state['user_info'] = payload
        st.session_state['user_id'] = payload.get('user_id', 'default_user')
        return True
    return False


def check_auth() -> bool:
    """
    检查认证状态（优先级）：
    1. session_state（已在内存中）
    2. URL query param _auth_token（localStorage 读取后注入）
    3. st.context.cookies（浏览器 Cookie）
    """
    if not AUTH_AVAILABLE:
        return True

    # 1. 已在 session
    if st.session_state.get('authenticated', False):
        return True

    # 2. URL query param（localStorage 写入后跳转携带）
    try:
        token = st.query_params.get("_auth_token", "")
        if token and _restore_from_token(token):
            # 清理 URL 中的敏感参数（由 JS 处理，Python 侧也清一下）
            try:
                params = dict(st.query_params)
                params.pop("_auth_token", None)
                st.query_params.update(params)
            except Exception:
                pass
            return True
    except Exception as e:
        logger.debug(f"Query param auth failed: {e}")

    # 3. 浏览器 Cookie（st.context.cookies，Streamlit 1.30+ 支持）
    try:
        cookies = st.context.cookies
        token = cookies.get("auth_token_ssm", "")
        if token and _restore_from_token(token):
            return True
    except Exception as e:
        logger.debug(f"Cookie auth failed: {e}")

    # 4. 触发 localStorage 读取（首次加载时注入 JS，下次刷新时通过 query param 传回）
    _inject_js(_READ_TOKEN_JS)

    return False


def get_current_user() -> dict:
    return st.session_state.get('user_info', {})


def logout():
    user_id = st.session_state.get('user_id', '')
    _clear_server_session(user_id)
    st.session_state['authenticated'] = False
    st.session_state['auth_token'] = None
    st.session_state['user_info'] = {}
    st.session_state['user_id'] = None
    _inject_js(_CLEAR_TOKEN_JS)


# ─────────────────────────────────────────────────────────────────
#  登录页面渲染
# ─────────────────────────────────────────────────────────────────

def render_login_page():
    if not AUTH_AVAILABLE:
        st.warning("认证模块未安装，请安装 bcrypt 和 pyjwt")
        return True

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
                username = st.text_input("用户名 / 邮箱", placeholder="输入用户名或邮箱")
                password = st.text_input("密码", type="password", placeholder="输入密码")
                remember = st.checkbox("🍪 记住我（30天免登录）", value=True)
                submitted = st.form_submit_button("登 录", type="primary", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("请填写用户名和密码")
                else:
                    with st.spinner("验证中..."):
                        token = auth_manager.authenticate(username, password)
                    if token:
                        payload = auth_manager.verify_token(token)
                        st.session_state['authenticated'] = True
                        st.session_state['auth_token'] = token
                        st.session_state['user_info'] = payload
                        st.session_state['user_id'] = payload.get('user_id', 'default_user')

                        if remember:
                            # 写入 localStorage（JS）
                            _inject_js(_WRITE_TOKEN_JS_TPL.format(
                                token=token, remember="true"
                            ))
                            # 服务端 session 兜底
                            _save_server_session(token, payload.get('user_id', 'u'))
                            st.toast("✅ 已记住登录状态，30天免登录", icon="🍪")
                        else:
                            _inject_js(_WRITE_TOKEN_JS_TPL.format(
                                token="", remember="false"
                            ))

                        st.success(f"✅ 欢迎回来，{payload.get('username', username)}！")
                        import time; time.sleep(0.8)
                        st.rerun()
                    else:
                        st.error("❌ 用户名或密码错误")

        with tab2:
            with st.form("register_form"):
                new_username = st.text_input("用户名", placeholder="3-20个字符", key="reg_user")
                new_email    = st.text_input("邮箱", placeholder="your@email.com", key="reg_email")
                new_password = st.text_input("密码", type="password", placeholder="至少6个字符", key="reg_pass")
                confirm_pass = st.text_input("确认密码", type="password", key="reg_confirm")
                reg_submit   = st.form_submit_button("注 册", type="primary", use_container_width=True)

            if reg_submit:
                if not all([new_username, new_email, new_password, confirm_pass]):
                    st.error("请填写所有字段")
                elif len(new_password) < 6:
                    st.error("密码至少需要6个字符")
                elif new_password != confirm_pass:
                    st.error("两次密码不一致")
                else:
                    try:
                        user = auth_manager.create_user(new_username, new_email, new_password)
                        st.success(f"✅ 注册成功！欢迎 {user.username}，请切换到登录标签页")
                    except ValueError as e:
                        st.error(f"❌ {e}")

    return st.session_state.get('authenticated', False)


def render_user_menu():
    user_info = get_current_user()
    if user_info:
        username = user_info.get('username', '用户')
        st.markdown(
            f'<div style="font-size:0.82rem;color:#64748b;padding:4px 0;">'
            f'👤 <strong style="color:#94a3b8;">{username}</strong>'
            f'</div>',
            unsafe_allow_html=True
        )
        if st.button("🚪 登出", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()
