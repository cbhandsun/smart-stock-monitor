"""
📡 市场信号流页面 - V7.0
工作流: 策略选股 → 点击分析 → 决策后加入自选 → 自选跟盘
"""
import streamlit as st
import pandas as pd

from main import (
    get_market_overview, find_value_stocks,
    find_momentum_stocks, find_growth_stocks,
)
from pages import load_watchlist, save_watchlist


def render(L, my_stocks, name_map):
    """渲染市场页面"""

    # ========== 页面头部 ==========
    hdr_col, refresh_col = st.columns([8, 1])
    with hdr_col:
        st.markdown(f"## 📡 {L.get('market_discovery', '实时信号流')}")
    with refresh_col:
        if st.button("🔄", key="refresh_market", use_container_width=True, help="刷新行情"):
            st.cache_data.clear()
            st.toast("市场行情已刷新", icon="📈")
            st.rerun()

    # ========== 大盘指数概览 ==========
    ov = get_market_overview()
    if not ov.empty:
        cols = st.columns(len(ov))
        for i, r in enumerate(ov.itertuples()):
            delta_color = "normal" if r.涨跌幅 >= 0 else "inverse"
            cols[i].metric(r.名称, f"{r.最新价:,.1f}", f"{r.涨跌幅:+.2f}%", delta_color=delta_color)

        avg_drop = ov['涨跌幅'].mean()
        if avg_drop <= -2.0:
            st.error(f"**⚠️ 智能风控警报：** 三大指数平均跌幅 `{avg_drop:.2f}%`。"
                     f"建议多头仓位降至 30% 以下，关注黄金 ETF (`518880`) 等避险资产。")
        elif avg_drop <= -1.0:
            st.warning(f"**🛡️ 风控提示：** 大盘平均跌幅 `{avg_drop:.2f}%`。建议停止加仓，清理弱势标的。")

    st.divider()

    # ========== 三栏工作流 ==========
    # 1️⃣ 策略选股  →  2️⃣ 决策分析  →  3️⃣ 自选跟盘
    tab_screen, tab_analyze, tab_track = st.tabs([
        "1️⃣ 策略选股", "2️⃣ 决策分析", "3️⃣ 自选跟盘"
    ])

    # ==========================================
    #  Tab 1: 策略选股
    # ==========================================
    with tab_screen:
        if 'capture_strat' not in st.session_state:
            st.session_state['capture_strat'] = 'Value'

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            if st.button(L.get('strategy_value', '💎 价值发现'), use_container_width=True,
                        type="primary" if st.session_state['capture_strat'] == 'Value' else "secondary"):
                st.session_state['capture_strat'] = 'Value'
                st.rerun()
        with sc2:
            if st.button(L.get('strategy_momentum', '🔥 动量追击'), use_container_width=True,
                        type="primary" if st.session_state['capture_strat'] == 'Momentum' else "secondary"):
                st.session_state['capture_strat'] = 'Momentum'
                st.rerun()
        with sc3:
            if st.button(L.get('strategy_growth', '🌟 成长之星'), use_container_width=True,
                        type="primary" if st.session_state['capture_strat'] == 'Growth' else "secondary"):
                st.session_state['capture_strat'] = 'Growth'
                st.rerun()

        # 策略说明
        strat_desc = {
            'Value': ('💎', '价值发现', '低市盈率 + 低市净率，基本面被低估的优质标的', '#3b82f6'),
            'Momentum': ('🔥', '动量追击', '涨幅 1%~9%，量价齐升的趋势股', '#10b981'),
            'Growth': ('🌟', '成长之星', '高成交额活跃股，机构资金关注的标的', '#f59e0b'),
        }
        icon, title, desc, color = strat_desc[st.session_state['capture_strat']]
        st.markdown(f"""
<div style="background: linear-gradient(135deg, rgba(30,41,59,0.5), rgba(15,23,42,0.6));
     border-left: 4px solid {color}; border-radius: 12px; padding: 14px 18px; margin: 8px 0;">
    <span style="font-size: 0.85rem; color: #94a3b8;">当前策略</span>
    <span style="font-size: 1.1rem; font-weight: 600; color: {color}; margin-left: 8px;">{icon} {title}</span>
    <span style="font-size: 0.85rem; color: #cbd5e1; margin-left: 12px;">{desc}</span>
</div>
""", unsafe_allow_html=True)

        # 数据表格
        with st.spinner("扫描市场中..."):
            if st.session_state['capture_strat'] == 'Value':
                df = find_value_stocks()
            elif st.session_state['capture_strat'] == 'Momentum':
                df = find_momentum_stocks()
            else:
                df = find_growth_stocks()

        if not df.empty:
            # 数据表格展示
            col_cfg = {
                "代码": st.column_config.TextColumn("代码", width="small"),
                "名称": st.column_config.TextColumn("名称", width="medium"),
                "最新价": st.column_config.NumberColumn("最新价", format="¥ %.2f"),
                "涨跌幅": st.column_config.NumberColumn("涨跌幅%", format="%.2f%%"),
            }
            if "PE" in df.columns:
                col_cfg["PE"] = st.column_config.ProgressColumn("PE", format="%.1f", min_value=0, max_value=50)
                col_cfg["PB"] = st.column_config.ProgressColumn("PB", format="%.2f", min_value=0, max_value=5)
            elif "成交额" in df.columns:
                col_cfg["成交额"] = st.column_config.NumberColumn("成交额", format="¥ %d")

            st.dataframe(df, hide_index=True, use_container_width=True, column_config=col_cfg)

            # 选股 → 分析 快捷操作
            st.markdown("---")
            stock_options = [f"{row['代码']} {row['名称']}" for _, row in df.iterrows()]
            pick_col, btn_col = st.columns([3, 1])
            with pick_col:
                picked = st.selectbox("🎯 选择标的进行深度分析", stock_options, key="strategy_pick", label_visibility="visible")
            with btn_col:
                st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)  # 对齐
                if st.button("📊 深度分析", key="go_analyze", type="primary", use_container_width=True):
                    picked_code = picked.split(" ")[0]
                    picked_name = picked.split(" ", 1)[1] if " " in picked else ""
                    st.session_state['selected_stock'] = picked_code
                    st.toast(f"已选择 {picked_name} ({picked_code})，请切换到「2️⃣ 决策分析」标签查看", icon="🔬")
        else:
            st.info("暂无符合条件的股票")

    # ==========================================
    #  Tab 2: 决策分析 (DNA Analyzer)
    # ==========================================
    with tab_analyze:
        from components.dna_analyzer import render_dna_analyzer

        # 显示当前分析的标的
        current = st.session_state.get('selected_stock', '601318')
        cur_name = name_map.get(current, '')

        # 快捷操作栏
        info_col, add_col = st.columns([5, 1])
        with info_col:
            in_watchlist = current in my_stocks
            status = "⭐ 已在自选" if in_watchlist else "📋 未加入自选"
            st.markdown(f"""
<div style="background: rgba(30,41,59,0.4); border-radius: 10px; padding: 10px 16px; 
     display: flex; align-items: center; gap: 12px;">
    <span style="font-size: 1.1rem; font-weight: 600; color: #f1f5f9;">🎯 {cur_name} ({current})</span>
    <span style="font-size: 0.8rem; color: {'#f59e0b' if in_watchlist else '#64748b'}; 
          background: {'rgba(245,158,11,0.1)' if in_watchlist else 'rgba(100,116,139,0.1)'}; 
          padding: 2px 10px; border-radius: 20px;">{status}</span>
</div>
""", unsafe_allow_html=True)

        with add_col:
            if current not in my_stocks:
                if st.button("📥 加入自选", key="add_to_watchlist_analyze", type="primary", use_container_width=True):
                    my_stocks.append(current)
                    save_watchlist(my_stocks)
                    st.toast(f"✅ {cur_name} 已加入自选", icon="⭐")
                    st.rerun()
            else:
                if st.button("❌ 移出自选", key="remove_from_watchlist_analyze", use_container_width=True):
                    my_stocks.remove(current)
                    save_watchlist(my_stocks)
                    st.toast(f"{cur_name} 已移出自选", icon="🗑️")
                    st.rerun()

        # DNA Analyzer 组件
        render_dna_analyzer(L, my_stocks, name_map)

    # ==========================================
    #  Tab 3: 自选跟盘
    # ==========================================
    with tab_track:
        if not my_stocks:
            st.info("📋 还没有自选股，请先在「策略选股」中挑选标的，分析后加入自选。")
        else:
            st.markdown(f"**⭐ 我的自选** — 共 {len(my_stocks)} 只")

            # 批量获取实时行情
            from main import get_stock_names_batch
            try:
                import requests
                sina_codes = [f"{'s_sh' if c.startswith('6') else 's_sz'}{c}" for c in my_stocks]
                url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
                headers = {'Referer': 'https://finance.sina.com.cn/'}
                r = requests.get(url, headers=headers, timeout=5)
                quotes = {}
                for line in r.text.strip().split(';'):
                    if '="' in line:
                        key = line.split('=')[0].split('_')[-1]
                        val = line.split('="')[1].strip('"')
                        parts = val.split(',')
                        if len(parts) > 3:
                            quotes[key] = {
                                'name': parts[0],
                                'price': float(parts[1]),
                                'change': float(parts[3])
                            }
            except Exception:
                quotes = {}

            # 列表渲染
            for s in my_stocks:
                q = None
                for key, val in quotes.items():
                    if s in key:
                        q = val
                        break

                s_name = q['name'] if q else name_map.get(s, '')
                s_price = q['price'] if q else 0
                s_change = q['change'] if q else 0
                change_color = "#ef4444" if s_change >= 0 else "#10b981"
                change_icon = "▲" if s_change >= 0 else "▼"

                col_stock, col_go, col_del = st.columns([5, 1, 1])
                with col_stock:
                    st.markdown(f"""
<div style="background: rgba(30,41,59,0.3); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px;
     padding: 12px 16px; display: flex; align-items: center; justify-content: space-between;">
    <div>
        <span style="font-weight: 600; color: #f1f5f9;">{s_name}</span>
        <span style="color: #64748b; font-size: 0.8rem; margin-left: 8px;">{s}</span>
    </div>
    <div>
        <span style="font-weight: 600; color: #f1f5f9;">{'¥%.2f' % s_price if s_price > 0 else '--'}</span>
        <span style="color: {change_color}; margin-left: 8px;">{change_icon} {abs(s_change):.2f}%</span>
    </div>
</div>
""", unsafe_allow_html=True)

                with col_go:
                    if st.button("📊", key=f"track_analyze_{s}", use_container_width=True, help="切换到决策分析"):
                        st.session_state['selected_stock'] = s
                        st.toast(f"已选择 {s_name}，切换到「决策分析」标签", icon="🔬")

                with col_del:
                    if st.button("×", key=f"track_del_{s}", use_container_width=True, help="移出自选"):
                        my_stocks.remove(s)
                        save_watchlist(my_stocks)
                        st.toast(f"{s_name} 已移出自选", icon="🗑️")
                        st.rerun()
