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


def render(L, my_stocks, name_map):
    """渲染市场页面 - 统一路由版本"""
    
    # 1. 顶部大盘指数 (Sticky/Unified)
    _render_market_bar()
    
    # 2. 导航路由 (State-Aware Router)
    if 'market_view' not in st.session_state:
        st.session_state['market_view'] = '📋 策略选股'
        
    views = ['📋 策略选股', '📊 深度分析', '⭐ 自选跟盘']
    
    # 将内部状态映射到显示名 (用于 backwards compatibility)
    view_map_rev = {
        'strategy': '📋 策略选股',
        'analyze': '📊 深度分析',
        'track': '⭐ 自选跟盘'
    }
    # 检查 session_state 是否有旧的状态值并转换
    current_view = st.session_state.get('market_view', 'strategy')
    if current_view in view_map_rev:
        current_view = view_map_rev[current_view]

    # 渲染导航 Pills
    col_nav, col_empty = st.columns([3, 1])
    with col_nav:
        selected_view = st.segmented_control(
            "视图导航", 
            options=views, 
            default=current_view,
            label_visibility="collapsed",
            key="market_view_router"
        )
    
    # 同步状态
    if selected_view:
        st.session_state['market_view'] = selected_view
    
    st.markdown("---")

    # 3. 页面路由分发
    active_view = st.session_state['market_view']
    
    if active_view == '📋 策略选股' or active_view == 'strategy':
        _render_strategy_view(L, my_stocks, name_map)
    elif active_view == '📊 深度分析' or active_view == 'analyze':
        _render_analyze_view(L, my_stocks, name_map)
    elif active_view == '⭐ 自选跟盘' or active_view == 'track':
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
# ============================================================
#  统一股票卡片渲染器 (Stock Grid Card)
# ============================================================
def _render_stock_card(code, stock_name, price, change, rank=0, extra="",
                       sector="概念挖掘", my_stocks=None, name_map=None, show_signals=True,
                       btn_prefix="s", show_watchlist_btn=True, show_remove_btn=False,
                       precomputed_signals=None):
    """三列网格化卡片 — 极简机构版重构"""
    if my_stocks is None: my_stocks = []

    chg_color = "var(--up-color)" if change >= 0 else "var(--down-color)"
    chg_icon = "▲" if change >= 0 else "▼"
    in_wl = "⭐" if code in my_stocks else ""

    # ---- 信号数据 (Signals) ----
    signals = precomputed_signals if precomputed_signals else _get_quick_signals(code)

    # ---- 估值丝带计算 (Piecewise Mapping for Diversity) ----
    pe_pct, pb_pct = 50, 50
    try:
        import re
        # 优先使用实时信号中的 PE/PB
        pe_val = signals.get('pe', 0)
        pb_val = signals.get('pb', 0)
        
        # 兜底: 尝试从 extra 字符串解析
        if pe_val == 0:
            pe_val = float(re.findall(r'PE ([\d.]+)', extra)[0]) if 'PE' in extra else 0
        if pb_val == 0:
            pb_val = float(re.findall(r'PB ([\d.]+)', extra)[0]) if 'PB' in extra else 0
        
        # PE 映射: 非线性分位模拟器
        if pe_val > 0:
            if pe_val < 15: pe_pct = int(5 + pe_val * 0.8) # 5-17%
            elif pe_val < 30: pe_pct = int(17 + (pe_val - 15) * 1.5) # 17-40%
            elif pe_val < 60: pe_pct = int(40 + (pe_val - 30) * 1.3) # 40-79%
            else: pe_pct = min(100, int(80 + (pe_val - 60) * 0.2)) # 80-100%
            
        # PB 映射
        if pb_val > 0:
            if pb_val < 1.0: pb_pct = int(pb_val * 10) # 0-10%
            elif pb_val < 2.5: pb_pct = int(10 + (pb_val - 1.0) * 20) # 10-40%
            elif pb_val < 5.0: pb_pct = int(40 + (pb_val - 2.5) * 15) # 40-77%
            else: pb_pct = min(100, int(77 + (pb_val - 5.0) * 2)) # 77-100%
    except Exception:
        pass

    pe_color = "rgba(16, 185, 129, 0.8)" if pe_pct < 30 else ("rgba(245, 158, 11, 0.8)" if pe_pct < 60 else "rgba(239, 68, 68, 0.8)")
    pb_color = "rgba(16, 185, 129, 0.8)" if pb_pct < 30 else ("rgba(245, 158, 11, 0.8)" if pb_pct < 60 else "rgba(239, 68, 68, 0.8)")

    # 兜底: 依然为 0 则显示灰色 (e.g. 刚刚上市的新股)
    pe_is_data = True
    if pe_val <= 0:
        pe_is_data = False
        pe_pct = 0
        pe_color = "rgba(148, 163, 184, 0.3)"

    # ---- 信号 Pill (Signals UI) ----
    metrics_html = ""
    action_html = ""
    if show_signals:
        # 已在上方统一获取 signals
        action_color = "var(--up-color)" if signals['action_short'] == '买入' else ("var(--down-color)" if signals['action_short'] == '卖出' else "#94a3b8")
        action_bg = "rgba(239, 68, 68, 0.15)" if signals['action_short'] == '买入' else ("rgba(16, 185, 129, 0.15)" if signals['action_short'] == '卖出' else "rgba(148, 163, 184, 0.1)")
        
        action_html = f'<span class="status-pill" style="background:{action_bg}; color:{action_color};">{signals["action"]}</span>'
        
        # 紧凑指标 pill (取评分和量比)
        score_c = "var(--up-color)" if signals['score'] >= 4 else "var(--accent)"
        metrics_html = f'<div style="display:flex;gap:4px; margin-top:4px;">' \
                       f'<span class="status-pill" style="background:rgba(56,189,248,0.1); color:{score_c};">分{signals["score"]}</span>' \
                       f'<span class="status-pill" style="background:rgba(56,189,248,0.1); color:var(--accent);">量{signals["vol_ratio"]:.1f}x</span>' \
                       f'</div>'

    # ---- 最终卡片 HTML (Quantum Bridge v7.2) ----
    delay = f"{rank * 0.05}s" if rank else "0s"
    row_sector = sector
    
    # 构建分析标签 HTML
    tags_html = ""
    if show_signals:
        for t in signals.get('tags', []):
            tags_html += f'<span class="analysis-tag">{t}</span>'

    # 构建 PE 数值文本
    pe_display_pct = f"{pe_pct}%" if pe_is_data else "N/A"
    
    card_html = (
        f'<div class="signal-card" style="animation: fadeInUp 0.4s ease-out backwards; animation-delay: {delay};">'
        f'  <div class="card-header">'
        f'    <div style="display:flex; flex-direction:column;">'
        f'      <div class="card-title">{stock_name} {in_wl}</div>'
        f'      <div style="display:flex; align-items:center; gap:6px; margin-top:2px;">'
        f'        <span class="card-code">{code}</span>'
        f'        <span class="status-pill" style="background:rgba(56,189,248,0.1); color:var(--accent); font-weight:600; border:1px solid rgba(56,189,248,0.2);">{row_sector}</span>'
        f'        {action_html}'
        f'      </div>'
        f'    </div>'
        f'    <div class="card-price-area">'
        f'      <div class="card-price">¥{price:.2f}</div>'
        f'      <div class="card-change" style="color:{chg_color};">{chg_icon}{abs(change):.2f}%</div>'
        f'    </div>'
        f'  </div>'
        f'  <div style="display:flex; gap:4px; flex-wrap:wrap; margin-top:4px;">{tags_html}</div>'
        f'  {metrics_html}'
        f'  <div style="margin-top:auto;">'
        f'    <div class="ribbon-label"><span>PE 分位</span><span>{pe_display_pct}</span></div>'
        f'    <div class="valuation-ribbon"><div class="ribbon-bar" style="width:{pe_pct or 100}%; background:{pe_color};"></div></div>'
        f'    <div class="valuation-ribbon" style="height:2px; margin-top:2px;"><div class="ribbon-bar" style="width:{pb_pct}%; background:{pb_color};"></div></div>'
        f'  </div>'
        f'</div>'
    )
    
    st.markdown(card_html, unsafe_allow_html=True)

    # 底部操作按钮 (使用 PRO_SSM_V7_ 唯一 Key)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("📊分析", key=f"PRO_SSM_V7_{btn_prefix}_a_{code}", use_container_width=True):
            st.session_state['selected_stock'] = code
            st.session_state['market_view'] = 'analyze'
            st.rerun()
    with c2:
        if show_watchlist_btn and code not in my_stocks:
            if st.button("⭐加自选", key=f"PRO_SSM_V7_{btn_prefix}_w_{code}", use_container_width=True):
                my_stocks.append(code)
                save_watchlist(my_stocks)
                st.toast(f"✅ {stock_name} 已加入自选", icon="⭐")
                st.rerun()
        elif show_remove_btn:
             if st.button("🗑️移除", key=f"PRO_SSM_V7_{btn_prefix}_d_{code}", use_container_width=True):
                my_stocks.remove(code)
                save_watchlist(my_stocks)
                st.toast(f"{stock_name} 已从自选移除", icon="🗑️")
                st.rerun()
    with c3:
        st.button("⚙️", key=f"PRO_SSM_V7_{btn_prefix}_cfg_{code}", use_container_width=True)



# ============================================================
#  视图 1: 策略选股
# ============================================================
def _render_strategy_view(L, my_stocks, name_map):
    """策略选股视图 — pill按钮 + 紧凑行"""

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

    # ========== 策略标签页 (Strategy Dynamic Tabs) ==========
    tabs = st.tabs([f"{label}" for _, label, _, _ in strat_defs])
    
    for i, (key, label, desc, color) in enumerate(strat_defs):
        with tabs[i]:
            st.caption(f"📌 {desc}")
            
            if key == 'Hotspot':
                _render_tag_filter_bar()
                _render_hotspot_strategy(L, my_stocks, name_map)
            elif key == 'Concept':
                _render_concept_strategy(L, my_stocks, name_map)
            else:
                # Value, Momentum, Growth, Mainforce, Northbound, Breakout
                func_map = {
                    'Value': find_value_stocks,
                    'Momentum': find_momentum_stocks,
                    'Growth': find_growth_stocks,
                    'Mainforce': lambda: __import__('core.strategies', fromlist=['find_mainforce_stocks']).find_mainforce_stocks(),
                    'Northbound': lambda: __import__('core.strategies', fromlist=['find_northbound_top']).find_northbound_top(),
                    'Breakout': lambda: __import__('core.strategies', fromlist=['find_tech_breakout']).find_tech_breakout()
                }
                
                if key in func_map:
                    df = func_map[key]()
                    _render_generic_strategy_tab(key, df, my_stocks, name_map)
                else:
                    st.info("💡 该策略正在接入中...")


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

    with st.spinner("获取 赛道行情..."):
        df = find_hotspot_stocks(sel)

    if df.empty:
        st.info("暂无数据")
        return

    _render_generic_strategy_tab(f"hot_{sel if sel else 'all'}", df, my_stocks, name_map)


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
        options = filtered['name'].tolist()[:50]
        selected_concept = st.selectbox("选择具体板块", options, key="concept_select_box_v1")

    if selected_concept:
        with st.spinner(f"正在加载 {selected_concept} 成分股..."):
            # 获取对应的 code (Tushare 概念代码)
            matched = filtered[filtered['name'] == selected_concept]
            if not matched.empty:
                concept_id = str(matched['code'].iloc[0])
                df = find_concept_stocks_detail(concept_id, selected_concept)
                if not df.empty:
                    _render_generic_strategy_tab(f"concept_{concept_id}", df, my_stocks, name_map)
                else:
                    st.warning("该板块暂无成分股数据")


# ============================================================
#  股票列表渲染 (调用统一 _render_stock_row)
# ============================================================
def _render_tag_filter_bar():
    """标签快速选择条 — 提供基于行业或信号的极速过滤"""
    st.markdown("""<style>
        .tag-pill {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            background: rgba(56, 189, 248, 0.1);
            color: #38bdf8;
            font-size: 0.75rem;
            cursor: pointer;
            border: 1px solid rgba(56, 189, 248, 0.2);
            margin-right: 8px;
            margin-bottom: 8px;
            transition: all 0.2s;
        }
        .tag-pill:hover {
            background: rgba(56, 189, 248, 0.2);
            border-color: #38bdf8;
        }
        .tag-pill.active {
            background: #38bdf8;
            color: #0f172a;
            font-weight: 700;
        }
    </style>""", unsafe_allow_html=True)

    tags = ["全部", "🤖 机器人", "🛩️ 低空经济", "⚡ AI算力", "🔋 固态电池", "🧬 创新药", "🌐 数据要素", "🔥 热门概念"]
    
    if 'active_tag' not in st.session_state:
        st.session_state['active_tag'] = "全部"
        
    cols = st.columns(len(tags))
    for i, tag in enumerate(tags):
        with cols[i]:
            is_active = st.session_state['active_tag'] == tag
            if st.button(tag, key=f"tag_filter_{i}", use_container_width=True, 
                        type="primary" if is_active else "secondary"):
                st.session_state['active_tag'] = tag
                # 如果选择了具体标签，自动尝试对应到热点赛道
                mapping = {
                    "🤖 机器人": "robot", "🛩️ 低空经济": "low_alt", "⚡ AI算力": "ai_power",
                    "🔋 固态电池": "solid_bat", "🧬 创新药": "bio_drug", "🌐 数据要素": "data_elem"
                }
                if tag in mapping:
                    st.session_state['capture_strat'] = 'Hotspot'
                    st.session_state['hotspot_sector'] = mapping[tag]
                elif tag == "全部":
                    st.session_state['capture_strat'] = 'Hotspot'
                    st.session_state['hotspot_sector'] = None
                st.rerun()

def _render_stock_list(df, my_stocks, name_map):
    """三列网格化渲染 — 增加标签过滤逻辑"""
    active_tag = st.session_state.get('active_tag', "全部")
    if active_tag != "全部" and '板块' in df.columns:
        # 去掉 emoji 后的名称匹配
        clean_tag = active_tag.split(' ')[-1]
        df = df[df['板块'].str.contains(clean_tag, na=False)]

    if df.empty:
        st.info(f"没有找到属于「{active_tag}」标签的个股")
        return

    cols_per_row = 3
    for i in range(0, len(df), cols_per_row):
        cols = st.columns(cols_per_row)
        chunk = df.iloc[i : i + cols_per_row]
        
        for idx_in_row, (idx, row) in enumerate(chunk.iterrows()):
            with cols[idx_in_row]:
                rank = i + idx_in_row + 1
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

                # 提取估值与板块
                pe = row.get('PE', row.get('市盈率', 0))
                pb = row.get('PB', row.get('市净率', 0))
                extra_val = f"PE {pe} PB {pb}" if pe else ""
                sector = row.get('板块', '概念挖掘')

                _render_stock_card(
                    code, stock_name, price, change,
                    rank=rank, extra=extra_val, sector=sector, my_stocks=my_stocks,
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

    # ---- 返回列表按钮 (Universal Navigation Back) ----
    if st.button("⬅️ 返回策略列表", key="back_to_strat"):
        st.session_state['market_view'] = '📋 策略选股'
        st.rerun()

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

    # ========== 渲染 — 机构版网格自愈逻辑 ==========
    cols_per_row = 3
    for i in range(0, len(stock_data), cols_per_row):
        cols = st.columns(cols_per_row)
        chunk = stock_data[i : i + cols_per_row]
        
        for idx_in_row, item in enumerate(chunk):
            with cols[idx_in_row]:
                _render_stock_card(
                    item['code'], item['name'], item['price'], item['change'],
                    my_stocks=my_stocks, btn_prefix=f"tk{i+idx_in_row}",
                    show_signals=True, show_watchlist_btn=False, show_remove_btn=True
                )


# ============================================================
#  技术信号计算
# ============================================================
@st.cache_data(ttl=600, show_spinner=False)
def _get_quick_signals(code: str) -> dict:
    """
    轻量级技术信号 (缓存 10min) - 统一 DNA 引擎版
    """
    import numpy as np
    from modules.data_loader import fetch_kline
    from modules.quant import calculate_metrics, calculate_all_indicators
    from modules.analysis.dna_engine import get_dna_score
    from core.tushare_client import get_ts_client

    default = {'status': '—', 'buy': '—', 'sell': '—', 'action': '—', 'action_short': '观望',
                'rsi': 50, 'vol_ratio': 1.0, 'score': 0, 'ma_pos': '—', 'macd_dir': '—', 'tags': []}
    try:
        full = ("sh" if code.startswith('6') else "sz") + code
        kline = fetch_kline(full, period='daily', datalen=100)
        if kline is None or kline.empty or len(kline) < 20:
            return default

        # 1. 统一指标计算
        kline = calculate_all_indicators(kline)
        q_metrics = calculate_metrics(kline)
        
        latest = kline.iloc[-1]
        prev = kline.iloc[-2]
        close = float(latest['收盘'])
        prev_close = float(prev['收盘'])
        day_change = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0
        
        # 量比计算
        vol = float(latest['成交量'])
        vol_avg5 = kline['成交量'].tail(5).mean()
        vol_ratio = round(vol / vol_avg5, 2) if vol_avg5 > 0 else 1.0

        # 2. 统一 DNA 算法评分 (-10 to +10)
        score = get_dna_score(q_metrics, day_change, vol_ratio)

        # 3. 状态及买卖点映射
        if score >= 3:
            status = "看多 🚀"
            buy = "建议布局"
            action = "🟢 逢低加仓" if score >= 6 else "🔵 持有为主"
            action_short = "买入"
        elif score <= -3:
            status = "看空 📉"
            buy = "暂缓进场"
            action = "🔴 警惕风险" if score <= -6 else "⚪ 止盈避险"
            action_short = "卖出"
        else:
            status = "震荡 ↔️"
            buy = "观望"
            action = "🟡 箱体震荡"
            action_short = "观望"

        # 4. 辅助指标
        ma_pos = '多头' if q_metrics.get('ma_trend') == 'up' else '回调'
        macd_val = q_metrics.get('macd_hist', 0)
        macd_dir = '红轴' if macd_val > 0 else '绿轴'
        
        # 5. 获取 Tushare 估值
        pe_val_db, pb_val_db = 0, 0
        ts = get_ts_client()
        if ts.available:
            basic = ts.get_daily_basic(code, limit=1)
            if basic is not None and not basic.empty:
                pe_val_db = float(basic.iloc[0].get('pe_ttm') or basic.iloc[0].get('pe') or 0)
                pb_val_db = float(basic.iloc[0].get('pb') or 0)

        # 6. 分析标签 (Refined from q_metrics)
        tags = []
        if score >= 5: tags.append("💎 机构看好")
        elif score <= -5: tags.append("⚠️ 风险提示")
        
        rsi_val = q_metrics.get('rsi', 50)
        if rsi_val < 30: tags.append("🟢 RSI超卖")
        elif rsi_val > 75: tags.append("🔴 RSI超买")
        
        if vol_ratio > 1.8: tags.append("🔥 放量突破")
        elif vol_ratio < 0.6: tags.append("❄️ 缩量调整")
        
        if day_change > 4: tags.append("🚀 走势强劲")
        
        # 补充均线位置
        if ma_pos == '多头': tags.append("📈 趋势多头")

        return {
            'status': status, 'buy': buy, 'sell': '一般' if score > -3 else '风险', 
            'action': action, 'action_short': action_short,
            'rsi': rsi_val, 'vol_ratio': vol_ratio, 'score': score,
            'ma_pos': ma_pos, 'macd_dir': macd_dir, 'tags': tags[:8],
            'pe': pe_val_db, 'pb': pb_val_db
        }
    except Exception:
        return default
    except Exception:
        return default
# ============================================================
#  批量信号处理引擎 (Batch Intelligence Engine)
# ============================================================
def _batch_get_all_signals(codes: list) -> dict:
    """多线程并发计算所有标的的实时信号 (加速秒开)"""
    import concurrent.futures
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_code = {executor.submit(_get_quick_signals, c): c for c in codes}
        for future in concurrent.futures.as_completed(future_to_code):
            c = future_to_code[future]
            try:
                results[c] = future.result()
            except Exception:
                results[c] = {'tags': [], 'action_short': '观望', 'score': 0, 'vol_ratio': 1.0, 'action': '—'}
    return results

def _render_generic_strategy_tab(key, df, my_stocks, name_map):
    """通用策略标签页渲染逻辑 (带过滤)"""
    if df.empty:
        st.info("💡 暂时没有符合该策略的标的。")
        return

    # 1. 预计算所有信号
    codes = df['代码'].astype(str).tolist()
    all_signals = _batch_get_all_signals(codes)
    
    # 2. 收集所有可用标签用于过滤
    all_available_tags = set()
    for s_data in all_signals.values():
        all_available_tags.update(s_data.get('tags', []))
    
    # 3. 过滤 UI
    col_f1, col_f2 = st.columns([4, 1])
    with col_f1:
        f_tags = st.multiselect("🔍 标签过滤 (多选并集)", sorted(list(all_available_tags)), 
                               key=f"filter_{key}", help="仅显示包含所选标签的标的")
    with col_f2:
        st.markdown(f'<div style="text-align:right; color:#64748b; padding-top:28px;">{len(df)} 支</div>', unsafe_allow_html=True)

    # 4. 执行过滤
    display_df = df
    if f_tags:
        filtered_codes = []
        for c, s_data in all_signals.items():
            if any(t in s_data.get('tags', []) for t in f_tags):
                filtered_codes.append(c)
        display_df = df[df['代码'].astype(str).isin(filtered_codes)]
        st.caption(f"✨ 过滤后匹配 {len(display_df)} 支")

    # 5. 渲染与状态保存 (Render & State preservation for Analysis)
    if not display_df.empty:
        # 保存当前列表到 session_state 供 "深度分析" 视图进行 上一只/下一只 导航
        st.session_state['_strat_list'] = display_df['代码'].astype(str).tolist()
        
        # 重写渲染循环以使用预计算的 all_signals
        cols_per_row = 3
        for i in range(0, len(display_df), cols_per_row):
            cols = st.columns(cols_per_row)
            chunk = display_df.iloc[i : i + cols_per_row]
            for idx_in_row, (_, row) in enumerate(chunk.iterrows()):
                with cols[idx_in_row]:
                    code = str(row.get('代码', ''))
                    # 模拟 _render_stock_list 的参数提取
                    price = float(row.get('最新价', 0))
                    change = float(row.get('涨跌幅', 0))
                    sector = row.get('板块', '概念挖掘')
                    pe = row.get('PE', row.get('市盈率', 0))
                    pb = row.get('PB', row.get('市净率', 0))
                    extra_val = f"PE {pe} PB {pb}" if pe else ""
                    
                    _render_stock_card(
                        code, str(row.get('名称', '')), price, change,
                        rank=i+idx_in_row+1, extra=extra_val, sector=sector,
                        my_stocks=my_stocks, name_map=name_map, btn_prefix=f"strat_{key}_{i+idx_in_row}",
                        precomputed_signals=all_signals.get(code)
                    )
    else:
        st.warning("🏮 没有匹配过滤条件的标的")
