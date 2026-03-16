"""
⚙️ 设置页面
"""
import streamlit as st

# 条件导入
try:
    from core.cache import RedisCache
    redis_cache = RedisCache()
except ImportError:
    redis_cache = None


def render(L, new_modules_available):
    st.header("⚙️ 设置")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("外观设置")
        theme = st.selectbox("主题", ["dark", "light"],
                            index=0 if st.session_state['theme'] == 'dark' else 1)
        if theme != st.session_state['theme']:
            st.session_state['theme'] = theme
            st.rerun()

    with col2:
        st.subheader("系统信息")
        st.write("版本: v7.0 Quantum Pro")
        st.write(f"新模块状态: {'✅ 已加载' if new_modules_available else '⚠️ 部分功能不可用'}")

        if new_modules_available and redis_cache:
            st.write(f"Redis缓存: {'✅ 已连接' if redis_cache.ping() else '⚠️ 未连接'}")
