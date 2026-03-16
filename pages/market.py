"""
📡 市场信号流页面 - V7.0
工作流: 策略选股 → 点击直接跳转分析 → 分析后加入自选
使用 session_state 驱动视图切换（替代 st.tabs，因为 tabs 无法程序化切换）
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

    # 初始化视图状态
    if 'market_view' not in st.session_state:
        st.session_state['market_view'] = 'strategy'  # strategy | analyze | track

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

    # ========== 视图导航条 ==========
    current_view = st.session_state['market_view']
    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if st.button("1️⃣ 策略选股", use_container_width=True,
                    type="primary" if current_view == 'strategy' else "secondary"):
            st.session_state['market_view'] = 'strategy'
            st.rerun()
    with nav2:
        if st.button("2️⃣ 决策分析", use_container_width=True,
                    type="primary" if current_view == 'analyze' else "secondary"):
            st.session_state['market_view'] = 'analyze'
            st.rerun()
    with nav3:
        if st.button("3️⃣ 自选跟盘", use_container_width=True,
                    type="primary" if current_view == 'track' else "secondary"):
            st.session_state['market_view'] = 'track'
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    #  视图 1: 策略选股
    # ==========================================
    if current_view == 'strategy':
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

        with st.spinner("扫描市场中..."):
            if st.session_state['capture_strat'] == 'Value':
                df = find_value_stocks()
            elif st.session_state['capture_strat'] == 'Momentum':
                df = find_momentum_stocks()
            else:
                df = find_growth_stocks()

        if not df.empty:
            st.caption("👇 选择一只股票，点击右侧「分析」直接跳转深度分析")

            # 渲染每只股票为一行，带分析按钮
            for idx, row in df.iterrows():
                code = str(row.get('代码', ''))
                stock_name = str(row.get('名称', ''))
                price = row.get('最新价', 0)
                change = row.get('涨跌幅', 0)

                change_color = "#ef4444" if change >= 0 else "#10b981"
                change_icon = "▲" if change >= 0 else "▼"

                extra = ""
                if 'PE' in df.columns:
                    pe_val = row.get('PE', 0)
                    pb_val = row.get('PB', 0)
                    extra = f"PE {pe_val:.1f} · PB {pb_val:.2f}"
                elif '成交额' in df.columns:
                    amt = row.get('成交额', 0)
                    extra = f"成交 {amt/100000000:.1f}亿" if amt > 0 else ""

                row_col, btn_col = st.columns([6, 1])
                with row_col:
                    st.markdown(f"""
<div style="background: rgba(30,41,59,0.25); border: 1px solid rgba(255,255,255,0.05);
     border-radius: 10px; padding: 10px 16px; margin: 2px 0;
     display: flex; align-items: center; justify-content: space-between;">
    <div>
        <span style="font-weight: 600; color: #f1f5f9; font-size: 0.95rem;">{stock_name}</span>
        <span style="color: #64748b; font-size: 0.78rem; margin-left: 6px;">{code}</span>
    </div>
    <div style="text-align: right;">
        <span style="font-weight: 600; color: #f1f5f9;">¥{price:.2f}</span>
        <span style="color: {change_color}; margin-left: 8px; font-size:0.85rem;">{change_icon}{abs(change):.2f}%</span>
        <span style="color: #64748b; font-size: 0.75rem; margin-left: 8px;">{extra}</span>
    </div>
</div>
""", unsafe_allow_html=True)

                with btn_col:
                    if st.button("📊 分析", key=f"analyze_{code}", use_container_width=True):
                        st.session_state['selected_stock'] = code
                        st.session_state['market_view'] = 'analyze'  # 直接跳转!
                        st.rerun()
        else:
            st.info("暂无符合条件的股票")

    # ==========================================
    #  视图 2: 决策分析
    # ==========================================
    elif current_view == 'analyze':
        from components.dna_analyzer import render_dna_analyzer

        current = st.session_state.get('selected_stock', '601318')
        cur_name = name_map.get(current, '')

        # 标的信息 + 加入自选
        info_col, back_col, add_col = st.columns([4, 1, 1])
        with info_col:
            in_watchlist = current in my_stocks
            status = "⭐ 已在自选" if in_watchlist else ""
            st.markdown(f"""
<div style="background: rgba(30,41,59,0.4); border-radius: 10px; padding: 10px 16px;
     display: flex; align-items: center; gap: 12px;">
    <span style="font-size: 1.1rem; font-weight: 600; color: #f1f5f9;">🎯 {cur_name} ({current})</span>
    <span style="font-size: 0.8rem; color: #f59e0b; background: rgba(245,158,11,0.1);
          padding: 2px 10px; border-radius: 20px;">{status}</span>
</div>
""", unsafe_allow_html=True)

        with back_col:
            if st.button("◀ 返回选股", key="back_to_strategy", use_container_width=True):
                st.session_state['market_view'] = 'strategy'
                st.rerun()

        with add_col:
            if current not in my_stocks:
                if st.button("📥 加入自选", key="add_watchlist", type="primary", use_container_width=True):
                    my_stocks.append(current)
                    save_watchlist(my_stocks)
                    st.toast(f"✅ {cur_name} 已加入自选", icon="⭐")
                    st.rerun()
            else:
                if st.button("❌ 移出自选", key="remove_watchlist", use_container_width=True):
                    my_stocks.remove(current)
                    save_watchlist(my_stocks)
                    st.toast(f"{cur_name} 已移出自选", icon="🗑️")
                    st.rerun()

        render_dna_analyzer(L, my_stocks, name_map)

    # ==========================================
    #  视图 3: 自选跟盘
    # ==========================================
    elif current_view == 'track':
        if not my_stocks:
            st.info("📋 还没有自选股，请先在「策略选股」中挑选标的，分析后加入自选。")
        else:
            st.markdown(f"**⭐ 我的自选** — 共 {len(my_stocks)} 只")

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
                    if st.button("📊", key=f"track_{s}", use_container_width=True, help="分析此标的"):
                        st.session_state['selected_stock'] = s
                        st.session_state['market_view'] = 'analyze'
                        st.rerun()

                with col_del:
                    if st.button("×", key=f"del_{s}", use_container_width=True, help="移出自选"):
                        my_stocks.remove(s)
                        save_watchlist(my_stocks)
                        st.toast(f"{s_name} 已移出自选", icon="🗑️")
                        st.rerun()
