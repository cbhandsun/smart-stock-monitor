"""
股票卡片渲染 — market 子包
_render_stock_card: 单张 3 列网格卡片
_render_stock_list: 批量列表渲染
_render_tag_filter_bar: 标签快速过滤条
_render_generic_strategy_tab: 通用策略标签页
"""
import re
import streamlit as st


def _render_stock_card(code, stock_name, price, change, rank=0, extra="",
                       sector="概念挖掘", my_stocks=None, name_map=None, show_signals=True,
                       btn_prefix="s", show_watchlist_btn=True, show_remove_btn=False,
                       precomputed_signals=None):
    """三列网格化卡片 — 极简机构版"""
    from pages.market._signals import _get_quick_signals
    from pages import save_watchlist

    if my_stocks is None:
        my_stocks = []

    chg_color = "var(--up-color)" if change >= 0 else "var(--down-color)"
    chg_icon = "▲" if change >= 0 else "▼"
    in_wl = "⭐" if code in my_stocks else ""

    signals = precomputed_signals if precomputed_signals else _get_quick_signals(code)

    # ---- 估值丝带 ----
    pe_pct, pb_pct = 50, 50
    try:
        pe_val = signals.get('pe', 0)
        pb_val = signals.get('pb', 0)
        if pe_val == 0:
            pe_val = float(re.findall(r'PE ([\d.]+)', extra)[0]) if 'PE' in extra else 0
        if pb_val == 0:
            pb_val = float(re.findall(r'PB ([\d.]+)', extra)[0]) if 'PB' in extra else 0

        if pe_val > 0:
            if pe_val < 15:   pe_pct = int(5 + pe_val * 0.8)
            elif pe_val < 30: pe_pct = int(17 + (pe_val - 15) * 1.5)
            elif pe_val < 60: pe_pct = int(40 + (pe_val - 30) * 1.3)
            else:             pe_pct = min(100, int(80 + (pe_val - 60) * 0.2))

        if pb_val > 0:
            if pb_val < 1.0:   pb_pct = int(pb_val * 10)
            elif pb_val < 2.5: pb_pct = int(10 + (pb_val - 1.0) * 20)
            elif pb_val < 5.0: pb_pct = int(40 + (pb_val - 2.5) * 15)
            else:              pb_pct = min(100, int(77 + (pb_val - 5.0) * 2))
    except Exception:
        pass

    pe_color = ("rgba(16, 185, 129, 0.8)" if pe_pct < 30
                else "rgba(245, 158, 11, 0.8)" if pe_pct < 60
                else "rgba(239, 68, 68, 0.8)")
    pb_color = ("rgba(16, 185, 129, 0.8)" if pb_pct < 30
                else "rgba(245, 158, 11, 0.8)" if pb_pct < 60
                else "rgba(239, 68, 68, 0.8)")

    pe_is_data = True
    if pe_val <= 0:
        pe_is_data = False
        pe_pct = 0
        pe_color = "rgba(148, 163, 184, 0.3)"

    # ---- 信号 Pill ----
    metrics_html = ""
    action_html = ""
    if show_signals:
        action_color = ("var(--up-color)" if signals['action_short'] == '买入'
                        else "var(--down-color)" if signals['action_short'] == '卖出'
                        else "#94a3b8")
        action_bg = ("rgba(239, 68, 68, 0.15)" if signals['action_short'] == '买入'
                     else "rgba(16, 185, 129, 0.15)" if signals['action_short'] == '卖出'
                     else "rgba(148, 163, 184, 0.1)")
        action_html = f'<span class="status-pill" style="background:{action_bg}; color:{action_color};">{signals["action"]}</span>'

        score_c = "var(--up-color)" if signals['score'] >= 4 else "var(--accent)"
        metrics_html = (
            f'<div style="display:flex;gap:4px; margin-top:4px;">'
            f'<span class="status-pill" style="background:rgba(56,189,248,0.1); color:{score_c};">分{signals["score"]}</span>'
            f'<span class="status-pill" style="background:rgba(56,189,248,0.1); color:var(--accent);">量{signals["vol_ratio"]:.1f}x</span>'
            f'</div>'
        )

    delay = f"{rank * 0.05}s" if rank else "0s"

    tags_html = ""
    if show_signals:
        for t in signals.get('tags', []):
            tags_html += f'<span class="analysis-tag">{t}</span>'

    pe_display_pct = f"{pe_pct}%" if pe_is_data else "N/A"

    card_html = (
        f'<div class="signal-card" style="animation: fadeInUp 0.4s ease-out backwards; animation-delay: {delay};">'
        f'  <div class="card-header">'
        f'    <div style="display:flex; flex-direction:column;">'
        f'      <div class="card-title">{stock_name} {in_wl}</div>'
        f'      <div style="display:flex; align-items:center; gap:6px; margin-top:2px;">'
        f'        <span class="card-code">{code}</span>'
        f'        <span class="status-pill" style="background:rgba(56,189,248,0.1); color:var(--accent); font-weight:600; border:1px solid rgba(56,189,248,0.2);">{sector}</span>'
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
    st.html(card_html)

    # ---- 操作按钮区 (分析 主操作 | 自选 + 设置 辅操作) ----
    btn_a, btn_b = st.columns([3, 2])
    with btn_a:
        if st.button("📊 深度分析", key=f"PRO_SSM_V7_{btn_prefix}_a_{code}",
                     use_container_width=True, type="primary"):
            st.session_state['selected_stock'] = code
            st.session_state['market_view'] = '📊 深度分析'
            st.rerun()
    with btn_b:
        if show_watchlist_btn and code not in my_stocks:
            if st.button("⭐", key=f"PRO_SSM_V7_{btn_prefix}_w_{code}",
                         use_container_width=True, help=f"加入自选: {stock_name}"):
                my_stocks.append(code)
                save_watchlist(my_stocks)
                st.toast(f"✅ {stock_name} 已加入自选", icon="⭐")
                st.rerun()
        elif show_remove_btn:
            if st.button("🗑️", key=f"PRO_SSM_V7_{btn_prefix}_d_{code}",
                         use_container_width=True, help=f"移除: {stock_name}"):
                my_stocks.remove(code)
                save_watchlist(my_stocks)
                st.toast(f"{stock_name} 已移出自选", icon="🗑️")
                st.rerun()
        else:
            st.button("✓ 已选", key=f"PRO_SSM_V7_{btn_prefix}_in_{code}",
                      use_container_width=True, disabled=True)


def _render_stock_list(df, my_stocks, name_map):
    """三列网格化渲染 — 增加标签过滤逻辑"""
    active_tag = st.session_state.get('active_tag', "全部")
    if active_tag != "全部" and '板块' in df.columns:
        clean_tag = active_tag.split(' ')[-1]
        df = df[df['板块'].str.contains(clean_tag, na=False)]

    if df.empty:
        st.info(f"没有找到属于「{active_tag}」标签的个股")
        return

    cols_per_row = 3
    for i in range(0, len(df), cols_per_row):
        cols = st.columns(cols_per_row)
        chunk = df.iloc[i: i + cols_per_row]
        for idx_in_row, (_, row) in enumerate(chunk.iterrows()):
            with cols[idx_in_row]:
                rank = i + idx_in_row + 1
                code = str(row.get('代码', ''))
                try:    price = float(row.get('最新价', 0))
                except: price = 0.0
                try:    change = float(row.get('涨跌幅', 0))
                except: change = 0.0

                pe = row.get('PE', row.get('市盈率', 0))
                pb = row.get('PB', row.get('市净率', 0))
                extra_val = f"PE {pe} PB {pb}" if pe else ""
                sector = row.get('板块', '概念挖掘')

                _render_stock_card(
                    code, str(row.get('名称', '')), price, change,
                    rank=rank, extra=extra_val, sector=sector, my_stocks=my_stocks,
                    btn_prefix=f"sl{rank}", show_signals=True
                )


def _render_tag_filter_bar():
    """标签快速选择条"""
    st.markdown("""<style>
        .tag-pill {
            display: inline-block; padding: 4px 12px; border-radius: 20px;
            background: rgba(56, 189, 248, 0.1); color: #38bdf8;
            font-size: 0.75rem; cursor: pointer;
            border: 1px solid rgba(56, 189, 248, 0.2);
            margin-right: 8px; margin-bottom: 8px; transition: all 0.2s;
        }
        .tag-pill:hover { background: rgba(56, 189, 248, 0.2); border-color: #38bdf8; }
        .tag-pill.active { background: #38bdf8; color: #0f172a; font-weight: 700; }
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


def _render_generic_strategy_tab(key, df, my_stocks, name_map):
    """通用策略标签页 — 批量信号预计算 + 标签过滤 + 网格渲染"""
    from pages.market._signals import _batch_get_all_signals

    if df is None or df.empty:
        st.info("📭 暂无匹配数据，请稍后重试或切换策略")
        return

    codes = df['代码'].astype(str).tolist()

    with st.spinner(f"⚡ 量化引擎计算中 ({len(codes)} 支)..."):
        all_signals = _batch_get_all_signals(codes)

    all_available_tags = set()
    for sig in all_signals.values():
        all_available_tags.update(sig.get('tags', []))

    st.markdown("---")
    sc1, sc2, sc3 = st.columns([1.5, 3, 1])

    preset_strategies = {
        "💡 自定义 (不套用)": [],
        "🎣 抄底猎手 (寻找超跌错杀)": ["🔮 极度超卖(底部反转?)", "🟢 RSI超卖(寻底)", "🧊 极致地量"],
        "🚀 突破跟随 (右侧追击)":    ["🌋 巨量爆发", "🔥 放量突破", "🚀 火箭发射", "📈 走势强劲", "🐉 MACD强多头"],
        "💎 价值低吸 (多头回调)":    ["💎 机构看好", "🛡️ 均线多头(支撑强)", "❄️ 缩量洗盘", "🟢 RSI超卖(寻底)"],
        "⚠️ 短线避险 (规避高位空头)": ["🌪️ 极度超买(见顶风险)", "🔴 RSI超买(高位)", "🐻 MACD强空头", "🥀 均线空头(阻力大)", "⚠️ 风险提示"],
    }

    with sc1:
        st.markdown("<p style='font-size:0.85rem; color:#94a3b8; margin-bottom:2px;'>👑 一键策略组合</p>", unsafe_allow_html=True)
        selected_preset = st.selectbox("一键策略组合", list(preset_strategies.keys()),
                                       label_visibility="collapsed", key=f"preset_{key}")

    with sc2:
        st.markdown("<p style='font-size:0.85rem; color:#94a3b8; margin-bottom:2px;'>🔍 标签过滤 (多选并集)</p>", unsafe_allow_html=True)
        preset_tags = preset_strategies[selected_preset]
        default_tags = [t for t in preset_tags if t in all_available_tags] if preset_tags else []
        f_tags = st.multiselect("标签过滤", sorted(list(all_available_tags)), default=default_tags,
                                key=f"filter_{key}", label_visibility="collapsed",
                                help="仅显示包含所选标签的标的. '一键策略'会自动帮你勾选有关联的标签！")

    with sc3:
        st.markdown(f'<div style="text-align:right; color:#64748b; margin-top:30px;">总计 {len(df)} 支</div>',
                    unsafe_allow_html=True)

    display_df = df
    if f_tags:
        filtered_codes = [c for c, s in all_signals.items()
                          if any(t in s.get('tags', []) for t in f_tags)]
        display_df = df[df['代码'].astype(str).isin(filtered_codes)]
        st.caption(f"✨ 过滤后匹配 {len(display_df)} 支")

    if not display_df.empty:
        st.session_state['_strat_list'] = display_df['代码'].astype(str).tolist()
        cols_per_row = 3
        for i in range(0, len(display_df), cols_per_row):
            cols = st.columns(cols_per_row)
            chunk = display_df.iloc[i: i + cols_per_row]
            for idx_in_row, (_, row) in enumerate(chunk.iterrows()):
                with cols[idx_in_row]:
                    code = str(row.get('代码', ''))
                    try:    price = float(row.get('最新价', 0))
                    except: price = 0.0
                    try:    change = float(row.get('涨跌幅', 0))
                    except: change = 0.0
                    sector = row.get('板块', '概念挖掘')
                    pe = row.get('PE', row.get('市盈率', 0))
                    pb = row.get('PB', row.get('市净率', 0))
                    extra_val = f"PE {pe} PB {pb}" if pe else ""

                    _render_stock_card(
                        code, str(row.get('名称', '')), price, change,
                        rank=i + idx_in_row + 1, extra=extra_val, sector=sector,
                        my_stocks=my_stocks, name_map=name_map,
                        btn_prefix=f"strat_{key}_{i + idx_in_row}",
                        precomputed_signals=all_signals.get(code)
                    )
    else:
        st.warning("🏮 没有匹配过滤条件的标的")
