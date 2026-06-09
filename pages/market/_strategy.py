"""
策略视图渲染 — market 子包 v2.1
所有 HTML 渲染统一使用 st.html()，彻底避免 Markdown 解析器干扰
"""
import streamlit as st

_HOTSPOT_STYLE = ""  # CSS 已在 style.css 中定义


def _render_strategy_view(L, my_stocks, name_map):
    """策略选股视图 — 精品 Tab 版"""
    from pages.market._card import _render_generic_strategy_tab
    from main import find_value_stocks, find_momentum_stocks, find_growth_stocks

    strat_defs = [
        ('Hotspot',    '🏭 2026热点',  '九大核心赛道龙头',      '#ef4444', 'HOT'),
        ('Value',      '💎 价值发现',  '低PE+低PB 优质标的',    '#3b82f6', 'VAL'),
        ('Momentum',   '🔥 动量追击',  '量价齐升趋势股',         '#10b981', 'MOM'),
        ('Growth',     '🌟 成长之星',  '机构资金高活跃股',       '#f59e0b', 'GRW'),
        ('Mainforce',  '💰 主力吸筹',  '连续净流入追踪',         '#ef4444', 'MF'),
        ('Northbound', '🔗 北向最爱',  '陆股通十大成交',         '#06b6d4', 'NB'),
        ('Breakout',   '📈 技术突破',  '均线金叉+放量突破',      '#8b5cf6', 'BRK'),
        ('Concept',    '📡 概念板块',  'Tushare 879个动态板块',  '#f97316', '879'),
    ]

    tabs = st.tabs([label for _, label, _, _, _ in strat_defs])

    for i, (key, label, desc, color, badge) in enumerate(strat_defs):
        with tabs[i]:
            # ✅ 用 st.html() 渲染描述条，避免 Markdown 解析器干扰
            st.html(
                f'<div class="strat-tab-hint">'
                f'<span class="strat-tab-badge" style="background:{color}1a;color:{color};border:1px solid {color}33;">{badge}</span>'
                f'{desc}'
                f'</div>'
            )

            if key == 'Hotspot':
                _render_hotspot_strategy(L, my_stocks, name_map)
            elif key == 'Concept':
                _render_concept_strategy(L, my_stocks, name_map)
            else:
                func_map = {
                    'Value':      find_value_stocks,
                    'Momentum':   find_momentum_stocks,
                    'Growth':     find_growth_stocks,
                    'Mainforce':  lambda: __import__('core.strategies', fromlist=['find_mainforce_stocks']).find_mainforce_stocks(),
                    'Northbound': lambda: __import__('core.strategies', fromlist=['find_northbound_top']).find_northbound_top(),
                    'Breakout':   lambda: __import__('core.strategies', fromlist=['find_tech_breakout']).find_tech_breakout(),
                }
                if key in func_map:
                    df = func_map[key]()
                    _render_generic_strategy_tab(key, df, my_stocks, name_map)
                else:
                    _render_coming_soon(label)


def _render_coming_soon(label: str):
    st.html(
        f'<div style="text-align:center;padding:48px 20px;">'
        f'<div style="font-size:2.5rem;margin-bottom:12px;">🚧</div>'
        f'<div style="font-size:1rem;font-weight:600;color:#475569;margin-bottom:6px;">{label} 正在建设中</div>'
        f'<div style="font-size:0.8rem;color:#334155;">该策略模块接入中，敬请期待</div>'
        f'</div>'
    )


def _render_hotspot_strategy(L, my_stocks, name_map):
    """九大热点赛道 — 横向滚动 Pill 选择器"""
    from core.strategies import HOTSPOT_2026, find_hotspot_stocks
    from pages.market._card import _render_generic_strategy_tab

    if 'hotspot_sector' not in st.session_state:
        st.session_state['hotspot_sector'] = None

    sel = st.session_state.get('hotspot_sector')

    # ── Pill 按钮行（用 st.columns 模拟，每行 5 个）──────────────
    sectors = [('__all__', '🔥 全部赛道', '#ef4444')] + [
        (k, v['name'], v['color']) for k, v in HOTSPOT_2026.items()
    ]

    cols_per_row = 5
    for row_start in range(0, len(sectors), cols_per_row):
        chunk = sectors[row_start: row_start + cols_per_row]
        cols = st.columns(len(chunk))
        for ci, (key, name, color) in enumerate(chunk):
            real_key = None if key == '__all__' else key
            is_active = sel == real_key
            with cols[ci]:
                if st.button(
                    name,
                    key=f"hs2_{key}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state['hotspot_sector'] = real_key
                    st.rerun()

    # ── 赛道描述条 ────────────────────────────────────────────────
    if sel and sel in HOTSPOT_2026:
        data = HOTSPOT_2026[sel]
        stock_count = len(data.get('stocks', []))
        st.html(
            f'<div class="hs-desc-bar">'
            f'<strong style="color:{data["color"]};">{data["name"]}</strong>'
            f' &nbsp;·&nbsp; {data["desc"]}'
            f' &nbsp;<span style="color:#334155;font-size:0.7rem;">({stock_count} 支标的)</span>'
            f'</div>'
        )

    # ── 加载数据 ──────────────────────────────────────────────────
    with st.spinner("⚡ 获取赛道行情..."):
        df = find_hotspot_stocks(sel)

    if df.empty:
        st.html(
            '<div style="text-align:center;padding:40px 20px;">'
            '<div style="font-size:2rem;margin-bottom:10px;">📡</div>'
            '<div style="color:#475569;font-size:0.9rem;">暂无行情数据</div>'
            '<div style="color:#334155;font-size:0.78rem;margin-top:6px;">非交易时段，价格数据缓存可能已过期</div>'
            '</div>'
        )
        return

    _render_generic_strategy_tab(f"hot_{sel or 'all'}", df, my_stocks, name_map)


def _render_concept_strategy(L, my_stocks, name_map):
    """Tushare 概念板块 — 搜索 + 快捷词条"""
    from core.strategies import find_concept_hot, find_concept_stocks_detail
    from pages.market._card import _render_generic_strategy_tab

    concepts = find_concept_hot()
    if concepts.empty:
        st.html(
            '<div style="text-align:center;padding:32px;">'
            '<div style="font-size:1.8rem;margin-bottom:8px;">🔌</div>'
            '<div style="color:#ef4444;font-size:0.88rem;font-weight:600;">Tushare 未连接</div>'
            '<div style="color:#475569;font-size:0.78rem;margin-top:4px;">请检查 TUSHARE_TOKEN 配置</div>'
            '</div>'
        )
        return

    # 检测是否为本地精选 Fallback 数据
    is_local_fallback = not concepts.empty and concepts.iloc[0].get('src') == 'local'
    if is_local_fallback:
        st.info("💡 提示：当前 Tushare 接口受限（积分不足或未配置），系统已自动切换到本地精选热点概念数据库。如需获取全部 800+ 概念板块，请检查 `.env` 配置文件中的 `TUSHARE_TOKEN` 并确保积分符合门槛（通常需要 2000 积分以上）。")

    # ── 热词快捷按钮 (2 行) ──────────────────────────────────────
    hot_words_1 = ['人形机器人', 'AI算力', '光模块', '低空经济', '核电']
    hot_words_2 = ['芯片', '创新药', '新能源', '量子计算', '军工']

    c_row1 = st.columns(len(hot_words_1))
    for i, word in enumerate(hot_words_1):
        with c_row1[i]:
            if st.button(word, key=f"hw1_{word}", use_container_width=True):
                st.session_state['concept_search'] = word

    c_row2 = st.columns(len(hot_words_2))
    for i, word in enumerate(hot_words_2):
        with c_row2[i]:
            if st.button(word, key=f"hw2_{word}", use_container_width=True):
                st.session_state['concept_search'] = word

    # ── 搜索 + 下拉选择 ──────────────────────────────────────────
    search_col, select_col = st.columns([1, 2])
    with search_col:
        search_text = st.text_input(
            "搜索板块", key="concept_search",
            placeholder="🔍  如: 机器人、光伏、芯片...",
            label_visibility="collapsed"
        )

    filtered = concepts
    if search_text:
        filtered = concepts[concepts['name'].str.contains(search_text, case=False, na=False)]

    if filtered.empty:
        st.caption(f"未找到「{search_text}」相关板块")
        return

    with select_col:
        options = filtered['name'].tolist()[:50]
        selected_concept = st.selectbox(
            "选择板块", options,
            key="concept_select_box_v1",
            label_visibility="collapsed"
        )

    if selected_concept:
        with st.spinner(f"正在加载 {selected_concept} 成分股..."):
            matched = filtered[filtered['name'] == selected_concept]
            if not matched.empty:
                concept_id = str(matched['code'].iloc[0])
                df = find_concept_stocks_detail(concept_id, selected_concept)
                if not df.empty:
                    _render_generic_strategy_tab(f"concept_{concept_id}", df, my_stocks, name_map)
                else:
                    st.html(
                        f'<div style="padding:16px;color:#64748b;font-size:0.85rem;">'
                        f'暂无「{selected_concept}」成分股数据</div>'
                    )
