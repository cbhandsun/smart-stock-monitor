"""
📡 市场信号流页面 - V8.0
改进: 紧凑列表 + 进度导航 + 前后切换 + Redis跟盘 + 搜索入口
"""
import streamlit as st
import pandas as pd

from main import (
    get_market_overview, find_value_stocks,
    find_momentum_stocks, find_growth_stocks,
    get_stock_names_batch,
)
from pages import load_watchlist, save_watchlist
from components.ui_components import stock_selector


def _progress_nav(current_view):
    """渲染步骤进度导航条 — 纯 CSS 视觉 + Streamlit 按钮"""
    steps = [
        ('strategy', '选股', '📋'),
        ('analyze', '分析', '📊'),
        ('track', '跟盘', '⭐'),
    ]
    items_html = ""
    for i, (key, label, icon) in enumerate(steps):
        is_active = key == current_view
        is_done = (
            (current_view == 'analyze' and key == 'strategy') or
            (current_view == 'track' and key in ('strategy', 'analyze'))
        )
        if is_active:
            dot_style = "background: #3b82f6; box-shadow: 0 0 10px rgba(59,130,246,0.5);"
            label_style = "color: #f1f5f9; font-weight: 700;"
        elif is_done:
            dot_style = "background: #10b981;"
            label_style = "color: #10b981;"
        else:
            dot_style = "background: #475569;"
            label_style = "color: #64748b;"

        items_html += f'''
        <div style="display: flex; flex-direction: column; align-items: center; z-index: 1;">
            <div style="width: 28px; height: 28px; border-radius: 50%; {dot_style}
                 display: flex; align-items: center; justify-content: center; font-size: 0.8rem;">
                {icon}
            </div>
            <span style="font-size: 0.75rem; margin-top: 3px; {label_style}">{label}</span>
        </div>
        '''
        if i < len(steps) - 1:
            line_color = "#10b981" if is_done else "#334155"
            items_html += f'<div style="flex: 1; height: 2px; background: {line_color}; margin: 14px 0 0; min-width: 60px;"></div>'

    st.markdown(f'''<div style="display: flex; align-items: flex-start; justify-content: center;
     padding: 6px 40px; margin: 0 0 4px;">{items_html}</div>''', unsafe_allow_html=True)

    # Streamlit 导航按钮
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("① 选股", use_container_width=True,
                     type="primary" if current_view == 'strategy' else "secondary",
                     key="nav_strategy"):
            st.session_state['market_view'] = 'strategy'
            st.rerun()
    with c2:
        if st.button("② 分析", use_container_width=True,
                     type="primary" if current_view == 'analyze' else "secondary",
                     key="nav_analyze"):
            st.session_state['market_view'] = 'analyze'
            st.rerun()
    with c3:
        if st.button("③ 跟盘", use_container_width=True,
                     type="primary" if current_view == 'track' else "secondary",
                     key="nav_track"):
            st.session_state['market_view'] = 'track'
            st.rerun()


def render(L, my_stocks, name_map):
    """渲染市场页面"""

    if 'market_view' not in st.session_state:
        st.session_state['market_view'] = 'strategy'

    # ========== 页面头部: 标题 + 搜索 + 刷新 ==========
    title_col, search_col, refresh_col = st.columns([4, 4, 1])
    with title_col:
        st.markdown(f"## 📡 {L.get('market_discovery', '实时信号流')}")
    with search_col:
        code = stock_selector(label="快速跳转分析", key_suffix="market_search")
        if code and code != st.session_state.get('_last_market_search', ''):
            st.session_state['_last_market_search'] = code
            st.session_state['selected_stock'] = code
            st.session_state['market_view'] = 'analyze'
            st.rerun()
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

    # ========== 步骤进度导航 ==========
    current_view = st.session_state['market_view']
    _progress_nav(current_view)

    # ==========================================
    #  视图 1: 策略选股
    # ==========================================
    if current_view == 'strategy':
        _render_strategy_view(L, my_stocks, name_map)

    # ==========================================
    #  视图 2: 决策分析
    # ==========================================
    elif current_view == 'analyze':
        _render_analyze_view(L, my_stocks, name_map)

    # ==========================================
    #  视图 3: 自选跟盘
    # ==========================================
    elif current_view == 'track':
        _render_track_view(L, my_stocks, name_map)


def _render_strategy_view(L, my_stocks, name_map):
    """策略选股视图 — 紧凑列表 + 快捷加自选"""

    if 'capture_strat' not in st.session_state:
        st.session_state['capture_strat'] = 'Value'

    # 策略选择按钮
    sc1, sc2, sc3 = st.columns(3)
    strat_map = {
        'Value': ('💎 价值发现', sc1),
        'Momentum': ('🔥 动量追击', sc2),
        'Growth': ('🌟 成长之星', sc3),
    }
    for key, (label, col) in strat_map.items():
        with col:
            if st.button(label, use_container_width=True,
                        type="primary" if st.session_state['capture_strat'] == key else "secondary",
                        key=f"strat_{key}"):
                st.session_state['capture_strat'] = key
                st.rerun()

    # 策略描述（紧凑）
    strat_info = {
        'Value': ('低 PE + 低 PB，被低估的优质标的', '#3b82f6'),
        'Momentum': ('涨幅 1%~9%，量价齐升的趋势股', '#10b981'),
        'Growth': ('高成交额活跃股，机构资金关注', '#f59e0b'),
    }
    desc, color = strat_info[st.session_state['capture_strat']]
    st.markdown(f'<div style="color: {color}; font-size: 0.82rem; padding: 4px 0 8px;">📌 {desc}</div>',
                unsafe_allow_html=True)

    # 获取数据
    with st.spinner("扫描市场中..."):
        if st.session_state['capture_strat'] == 'Value':
            df = find_value_stocks()
        elif st.session_state['capture_strat'] == 'Momentum':
            df = find_momentum_stocks()
        else:
            df = find_growth_stocks()

    if df.empty:
        st.info("暂无符合条件的股票")
        return

    # 保存策略列表到 session（供分析视图前后切换）
    st.session_state['_strat_list'] = df['代码'].tolist()

    # ---- 紧凑列表渲染 (每行单独渲染) ----
    for rank, (idx, row) in enumerate(df.iterrows(), 1):
        code = str(row.get('代码', ''))
        stock_name = str(row.get('名称', ''))
        try:
            price = float(row.get('最新价', 0))
        except (ValueError, TypeError):
            price = 0.0
        try:
            change = float(row.get('涨跌幅', 0))
        except (ValueError, TypeError):
            change = 0.0

        chg_color = "#ef4444" if change >= 0 else "#10b981"
        chg_icon = "▲" if change >= 0 else "▼"

        # 额外数据
        extra = ""
        if 'PE' in df.columns:
            try:
                pe = float(row.get('PE', 0) or 0)
                pb = float(row.get('PB', 0) or 0)
            except (ValueError, TypeError):
                pe, pb = 0, 0
            extra = f"PE {pe:.1f} · PB {pb:.2f}"
        elif '成交额' in df.columns:
            try:
                amt = float(row.get('成交额', 0) or 0)
            except (ValueError, TypeError):
                amt = 0
            if amt > 0:
                extra = f"成交 {amt/1e8:.1f}亿"

        # 排名徽章颜色
        if rank <= 3:
            badge_bg = "rgba(245,158,11,0.2)"
            badge_color = "#f59e0b"
        elif rank <= 5:
            badge_bg = "rgba(59,130,246,0.15)"
            badge_color = "#60a5fa"
        else:
            badge_bg = "rgba(71,85,105,0.2)"
            badge_color = "#94a3b8"

        in_wl = "⭐" if code in my_stocks else ""

        # 每行: 信息区 | 分析按钮 | 加自选按钮
        info_col, btn1_col, btn2_col = st.columns([6, 1, 1])
        with info_col:
            st.markdown(f'''<div style="display:flex; align-items:center; padding:6px 10px;
     background:rgba(30,41,59,0.25); border-radius:8px; gap:8px; margin:1px 0;">
    <span style="background:{badge_bg}; color:{badge_color}; font-weight:700;
          font-size:0.75rem; padding:2px 7px; border-radius:6px; min-width:24px;
          text-align:center;">#{rank}</span>
    <span style="font-weight:600; color:#f1f5f9; font-size:0.88rem;">{stock_name}</span>
    <span style="color:#64748b; font-size:0.73rem;">{code}</span>
    <span>{in_wl}</span>
    <span style="margin-left:auto; font-weight:600; color:#f1f5f9;">¥{price:.2f}</span>
    <span style="color:{chg_color}; font-size:0.82rem;">{chg_icon}{abs(change):.2f}%</span>
    <span style="color:#64748b; font-size:0.73rem;">{extra}</span>
</div>''', unsafe_allow_html=True)

        with btn1_col:
            if st.button("📊", key=f"a_{code}", help=f"分析 {stock_name}", use_container_width=True):
                st.session_state['selected_stock'] = code
                st.session_state['market_view'] = 'analyze'
                st.rerun()
        with btn2_col:
            if code not in my_stocks:
                if st.button("⭐", key=f"w_{code}", help=f"加自选 {stock_name}", use_container_width=True):
                    my_stocks.append(code)
                    save_watchlist(my_stocks)
                    st.toast(f"✅ {stock_name} 已加入自选", icon="⭐")
                    st.rerun()
            else:
                st.button("✓", key=f"w_{code}", disabled=True, use_container_width=True,
                         help="已在自选")


def _render_analyze_view(L, my_stocks, name_map):
    """决策分析视图 — 前后切换 + 加自选"""
    from components.dna_analyzer import render_dna_analyzer

    current = st.session_state.get('selected_stock', '601318')
    cur_name = name_map.get(current, '')
    strat_list = st.session_state.get('_strat_list', [])
    in_watchlist = current in my_stocks

    # ---- 头部: 返回 | 标的信息 | 加自选 | 前后切换 ----
    top1, top2, top3 = st.columns([1, 4, 2])

    with top1:
        if st.button("◀ 返回", key="back_to_strategy", use_container_width=True):
            st.session_state['market_view'] = 'strategy'
            st.rerun()

    with top2:
        status_badge = '⭐ 已自选' if in_watchlist else ''
        st.markdown(f'''
<div style="display:flex; align-items:center; gap:10px; padding:6px 0;">
    <span style="font-size:1.15rem; font-weight:700; color:#f1f5f9;">🎯 {cur_name}</span>
    <span style="color:#64748b; font-size:0.85rem;">{current}</span>
    <span style="color:#f59e0b; font-size:0.78rem; background:rgba(245,158,11,0.1);
          padding:1px 8px; border-radius:12px;">{status_badge}</span>
</div>''', unsafe_allow_html=True)

    with top3:
        ac1, ac2, ac3 = st.columns(3)
        # 前后切换
        if strat_list and current in strat_list:
            cur_idx = strat_list.index(current)
            with ac1:
                if cur_idx > 0:
                    if st.button("◀", key="prev_stock", use_container_width=True, help="上一只"):
                        st.session_state['selected_stock'] = strat_list[cur_idx - 1]
                        st.rerun()
            with ac3:
                if cur_idx < len(strat_list) - 1:
                    if st.button("▶", key="next_stock", use_container_width=True, help="下一只"):
                        st.session_state['selected_stock'] = strat_list[cur_idx + 1]
                        st.rerun()

        # 加自选/移出自选
        with ac2:
            if not in_watchlist:
                if st.button("📥", key="add_wl", type="primary", use_container_width=True, help="加入自选"):
                    my_stocks.append(current)
                    save_watchlist(my_stocks)
                    st.toast(f"✅ {cur_name} 已加入自选", icon="⭐")
                    st.rerun()
            else:
                if st.button("❌", key="rm_wl", use_container_width=True, help="移出自选"):
                    my_stocks.remove(current)
                    save_watchlist(my_stocks)
                    st.toast(f"{cur_name} 已移出自选", icon="🗑️")
                    st.rerun()

    # 如果有策略列表，显示进度
    if strat_list and current in strat_list:
        cur_idx = strat_list.index(current)
        st.caption(f"策略列表进度: {cur_idx + 1} / {len(strat_list)}")

    render_dna_analyzer(L, my_stocks, name_map)


def _render_track_view(L, my_stocks, name_map):
    """自选跟盘视图 — Redis 缓存 + 排序"""
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
        st.markdown('''
<div style="text-align:center; padding:60px 20px; color:#64748b;">
    <div style="font-size:3rem; margin-bottom:16px;">📋</div>
    <div style="font-size:1.1rem; font-weight:600; color:#94a3b8; margin-bottom:8px;">还没有自选股</div>
    <div style="font-size:0.85rem;">在「① 选股」中挑选标的，点击 ⭐ 即可加入自选</div>
</div>''', unsafe_allow_html=True)
        return

    # 排序选项
    sort_col, count_col = st.columns([3, 1])
    with sort_col:
        sort_by = st.radio("排序", ["加入顺序", "涨幅↓", "涨幅↑"], horizontal=True,
                          label_visibility="collapsed", key="track_sort")
    with count_col:
        st.markdown(f'<div style="text-align:right; color:#64748b; padding:8px 0;">⭐ {len(my_stocks)} 只</div>',
                    unsafe_allow_html=True)

    # 获取行情 (通过 Redis 缓存)
    try:
        import requests
        sina_codes = [f"{'s_sh' if c.startswith('6') else 's_sz'}{c}" for c in my_stocks]
        url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
        headers = {'Referer': 'https://finance.sina.com.cn/'}

        # 尝试 Redis 缓存
        quotes = {}
        try:
            from core.cache import RedisCache
            _redis = RedisCache()
            if _redis.ping():
                cached = _redis.get("track:watchlist_quotes")
                if cached:
                    quotes = cached
        except Exception:
            pass

        if not quotes:
            r = requests.get(url, headers=headers, timeout=5)
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
            # 写入 Redis (60s)
            try:
                if _redis and _redis.ping():
                    _redis.set("track:watchlist_quotes", quotes, expire=60)
            except Exception:
                pass
    except Exception:
        quotes = {}

    # 构建数据列表
    stock_data = []
    for s in my_stocks:
        q = None
        for key, val in quotes.items():
            if s in key:
                q = val
                break
        stock_data.append({
            'code': s,
            'name': q['name'] if q else name_map.get(s, s),
            'price': q['price'] if q else 0,
            'change': q['change'] if q else 0,
        })

    # 排序
    if sort_by == "涨幅↓":
        stock_data.sort(key=lambda x: x['change'], reverse=True)
    elif sort_by == "涨幅↑":
        stock_data.sort(key=lambda x: x['change'])

    # 渲染 — 紧凑列表
    for i, item in enumerate(stock_data):
        s = item['code']
        s_name = item['name']
        s_price = item['price']
        s_change = item['change']
        chg_color = "#ef4444" if s_change >= 0 else "#10b981"
        chg_icon = "▲" if s_change >= 0 else "▼"

        col_stock, col_go, col_del = st.columns([5, 1, 1])
        with col_stock:
            st.markdown(f'''
<div style="background: rgba(30,41,59,0.3); border: 1px solid rgba(255,255,255,0.06);
     border-radius: 10px; padding: 10px 14px; display: flex; align-items: center;
     justify-content: space-between;">
    <div>
        <span style="font-weight: 600; color: #f1f5f9;">{s_name}</span>
        <span style="color: #64748b; font-size: 0.8rem; margin-left: 8px;">{s}</span>
    </div>
    <div>
        <span style="font-weight: 600; color: #f1f5f9;">{'¥%.2f' % s_price if s_price > 0 else '--'}</span>
        <span style="color: {chg_color}; margin-left: 8px;">{chg_icon} {abs(s_change):.2f}%</span>
    </div>
</div>''', unsafe_allow_html=True)

        with col_go:
            if st.button("📊", key=f"track_{i}_{s}", use_container_width=True, help="分析此标的"):
                st.session_state['selected_stock'] = s
                st.session_state['market_view'] = 'analyze'
                st.rerun()

        with col_del:
            if st.button("🗑️", key=f"del_{i}_{s}", use_container_width=True, help="移出自选"):
                my_stocks.remove(s)
                save_watchlist(my_stocks)
                st.toast(f"{s_name} 已移出自选", icon="🗑️")
                st.rerun()
