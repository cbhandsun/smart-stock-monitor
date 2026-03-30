import streamlit as st
import plotly.graph_objects as go
import os
import datetime

from main import get_stock_names_batch, generate_ai_report, generate_ai_report_stream
from modules.data_loader import fetch_kline, fetch_trading_signals, fetch_research_reports
from pages import save_watchlist, load_cached_report, REPORT_DIR

# conditional imports
try:
    from modules.fundamentals import get_financial_health_score
    from modules.quant import calculate_metrics, calculate_all_indicators
    from modules.analysis.dna_engine import get_dna_score, generate_tech_analysis
    from utils.charts import create_candlestick_chart
    from utils.tv_charts import render_tv_chart
except ImportError:
    get_financial_health_score = None
    calculate_metrics = None
    calculate_all_indicators = None
    get_dna_score = None
    generate_tech_analysis = None
    create_candlestick_chart = None
    render_tv_chart = None


def _render_daily_info(full_symbol, stock_name):
    """渲染当日基本信息面板 (Standardized v7.1)"""
    import requests
    try:
        from core.cache import RedisCache
        _rc = RedisCache()
        cache_key = f"quote:daily:{full_symbol}"
        quote = _rc.get(cache_key)

        if not quote:
            url = f"https://hq.sinajs.cn/list={full_symbol}"
            headers = {'Referer': 'https://finance.sina.com.cn/'}
            r = requests.get(url, headers=headers, timeout=5)
            raw = r.text.strip()
            if '="' not in raw or raw.endswith('=""'): return
            parts = raw.split('="')[1].strip('"').split(',')
            if len(parts) < 32: return
            quote = {
                'price': float(parts[3] or 0),
                'open': float(parts[1] or 0),
                'prev_close': float(parts[2] or 0),
                'high': float(parts[4] or 0),
                'low': float(parts[5] or 0),
                'amount': float(parts[9] or 0),
                'volume': float(parts[8] or 0),
            }
            pc = quote['prev_close']
            if pc > 0:
                quote['change_pct'] = (quote['price'] - pc) / pc * 100
                quote['amplitude'] = (quote['high'] - quote['low']) / pc * 100
            _rc.set(cache_key, quote, expire=30)

        price = quote['price']
        if price <= 0: return
        chg_pct = quote['change_pct']
        color = "var(--up-color)" if chg_pct >= 0 else "var(--down-color)"
        arrow = "▲" if chg_pct >= 0 else "▼"

        # Valuation Calculation
        pe_pct, pb_pct = 50, 50
        try:
            from core.tushare_client import get_ts_client
            ts = get_ts_client()
            if ts.available:
                db_data = ts.get_daily_basic(full_symbol.split('s')[-1])
                if db_data is not None and not db_data.empty:
                    pe_val = float(db_data.iloc[-1].get('pe', 0))
                    pb_val = float(db_data.iloc[-1].get('pb', 0))
                    pe_pct = min(100, max(5, int(pe_val * 2)))
                    pb_pct = min(100, max(5, int(pb_val * 20)))
        except: pass

        pe_color = "var(--accent)" if pe_pct < 40 else ("#f59e0b" if pe_pct < 70 else "var(--up-color)")

        html = f"""<div class="dna-quote-card">
    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
            <div style="color:#64748b; font-size:0.7rem; margin-bottom:4px;">REAL-TIME QUOTE</div>
            <div style="display:flex; align-items:baseline; gap:12px;">
                <span style="font-family:'JetBrains Mono',sans-serif; font-size:2.2rem; font-weight:800; color:{color};">¥{price:.2f}</span>
                <span style="color:{color}; font-size:1.1rem; font-weight:700;">{arrow}{abs(quote['price'] - quote['prev_close']):.2f} ({chg_pct:+.2f}%)</span>
            </div>
        </div>
        <div style="text-align:right;">
             <div style="color:#f8fafc; font-size:0.95rem; font-weight:700;">成交额 {quote['amount']/1e8:.2f}亿</div>
             <div style="color:#64748b; font-size:0.75rem;">振幅 {quote['amplitude']:.2f}%</div>
        </div>
    </div>
    <div style="margin-top:20px;">
        <div class="ribbon-label"><span>💎 机构估值分位 (PE Ribbon)</span><span>风险权重: {pe_pct}%</span></div>
        <div class="valuation-ribbon" style="height:6px; background:rgba(255,255,255,0.05);">
            <div class="ribbon-bar" style="width:{pe_pct}%; background:{pe_color}; box-shadow: 0 0 10px {pe_color}66;"></div>
        </div>
    </div>
    <div style="display:flex; gap:24px; margin-top:20px; padding-top:15px; border-top:1px solid rgba(255,255,255,0.05);">
        <div><div class="dna-price-label">最高/最低</div><div class="dna-price-val">{quote['high']:.2f} / {quote['low']:.2f}</div></div>
        <div><div class="dna-price-label">今开/昨收</div><div class="dna-price-val">{quote['open']:.2f} / {quote['prev_close']:.2f}</div></div>
        <div><div class="dna-price-label">成交额</div><div class="dna-price-val">{quote['amount']/1e8:.2f} 亿</div></div>
    </div>
</div>"""
        st.markdown(html, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Quote Redner Error: {e}")
    except Exception:
        pass


def _create_indicator_chart(data, name, theme="dark"):
    """创建技术指标副图"""
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    fig = go.Figure()

    if name == 'MACD':
        fig.add_trace(go.Bar(
            x=data['日期'], y=data['MACD_Hist'], name='Histogram',
            marker_color=['#ef4444' if v < 0 else '#10b981' for v in data['MACD_Hist']]
        ))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['MACD'], name='MACD', line=dict(color='#3b82f6')))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['MACD_Signal'], name='Signal', line=dict(color='#f59e0b')))
    elif name == 'KDJ':
        fig.add_trace(go.Scatter(x=data['日期'], y=data['KDJ_K'], name='K', line=dict(color='#3b82f6')))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['KDJ_D'], name='D', line=dict(color='#f59e0b')))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['KDJ_J'], name='J', line=dict(color='#ec4899')))
        fig.add_hline(y=80, line_dash="dash", line_color="red")
        fig.add_hline(y=20, line_dash="dash", line_color="green")
    elif name == 'RSI':
        fig.add_trace(go.Scatter(x=data['日期'], y=data['RSI'], name='RSI', line=dict(color='#3b82f6', fill='tozeroy')))
        fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="超买")
        fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超卖")
    elif name == 'CCI':
        fig.add_trace(go.Scatter(x=data['日期'], y=data['CCI'], name='CCI', line=dict(color='#8b5cf6')))
        fig.add_hline(y=100, line_dash="dash", line_color="red")
        fig.add_hline(y=-100, line_dash="dash", line_color="green")

    fig.update_layout(
        template=template, height=200,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def _render_tech_observation(kline, q_metrics, stock_name, stock_code):
    """渲染深度技术分析面板 (Cleaned v7.2)"""
    if generate_tech_analysis is None: return
    
    k_analysis, indicators, score, levels, advice = generate_tech_analysis(kline, q_metrics)
    
    def _to_html(items):
        return "".join([f'<div style="margin-bottom:6px; color:#cbd5e1;">• {item}</div>' for item in items])

    signal_color = "#10b981" if score >= 3 else ("#ef4444" if score <= -3 else "#f59e0b")
    signal_text = "核心看多" if score >= 3 else ("风险警示" if score <= -3 else "中性观望")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""<div class="dna-tech-box">
<div style="font-weight:800; color:#f8fafc; margin-bottom:15px; font-size:1.1rem;">🔬 技术形态扫描</div>
{_to_html(k_analysis)}
<div style="margin-top:20px; padding-top:15px; border-top:1px solid rgba(255,255,255,0.05);">
<div style="font-weight:700; color:#94a3b8; margin-bottom:10px;">📉 指标研判</div>
{_to_html(indicators)}
</div>
</div>""", unsafe_allow_html=True)
    
    with c2:
        st.markdown(f"""<div class="dna-tech-box" style="border-left: 4px solid {signal_color};">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
<span style="font-weight:800; color:#f8fafc; font-size:1.1rem;">🎯 决策建议</span>
<span class="status-pill" style="background:{signal_color}22; color:{signal_color}; padding:4px 10px;">{signal_text}</span>
</div>
<div style="font-size:2.5rem; font-weight:800; color:{signal_color}; text-align:center; margin:15px 0;">{score:+=d}</div>
<div style="background:rgba(255,255,255,0.03); border-radius:8px; padding:12px; margin-bottom:20px;">
<div style="color:#e2e8f0; font-size:0.95rem; line-height:1.5;">{advice}</div>
</div>
<div style="margin-top:20px; padding-top:15px; border-top:1px solid rgba(255,255,255,0.05);">
<div style="font-weight:700; color:#94a3b8; margin-bottom:10px;">📍 关键价位</div>
{_to_html(levels)}
</div>
</div>""", unsafe_allow_html=True)



def render_dna_analyzer(L, my_stocks, name_map, default_target=None):
    """
    渲染 DNA Analyzer (可嵌入任意页面)
    使用 Tabs 组织信息层级：行情走势 | 技术分析 | AI 研判
    """
    st.divider()

    # ---- 标的选择 + 刷新 (始终可见，不放在 Tab 里) ----
    target = default_target if default_target else st.session_state.get('selected_stock', '601318')
    if target not in my_stocks:
        my_stocks_dropdown = [target] + my_stocks
        if target not in name_map:
            new_names = get_stock_names_batch([target])
            name_map.update(new_names)
    else:
        my_stocks_dropdown = my_stocks

    hdr_col, sel_col, refresh_col = st.columns([3, 2, 1])
    with hdr_col:
        st.markdown(f"### <span style='color:var(--accent); font-family:Outfit;'>DNA</span> {L.get('dna_analysis', '深度决策中心')}", unsafe_allow_html=True)
    with sel_col:
        sel_stock = st.selectbox(
            "标的", my_stocks_dropdown,
            index=my_stocks_dropdown.index(target) if target in my_stocks_dropdown else 0,
            format_func=lambda x: f"{x} {name_map.get(x, '')}",
            label_visibility="collapsed",
            key=f"PRO_SSM_V7_DNA_selector"
        )
        st.session_state['selected_stock'] = sel_stock
    with refresh_col:
        if st.button("🔄", key=f"PRO_SSM_V7_DNA_refresh", use_container_width=True, help="刷新当前标的"):
            st.cache_data.clear()
            st.toast(f"📊 {sel_stock} 数据已刷新", icon="✨")
            st.rerun()

    # ---- 数据获取 (所有 Tab 共享) ----
    if 'selected_period' not in st.session_state:
        st.session_state['selected_period'] = 'daily'
    if 'selected_indicators' not in st.session_state:
        st.session_state['selected_indicators'] = ['MA']

    selected_period = st.session_state.get('selected_period', 'daily')
    full_symbol = "sh" + sel_stock if sel_stock.startswith('6') else "sz" + sel_stock
    kline = fetch_kline(full_symbol, period=selected_period, datalen=100)

    if not kline.empty and calculate_all_indicators:
        kline = calculate_all_indicators(kline)

    f_data = get_financial_health_score(sel_stock) if get_financial_health_score else None
    q_metrics = calculate_metrics(kline) if calculate_metrics else {}

    # 获取高级指标 (10000 积分尊享)
    db_data = None
    try:
        from core.tushare_client import get_ts_client
        ts = get_ts_client()
        if ts.available:
            db_data = ts.get_daily_basic(sel_stock)
    except Exception:
        pass

    # ========== 七大 Tab ==========
    tab_chart, tab_tech, tab_fund, tab_dragon, tab_finance, tab_ai, tab_profile = st.tabs(
        ["📊 走势", "🔬 技术", "💰 资金", "🐉 龙虎", "📈 财务", "🤖 AI", "🏢 简介"])

    # -------- Tab 1: 行情走势 --------
    with tab_chart:
        # 时间周期选择器 (紧凑行内)
        # 时间周期选择器 (Quantum Pills)
        period_cols = st.columns(8)
        periods = ['1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly']
        period_labels = ['1分', '5分', '15分', '30分', '60分', '日线', '周线', '月线']

        for i, (period, label) in enumerate(zip(periods, period_labels)):
            with period_cols[i]:
                if st.button(label, key=f"PRO_SSM_V7_DNA_period_{period}",
                            type="primary" if st.session_state['selected_period'] == period else "secondary",
                            use_container_width=True):
                    st.session_state['selected_period'] = period
                    st.rerun()

        # 均线叠加选择 (Quantum Pills)
        ind_cols = st.columns(6)
        available_indicators = {'MA': '均线', 'BB': '布林带', 'MACD': 'MACD', 'KDJ': 'KDJ', 'RSI': 'RSI', 'CCI': 'CCI'}
        for i, (key, label) in enumerate(available_indicators.items()):
            with ind_cols[i]:
                is_selected = key in st.session_state['selected_indicators']
                if st.button(label, key=f"PRO_SSM_V7_DNA_ind_{key}",
                            type="primary" if is_selected else "secondary",
                            use_container_width=True):
                    if is_selected:
                        st.session_state['selected_indicators'].remove(key)
                    else:
                        st.session_state['selected_indicators'].append(key)
                    st.rerun()

        # ---- 当日基本信息面板 ----
        _render_daily_info(full_symbol, name_map.get(sel_stock, sel_stock))

        # K线图
        if not kline.empty and render_tv_chart:
            indicators_to_show = []
            selected_indicators = st.session_state.get('selected_indicators', ['MA'])

            if 'MA' in selected_indicators:
                indicators_to_show.extend(['MA5', 'MA20', 'MA60'])
            if 'BB' in selected_indicators and 'BB_Upper' in kline.columns:
                indicators_to_show.extend(['BB_Upper', 'BB_Middle', 'BB_Lower'])

            theme_str = st.session_state.get('theme', 'dark')
            render_tv_chart(kline, height=480, theme=theme_str, indicators=indicators_to_show)

            # 副图指标 (折叠)
            sub_indicators = []
            if 'MACD' in selected_indicators and 'MACD' in kline.columns:
                sub_indicators.append(('MACD', kline[['日期', 'MACD', 'MACD_Signal', 'MACD_Hist']]))
            if 'KDJ' in selected_indicators and 'KDJ_K' in kline.columns:
                sub_indicators.append(('KDJ', kline[['日期', 'KDJ_K', 'KDJ_D', 'KDJ_J']]))
            if 'RSI' in selected_indicators and 'RSI' in kline.columns:
                sub_indicators.append(('RSI', kline[['日期', 'RSI']]))
            if 'CCI' in selected_indicators and 'CCI' in kline.columns:
                sub_indicators.append(('CCI', kline[['日期', 'CCI']]))

            for name, data in sub_indicators:
                with st.expander(f"📈 {name} 指标", expanded=False):
                    sub_fig = _create_indicator_chart(data, name, theme_str)
                    st.plotly_chart(sub_fig, use_container_width=True, height=250)

        # 技术观察 + 策略建议 (并排)
        _render_tech_observation(kline, q_metrics, name_map.get(sel_stock, sel_stock), sel_stock)

    # -------- Tab 2: 技术分析 --------
    with tab_tech:
        # 核心指标卡片 - 第一排：财务与分担
        r1c1, r1c2, r1c3 = st.columns(3)
        fin_score = f_data.get('score', 50) if f_data else 50
        fin_source = f_data.get('source', '') if f_data else ''
        r1c1.metric(L.get('fin_health', '财务健康分'), f"{fin_score}%", delta=fin_source if fin_source else None, delta_color="off")
        
        # 估值核心 (10000 积分尊享数据)
        pe_val = "N/A"
        pb_val = "N/A"
        if db_data is not None and not db_data.empty:
            latest_v = db_data.iloc[-1]
            try:
                pe_raw = latest_v.get('pe') or latest_v.get('pe_ttm') or 0
                pb_raw = latest_v.get('pb') or 0
                pe_val = f"{float(pe_raw):.2f}"
                pb_val = f"{float(pb_raw):.2f}"
            except (ValueError, TypeError):
                pass
            
        r1c2.metric("市盈率 (PE/TTM)", pe_val, help="基于 Tushare Pro 实时同步")
        r1c3.metric("市净率 (PB)", pb_val)

        # 核心指标卡片 - 第二排：技术形态
        r2c1, r2c2, r2c3 = st.columns(3)
        rsi_val = q_metrics.get('rsi', 0) or 0
        r2c1.metric("RSI(14)", f"{float(rsi_val):.1f}")
        
        vol_ann = q_metrics.get('volatility_ann', 0) or 0
        r2c2.metric(L.get('ann_vol', '年化波动率'), f"{float(vol_ann):.1f}%")
        
        dmi_adx = q_metrics.get('dmi_adx', 0) or 0
        adx_f = float(dmi_adx)
        adx_strength = "强趋势" if adx_f > 40 else "弱趋势" if adx_f < 20 else "震荡"
        r2c3.metric(f"ADX({adx_f:.1f})", adx_strength)

        if f_data and f_data.get('analysis'):
            st.caption(f"📊 {f_data['analysis']}")

        if st.button(L.get('invoke_ai', '启动多模态 AI 研判'), key=f"PRO_SSM_V7_DNA_invoke_ai", type="primary", use_container_width=True):
            with st.spinner("🧠 AI 正在分析市场数据..."):
                # 改为流式直连展示，并捕获结果用于保存
                rep = st.write_stream(generate_ai_report_stream(sel_stock, name_map.get(sel_stock, ''), full_symbol))
                st.success("✅ 分析完成！")
                
                os.makedirs(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}", exist_ok=True)
                with open(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{sel_stock}.md", "w") as f:
                    f.write(rep)
                st.toast("报告已保存", icon="📁")

        # ---- 估值丝带 (10000 积分看板) ----
        if db_data is not None and not db_data.empty:
            st.divider()
            st.markdown("##### 💎 历史估值偏离度 (PE/PB Ribbon)")
            db_sorted = db_data.sort_values('trade_date')
            dates = db_sorted['trade_date'].astype(str)
            
            v_col1, v_col2 = st.columns(2)
            with v_col1:
                fig_pe = go.Figure()
                fig_pe.add_trace(go.Scatter(
                    x=dates, y=db_sorted['pe'], name='PE(TTM)',
                    line=dict(color='#38bdf8', width=2),
                    fill='tozeroy', fillcolor='rgba(56,189,248,0.05)'
                ))
                fig_pe.update_layout(template='plotly_dark', height=250, margin=dict(l=0,r=0,t=20,b=0), yaxis_title="PE")
                st.plotly_chart(fig_pe, use_container_width=True, key=f"pe_{sel_stock}")
            with v_col2:
                fig_pb = go.Figure()
                fig_pb.add_trace(go.Scatter(
                    x=dates, y=db_sorted['pb'], name='PB',
                    line=dict(color='#f59e0b', width=2),
                    fill='tozeroy', fillcolor='rgba(245,158,11,0.05)'
                ))
                fig_pb.update_layout(template='plotly_dark', height=250, margin=dict(l=0,r=0,t=20,b=0), yaxis_title="PB")
                st.plotly_chart(fig_pb, use_container_width=True, key=f"pb_{sel_stock}")

        # 行情快照
        st.divider()
        if not kline.empty:
            latest = kline.iloc[-1]
            snap_cols = st.columns(5)
            snap_cols[0].metric("开盘", f"¥{latest.get('开盘', 0):.2f}")
            snap_cols[1].metric("最高", f"¥{latest.get('最高', 0):.2f}")
            snap_cols[2].metric("最低", f"¥{latest.get('最低', 0):.2f}")
            snap_cols[3].metric("收盘", f"¥{latest.get('收盘', 0):.2f}")
            vol = latest.get('成交量', 0)
            vol_str = f"{vol/10000:.0f}万手" if vol > 10000 else f"{vol:.0f}手"
            snap_cols[4].metric("成交量", vol_str)

    # -------- Tab 3: AI 研判 --------
    with tab_ai:
        st.caption(f"数据时间: {datetime.datetime.now().strftime('%H:%M:%S')}")

        cached, is_cached = load_cached_report(sel_stock)

        if is_cached:
            st.success("📄 已有今日 AI 报告", icon="✅")
        else:
            st.info("🤖 点击下方按钮生成 AI 深度分析报告", icon="💡")

        if st.button(L.get('invoke_ai', '启动多模态 AI 研判'), key=f"invoke_ai_{id(render_dna_analyzer)}", type="primary", use_container_width=True):
            with st.spinner("🧠 AI 正在分析市场数据..."):
                # 改为流式直连展示，并捕获结果用于保存
                rep = st.write_stream(generate_ai_report_stream(sel_stock, name_map.get(sel_stock, ''), full_symbol))
                st.success("✅ 分析完成！")

                os.makedirs(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}", exist_ok=True)
                with open(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{sel_stock}.md", "w") as f:
                    f.write(rep)

                st.toast("报告已保存", icon="📁")
                st.balloons()
        elif is_cached:
            st.markdown(f"<div class='ai-box'>{cached}</div>", unsafe_allow_html=True)

    # -------- Tab 3: 资金面 --------
    with tab_fund:
        st.caption(f"💰 {name_map.get(sel_stock, sel_stock)} 资金面分析 | 数据来源: Tushare Pro")
        try:
            from core.tushare_client import get_ts_client, cached_moneyflow_single, cached_margin, cached_holder_number
            ts = get_ts_client()
            if not ts.available:
                st.warning("Tushare 未连接，资金面数据不可用")
            else:
                fund_c1, fund_c2 = st.columns(2)

                # 个股资金流向
                with fund_c1:
                    st.markdown("##### 📊 资金流向 (近 20 日)")
                    mf = cached_moneyflow_single(sel_stock, days=20)
                    if mf is not None and not mf.empty:
                        fig_mf = go.Figure()
                        dates = mf['trade_date'].astype(str)
                        # 净流入 = 买入 - 卖出
                        for label, buy_col, sell_col, color in [
                            ('超大单', 'buy_elg_vol', 'sell_elg_vol', '#ef4444'),
                            ('大单', 'buy_lg_vol', 'sell_lg_vol', '#f97316'),
                            ('中单', 'buy_md_vol', 'sell_md_vol', '#3b82f6'),
                            ('小单', 'buy_sm_vol', 'sell_sm_vol', '#10b981'),
                        ]:
                            if buy_col in mf.columns and sell_col in mf.columns:
                                net = mf[buy_col].astype(float) - mf[sell_col].astype(float)
                                fig_mf.add_trace(go.Bar(
                                    x=dates, y=net / 10000,
                                    name=label, marker_color=color, opacity=0.8
                                ))
                        fig_mf.update_layout(
                            barmode='group', template='plotly_dark',
                            height=320, margin=dict(l=10, r=10, t=30, b=30),
                            yaxis_title='净流入(万手)', legend=dict(orientation='h', y=1.02)
                        )
                        st.plotly_chart(fig_mf, use_container_width=True, key=f"mf_{sel_stock}")

                        # 总净流入指标
                        if 'net_mf_vol' in mf.columns:
                            latest_net = float(mf.iloc[-1]['net_mf_vol'] or 0)
                            trend = sum(mf['net_mf_vol'].astype(float).tail(5)) / 5
                            m1, m2 = st.columns(2)
                            m1.metric("最新净流入", f"{latest_net/10000:.1f}万手")
                            m2.metric("5日均值", f"{trend/10000:.1f}万手",
                                     delta="净流入" if trend > 0 else "净流出",
                                     delta_color="normal" if trend > 0 else "inverse")
                    else:
                        st.info("暂无资金流向数据")

                # 融资融券
                with fund_c2:
                    st.markdown("##### 📈 融资融券余额 (近 30 日)")
                    mg = cached_margin(sel_stock, days=30)
                    if mg is not None and not mg.empty:
                        fig_mg = go.Figure()
                        dates_mg = mg['trade_date'].astype(str)
                        if 'rzye' in mg.columns:
                            rzye = mg['rzye'].astype(float) / 1e8
                            fig_mg.add_trace(go.Scatter(
                                x=dates_mg, y=rzye, name='融资余额(亿)',
                                line=dict(color='#ef4444', width=2), fill='tozeroy',
                                fillcolor='rgba(239,68,68,0.1)'
                            ))
                        if 'rqye' in mg.columns:
                            rqye = mg['rqye'].astype(float) / 1e8
                            fig_mg.add_trace(go.Scatter(
                                x=dates_mg, y=rqye, name='融券余额(亿)',
                                line=dict(color='#3b82f6', width=2), yaxis='y2'
                            ))
                        fig_mg.update_layout(
                            template='plotly_dark', height=320,
                            margin=dict(l=10, r=50, t=30, b=30),
                            yaxis=dict(title='融资余额(亿)'),
                            yaxis2=dict(title='融券余额(亿)', overlaying='y', side='right'),
                            legend=dict(orientation='h', y=1.02)
                        )
                        st.plotly_chart(fig_mg, use_container_width=True, key=f"mg_{sel_stock}")

                        # 融资指标
                        if 'rzye' in mg.columns:
                            latest_rz = float(mg.iloc[-1]['rzye'] or 0) / 1e8
                            prev_rz = float(mg.iloc[-2]['rzye'] or 0) / 1e8 if len(mg) > 1 else latest_rz
                            change_rz = latest_rz - prev_rz
                            m1, m2 = st.columns(2)
                            m1.metric("融资余额", f"{latest_rz:.2f}亿",
                                     delta=f"{change_rz:+.2f}亿",
                                     delta_color="normal" if change_rz > 0 else "inverse")
                            if 'rzmre' in mg.columns:
                                rzmre = float(mg.iloc[-1].get('rzmre', 0) or 0) / 1e8
                                m2.metric("融资买入", f"{rzmre:.2f}亿")
                    else:
                        st.info("暂无融资融券数据 (可能该股不支持两融)")

                # 股东人数变化
                st.divider()
                st.markdown("##### 👥 股东人数变化")
                hn = cached_holder_number(sel_stock)
                if hn is not None and not hn.empty:
                    fig_hn = go.Figure()
                    hn_sorted = hn.sort_values('end_date')
                    if 'holder_num' in hn_sorted.columns:
                        fig_hn.add_trace(go.Scatter(
                            x=hn_sorted['end_date'].astype(str),
                            y=hn_sorted['holder_num'].astype(float) / 10000,
                            name='股东人数(万)', mode='lines+markers',
                            line=dict(color='#8b5cf6', width=2),
                            marker=dict(size=8)
                        ))
                        fig_hn.update_layout(
                            template='plotly_dark', height=250,
                            margin=dict(l=10, r=10, t=30, b=30),
                            yaxis_title='股东人数(万)'
                        )
                        st.plotly_chart(fig_hn, use_container_width=True, key=f"hn_{sel_stock}")
                        latest_hn = float(hn_sorted.iloc[-1].get('holder_num', 0) or 0)
                        prev_hn = float(hn_sorted.iloc[-2].get('holder_num', 0) or 0) if len(hn_sorted) > 1 else latest_hn
                        change_hn = latest_hn - prev_hn
                        st.caption(f"最新股东人数: {latest_hn/10000:.2f}万 | 变化: {change_hn/10000:+.2f}万 {'(筹码集中)' if change_hn < 0 else '(筹码分散)'}")
                else:
                    st.info("暂无股东人数数据")

                # ---- 回购与调研 (10000 积分尊享) ----
                st.divider()
                st.markdown("##### 🚀 机构调研 & 股份回购 (Alpha Signals)")
                alpha_c1, alpha_c2 = st.columns(2)
                
                with alpha_c1:
                    st.markdown("🏢 **股份回购记录**")
                    rep = ts.get_repurchase(sel_stock)
                    if rep is not None and not rep.empty:
                        for _, row in rep.head(3).iterrows():
                            st.markdown(f"""
                            <div style="background:rgba(239,68,68,0.05); border-left:3px solid #ef4444; padding:8px 12px; margin-bottom:8px; border-radius:4px;">
                                <div style="font-size:0.8rem; color:#94a3b8">{row['ann_date']}</div>
                                <div style="font-size:0.9rem; color:#ef4444; font-weight:600;">回购金额: {row['vol']:.2f} 万/股</div>
                                <div style="font-size:0.75rem; color:#64748b">回购区间: {row['low_limit']}-{row['high_limit']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.caption("近期无回购记录")

                with alpha_c2:
                    st.markdown("🔍 **调研活动**")
                    surv = ts.get_stk_surv(sel_stock)
                    if surv is not None and not surv.empty:
                        for _, row in surv.head(3).iterrows():
                            st.markdown(f"""
                            <div style="background:rgba(56,189,248,0.05); border-left:3px solid #38bdf8; padding:8px 12px; margin-bottom:8px; border-radius:4px;">
                                <div style="font-size:0.8rem; color:#94a3b8">{row['ann_date']}</div>
                                <div style="font-size:0.9rem; color:#e2e8f0; font-weight:600;">调研机构: {row['org_name'][:15]}...</div>
                                <div style="font-size:0.75rem; color:#64748b">类型: {row['surv_type'] or '实地'}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.caption("近期无调研活动")
        except Exception as e:
            st.error(f"资金面数据加载失败: {e}")

    # -------- Tab 4: 龙虎榜 --------
    with tab_dragon:
        st.caption(f"🐉 {name_map.get(sel_stock, sel_stock)} 龙虎榜 & 大宗交易 | 数据来源: Tushare Pro")
        try:
            from core.tushare_client import get_ts_client, cached_holder_trade
            ts = get_ts_client()
            if not ts.available:
                st.warning("Tushare 未连接，龙虎榜数据不可用")
            else:
                dragon_c1, dragon_c2 = st.columns([3, 2])

                # 龙虎榜记录
                with dragon_c1:
                    st.markdown("##### 📋 龙虎榜上榜记录")
                    top = ts.get_top_list(symbol=sel_stock)
                    if top is not None and not top.empty:
                        display_cols = []
                        col_rename = {}
                        for orig, disp in [
                            ('trade_date', '日期'), ('reason', '上榜原因'),
                            ('close', '收盘'), ('pct_change', '涨跌幅'),
                            ('turnover_rate', '换手率'),
                            ('buy', '买入额(万)'), ('sell', '卖出额(万)'),
                            ('net_buy', '净买入(万)')  
                        ]:
                            if orig in top.columns:
                                display_cols.append(orig)
                                col_rename[orig] = disp

                        show_df = top[display_cols].rename(columns=col_rename) if display_cols else top
                        # 格式化金额为万
                        for c in ['买入额(万)', '卖出额(万)', '净买入(万)']:
                            if c in show_df.columns:
                                show_df[c] = show_df[c].apply(
                                    lambda x: f"{float(x or 0)/10000:.0f}" if x else '0')
                        st.dataframe(show_df.head(10), use_container_width=True, hide_index=True)
                    else:
                        st.info("该股近期未上龙虎榜")

                    # 营业部明细
                    st.markdown("##### 🏢 龙虎榜营业部")
                    inst = ts.get_top_inst(symbol=sel_stock)
                    if inst is not None and not inst.empty:
                        inst_cols = []
                        inst_rename = {}
                        for orig, disp in [
                            ('trade_date', '日期'), ('exalter', '营业部'),
                            ('buy', '买入(万)'), ('sell', '卖出(万)'),
                            ('net_buy', '净买入(万)'), ('side', '方向')
                        ]:
                            if orig in inst.columns:
                                inst_cols.append(orig)
                                inst_rename[orig] = disp
                        show_inst = inst[inst_cols].rename(columns=inst_rename) if inst_cols else inst
                        for c in ['买入(万)', '卖出(万)', '净买入(万)']:
                            if c in show_inst.columns:
                                show_inst[c] = show_inst[c].apply(
                                    lambda x: f"{float(x or 0)/10000:.0f}" if x else '0')
                        st.dataframe(show_inst.head(15), use_container_width=True, hide_index=True)
                    else:
                        st.info("暂无营业部数据")

                # 大宗交易
                with dragon_c2:
                    st.markdown("##### 📦 大宗交易记录")
                    bt = ts.get_block_trade(symbol=sel_stock, days=60)
                    if bt is not None and not bt.empty:
                        bt_cols = []
                        bt_rename = {}
                        for orig, disp in [
                            ('trade_date', '日期'), ('price', '成交价'),
                            ('vol', '成交量(万股)'), ('amount', '成交额(万)'),
                            ('buyer', '买方'), ('seller', '卖方')
                        ]:
                            if orig in bt.columns:
                                bt_cols.append(orig)
                                bt_rename[orig] = disp
                        show_bt = bt[bt_cols].rename(columns=bt_rename) if bt_cols else bt
                        if '成交量(万股)' in show_bt.columns:
                            show_bt['成交量(万股)'] = show_bt['成交量(万股)'].apply(
                                lambda x: f"{float(x or 0)/10000:.1f}")
                        if '成交额(万)' in show_bt.columns:
                            show_bt['成交额(万)'] = show_bt['成交额(万)'].apply(
                                lambda x: f"{float(x or 0)/10000:.0f}")
                        st.dataframe(show_bt.head(10), use_container_width=True, hide_index=True)

                        # 大宗交易趋势
                        if 'amount' in bt.columns and len(bt) > 2:
                            fig_bt = go.Figure()
                            bt_sorted = bt.sort_values('trade_date')
                            fig_bt.add_trace(go.Bar(
                                x=bt_sorted['trade_date'].astype(str),
                                y=bt_sorted['amount'].astype(float) / 1e4,
                                name='成交额(万)', marker_color='#8b5cf6', opacity=0.8
                            ))
                            fig_bt.update_layout(
                                template='plotly_dark', height=250,
                                margin=dict(l=10, r=10, t=30, b=30),
                                yaxis_title='成交额(万)'
                            )
                            st.plotly_chart(fig_bt, use_container_width=True, key=f"bt_{sel_stock}")
                    else:
                        st.info("该股近期无大宗交易")

                # 股东增减持
                st.divider()
                st.markdown("##### 📢 股东增减持")
                ht = cached_holder_trade(sel_stock)
                if ht is not None and not ht.empty:
                    ht_cols = []
                    ht_rename = {}
                    for orig, disp in [
                        ('ann_date', '公告日'), ('holder_name', '股东名称'),
                        ('holder_type', '类型'), ('in_de', '增/减持'),
                        ('change_vol', '变动股数(万)'), ('change_ratio', '占比%'),
                        ('after_share', '变动后持股(万)'), ('after_ratio', '变动后占比%')
                    ]:
                        if orig in ht.columns:
                            ht_cols.append(orig)
                            ht_rename[orig] = disp
                    show_ht = ht[ht_cols].rename(columns=ht_rename) if ht_cols else ht
                    if '变动股数(万)' in show_ht.columns:
                        show_ht['变动股数(万)'] = show_ht['变动股数(万)'].apply(
                            lambda x: f"{float(x or 0)/10000:.1f}")
                    if '变动后持股(万)' in show_ht.columns:
                        show_ht['变动后持股(万)'] = show_ht['变动后持股(万)'].apply(
                            lambda x: f"{float(x or 0)/10000:.1f}")
                    st.dataframe(show_ht, use_container_width=True, hide_index=True)
                else:
                    st.info("暂无股东增减持记录")
        except Exception as e:
            st.error(f"龙虎榜数据加载失败: {e}")

    # -------- Tab 6: 公司简介 --------
    with tab_profile:
        stock_name_display = name_map.get(sel_stock, sel_stock)
        st.caption(f"🏢 {stock_name_display} 公司简介 | 数据来源: Tushare Pro")
        try:
            from core.tushare_client import get_ts_client, cached_stock_company
            ts = get_ts_client()
            if not ts.available:
                st.warning("Tushare 未连接，公司简介不可用")
            else:
                # 公司详细信息
                company = cached_stock_company(sel_stock)
                # 基础信息 (行业/地区/上市日期)
                basics = ts.get_stock_basic()
                basic_info = {}
                if basics is not None and not basics.empty:
                    row = basics[basics['symbol'] == sel_stock]
                    if not row.empty:
                        basic_info = row.iloc[0].to_dict()

                if company is not None and not company.empty:
                    c = company.iloc[0]

                    # ---- 头部: 公司名 + 行业标签 ----
                    industry = basic_info.get('industry', '')
                    area = basic_info.get('area', c.get('province', ''))
                    list_date = basic_info.get('list_date', '')
                    if list_date and len(str(list_date)) == 8:
                        list_date = f"{str(list_date)[:4]}-{str(list_date)[4:6]}-{str(list_date)[6:]}"

                    industry_badge = f'<span class="badge badge-info" style="margin-left:8px;">{industry}</span>' if industry else ''
                    area_badge = f'<span class="badge badge-success" style="margin-left:4px;">{area}</span>' if area else ''

                    st.markdown(f'''<div style="margin-bottom: 16px;">
    <span style="font-family: Outfit, sans-serif; font-size: 1.4rem; font-weight: 700;
          color: #f1f5f9;">{stock_name_display}</span>
    <span style="color: #64748b; font-size: 0.85rem; margin-left: 8px;">{sel_stock}</span>
    {industry_badge}{area_badge}
</div>''', unsafe_allow_html=True)

                    # ---- 关键信息卡片 (2列) ----
                    prof_c1, prof_c2 = st.columns([2, 3])

                    with prof_c1:
                        chairman = c.get('chairman', '—') or '—'
                        manager = c.get('manager', '—') or '—'
                        secretary = c.get('secretary', '—') or '—'
                        reg_capital = c.get('reg_capital', 0)
                        try:
                            reg_capital = float(reg_capital or 0)
                            reg_str = f"{reg_capital/10000:.2f} 亿元" if reg_capital > 10000 else f"{reg_capital:.0f} 万元"
                        except (ValueError, TypeError):
                            reg_str = str(reg_capital)
                        employees = c.get('employees', 0)
                        try:
                            employees = int(float(employees or 0))
                            emp_str = f"{employees:,} 人"
                        except (ValueError, TypeError):
                            emp_str = str(employees)
                        setup_date = c.get('setup_date', '—') or '—'
                        if setup_date and len(str(setup_date)) == 8:
                            setup_date = f"{str(setup_date)[:4]}-{str(setup_date)[4:6]}-{str(setup_date)[6:]}"
                        website = c.get('website', '') or ''
                        email = c.get('email', '') or ''

                        # 信息卡
                        items = [
                            ('👤 董事长', chairman),
                            ('👨‍💼 总经理', manager),
                            ('📝 董秘', secretary),
                            ('💰 注册资本', reg_str),
                            ('👥 员工人数', emp_str),
                            ('📅 成立日期', str(setup_date)),
                            ('📅 上市日期', str(list_date) if list_date else '—'),
                        ]

                        rows_html = ''.join(
                            f'<div style="display:flex; justify-content:space-between; padding:6px 0;'
                            f' border-bottom:1px solid rgba(255,255,255,0.04);'
                            f' font-size:0.85rem;">'
                            f'<span style="color:#94a3b8;">{label}</span>'
                            f'<span style="color:#e2e8f0; font-weight:500;">{val}</span></div>'
                            for label, val in items
                        )

                        web_html = ''
                        if website:
                            web_html = (f'<div style="margin-top:10px; font-size:0.82rem;">'
                                        f'<span style="color:#94a3b8;">🌐 </span>'
                                        f'<a href="{website}" target="_blank" '
                                        f'style="color:#38bdf8; text-decoration:none;">{website}</a></div>')
                        if email:
                            web_html += (f'<div style="font-size:0.82rem;">'
                                         f'<span style="color:#94a3b8;">📧 </span>'
                                         f'<span style="color:#cbd5e1;">{email}</span></div>')

                        st.markdown(f'''<div class="ssm-card">
    <div style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9;
         margin-bottom: 10px;">📋 基本信息</div>
    {rows_html}
    {web_html}
</div>''', unsafe_allow_html=True)

                    with prof_c2:
                        # 主营业务
                        main_biz = c.get('main_business', '') or ''
                        if main_biz:
                            st.markdown(f'''<div class="ssm-card" style="margin-bottom: 12px;">
    <div style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9;
         margin-bottom: 8px;">💼 主营业务</div>
    <div style="color: #cbd5e1; font-size: 0.85rem; line-height: 1.7;">{main_biz}</div>
</div>''', unsafe_allow_html=True)

                        # 公司简介
                        intro = c.get('introduction', '') or ''
                        if intro:
                            # 截断过长简介并提供展开
                            if len(intro) > 300:
                                with st.expander("📖 公司简介", expanded=True):
                                    st.markdown(f'''<div style="color: #cbd5e1; font-size: 0.85rem;
                                         line-height: 1.8;">{intro}</div>''',
                                               unsafe_allow_html=True)
                            else:
                                st.markdown(f'''<div class="ssm-card">
    <div style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9;
         margin-bottom: 8px;">📖 公司简介</div>
    <div style="color: #cbd5e1; font-size: 0.85rem; line-height: 1.8;">{intro}</div>
</div>''', unsafe_allow_html=True)

                        # 经营范围
                        biz_scope = c.get('business_scope', '') or ''
                        if biz_scope:
                            with st.expander("📜 经营范围"):
                                st.markdown(f'''<div style="color: #94a3b8; font-size: 0.82rem;
                                     line-height: 1.7;">{biz_scope}</div>''',
                                           unsafe_allow_html=True)
                else:
                    st.info("暂无公司简介数据")
        except Exception as e:
            st.error(f"公司简介加载失败: {e}")

    # -------- Tab 5: 财务基本面 --------
    with tab_finance:
        stock_name_fin = name_map.get(sel_stock, sel_stock)
        st.caption(f"📈 {stock_name_fin} 财务基本面分析 | 数据来源: Tushare Pro")
        try:
            from core.tushare_client import (get_ts_client, cached_fina_indicator,
                cached_income, cached_balancesheet, cached_forecast)
            ts = get_ts_client()
            if not ts.available:
                st.warning("Tushare 未连接，财务数据不可用")
            else:
                fin_c1, fin_c2 = st.columns(2)

                # ====== 左列: 财务指标 + 利润表 ======
                with fin_c1:
                    # -- 核心财务指标 --
                    st.markdown("##### 📋 核心财务指标 (最近 4 期)")
                    fina = cached_fina_indicator(sel_stock)
                    if fina is not None and not fina.empty:
                        # 最新一期指标卡片
                        latest = fina.iloc[0]
                        end_date = str(latest.get('end_date', ''))
                        if len(end_date) == 8:
                            end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

                        def _safe_float(v):
                            try:
                                return float(v or 0)
                            except (ValueError, TypeError):
                                return 0.0

                        roe = _safe_float(latest.get('roe', 0))
                        eps = _safe_float(latest.get('eps', 0))
                        roa = _safe_float(latest.get('roa', 0))
                        debt = _safe_float(latest.get('debt_to_assets', 0))
                        gross_margin = _safe_float(latest.get('grossprofit_margin', 0))
                        np_yoy = _safe_float(latest.get('netprofit_yoy', 0))
                        rev_yoy = _safe_float(latest.get('or_yoy', 0))

                        # 健康评级
                        def _health(val, good, warn):
                            if val >= good:
                                return '#10b981', '优'
                            elif val >= warn:
                                return '#f59e0b', '中'
                            else:
                                return '#ef4444', '弱'

                        indicators = [
                            ('ROE (%)', f'{roe:.2f}', *_health(roe, 15, 8)),
                            ('EPS (元)', f'{eps:.2f}', '#e2e8f0', ''),
                            ('ROA (%)', f'{roa:.2f}', *_health(roa, 8, 3)),
                            ('资产负债率', f'{debt:.1f}%', *_health(100-debt, 50, 30)),
                            ('毛利率', f'{gross_margin:.1f}%', *_health(gross_margin, 40, 20)),
                            ('净利润增长', f'{np_yoy:+.1f}%', *_health(np_yoy, 20, 0)),
                            ('营收增长', f'{rev_yoy:+.1f}%', *_health(rev_yoy, 15, 0)),
                        ]

                        cards_html = ''.join(
                            f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
                            f'border-bottom:1px solid rgba(255,255,255,0.04);font-size:0.84rem;">'
                            f'<span style="color:#94a3b8;">{label}</span>'
                            f'<span style="color:{color};font-weight:600;">{val}'
                            f'{" " + tag if tag else ""}</span></div>'
                            for label, val, color, tag in indicators
                        )

                        st.markdown(
                            f'<div class="ssm-card">'
                            f'<div style="font-size:0.78rem;color:#64748b;margin-bottom:8px;">'
                            f'报告期: {end_date}</div>'
                            f'{cards_html}</div>',
                            unsafe_allow_html=True
                        )

                        # 趋势表 (4 期)
                        with st.expander("📊 近 4 期财务指标趋势"):
                            display_cols = []
                            col_rename = {}
                            for orig, disp in [
                                ('end_date', '报告期'), ('roe', 'ROE%'),
                                ('eps', 'EPS'), ('roa', 'ROA%'),
                                ('debt_to_assets', '负债率%'),
                                ('grossprofit_margin', '毛利率%'),
                                ('netprofit_yoy', '净利增长%'),
                                ('or_yoy', '营收增长%'),
                            ]:
                                if orig in fina.columns:
                                    display_cols.append(orig)
                                    col_rename[orig] = disp
                            show_fina = fina[display_cols].rename(columns=col_rename)
                            if '报告期' in show_fina.columns:
                                show_fina['报告期'] = show_fina['报告期'].astype(str).apply(
                                    lambda x: f"{x[:4]}-{x[4:6]}" if len(x) == 8 else x)
                            st.dataframe(show_fina, use_container_width=True, hide_index=True)
                    else:
                        st.info("暂无财务指标数据")

                    # -- 利润表 --
                    st.markdown("##### 💰 营收 & 利润 趋势")
                    income = cached_income(sel_stock)
                    if income is not None and not income.empty:
                        inc_sorted = income.sort_values('end_date')
                        fig_inc = go.Figure()
                        dates_inc = inc_sorted['end_date'].astype(str).apply(
                            lambda x: f"{x[:4]}-{x[4:6]}" if len(x) == 8 else x)

                        if 'revenue' in inc_sorted.columns:
                            rev = inc_sorted['revenue'].astype(float) / 1e8
                            fig_inc.add_trace(go.Bar(
                                x=dates_inc, y=rev, name='营业收入(亿)',
                                marker_color='#3b82f6', opacity=0.7
                            ))
                        if 'n_income' in inc_sorted.columns:
                            ni = inc_sorted['n_income'].astype(float) / 1e8
                            fig_inc.add_trace(go.Scatter(
                                x=dates_inc, y=ni, name='净利润(亿)',
                                line=dict(color='#10b981', width=2.5),
                                mode='lines+markers', marker=dict(size=8)
                            ))
                        if 'operate_profit' in inc_sorted.columns:
                            op = inc_sorted['operate_profit'].astype(float) / 1e8
                            fig_inc.add_trace(go.Scatter(
                                x=dates_inc, y=op, name='营业利润(亿)',
                                line=dict(color='#f59e0b', width=2, dash='dot'),
                                mode='lines+markers', marker=dict(size=6)
                            ))

                        fig_inc.update_layout(
                            template='plotly_dark', height=300,
                            margin=dict(l=10, r=10, t=30, b=30),
                            legend=dict(orientation='h', y=1.05),
                            yaxis_title='金额(亿元)'
                        )
                        st.plotly_chart(fig_inc, use_container_width=True, key=f"inc_{sel_stock}")
                    else:
                        st.info("暂无利润表数据")

                # ====== 右列: 资产负债表 + 业绩预告 ======
                with fin_c2:
                    # -- 资产负债表 --
                    st.markdown("##### 🏦 资产结构")
                    bs = cached_balancesheet(sel_stock)
                    if bs is not None and not bs.empty:
                        bs_sorted = bs.sort_values('end_date')
                        fig_bs = go.Figure()
                        dates_bs = bs_sorted['end_date'].astype(str).apply(
                            lambda x: f"{x[:4]}-{x[4:6]}" if len(x) == 8 else x)

                        if 'total_assets' in bs_sorted.columns:
                            ta = bs_sorted['total_assets'].astype(float) / 1e8
                            fig_bs.add_trace(go.Bar(
                                x=dates_bs, y=ta, name='总资产(亿)',
                                marker_color='#3b82f6', opacity=0.7
                            ))
                        if 'total_liab' in bs_sorted.columns:
                            tl = bs_sorted['total_liab'].astype(float) / 1e8
                            fig_bs.add_trace(go.Bar(
                                x=dates_bs, y=tl, name='总负债(亿)',
                                marker_color='#ef4444', opacity=0.6
                            ))
                        if 'total_hldr_eqy_exc_min_int' in bs_sorted.columns:
                            eq = bs_sorted['total_hldr_eqy_exc_min_int'].astype(float) / 1e8
                            fig_bs.add_trace(go.Scatter(
                                x=dates_bs, y=eq, name='净资产(亿)',
                                line=dict(color='#10b981', width=2.5),
                                mode='lines+markers', marker=dict(size=8)
                            ))

                        fig_bs.update_layout(
                            barmode='group', template='plotly_dark', height=300,
                            margin=dict(l=10, r=10, t=30, b=30),
                            legend=dict(orientation='h', y=1.05),
                            yaxis_title='金额(亿元)'
                        )
                        st.plotly_chart(fig_bs, use_container_width=True, key=f"bs_{sel_stock}")

                        # 最新一期指标卡
                        latest_bs = bs_sorted.iloc[-1]
                        def _sf(v):
                            try:
                                return float(v or 0)
                            except (ValueError, TypeError):
                                return 0.0
                        ta_v = _sf(latest_bs.get('total_assets', 0)) / 1e8
                        tl_v = _sf(latest_bs.get('total_liab', 0)) / 1e8
                        eq_v = _sf(latest_bs.get('total_hldr_eqy_exc_min_int', 0)) / 1e8
                        cash_v = _sf(latest_bs.get('money_cap', 0)) / 1e8
                        debt_ratio = (tl_v / ta_v * 100) if ta_v > 0 else 0

                        bs_items = [
                            ('总资产', f'{ta_v:.2f}亿'),
                            ('总负债', f'{tl_v:.2f}亿'),
                            ('净资产', f'{eq_v:.2f}亿'),
                            ('货币资金', f'{cash_v:.2f}亿'),
                            ('资产负债率', f'{debt_ratio:.1f}%'),
                        ]
                        bs_html = ''.join(
                            f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
                            f'border-bottom:1px solid rgba(255,255,255,0.04);font-size:0.82rem;">'
                            f'<span style="color:#94a3b8;">{label}</span>'
                            f'<span style="color:#e2e8f0;font-weight:500;">{val}</span></div>'
                            for label, val in bs_items
                        )
                        st.markdown(f'<div class="ssm-card">{bs_html}</div>', unsafe_allow_html=True)
                    else:
                        st.info("暂无资产负债表数据")

                    # -- 业绩预告 --
                    st.markdown("##### 📢 业绩预告")
                    fc = cached_forecast(sel_stock)
                    if fc is not None and not fc.empty:
                        fc_cols = []
                        fc_rename = {}
                        for orig, disp in [
                            ('ann_date', '公告日'), ('end_date', '报告期'),
                            ('type', '类型'), ('p_change_min', '预计增幅下限%'),
                            ('p_change_max', '预计增幅上限%'), ('net_profit_min', '预计净利下限(万)'),
                            ('net_profit_max', '预计净利上限(万)'), ('summary', '摘要'),
                        ]:
                            if orig in fc.columns:
                                fc_cols.append(orig)
                                fc_rename[orig] = disp
                        show_fc = fc[fc_cols].rename(columns=fc_rename) if fc_cols else fc
                        # 格式化日期
                        for dc in ['公告日', '报告期']:
                            if dc in show_fc.columns:
                                show_fc[dc] = show_fc[dc].astype(str).apply(
                                    lambda x: f"{x[:4]}-{x[4:6]}-{x[6:]}" if len(x) == 8 else x)
                        # 格式化净利
                        for nc in ['预计净利下限(万)', '预计净利上限(万)']:
                            if nc in show_fc.columns:
                                show_fc[nc] = show_fc[nc].apply(
                                    lambda x: f"{float(x or 0)/10000:.0f}" if x else '—')
                        st.dataframe(show_fc.head(5), use_container_width=True, hide_index=True)
                    else:
                        st.info("暂无业绩预告")

                # ====== 财务健康度雷达图 ======
                if fina is not None and not fina.empty:
                    st.divider()
                    st.markdown("##### 🎯 财务健康度雷达")
                    latest = fina.iloc[0]
                    def _sf2(v):
                        try:
                            return float(v or 0)
                        except (ValueError, TypeError):
                            return 0.0

                    roe_s = min(_sf2(latest.get('roe', 0)) / 25 * 100, 100)
                    gm_s = min(_sf2(latest.get('grossprofit_margin', 0)) / 60 * 100, 100)
                    debt_s = max(100 - _sf2(latest.get('debt_to_assets', 0)), 0)
                    np_s = min(max(_sf2(latest.get('netprofit_yoy', 0)) + 50, 0), 100)
                    rev_s = min(max(_sf2(latest.get('or_yoy', 0)) + 50, 0), 100)

                    categories = ['盈利能力(ROE)', '毛利水平', '债务安全', '利润增长', '营收增长']
                    values = [roe_s, gm_s, debt_s, np_s, rev_s]

                    fig_radar = go.Figure(data=go.Scatterpolar(
                        r=values + [values[0]],
                        theta=categories + [categories[0]],
                        fill='toself',
                        fillcolor='rgba(59,130,246,0.15)',
                        line=dict(color='#3b82f6', width=2),
                        marker=dict(size=6, color='#60a5fa')
                    ))
                    fig_radar.update_layout(
                        polar=dict(
                            bgcolor='rgba(15,23,42,0.5)',
                            radialaxis=dict(visible=True, range=[0, 100],
                                          gridcolor='rgba(255,255,255,0.05)',
                                          tickfont=dict(size=9, color='#64748b')),
                            angularaxis=dict(gridcolor='rgba(255,255,255,0.08)',
                                           tickfont=dict(size=11, color='#94a3b8'))
                        ),
                        template='plotly_dark', height=350,
                        margin=dict(l=60, r=60, t=30, b=30),
                        showlegend=False
                    )
                    st.plotly_chart(fig_radar, use_container_width=True, key=f"radar_{sel_stock}")
        except Exception as e:
            st.error(f"财务数据加载失败: {e}")
