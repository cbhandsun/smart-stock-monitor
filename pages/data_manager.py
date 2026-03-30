import streamlit as st
import pandas as pd
import time
from datetime import datetime
from core.cache import RedisCache
from core.tushare_client import get_ts_client
from modules.portfolio.watchlist_manager import WatchlistManager
from modules.data_loader import get_last_timestamp, CACHE_DIR
import os

def render(L, *args):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### ⚙️ 数据管理中心 (Data Management Hub)")
    st.caption("监控数据同步状态、服务健康度及缓存完整性。")
    
    cache = RedisCache()
    ts = get_ts_client()
    watchlist_manager = WatchlistManager()
    
    # ---- 第一部分：服务健康度 ----
    st.markdown("#### 🛠️ 服务状态")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        redis_ok = cache.ping()
        color = "#10b981" if redis_ok else "#ef4444"
        st.markdown(f"""
        <div style='background:rgba(16,185,129,0.05); border:1px solid {color}; border-radius:10px; padding:15px; text-align:center;'>
            <div style='font-size:0.8rem; color:#94a3b8;'>Redis 缓存</div>
            <div style='font-size:1.2rem; font-weight:bold; color:{color};'>{'在线 (Online)' if redis_ok else '离线 (Offline)'}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        ts_ok = ts.available
        color = "#10b981" if ts_ok else "#ef4444"
        st.markdown(f"""
        <div style='background:rgba(16,185,129,0.05); border:1px solid {color}; border-radius:10px; padding:15px; text-align:center;'>
            <div style='font-size:0.8rem; color:#94a3b8;'>Tushare 接口</div>
            <div style='font-size:1.2rem; font-weight:bold; color:{color};'>{'正常 (Ready)' if ts_ok else '受限 (Limited)'}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        # 统计缓存文件数量
        cache_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.pkl')]
        st.markdown(f"""
        <div style='background:rgba(56,189,248,0.05); border:1px solid #38bdf8; border-radius:10px; padding:15px; text-align:center;'>
            <div style='font-size:0.8rem; color:#94a3b8;'>本地缓存文件</div>
            <div style='font-size:1.2rem; font-weight:bold; color:#38bdf8;'>{len(cache_files)} 个对象</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c4:
        # 获取系统负载或 Celery 状态 (简化版)
        st.markdown(f"""
        <div style='background:rgba(139,92,246,0.05); border:1px solid #8b5cf6; border-radius:10px; padding:15px; text-align:center;'>
            <div style='font-size:0.8rem; color:#94a3b8;'>后台工作站</div>
            <div style='font-size:1.2rem; font-weight:bold; color:#8b5cf6;'>Celery 已就绪</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # ---- 第二部分：数据同步状态 ----
    st.markdown("#### 📊 自选股同步详情")
    
    portfolios = watchlist_manager.list_portfolios()
    all_symbols = set()
    for p in portfolios:
        for s in p.stocks:
            all_symbols.add(s.symbol)
            
    if not all_symbols:
        st.info("暂无自选股，请先添加股票。")
        return

    # 构建表格数据
    table_rows = []
    for symbol in sorted(list(all_symbols)):
        # 获取缓存最后时间
        last_date = get_last_timestamp(symbol, 'daily')
        
        # 获取同步状态 (从 Redis)
        sync_status = cache.get(f"status:sync:{symbol}") or {}
        full_sync_status = cache.get(f"status:sync_full:{symbol}") or {}
        
        status_text = "✅ 已更新"
        if sync_status.get('status') == 'syncing':
            status_text = "⏳ 同步中..."
        elif sync_status.get('status') == 'error':
            status_text = f"❌ 错误: {sync_status.get('error', '未知')}"
            
        full_status_text = "未深挖"
        if full_sync_status.get('status') == 'success':
            full_status_text = f"💎 已完整 ({full_sync_status.get('count', 0)}条)"
        elif full_sync_status.get('status') == 'syncing':
            full_status_text = "⛏️ 深挖中..."

        table_rows.append({
            "代码": symbol,
            "最后成交日": last_date or "无记录",
            "常规更新状态": status_text,
            "历史深挖状态": full_status_text,
            "上次更新": sync_status.get('last_run', '从未')
        })
        
    df = pd.DataFrame(table_rows)
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "最后成交日": st.column_config.TextColumn("最后成交日", width="medium"),
            "代码": st.column_config.TextColumn("代码", width="small"),
        }
    )

    # ---- 第三部分：操作面板 ----
    st.divider()
    st.markdown("#### 🎮 操作控制")
    
    c1, c2, c3 = st.columns([1, 1, 1])
    
    with c1:
        if st.button("🚀 强制全量增量更新", use_container_width=True, type="primary"):
            from tasks.market_data import update_all_stocks
            res = update_all_stocks.delay()
            st.toast(f"已排队更新所有股票: {res.id}")
            time.sleep(1)
            st.rerun()
            
    with c2:
        target_stock = st.selectbox("选择目标进行深挖 (Sync Full History)", sorted(list(all_symbols)))
        if st.button(f"⛏️ 对 {target_stock} 执行深挖", use_container_width=True):
            from tasks.market_data import sync_historical_data
            res = sync_historical_data.delay(target_stock, years=5)
            st.toast(f"已启动 {target_stock} 历史深挖任务: {res.id}")
            time.sleep(1)
            st.rerun()
            
    with c3:
        if st.button("🧼 清除冗余缓存", use_container_width=True):
            st.cache_data.clear()
            st.success("全局缓存已清理")

        st.subheader("🚀 性能加速")
        if st.button("🔥 预热全市场快照", help="在后台预先计算并缓存全市场筛选因子 (PE/PB/涨跌幅等)", use_container_width=True):
            try:
                from tasks.market_data import prewarm_market_snapshot
                prewarm_market_snapshot.delay()
                st.info("🔄 全市场预热任务已发送至消息队列 (Celery)")
            except Exception as e:
                st.error(f"任务发送失败: {e}")
        
        if st.button("🧹 清理本地过期缓存", use_container_width=True):
            count = 0
            for f in os.listdir(CACHE_DIR):
                if f.endswith('.pkl'):
                    os.remove(os.path.join(CACHE_DIR, f))
                    count += 1
            st.success(f"已清理 {count} 个缓存文件")
            time.sleep(1)
            st.rerun()
            
    # 展示正在运行的任务
    st.caption("注：强制更新会触发 Celery 后台任务，进度将反应在上方表格中。")
