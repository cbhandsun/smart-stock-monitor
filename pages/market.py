"""
📡 市场信号流页面 - V9.0
改进: Tab导航 + 内联指数条 + pill策略 + 紧凑股票行 + 统一渲染
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


# ============================================================
#  页面入口
# ============================================================
def render(L, my_stocks, name_map):
    """渲染市场页面"""

    # 首次加载(全新会话)默认选股; 页面内切换靠按钮管理 market_view
    if 'market_view' not in st.session_state:
        st.session_state['market_view'] = 'strategy'

    current_view = st.session_state['market_view']

    # ========== 紧凑头部: 标题 | 导航 | 搜索 | 刷新 ==========
    h1, h2, h3, h4, h5, h6 = st.columns([2.5, 1, 1, 1, 3, 0.5])
    with h1:
        st.markdown(f"### 📡 {L.get('market_discovery', '实时信号流')}")
    with h2:
        if st.button("📋选股", use_container_width=True,
                     type="primary" if current_view == 'strategy' else "secondary",
                     key="nav_strategy"):
            st.session_state['market_view'] = 'strategy'
            st.rerun()
    with h3:
        if st.button("📊分析", use_container_width=True,
                     type="primary" if current_view == 'analyze' else "secondary",
                     key="nav_analyze"):
            st.session_state['market_view'] = 'analyze'
            st.rerun()
    with h4:
        if st.button("⭐跟盘", use_container_width=True,
                     type="primary" if current_view == 'track' else "secondary",
                     key="nav_track"):
            st.session_state['market_view'] = 'track'
            st.rerun()
    with h5:
        code = stock_selector(label="快速跳转", key_suffix="market_search")
        if code and code != st.session_state.get('_last_market_search', ''):
            st.session_state['_last_market_search'] = code
            st.session_state['selected_stock'] = code
            st.session_state['market_view'] = 'analyze'
            st.rerun()
    with h6:
        if st.button("🔄", key="refresh_market", use_container_width=True, help="刷新行情"):
            st.cache_data.clear()
            st.toast("行情已刷新", icon="📈")
            st.rerun()

    # ========== 大盘指数: 内联紧凑条 ==========
    _render_market_bar()

    if current_view == 'strategy':
        _render_strategy_view(L, my_stocks, name_map)
    elif current_view == 'analyze':
        _render_analyze_view(L, my_stocks, name_map)
    elif current_view == 'track':
        _render_track_view(L, my_stocks, name_map)


# ============================================================
#  大盘指数 — 内联条
# ============================================================
def _render_market_bar():
    """内联大盘指数条"""
    ov = get_market_overview()
    if ov.empty:
        return

    items_html = ""
    for _, r in ov.iterrows():
        chg = float(r.get('涨跌幅', 0))
        chg_cls = "idx-up" if chg >= 0 else "idx-down"
        chg_icon = "▲" if chg >= 0 else "▼"
        price = float(r.get('最新价', 0))
        items_html += (
            f'<span class="idx-name">{r["名称"]}</span>'
            f'<span class="idx-price">{price:,.1f}</span>'
            f'<span class="{chg_cls}">{chg_icon}{abs(chg):.2f}%</span>'
            f'<span style="color:#334155;">|</span>'
        )

    st.markdown(f'<div class="market-bar">{items_html}</div>', unsafe_allow_html=True)

    # 风控警报
    avg_drop = ov['涨跌幅'].mean()
    if avg_drop <= -2.0:
        st.error(f"**⚠️ 智能风控警报：** 三大指数平均跌幅 `{avg_drop:.2f}%`。"
                 f"建议多头仓位降至 30% 以下，关注黄金 ETF (`518880`) 等避险资产。")
    elif avg_drop <= -1.0:
        st.warning(f"**🛡️ 风控提示：** 大盘平均跌幅 `{avg_drop:.2f}%`。建议停止加仓，清理弱势标的。")


# ============================================================
#  统一股票行渲染器
# ============================================================
def _render_stock_row(code, stock_name, price, change, rank=0, extra="",
                      my_stocks=None, name_map=None, show_signals=True,
                      btn_prefix="s", show_watchlist_btn=True, show_remove_btn=False):
    """紧凑双行卡片 — 通用组件，选股/跟盘共用"""
    if my_stocks is None:
        my_stocks = []

    chg_color = "#ef4444" if change >= 0 else "#10b981"
    chg_icon = "▲" if change >= 0 else "▼"
    in_wl = "⭐" if code in my_stocks else ""

    # 排名徽章
    if rank > 0:
        if rank <= 3:
            badge_bg, badge_color = "rgba(245,158,11,0.2)", "#f59e0b"
        elif rank <= 5:
            badge_bg, badge_color = "rgba(59,130,246,0.15)", "#60a5fa"
        else:
            badge_bg, badge_color = "rgba(71,85,105,0.2)", "#94a3b8"
        rank_html = f'<span class="sr-rank" style="background:{badge_bg};color:{badge_color};">#{rank}</span>'
    else:
        rank_html = ""

    # 信号 + 指标
    metrics_html = ""
    action_badge = ""
    if show_signals:
        signals = _get_quick_signals(code)

        # 操作建议 badge (第一行右侧)
        action_color = {"买入": "#ef4444", "卖出": "#10b981", "持有": "#3b82f6", "观望": "#64748b"}.get(
            signals['action_short'], '#94a3b8')
        action_bg = {"买入": "rgba(239,68,68,0.15)", "卖出": "rgba(16,185,129,0.15)",
                     "持有": "rgba(59,130,246,0.15)", "观望": "rgba(100,116,139,0.1)"}.get(
            signals['action_short'], 'rgba(100,116,139,0.1)')
        action_badge = (f'<span style="background:{action_bg};color:{action_color};'
                       f'padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:600;'
                       f'white-space:nowrap;">{signals["action"]}</span>')

        # 第二行指标 pills
        rsi = signals.get('rsi', 50)
        vol_ratio = signals.get('vol_ratio', 1.0)
        score = signals.get('score', 0)
        ma_pos = signals.get('ma_pos', '—')
        macd_dir = signals.get('macd_dir', '—')

        # RSI 颜色
        if rsi > 70: rsi_c, rsi_bg = '#ef4444', 'rgba(239,68,68,0.12)'
        elif rsi < 30: rsi_c, rsi_bg = '#10b981', 'rgba(16,185,129,0.12)'
        else: rsi_c, rsi_bg = '#94a3b8', 'rgba(148,163,184,0.08)'

        # 量比颜色
        if vol_ratio > 2.0: vr_c, vr_bg = '#ef4444', 'rgba(239,68,68,0.12)'
        elif vol_ratio > 1.2: vr_c, vr_bg = '#f59e0b', 'rgba(245,158,11,0.12)'
        else: vr_c, vr_bg = '#94a3b8', 'rgba(148,163,184,0.08)'

        # 评分颜色
        if score >= 4: sc_c, sc_bg = '#ef4444', 'rgba(239,68,68,0.12)'
        elif score >= 3: sc_c, sc_bg = '#f59e0b', 'rgba(245,158,11,0.12)'
        elif score <= 1: sc_c, sc_bg = '#10b981', 'rgba(16,185,129,0.12)'
        else: sc_c, sc_bg = '#94a3b8', 'rgba(148,163,184,0.08)'

        # MA 位置颜色
        ma_c = '#ef4444' if '多头' in ma_pos else ('#10b981' if '空头' in ma_pos else '#f59e0b')

        # MACD 颜色
        macd_c = '#ef4444' if '红' in macd_dir else ('#10b981' if '绿' in macd_dir else '#94a3b8')

        # 买卖信号
        buy_color = "#10b981" if "可" in signals['buy'] or "建议" in signals['buy'] else (
            "#f59e0b" if "关注" in signals['buy'] or "向好" in signals['buy'] else "#64748b")
        sell_color = "#ef4444" if "止损" in signals['sell'] or "减仓" in signals['sell'] else (
            "#f59e0b" if "关注" in signals['sell'] or "风险" in signals['sell'] else "#64748b")

        pill = ('<span style="font-size:0.7rem;padding:1px 6px;border-radius:4px;'
               'white-space:nowrap;background:{bg};color:{c};">{txt}</span>')

        metrics_html = ('<div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:4px;">'
            + pill.format(bg=sc_bg, c=sc_c, txt=f'评分 {score}/5')
            + pill.format(bg=rsi_bg, c=rsi_c, txt=f'RSI {rsi:.0f}')
            + pill.format(bg=vr_bg, c=vr_c, txt=f'量比 {vol_ratio:.1f}')
            + pill.format(bg='rgba(148,163,184,0.08)', c=ma_c, txt=f'均线 {ma_pos}')
            + pill.format(bg='rgba(148,163,184,0.08)', c=macd_c, txt=f'MACD {macd_dir}')
            + pill.format(bg='rgba(148,163,184,0.08)', c=buy_color, txt=f'买 {signals["buy"]}')
            + pill.format(bg='rgba(148,163,184,0.08)', c=sell_color, txt=f'卖 {signals["sell"]}')
            + '</div>')

    extra_html = f'<span class="sr-extra">{extra}</span>' if extra else ''
    price_str = f"¥{price:.2f}" if price > 0 else "--"

    # 卡片 HTML + 按钮列
    row_col, btn_col = st.columns([7, 1])
    with row_col:
        delay = f"{rank * 0.02 if rank else 0}s"
        html = (f'<div class="stock-row" style="animation:fadeInUp 0.25s ease-out backwards;'
                f'animation-delay:{delay};flex-direction:column;align-items:stretch;">'
                f'<div style="display:flex;align-items:center;gap:8px;">'
                f'{rank_html}'
                f'<span class="sr-name">{stock_name}</span>'
                f'<span class="sr-code">{code} {in_wl}</span>'
                f'{extra_html}'
                f'<span class="sr-price">{price_str}</span>'
                f'<span class="sr-change" style="color:{chg_color};">{chg_icon}{abs(change):.2f}%</span>'
                f'{action_badge}'
                f'</div>'
                f'{metrics_html}'
                f'</div>')
        st.markdown(html, unsafe_allow_html=True)

    with btn_col:
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("📊", key=f"{btn_prefix}_a_{code}", help=f"分析 {stock_name}"):
                st.session_state['selected_stock'] = code
                st.session_state['market_view'] = 'analyze'
                st.rerun()
        with bc2:
            if show_remove_btn:
                if st.button("🗑️", key=f"{btn_prefix}_d_{code}", help="移出自选"):
                    my_stocks.remove(code)
                    save_watchlist(my_stocks)
                    st.toast(f"{stock_name} 已移出自选", icon="🗑️")
                    st.rerun()
            elif show_watchlist_btn:
                if code not in my_stocks:
                    if st.button("⭐", key=f"{btn_prefix}_w_{code}", help=f"加自选"):
                        my_stocks.append(code)
                        save_watchlist(my_stocks)
                        st.toast(f"✅ {stock_name} 已加入自选", icon="⭐")
                        st.rerun()
                else:
                    st.button("✓", key=f"{btn_prefix}_w_{code}", disabled=True, help="已在自选")


# ============================================================
#  视图 1: 策略选股
# ============================================================
def _render_strategy_view(L, my_stocks, name_map):
    """策略选股视图 — pill按钮 + 紧凑行"""

    if 'capture_strat' not in st.session_state:
        st.session_state['capture_strat'] = 'Hotspot'

    # ========== 策略 pill 按钮 ==========
    strat_defs = [
        ('Hotspot', '🏭 2026热点', '2026 六大核心赛道龙头', '#ef4444'),
        ('Value', '💎 价值发现', '低PE+低PB，被低估的优质标的', '#3b82f6'),
        ('Momentum', '🔥 动量追击', '涨幅1~9%，量价齐升的趋势股', '#10b981'),
        ('Growth', '🌟 成长之星', '高成交额活跃股，机构资金关注', '#f59e0b'),
        ('Mainforce', '💰 主力吸筹', '连续3日主力净流入', '#ef4444'),
        ('Northbound', '🔗 北向最爱', '陆股通十大成交股', '#06b6d4'),
        ('Breakout', '📈 技术突破', '均线金叉+放量突破', '#8b5cf6'),
        ('Concept', '📡 概念板块', 'Tushare 879个概念板块', '#f97316'),
    ]

    current_strat = st.session_state['capture_strat']

    # Pill buttons via Streamlit columns (8 pills)
    pill_cols = st.columns(8)
    for i, (key, label, desc, color) in enumerate(strat_defs):
        with pill_cols[i]:
            btn_type = "primary" if current_strat == key else "secondary"
            if st.button(label, use_container_width=True, type=btn_type, key=f"pill_{key}"):
                st.session_state['capture_strat'] = key
                st.rerun()

    # 策略描述 (紧凑)
    for key, _, desc, color in strat_defs:
        if key == current_strat:
            st.caption(f"📌 {desc}")
            break

    # ========== 策略分发 ==========
    if current_strat == 'Hotspot':
        _render_hotspot_strategy(L, my_stocks, name_map)
        return

    if current_strat == 'Concept':
        _render_concept_strategy(L, my_stocks, name_map)
        return

    # ========== 常规策略 ==========
    strat_labels = {
        'Value': '💎 扫描价值股...',
        'Momentum': '🔥 扫描动量股...',
        'Growth': '🌟 扫描成长股...',
        'Mainforce': '💰 分析3日主力资金...',
        'Northbound': '🔗 获取陆股通数据...',
        'Breakout': '📈 扫描技术突破信号...',
    }
    load_label = strat_labels.get(current_strat, '扫描中...')

    is_tushare = current_strat in ('Mainforce', 'Northbound', 'Breakout')

    if is_tushare:
        with st.status(load_label, expanded=True) as status:
            if current_strat == 'Mainforce':
                from core.strategies import find_mainforce_stocks
                df = find_mainforce_stocks()
            elif current_strat == 'Northbound':
                from core.strategies import find_northbound_top
                df = find_northbound_top()
            else:
                from core.strategies import find_tech_breakout
                df = find_tech_breakout()
            if not df.empty:
                status.update(label=f"✅ 找到 {len(df)} 只标的", state="complete")
            else:
                status.update(label="未找到符合条件的标的", state="error")
    else:
        with st.spinner(load_label):
            if current_strat == 'Value':
                df = find_value_stocks()
            elif current_strat == 'Momentum':
                df = find_momentum_stocks()
            elif current_strat == 'Growth':
                df = find_growth_stocks()
            else:
                df = pd.DataFrame()

    if df.empty:
        st.info("暂无符合条件的股票，请稍后重试")
        return

    st.session_state['_strat_list'] = df['代码'].tolist()
    _render_stock_list(df, my_stocks, name_map)


def _render_hotspot_strategy(L, my_stocks, name_map):
    """2026 六大热点赛道"""
    from core.strategies import HOTSPOT_2026, find_hotspot_stocks

    if 'hotspot_sector' not in st.session_state:
        st.session_state['hotspot_sector'] = None

    # 子赛道选择按钮
    sub_cols = st.columns(7)
    with sub_cols[0]:
        if st.button("🔥 全部", use_container_width=True,
                    type="primary" if st.session_state['hotspot_sector'] is None else "secondary",
                    key="hs_all"):
            st.session_state['hotspot_sector'] = None
            st.rerun()

    for i, (key, data) in enumerate(HOTSPOT_2026.items()):
        with sub_cols[i + 1]:
            short_name = data['name'].split(' ')[-1][:4]
            if st.button(f"{data['name'][:2]}{short_name}", use_container_width=True,
                        type="primary" if st.session_state['hotspot_sector'] == key else "secondary",
                        key=f"hs_{key}"):
                st.session_state['hotspot_sector'] = key
                st.rerun()

    sel = st.session_state['hotspot_sector']
    if sel and sel in HOTSPOT_2026:
        sector = HOTSPOT_2026[sel]
        st.caption(f"💡 {sector['desc']}")

    with st.spinner("获取 2026 赛道行情..."):
        df = find_hotspot_stocks(sel)

    if df.empty:
        st.info("暂无数据")
        return

    st.session_state['_strat_list'] = df['代码'].tolist()
    _render_stock_list(df, my_stocks, name_map)


def _render_concept_strategy(L, my_stocks, name_map):
    """Tushare 概念板块动态选择"""
    from core.strategies import find_concept_hot, find_concept_stocks_detail

    concepts = find_concept_hot()
    if concepts.empty:
        st.info("无法加载概念板块列表，Tushare 可能未连接")
        return

    hot_words = ['机器人', '光伏', '芯片', '半导体', '新能源', '医药', '锂电池', '军工']
    hw_cols = st.columns(len(hot_words))
    for i, word in enumerate(hot_words):
        with hw_cols[i]:
            if st.button(word, key=f"hw_{word}", use_container_width=True):
                st.session_state['concept_search'] = word
                st.rerun()

    search_col, select_col = st.columns([1, 2])
    with search_col:
        search_text = st.text_input("🔍 搜索概念", key="concept_search",
                                    placeholder="如: 机器人、光伏、芯片...")

    filtered = concepts
    if search_text:
        filtered = concepts[concepts['name'].str.contains(search_text, case=False, na=False)]

    if filtered.empty:
        st.info(f"未找到包含 '{search_text}' 的概念板块")
        return

    with select_col:
        options = filtered['name'].tolist()[:30]
        selected = st.selectbox("选择概念板块", options, key="concept_select")

    if selected:
        concept_row = filtered[filtered['name'] == selected].iloc[0]
        concept_id = str(concept_row.get('code', ''))

        st.caption(f"📌 {selected} (Tushare ID: {concept_id})")

        with st.status(f"获取 {selected} 成分股行情...", expanded=True) as status:
            df = find_concept_stocks_detail(concept_id, selected)
            if df.empty:
                status.update(label="暂无成分股数据", state="error")
                return
            status.update(label=f"✅ {selected} — {len(df)} 只成分股", state="complete")

        st.session_state['_strat_list'] = df['代码'].tolist()
        _render_stock_list(df, my_stocks, name_map)


# ============================================================
#  股票列表渲染 (调用统一 _render_stock_row)
# ============================================================
def _render_stock_list(df, my_stocks, name_map):
    """渲染策略股票列表 — 紧凑行"""

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

        # 额外数据
        extra = ""
        if 'PE' in df.columns:
            try:
                pe = float(row.get('PE', 0) or 0)
                pb = float(row.get('PB', 0) or 0)
            except (ValueError, TypeError):
                pe, pb = 0, 0
            extra = f"PE {pe:.1f} · PB {pb:.2f}"
        elif '板块' in df.columns and row.get('板块'):
            extra = str(row.get('板块', ''))
        elif '成交额' in df.columns:
            try:
                amt = float(row.get('成交额', 0) or 0)
            except (ValueError, TypeError):
                amt = 0
            if amt > 0:
                extra = f"成交 {amt/1e8:.1f}亿"

        _render_stock_row(
            code, stock_name, price, change,
            rank=rank, extra=extra, my_stocks=my_stocks,
            btn_prefix=f"sl{rank}", show_signals=True
        )


# ============================================================
#  视图 2: 决策分析
# ============================================================
def _render_analyze_view(L, my_stocks, name_map):
    """决策分析视图 — 紧凑导航"""
    from components.dna_analyzer import render_dna_analyzer

    current = st.session_state.get('selected_stock', '601318')
    cur_name = name_map.get(current, '')
    strat_list = st.session_state.get('_strat_list', [])
    in_watchlist = current in my_stocks

    # ---- 紧凑操作栏: ◀ | 进度 | 加/移自选 | ▶ ----
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
        # 无策略列表时只显示自选操作
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


# ============================================================
#  视图 3: 自选跟盘
# ============================================================
def _render_track_view(L, my_stocks, name_map):
    """自选跟盘视图 — 复用统一行渲染"""
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
        empty_html = ('<div style="text-align:center;padding:40px 20px;color:#64748b;">'
                      '<div style="font-size:2.5rem;margin-bottom:12px;">📋</div>'
                      '<div style="font-size:1rem;font-weight:600;color:#94a3b8;margin-bottom:6px;">还没有自选股</div>'
                      '<div style="font-size:0.82rem;">在「📋 选股」中挑选标的，点击 ⭐ 即可加入自选</div>'
                      '</div>')
        st.markdown(empty_html, unsafe_allow_html=True)
        return

    # 排序选项 + 数量
    sort_col, count_col = st.columns([4, 1])
    with sort_col:
        sort_by = st.radio("排序", ["加入顺序", "涨幅↓", "涨幅↑"], horizontal=True,
                          label_visibility="collapsed", key="track_sort")
    with count_col:
        st.markdown(f'<div style="text-align:right; color:#64748b; padding:6px 0; font-size:0.85rem;">⭐ {len(my_stocks)} 只</div>',
                    unsafe_allow_html=True)

    # 获取行情 (通过 Sina + Redis 缓存)
    try:
        import requests
        sina_codes = [f"{'s_sh' if c.startswith('6') else 's_sz'}{c}" for c in my_stocks]
        url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
        headers = {'Referer': 'https://finance.sina.com.cn/'}

        quotes = {}
        try:
            from core.cache import RedisCache
            _redis = getattr(_render_track_view, '_redis', None)
            if _redis is None:
                _redis = RedisCache()
                _render_track_view._redis = _redis if _redis.ping() else None
                _redis = _render_track_view._redis
            if _redis:
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
            try:
                if _redis:
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

    if sort_by == "涨幅↓":
        stock_data.sort(key=lambda x: x['change'], reverse=True)
    elif sort_by == "涨幅↑":
        stock_data.sort(key=lambda x: x['change'])

    # ========== 渲染 — 复用统一行组件 ==========
    for i, item in enumerate(stock_data):
        _render_stock_row(
            item['code'], item['name'], item['price'], item['change'],
            my_stocks=my_stocks, btn_prefix=f"tk{i}",
            show_signals=True, show_watchlist_btn=False, show_remove_btn=True
        )


# ============================================================
#  技术信号计算
# ============================================================
@st.cache_data(ttl=600, show_spinner=False)
def _get_quick_signals(code: str) -> dict:
    """
    轻量级技术信号 (缓存 2min)
    基于 30 日 K 线: MA5/MA20 (kline 自带), RSI/MACD (自算)
    返回: {status, buy, sell, action, action_short}
    """
    import numpy as np
    default = {'status': '—', 'buy': '—', 'sell': '—', 'action': '—', 'action_short': '观望',
                'rsi': 50, 'vol_ratio': 1.0, 'score': 0, 'ma_pos': '—', 'macd_dir': '—'}
    try:
        from modules.data_loader import fetch_kline
        full = ("sh" if code.startswith('6') else "sz") + code
        kline = fetch_kline(full, period='daily', datalen=60)
        if kline is None or kline.empty or len(kline) < 15:
            return default

        closes = kline['收盘'].astype(float)
        volumes = kline['成交量'].astype(float)

        # --- MA ---
        ma5 = float(kline.iloc[-1].get('MA5', 0) or 0)
        ma20 = float(kline.iloc[-1].get('MA20', 0) or 0)
        if ma5 == 0:
            ma5 = closes.tail(5).mean()
        if ma20 == 0:
            ma20 = closes.tail(20).mean()
        ma10 = closes.tail(10).mean()

        prev_ma5 = float(kline.iloc[-2].get('MA5', 0) or 0)
        prev_ma20 = float(kline.iloc[-2].get('MA20', 0) or 0)
        if prev_ma5 == 0:
            prev_ma5 = closes.iloc[-6:-1].mean()
        if prev_ma20 == 0 and len(closes) >= 21:
            prev_ma20 = closes.iloc[-21:-1].mean()

        # --- RSI (14日) ---
        delta = closes.diff()
        gain = delta.clip(lower=0)
        loss = (-delta.clip(upper=0))
        avg_gain = gain.rolling(14, min_periods=14).mean()
        avg_loss = loss.rolling(14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50

        # --- MACD (12,26,9) ---
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist_series = macd_line - signal_line
        macd_hist = float(macd_hist_series.iloc[-1])
        prev_macd_hist = float(macd_hist_series.iloc[-2])

        close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2])
        vol = float(volumes.iloc[-1])
        vol_avg5 = float(volumes.tail(5).mean())

        # ===== 状态判断 (5分制) =====
        score = 0
        if ma5 > ma20: score += 1
        if ma5 > ma10: score += 1
        if close > ma20: score += 1
        if macd_hist > 0: score += 1
        if rsi > 50: score += 1

        if score >= 4:
            status = "看多 📈"
        elif score <= 1:
            status = "看空 📉"
        else:
            status = "震荡 ↔️"

        # ===== 买点判断 =====
        buy_signals = []
        if ma5 > ma20 and prev_ma5 <= prev_ma20:
            buy_signals.append("金叉")
        if rsi < 35:
            buy_signals.append("超卖")
        if macd_hist > 0 and prev_macd_hist <= 0:
            buy_signals.append("MACD翻红")
        if close > ma20 and vol < vol_avg5 * 0.8 and close < prev_close:
            buy_signals.append("缩量回踩")

        if buy_signals:
            buy = f"可关注({','.join(buy_signals[:2])})"
        elif score >= 3 and close > ma20:
            buy = "趋势向好"
        else:
            buy = "暂不明确"

        # ===== 卖点判断 =====
        sell_signals = []
        if ma5 < ma20 and prev_ma5 >= prev_ma20:
            sell_signals.append("死叉")
        if rsi > 75:
            sell_signals.append("超买")
        if macd_hist < 0 and prev_macd_hist >= 0:
            sell_signals.append("MACD翻绿")
        if close < prev_close and vol > vol_avg5 * 1.5:
            sell_signals.append("放量下跌")

        if sell_signals:
            sell = f"⚠ 关注({','.join(sell_signals[:2])})"
        elif score <= 2:
            sell = "注意风险"
        else:
            sell = "暂无信号"

        # ===== 操作建议 =====
        if buy_signals and score >= 3:
            action = "🟢 逢低布局"
            action_short = "买入"
        elif sell_signals and score <= 2:
            action = "🔴 考虑减仓"
            action_short = "卖出"
        elif score >= 4:
            action = "🔵 持有待涨"
            action_short = "持有"
        elif score <= 1:
            action = "⚪ 回避观望"
            action_short = "观望"
        else:
            action = "🟡 震荡等待"
            action_short = "观望"

        # 均线位置
        if ma5 > ma10 > ma20:
            ma_pos = '多头排列'
        elif ma5 < ma10 < ma20:
            ma_pos = '空头排列'
        elif close > ma20:
            ma_pos = '站上MA20'
        else:
            ma_pos = '跌破MA20'

        # MACD 方向
        if macd_hist > 0 and macd_hist > prev_macd_hist:
            macd_dir = '红柱增'
        elif macd_hist > 0:
            macd_dir = '红柱缩'
        elif macd_hist < 0 and macd_hist < prev_macd_hist:
            macd_dir = '绿柱增'
        elif macd_hist < 0:
            macd_dir = '绿柱缩'
        else:
            macd_dir = '零轴'

        # 量比
        vol_ratio = round(vol / vol_avg5, 2) if vol_avg5 > 0 else 1.0

        return {
            'status': status, 'buy': buy, 'sell': sell,
            'action': action, 'action_short': action_short,
            'rsi': rsi, 'vol_ratio': vol_ratio, 'score': score,
            'ma_pos': ma_pos, 'macd_dir': macd_dir,
        }
    except Exception:
        return default
