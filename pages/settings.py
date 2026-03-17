"""
⚙️ 设置页面 — V2.0
三列面板 + 系统健康仪表盘 + 缓存管理
"""
import streamlit as st
import os
import glob

# 条件导入
try:
    from core.cache import RedisCache
    redis_cache = RedisCache()
except ImportError:
    redis_cache = None


def _get_cache_size():
    """统计文件缓存大小"""
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")
    if not os.path.exists(cache_dir):
        return 0, 0
    files = glob.glob(os.path.join(cache_dir, "*.json"))
    total_bytes = sum(os.path.getsize(f) for f in files if os.path.isfile(f))
    return len(files), total_bytes


def render(L, new_modules_available):
    from components.ui_components import page_header, info_card

    page_header("设置", icon="⚙️")

    col1, col2, col3 = st.columns(3)

    # ---- 列 1: 外观设置 ----
    with col1:
        st.markdown("##### 🎨 外观设置")
        theme = st.selectbox("主题", ["dark", "light"],
                            index=0 if st.session_state['theme'] == 'dark' else 1)
        if theme != st.session_state['theme']:
            st.session_state['theme'] = theme
            st.rerun()

        lang = st.session_state.get('lang', 'zh')
        st.markdown(f'''<div style="background:rgba(30,41,59,0.35); border:1px solid rgba(255,255,255,0.06);
            border-radius:10px; padding:10px 14px; margin-top:12px; font-size:0.82rem;">
            <div style="color:#94a3b8; margin-bottom:4px;">当前配置</div>
            <div style="color:#e2e8f0;">主题: <strong>{"🌙 深色" if theme == "dark" else "☀️ 浅色"}</strong></div>
            <div style="color:#e2e8f0;">语言: <strong>{"🇨🇳 中文" if lang == "zh" else "🇺🇸 English"}</strong></div>
        </div>''', unsafe_allow_html=True)

    # ---- 列 2: 系统信息 ----
    with col2:
        st.markdown("##### 📊 系统健康")

        # Redis 状态
        redis_ok = redis_cache and redis_cache.ping() if redis_cache else False
        redis_dot = "online" if redis_ok else "offline"
        redis_label = "已连接" if redis_ok else "未连接"

        # Tushare 状态
        ts_ok = False
        try:
            from core.tushare_client import get_ts_client
            ts = get_ts_client()
            ts_ok = ts.available
        except Exception:
            pass
        ts_dot = "online" if ts_ok else "offline"
        ts_label = "已连接" if ts_ok else "未连接"

        st.markdown(f'''<div style="background:rgba(30,41,59,0.35); border:1px solid rgba(255,255,255,0.06);
            border-radius:12px; padding:14px 18px; line-height:2.2;">
            <div style="font-size:0.85rem; color:#94a3b8; margin-bottom:6px;">服务状态</div>
            <div style="font-size:0.85rem; color:#e2e8f0;">
                <span class="health-dot {redis_dot}"></span> Redis 缓存: <strong>{redis_label}</strong>
            </div>
            <div style="font-size:0.85rem; color:#e2e8f0;">
                <span class="health-dot {ts_dot}"></span> Tushare Pro: <strong>{ts_label}</strong>
            </div>
            <div style="font-size:0.85rem; color:#e2e8f0;">
                <span class="health-dot {"online" if new_modules_available else "offline"}"></span>
                扩展模块: <strong>{"✅ 已加载" if new_modules_available else "⚠️ 部分不可用"}</strong>
            </div>
        </div>''', unsafe_allow_html=True)

        st.markdown(f'''<div style="background:rgba(30,41,59,0.35); border:1px solid rgba(255,255,255,0.06);
            border-radius:12px; padding:14px 18px; margin-top:10px;">
            <div style="font-size:0.85rem; color:#94a3b8;">版本信息</div>
            <div style="font-family:'Outfit',sans-serif; font-size:1.2rem; font-weight:700; color:#f1f5f9;">
                SSM Quantum Pro
            </div>
            <div style="font-size:0.78rem; color:#64748b;">v7.0 | AI 量化投研工作站</div>
        </div>''', unsafe_allow_html=True)

    # ---- 列 3: 缓存管理 ----
    with col3:
        st.markdown("##### 🗄️ 缓存管理")

        cache_files, cache_bytes = _get_cache_size()
        cache_mb = cache_bytes / (1024 * 1024) if cache_bytes > 0 else 0

        info_card("文件缓存", f"{cache_files} 个", subtitle=f"占用 {cache_mb:.1f} MB", icon="📦", color="#8b5cf6")

        st.markdown("")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑️ 清除文件缓存", use_container_width=True):
                cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")
                if os.path.exists(cache_dir):
                    for f in glob.glob(os.path.join(cache_dir, "*.json")):
                        try:
                            os.remove(f)
                        except OSError:
                            pass
                st.cache_data.clear()
                st.toast("文件缓存已清除", icon="🗑️")
                st.rerun()
        with c2:
            if st.button("🔄 清除 Redis", use_container_width=True):
                if redis_cache:
                    try:
                        redis_cache.flush()
                        st.toast("Redis 缓存已清除", icon="🔄")
                    except Exception as e:
                        st.toast(f"清除失败: {e}", icon="❌")
                else:
                    st.toast("Redis 未连接", icon="⚠️")
                st.rerun()
