"""
📊 数据完整性监控页 — SSM Data Health Dashboard
功能:
  - 各股票 K 线数据最新日期 & 缺口识别
  - Redis / PostgreSQL / Tushare 连接健康检查
  - Celery 任务最近执行情况
  - 手动触发同步按钮
"""
import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta


def render(L):
    st.markdown("""
    <style>
    .health-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(56, 189, 248, 0.15);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .health-title {
        font-size: 0.78rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 4px;
    }
    .health-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .status-ok   { color: #10b981; }
    .status-warn { color: #f59e0b; }
    .status-err  { color: #ef4444; }
    .data-stale  { background: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.3); }
    .data-fresh  { background: rgba(16, 185, 129, 0.06); border-color: rgba(16, 185, 129, 0.2); }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("## 🩺 数据完整性监控")
    st.caption("实时诊断数据管道各节点的健康状态 — 识别陈旧数据与连接异常")

    # ── Section 1: 基础设施连接状态 ──────────────────────────
    st.markdown("### 🔌 基础设施连接")

    infra_cols = st.columns(4)

    # 1a. Redis
    with infra_cols[0]:
        redis_ok, redis_info = _check_redis()
        cls = "status-ok" if redis_ok else "status-err"
        icon = "✅" if redis_ok else "❌"
        st.html(f"""
        <div class="health-card">
            <div class="health-title">Redis L1 Cache</div>
            <div class="health-value"><span class="{cls}">{icon} {'在线' if redis_ok else '离线'}</span></div>
            <div style="font-size:0.72rem; color:#64748b; margin-top:4px;">{redis_info}</div>
        </div>""")

    # 1b. PostgreSQL
    with infra_cols[1]:
        pg_ok, pg_info = _check_postgres()
        cls = "status-ok" if pg_ok else "status-err"
        icon = "✅" if pg_ok else "❌"
        st.html(f"""
        <div class="health-card">
            <div class="health-title">PostgreSQL</div>
            <div class="health-value"><span class="{cls}">{icon} {'在线' if pg_ok else '离线'}</span></div>
            <div style="font-size:0.72rem; color:#64748b; margin-top:4px;">{pg_info}</div>
        </div>""")

    # 1c. Tushare
    with infra_cols[2]:
        ts_ok, ts_info = _check_tushare()
        cls = "status-ok" if ts_ok else "status-warn"
        icon = "✅" if ts_ok else "⚠️"
        st.html(f"""
        <div class="health-card">
            <div class="health-title">Tushare Pro</div>
            <div class="health-value"><span class="{cls}">{icon} {'可用' if ts_ok else '受限'}</span></div>
            <div style="font-size:0.72rem; color:#64748b; margin-top:4px;">{ts_info}</div>
        </div>""")

    # 1d. 文件缓存
    with infra_cols[3]:
        fc_count, fc_size_mb = _check_file_cache()
        st.html(f"""
        <div class="health-card">
            <div class="health-title">文件缓存 L2</div>
            <div class="health-value" style="color:#38bdf8;">📁 {fc_count} 文件</div>
            <div style="font-size:0.72rem; color:#64748b; margin-top:4px;">{fc_size_mb:.1f} MB 占用</div>
        </div>""")

    st.markdown("---")

    # ── Section 2: K 线数据新鲜度扫描 ──────────────────────
    st.markdown("### 📅 K 线数据新鲜度")

    col_left, col_right = st.columns([3, 1])
    with col_right:
        if st.button("🔄 刷新扫描", use_container_width=True, key="dh_refresh"):
            st.cache_data.clear()
            st.rerun()
        if st.button("🧹 清理过期缓存", use_container_width=True, key="dh_cleanup"):
            from core.file_cache import cleanup_old_cache
            removed = cleanup_old_cache(max_age_days=7)
            st.toast(f"✅ 已清理 {removed} 个过期缓存文件", icon="🧹")

    with col_left:
        with st.spinner("扫描 K 线数据新鲜度..."):
            freshness_df = _scan_kline_freshness()

        if freshness_df.empty:
            st.info("📭 数据库中暂无 K 线数据，请先同步")
        else:
            today = datetime.now().strftime('%Y%m%d')
            stale_mask = freshness_df['最新交易日'] < (
                datetime.now() - timedelta(days=3)
            ).strftime('%Y%m%d')
            stale_count = stale_mask.sum()
            fresh_count = len(freshness_df) - stale_count

            metric_c1, metric_c2, metric_c3 = st.columns(3)
            metric_c1.metric("覆盖股票数", len(freshness_df))
            metric_c2.metric("✅ 数据新鲜", fresh_count)
            metric_c3.metric("⚠️ 数据陈旧(>3天)", stale_count,
                             delta=f"-{stale_count}" if stale_count else None,
                             delta_color="inverse")

            freshness_df['状态'] = freshness_df['最新交易日'].apply(
                lambda d: "🟢 新鲜" if d >= (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')
                else ("🟡 轻微滞后" if d >= (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
                else "🔴 严重滞后")
            )

            # 按状态排序（滞后的排前面）
            freshness_df = freshness_df.sort_values('最新交易日')

            st.dataframe(
                freshness_df,
                use_container_width=True,
                column_config={
                    "股票代码":   st.column_config.TextColumn("代码", width=80),
                    "股票名称":   st.column_config.TextColumn("名称", width=100),
                    "最新交易日": st.column_config.TextColumn("最新日期", width=100),
                    "K线条数":   st.column_config.NumberColumn("数据量", format="%d 条", width=80),
                    "状态":       st.column_config.TextColumn("状态", width=100),
                },
                height=400,
            )

    st.markdown("---")

    # ── Section 3: 文件缓存详情 ──────────────────────────────
    st.markdown("### 📂 文件缓存详情")

    cache_detail_df = _scan_file_cache_detail()
    if cache_detail_df.empty:
        st.info("没有文件缓存")
    else:
        old_mask = cache_detail_df['修改时间'] < (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M')
        st.caption(f"共 {len(cache_detail_df)} 个缓存文件，其中 {old_mask.sum()} 个超过 2 天")
        st.dataframe(
            cache_detail_df,
            use_container_width=True,
            column_config={
                "文件名":   st.column_config.TextColumn("文件名", width=250),
                "大小(KB)": st.column_config.NumberColumn("大小", format="%.1f KB"),
                "修改时间": st.column_config.TextColumn("最后写入", width=150),
            },
            height=250,
        )

    st.markdown("---")

    # ── Section 4: Redis 缓存 Key 摘要 ───────────────────────
    st.markdown("### 🔑 Redis Key 分布")
    _render_redis_key_summary()

    # ── Section 5: 手动触发同步 ─────────────────────────────
    st.markdown("---")
    st.markdown("### ⚡ 手动触发同步任务")
    _render_manual_sync_buttons()


# ─── 检测函数 ────────────────────────────────────────────────

def _check_redis():
    try:
        from core.cache import RedisCache
        cache = RedisCache()
        if cache.ping():
            # 获取 key 数量
            count = cache.client.dbsize() if cache.client else 0
            return True, f"{count} keys 已缓存"
        return False, "无法 PING"
    except Exception as e:
        return False, str(e)[:50]


def _check_postgres():
    try:
        from core.database import get_engine
        engine = get_engine()
        if engine is None:
            return False, "Engine 未初始化"
        with engine.connect() as conn:
            result = conn.execute(__import__('sqlalchemy').text("SELECT version()")).fetchone()
            ver = result[0].split(' ')[1] if result else "?"
            return True, f"PG {ver}"
    except Exception as e:
        return False, str(e)[:60]


def _check_tushare():
    try:
        from core.tushare_client import get_ts_client
        ts = get_ts_client()
        if ts.available:
            return True, f"积分: {getattr(ts, '_points', 'N/A')}"
        return False, "Token 无效或积分不足"
    except Exception as e:
        return False, str(e)[:50]


def _check_file_cache():
    try:
        import glob
        from core.file_cache import CACHE_DIR
        files = glob.glob(os.path.join(CACHE_DIR, "*.json"))
        total_bytes = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        return len(files), total_bytes / (1024 * 1024)
    except Exception:
        return 0, 0.0


@st.cache_data(ttl=60, show_spinner=False)
def _scan_kline_freshness() -> pd.DataFrame:
    """从 PG kline_daily 表扫描每支股票的最新数据日期"""
    try:
        from core.database import get_engine
        import sqlalchemy
        engine = get_engine()
        if engine is None:
            return pd.DataFrame()
        sql = sqlalchemy.text("""
            SELECT
                k.ts_code AS "股票代码",
                COALESCE(s.name, k.ts_code) AS "股票名称",
                MAX(k.trade_date) AS "最新交易日",
                COUNT(*) AS "K线条数"
            FROM kline_daily k
            LEFT JOIN stock_basic s ON s.ts_code = k.ts_code
            GROUP BY k.ts_code, s.name
            ORDER BY MAX(k.trade_date) ASC
        """)
        with engine.connect() as conn:
            df = pd.read_sql(sql, conn)
        return df
    except Exception as e:
        return pd.DataFrame()


@st.cache_data(ttl=30, show_spinner=False)
def _scan_file_cache_detail() -> pd.DataFrame:
    try:
        import glob
        from core.file_cache import CACHE_DIR
        rows = []
        for f in sorted(glob.glob(os.path.join(CACHE_DIR, "*.json")), key=os.path.getmtime, reverse=True):
            mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M')
            size_kb = os.path.getsize(f) / 1024
            rows.append({
                "文件名": os.path.basename(f),
                "大小(KB)": round(size_kb, 1),
                "修改时间": mtime,
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def _render_redis_key_summary():
    try:
        from core.cache import RedisCache
        cache = RedisCache()
        if not cache.ping():
            st.info("Redis 离线，无法查看 Key 分布")
            return

        patterns = {
            "stock:*": "股票行情",
            "kline:*": "K线缓存",
            "market:*": "市场概览",
            "snapshot:*": "估值快照",
            "ai:response:*": "AI 回应",
            "session:*": "用户会话",
            "status:sync:*": "同步状态",
        }

        rows = []
        for pat, label in patterns.items():
            try:
                keys = cache.client.keys(pat)
                rows.append({"类型": label, "Key前缀": pat, "数量": len(keys)})
            except Exception:
                rows.append({"类型": label, "Key前缀": pat, "数量": "?"})

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True,
                     column_config={
                         "类型": st.column_config.TextColumn(width=120),
                         "Key前缀": st.column_config.TextColumn(width=160),
                         "数量": st.column_config.NumberColumn(width=80),
                     }, height=300)
    except Exception as e:
        st.warning(f"Redis Key 扫描失败: {e}")


def _render_manual_sync_buttons():
    btn_cols = st.columns(4)

    with btn_cols[0]:
        if st.button("📈 同步全市场估值", use_container_width=True, key="dh_sync_val"):
            try:
                from tasks.market_data import sync_market_valuation
                task = sync_market_valuation.delay()
                st.toast(f"✅ 估值同步任务已提交 [{task.id[:8]}]", icon="📈")
            except Exception as e:
                st.error(f"提交失败: {e}")

    with btn_cols[1]:
        if st.button("🏪 预热市场快照", use_container_width=True, key="dh_prewarm"):
            try:
                from tasks.market_data import prewarm_market_snapshot
                task = prewarm_market_snapshot.delay()
                st.toast(f"✅ 预热任务已提交 [{task.id[:8]}]", icon="🏪")
            except Exception as e:
                st.error(f"提交失败: {e}")

    with btn_cols[2]:
        if st.button("📋 生成今日研报", use_container_width=True, key="dh_daily_report"):
            try:
                from tasks.reports import generate_daily_report
                task = generate_daily_report.delay()
                st.toast(f"✅ 日报任务已提交 [{task.id[:8]}]", icon="📋")
            except Exception as e:
                st.error(f"提交失败: {e}")

    with btn_cols[3]:
        if st.button("📊 生成周报", use_container_width=True, key="dh_weekly_report"):
            try:
                from tasks.reports import generate_weekly_report
                task = generate_weekly_report.delay()
                st.toast(f"✅ 周报任务已提交 [{task.id[:8]}]", icon="📊")
            except Exception as e:
                st.error(f"提交失败: {e}")

    # 自定义股票同步
    st.markdown("#### 🎯 单股强制同步")
    sync_col1, sync_col2 = st.columns([2, 1])
    with sync_col1:
        target_code = st.text_input("输入股票代码", placeholder="如: 601318", key="dh_sync_code")
    with sync_col2:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 强制同步", use_container_width=True, key="dh_force_sync"):
            if target_code:
                try:
                    from tasks.market_data import sync_historical_data
                    task = sync_historical_data.delay(target_code.strip(), years=1)
                    st.toast(f"✅ {target_code} 同步任务已提交", icon="🔄")
                except Exception as e:
                    st.error(f"提交失败: {e}")
            else:
                st.warning("请输入股票代码")
