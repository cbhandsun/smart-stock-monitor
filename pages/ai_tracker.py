import streamlit as st
import pandas as pd
from modules.portfolio.watchlist_manager import WatchlistManager
from main import get_stock_names_batch
from modules.data_loader import fetch_quotes_concurrent
from components.dna_analyzer import render_dna_analyzer
from pages import save_watchlist

watchlist_manager = WatchlistManager()

# Pre-defined AI Sub-Sectors & Core Target Stocks (Symbols only)
AI_SECTORS = {
    "ai_compute": {
        "name": "⚡ 算力芯片核心",
        "desc": "以 GPU、AI 推理/训练芯片、以及配套的高端 PCB 相关的核心算力底座企业。",
        "stocks": ["300308", "688256", "688041", "002371", "688072"]  # 中际旭创, 寒武纪, 海光信息, 北方华创, 拓荆科技 
    },
    "ai_servers": {
        "name": "💻 AI 服务器与液冷",
        "desc": "为 AI 集群大模型训练提供整机服务器及高级散热解决方案的核心组装与硬件商。",
        "stocks": ["601138", "000977", "603019", "000021", "300438"]  # 工业富联, 浪潮信息, 中科曙光, 深科技, 鹏鼎控股
    },
    "aigc_apps": {
        "name": "🤖 AIGC 大模型及应用",
        "desc": "具备从 0 到 1 训练行业大模型能力，或在自动驾驶、办公助理有核心 AI 落地场景的龙头企业。",
        "stocks": ["002230", "300418", "688111", "300459", "002229"]  # 科大讯飞, 昆仑万维, 金山办公, 汤姆猫, 鸿博股份
    }
}


def get_ai_sector_df(sector_key=None):
    """
    获取 AI 板块股票数据，返回与 market 策略选股兼容的 DataFrame
    sector_key: None=全部, 'ai_compute'/'ai_servers'/'aigc_apps'
    返回 DataFrame 包含: 代码, 名称, 最新价, 涨跌幅, 板块
    """
    if sector_key and sector_key in AI_SECTORS:
        sectors = {sector_key: AI_SECTORS[sector_key]}
    else:
        sectors = AI_SECTORS

    all_symbols = []
    symbol_sector = {}
    for key, data in sectors.items():
        for s in data["stocks"]:
            all_symbols.append(s)
            symbol_sector[s] = data["name"]

    if not all_symbols:
        return pd.DataFrame()

    name_map = get_stock_names_batch(all_symbols)
    live_quotes = fetch_quotes_concurrent(all_symbols)

    rows = []
    for sym in all_symbols:
        q = live_quotes.get(sym, {})
        rows.append({
            "代码": sym,
            "名称": name_map.get(sym, sym),
            "最新价": float(q.get("最新价", 0)),
            "涨跌幅": float(q.get("涨跌幅", 0)),
            "板块": symbol_sector.get(sym, ""),
        })

    return pd.DataFrame(rows)


def _init_ai_portfolios():
    """Ensure our AI tracking portfolios are seeded in the Watchlist Manager"""
    existing = {p.name: p.id for p in watchlist_manager.list_portfolios()}
    
    for sector_key, sector_data in AI_SECTORS.items():
        if sector_data["name"] not in existing:
            # Create the portfolio
            new_p = watchlist_manager.create_portfolio(sector_data["name"], sector_data["desc"])
            
            # Fetch names in batch
            name_map = get_stock_names_batch(sector_data["stocks"])
            
            # Seed the stocks
            for sym in sector_data["stocks"]:
                watchlist_manager.add_stock(new_p.id, symbol=sym, name=name_map.get(sym, sym), tags=["AI", sector_key])

def render(L, my_stocks, name_map):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"### 📡 AI Sector Tracker (人工智能核心赛道雷达)")
    st.caption("实时跟踪 A 股核心 AI 子板块龙头，捕捉产业链轮动带来的买卖共振点。")
    st.info("💡 提示：AI 赛道已融入「📡 市场信号流」的策略选股视图，可在那里使用完整的 选股→分析→跟盘 流程。")
    st.divider()

    # Pre-flight check to bootstrap data
    _init_ai_portfolios()

    portfolios = watchlist_manager.list_portfolios()
    # Filter only AI ones
    ai_portfolios = [p for p in portfolios if p.name in [v["name"] for v in AI_SECTORS.values()]]

    if not ai_portfolios:
        st.warning("AI 板块正在初始化或数据拉取失败，请检查网络。")
        return

    # Use Premium Streamlit Tabs
    tabs = st.tabs([p.name for p in ai_portfolios])

    for i, p in enumerate(ai_portfolios):
        with tabs[i]:
            st.markdown(f"<p style='color: #94a3b8; font-size: 0.95rem; line-height: 1.6;'>{p.description}</p>", unsafe_allow_html=True)
            
            symbols = [s['symbol'] for s in p.stocks]
            if not symbols:
                st.info("此板块暂无监控标的。")
                continue
                
            # Fetch Realtime Context concurrently
            name_map = get_stock_names_batch(symbols)
            live_quotes = fetch_quotes_concurrent(symbols)
            
            # Build DataFrame for Display
            table_data = []
            for stock in p.stocks:
                sym = stock['symbol']
                q_data = live_quotes.get(sym, {})
                
                price = float(q_data.get("最新价", 0.0))
                pct = float(q_data.get("涨跌幅", 0.0))
                turnover = float(q_data.get("换手率", 0.0))
                vr = float(q_data.get("量比", 0.0))

                table_data.append({
                    "📌": False,
                    "代码": sym,
                    "名称": name_map.get(sym, stock['name']),
                    "最新价": price,
                    "涨跌幅": pct,
                    "换手率": turnover,
                    "量比": vr,
                    "主力状态": "📈 偏多" if pct > 2.0 else "📉 调整" if pct < -2.0 else "⏸️ 震荡",
                })
            
            df = pd.DataFrame(table_data)
            
            if not df.empty:
                col_cfg = {
                    "📌": st.column_config.CheckboxColumn("选择", default=False),
                    "代码": st.column_config.TextColumn("代码", width="small"),
                    "名称": st.column_config.TextColumn("企业名称", width="medium"),
                    "最新价": st.column_config.NumberColumn("最新价", format="¥ %.2f"),
                    "涨跌幅": st.column_config.NumberColumn("涨跌幅", format="%.2f%%"),
                    "换手率": st.column_config.NumberColumn("日换手率", format="%.2f%%"),
                    "量比": st.column_config.NumberColumn("量比", format="%.2f"),
                }
                
                res = st.data_editor(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config=col_cfg,
                    disabled=["代码", "名称", "最新价", "涨跌幅", "换手率", "量比", "主力状态"]
                )
                
                sel = res[res["📌"] == True]
                
                c1, c2, c3 = st.columns([1,1,4])
                with c1:
                    if st.button(f"📥 Sync to Workspace", key=f"btn_ai_sync_{p.id}", use_container_width=True, type="primary"):
                        if not sel.empty:
                            added = [c for c in sel['代码'] if c not in my_stocks]
                            my_stocks.extend(added)
                            save_watchlist(my_stocks)
                            st.toast(f"✅ 已添加 {len(added)} 只股票到自选组合", icon="🎯")
                            st.balloons()
                            st.rerun()
                        else:
                            st.warning("请先勾选需要添加的股票")
                with c2:
                    if st.button(f"🔍 全面体检 ({p.name.split(' ')[1]})", key=f"btn_ai_scan_{p.id}", use_container_width=True, type="secondary"):
                         # auto-select the first checked one, or the first one in the list for dna analyzer
                         if not sel.empty:
                             st.session_state['selected_stock'] = sel.iloc[0]['代码']
                         elif not df.empty:
                             st.session_state['selected_stock'] = df.iloc[0]['代码']
                         st.rerun()

    # Append DNA Analyzer globally to the page
    render_dna_analyzer(L, my_stocks, name_map)

