"""
分析视图 & 跟盘视图 — market 子包
_render_analyze_view: DNA 深度分析 + 上/下一只导航
_render_track_view: 自选股跟盘网格
"""
import streamlit as st
import requests


def _render_analyze_view(L, my_stocks, name_map):
    """决策分析视图 — 紧凑导航"""
    from components.dna_analyzer import render_dna_analyzer
    from pages import save_watchlist

    current = st.session_state.get('selected_stock', '601318')
    cur_name = name_map.get(current, '')
    strat_list = st.session_state.get('_strat_list', [])
    in_watchlist = current in my_stocks

    if st.button("⬅️ 返回策略列表", key="back_to_strat"):
        st.session_state['market_view'] = '📋 策略选股'
        st.rerun()

    if strat_list and current in strat_list:
        cur_idx = strat_list.index(current)
        c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
        with c1:
            if cur_idx > 0:
                if st.button("◀ 上一只", key="prev_stock", use_container_width=True):
                    st.session_state['selected_stock'] = strat_list[cur_idx - 1]
                    st.rerun()
        with c2:
            st.caption(f"🎯 {cur_name} ({current}) — {cur_idx + 1}/{len(strat_list)}")
        with c3:
            if not in_watchlist:
                if st.button("⭐ 加自选", key="add_wl", type="primary", use_container_width=True):
                    my_stocks.append(current)
                    save_watchlist(my_stocks)
                    st.toast(f"✅ {cur_name} 已加入自选", icon="⭐")
                    st.rerun()
            else:
                if st.button("❌ 移出自选", key="rm_wl", use_container_width=True):
                    my_stocks.remove(current)
                    save_watchlist(my_stocks)
                    st.toast(f"{cur_name} 已移出自选", icon="🗑️")
                    st.rerun()
        with c4:
            if cur_idx < len(strat_list) - 1:
                if st.button("下一只 ▶", key="next_stock", use_container_width=True):
                    st.session_state['selected_stock'] = strat_list[cur_idx + 1]
                    st.rerun()
    else:
        _, wl_col, _ = st.columns([3, 2, 3])
        with wl_col:
            if not in_watchlist:
                if st.button("⭐ 加自选", key="add_wl", type="primary", use_container_width=True):
                    my_stocks.append(current)
                    save_watchlist(my_stocks)
                    st.toast(f"✅ {cur_name} 已加入自选", icon="⭐")
                    st.rerun()
            else:
                if st.button("❌ 移出自选", key="rm_wl", use_container_width=True):
                    my_stocks.remove(current)
                    save_watchlist(my_stocks)
                    st.toast(f"{cur_name} 已移出自选", icon="🗑️")
                    st.rerun()

    render_dna_analyzer(L, my_stocks, name_map)


def _render_track_view(L, my_stocks, name_map):
    """自选跟盘视图 — 复用统一行渲染"""
    from pages.market._card import _render_stock_card
    from pages import save_watchlist

    # 去重
    seen = set()
    deduped = []
    for s in my_stocks:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    if len(deduped) != len(my_stocks):
        my_stocks.clear()
        my_stocks.extend(deduped)
        save_watchlist(my_stocks)

    if not my_stocks:
        st.markdown(
            '<div style="text-align:center;padding:40px 20px;color:#64748b;">'
            '<div style="font-size:2.5rem;margin-bottom:12px;">📋</div>'
            '<div style="font-size:1rem;font-weight:600;color:#94a3b8;margin-bottom:6px;">还没有自选股</div>'
            '<div style="font-size:0.82rem;">在「📋 选股」中挑选标的，点击 ⭐ 即可加入自选</div>'
            '</div>',
            unsafe_allow_html=True
        )
        return

    sort_col, count_col = st.columns([4, 1])
    with sort_col:
        sort_by = st.radio("排序", ["加入顺序", "涨幅↓", "涨幅↑"], horizontal=True,
                           label_visibility="collapsed", key="track_sort")
    with count_col:
        st.markdown(
            f'<div style="text-align:right; color:#64748b; padding:6px 0; font-size:0.85rem;">⭐ {len(my_stocks)} 只</div>',
            unsafe_allow_html=True
        )

    # 实时行情 via fetch_quotes_concurrent (带 L1/L2 缓存，秒开)
    with st.spinner("⚡ 获取自选股实时行情..."):
        from modules.data_loader import fetch_quotes_concurrent
        quotes = fetch_quotes_concurrent(my_stocks)

    stock_data = []
    for s in my_stocks:
        q = quotes.get(s, {})
        stock_data.append({
            'code':   s,
            'name':   name_map.get(s, s),
            'price':  q.get('price', 0.0),
            'change': q.get('change_pct', 0.0),
        })

    if sort_by == "涨幅↓":
        stock_data.sort(key=lambda x: x['change'], reverse=True)
    elif sort_by == "涨幅↑":
        stock_data.sort(key=lambda x: x['change'])

    cols_per_row = 3
    for i in range(0, len(stock_data), cols_per_row):
        cols = st.columns(cols_per_row)
        chunk = stock_data[i: i + cols_per_row]
        for idx_in_row, item in enumerate(chunk):
            with cols[idx_in_row]:
                _render_stock_card(
                    item['code'], item['name'], item['price'], item['change'],
                    my_stocks=my_stocks, btn_prefix=f"tk{i + idx_in_row}",
                    show_signals=True, show_watchlist_btn=False, show_remove_btn=True
                )
