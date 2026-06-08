"""推荐页面 v2.0 — 四维评分 × 赛道分析"""
import streamlit as st
from utils.html_renderer import render_html
import pandas as pd
from datetime import datetime
from utils.global_market_data import get_global_realtime_data



_GRADE = {
    "S":  {"color":"#f43f5e","bg":"rgba(244,63,94,0.08)","brd":"rgba(244,63,94,0.3)"},
    "A+": {"color":"#fb923c","bg":"rgba(251,146,60,0.08)","brd":"rgba(251,146,60,0.3)"},
    "A":  {"color":"#f59e0b","bg":"rgba(245,158,11,0.06)","brd":"rgba(245,158,11,0.2)"},
    "B":  {"color":"#10b981","bg":"rgba(16,185,129,0.06)","brd":"rgba(16,185,129,0.2)"},
    "C":  {"color":"#64748b","bg":"rgba(100,116,139,0.05)","brd":"rgba(100,116,139,0.15)"},
}


def _kpi(label, value, unit, color):
    return (
        f'<div style="background:rgba(10,20,45,0.8);border:1px solid rgba(255,255,255,0.06);'
        f'border-radius:10px;padding:14px 16px;text-align:center;">'
        f'<div style="font-size:0.68rem;color:#475569;margin-bottom:4px;">{label}</div>'
        f'<div style="font-size:1.6rem;font-weight:800;color:{color};line-height:1;">{value}</div>'
        f'<div style="font-size:0.65rem;color:#334155;margin-top:2px;">{unit}</div></div>'
    )


def _grade_badge(g):
    m = _GRADE.get(g, _GRADE["C"])
    return (f'<span style="background:{m["bg"]};border:1px solid {m["brd"]};color:{m["color"]};'
            f'font-weight:800;font-size:0.9rem;padding:3px 10px;border-radius:8px;">{g}</span>')


def _score_bar(val, mx, color):
    pct = min(val / mx * 100, 100)
    return (f'<div style="background:rgba(255,255,255,0.06);border-radius:4px;height:4px;">'
            f'<div style="background:{color};height:100%;width:{pct:.0f}%;border-radius:4px;"></div></div>')


def _stock_card(row, rank, my_stocks):
    code  = row["代码"]; name = row["名称"]
    price = row["最新价"]; chg = row["涨跌幅"]
    grade = row["评级"]; label = row["评级标签"]
    score = row["总评分"]; hits = row["命中策略"]
    reason = row["荐股理由"]; action = row["操作建议"]
    sec_name = row["赛道名"]; sec_color = row["赛道色"]
    boom = row["景气度"]; catalyst = row["催化剂"]

    m = _GRADE.get(grade, _GRADE["C"])
    chg_c = "#f43f5e" if chg >= 0 else "#10b981"
    chg_i = "▲" if chg >= 0 else "▼"
    px = f"{price:,.2f}" if price > 0 else "—"
    rk_c = {1:"#f59e0b",2:"#94a3b8",3:"#b45309"}.get(rank,"#334155")
    star = "⭐" if code in my_stocks else ""

    s_strat = row["策略分"]; s_sec = row["赛道分"]
    s_tech = row["技术分"]; s_res = row["共振加成"]
    s_sent = row.get("舆情分", 0.0)
    s_us = row.get("美股溢价", 0.0)
    s_glob = row.get("全球折价", 0.0)

    exec_sig = row.get("交易信号", "—")
    exec_sig_color = "#94a3b8"
    if "分批建仓" in exec_sig or "买入" in exec_sig:
        exec_sig_color = "#10b981"
    elif "减仓" in exec_sig or "卖出" in exec_sig or "避险" in exec_sig:
        exec_sig_color = "#ef4444"
    elif "止盈" in exec_sig:
        exec_sig_color = "#f59e0b"

    tags = "".join(
        f'<span style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);'
        f'border-radius:5px;padding:2px 6px;font-size:0.67rem;color:#94a3b8;">{t}</span> '
        for t in hits.split()
    )

    return f"""
<div style="background:linear-gradient(135deg,rgba(10,20,45,0.92),rgba(12,22,48,0.96));
  border:1px solid {m['brd']};border-left:3px solid {m['color']};
  border-radius:12px;padding:16px;margin-bottom:10px;">

  <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="background:{rk_c}22;color:{rk_c};border:1px solid {rk_c}55;
        border-radius:6px;font-size:0.72rem;font-weight:800;padding:2px 8px;">#{rank}</span>
      <div>
        <span style="font-size:1rem;font-weight:800;color:#f1f5f9;">{name}</span>
        <span style="font-size:0.72rem;color:#475569;margin-left:8px;font-family:monospace;">{code}</span>
        {f'<span style="font-size:0.65rem;background:rgba(56,189,248,0.1);color:#38bdf8;border:1px solid rgba(56,189,248,0.2);border-radius:4px;padding:1px 5px;margin-left:5px;">{star}自选</span>' if star else ""}
      </div>
    </div>
    <div style="text-align:right;">
      {_grade_badge(grade)}
      <div style="font-size:0.68rem;color:{m['color']};margin-top:3px;">{label}</div>
    </div>
  </div>

  <div style="display:flex;gap:16px;margin-bottom:10px;flex-wrap:wrap;">
    <div>
      <div style="font-size:1.15rem;font-weight:700;color:#f1f5f9;font-family:monospace;">{px}</div>
      <div style="font-size:0.78rem;font-weight:600;color:{chg_c};">{chg_i}{abs(chg):.2f}%</div>
    </div>
    <div style="flex:1;min-width:160px;">
      <div style="display:flex;justify-content:space-between;font-size:0.65rem;color:#475569;margin-bottom:3px;">
        <span>综合评分 {score}</span><span style="color:{m['color']};font-weight:700;">{score}/20.0</span>
      </div>
      {_score_bar(score, 20, m['color'])}
      <div style="display:flex;gap:8px;margin-top:6px;font-size:0.62rem;color:#475569;flex-wrap:wrap;">
        <span>策略{s_strat}</span><span>赛道{s_sec}</span>
        <span>技术{s_tech}</span><span style="color:#f59e0b;">+共振{s_res}</span>
        <span style="color:#38bdf8;">+舆情{s_sent:+.1f}</span>
        <span style="color:#a855f7;">+美股溢价{s_us:+.1f}</span>
        <span style="color:#ef4444;">全球折价{s_glob:+.1f}</span>
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:0.65rem;color:#475569;">操作建议</div>
      <div style="font-size:0.82rem;font-weight:700;margin-top:2px;">{action}</div>
    </div>
  </div>

  <div style="margin-bottom:8px;">{tags}</div>

  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;border-top:1px solid rgba(255,255,255,0.04);padding-top:8px;margin-top:4px;">
    {'<span style="background:' + sec_color + '15;color:' + sec_color + ';border:1px solid ' + sec_color + '40;border-radius:5px;font-size:0.68rem;padding:2px 7px;white-space:nowrap;">' + sec_name + f' 景气{boom}/10</span>' if sec_name != "—" else ""}
    <span style="font-size:0.72rem;color:#64748b;font-style:italic;flex:1;">{reason}</span>
  </div>
  
  <div style="font-size:0.68rem;color:#64748b;margin-top:6px;padding:6px;background:rgba(255,255,255,0.02);border-radius:6px;border:1px solid rgba(255,255,255,0.03);">
    {f'🌎 <b>美股映射</b>：{row.get("美股理由")}<br>' if row.get("美股理由") else ""}
    {f'📰 <b>舆情风向</b>：<span style="color:#38bdf8;font-weight:700;">[{row.get("舆情标签")}]</span> {row.get("舆情理由")}<br>' if row.get("舆情理由") else ""}
    {f'🎯 <b>交易执行</b>：<span style="color:{exec_sig_color};font-weight:800;">{exec_sig}</span> (建议价区: <span style="font-family:monospace;color:#f1f5f9;">{row.get("买入区间")}</span> | 止损: <span style="font-family:monospace;color:#ef4444;">{row.get("止损点")}</span> | 止盈: <span style="font-family:monospace;color:#10b981;">{row.get("止盈点")}</span>)<br>' if exec_sig != "—" else ""}
  </div>
  {f'<div style="font-size:0.7rem;color:#475569;margin-top:5px;padding:4px 8px;background:rgba(56,189,248,0.04);border-radius:4px;">⚡ {catalyst}</div>' if catalyst else ""}
</div>"""


def _sector_card(row):
    color = row["color"]; name = row["sector_name"]
    boom = row["boom_score"]; heat = row["热度指数"]
    rec = row["recommended_cnt"]; total = row["total_stocks"]
    thesis = row["thesis"][:60] + "…" if len(row.get("thesis","")) > 60 else row.get("thesis","")
    pct = min(heat / 10 * 100, 100)
    return f"""
<div style="background:rgba(10,20,45,0.8);border:1px solid {color}30;
  border-left:3px solid {color};border-radius:10px;padding:12px;margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
    <span style="font-size:0.9rem;font-weight:700;color:#f1f5f9;">{name}</span>
    <div style="display:flex;gap:8px;align-items:center;">
      <span style="font-size:0.65rem;color:{color};background:{color}15;border:1px solid {color}30;
        border-radius:5px;padding:2px 7px;">景气 {boom}/10</span>
      <span style="font-size:0.65rem;color:#94a3b8;">推荐 {rec}/{total}</span>
    </div>
  </div>
  <div style="margin-bottom:6px;">
    <div style="display:flex;justify-content:space-between;font-size:0.62rem;color:#475569;margin-bottom:2px;">
      <span>热度指数</span><span style="color:{color};font-weight:700;">{heat:.1f}</span>
    </div>
    <div style="background:rgba(255,255,255,0.06);border-radius:4px;height:5px;">
      <div style="background:{color};height:100%;width:{pct:.0f}%;border-radius:4px;"></div>
    </div>
  </div>
  <div style="font-size:0.7rem;color:#64748b;font-style:italic;">{thesis}</div>
</div>"""


def render(L, my_stocks=None, name_map=None):
    my_stocks = my_stocks or []

    # ── 页头 ─────────────────────────────────────────────────────
    hc1, hc2 = st.columns([5, 1])
    with hc1:
        st.html(
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">'
            '<span style="font-size:1.4rem;font-weight:900;color:#f1f5f9;">🎯 AI 荐股</span>'
            '<span style="background:rgba(244,63,94,0.1);color:#f43f5e;border:1px solid rgba(244,63,94,0.2);'
            'border-radius:20px;font-size:0.65rem;font-weight:700;padding:2px 9px;">MULTI-STRATEGY × SECTOR</span>'
            '</div>'
            '<div style="font-size:0.78rem;color:#475569;margin-bottom:12px;">'
            '四维评分：策略共振 × 赛道景气 × 技术动量 × 多策略加成</div>')
    with hc2:
        refresh = st.button("🔄 刷新", key="rec_refresh", use_container_width=True)

    # ── 算法说明面板 ──────────────────────────────────────────────
    with st.expander("📐 算法说明 — 四维评分体系", expanded=False):
        from core.recommender import STRATEGY_WEIGHTS, SECTOR_META
        from core.strategies import HOTSPOT_2026

        st.html("""
<div style="background:rgba(56,189,248,0.04);border:1px solid rgba(56,189,248,0.1);
border-radius:10px;padding:14px 18px;margin-bottom:12px;">
<div style="font-size:0.85rem;font-weight:700;color:#38bdf8;margin-bottom:8px;">
📊 总评分 = 策略分 + 赛道分 + 技术分 + 共振加成
</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;font-size:0.75rem;">
  <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.2);border-radius:8px;padding:10px;text-align:center;">
    <div style="font-size:1.1rem;margin-bottom:4px;">⚡</div>
    <div style="font-weight:700;color:#f43f5e;">策略分</div>
    <div style="color:#64748b;margin-top:4px;">7条选股策略各自权重累加</div>
    <div style="color:#94a3b8;font-size:0.68rem;margin-top:2px;">满分约 14 分</div>
  </div>
  <div style="background:rgba(249,115,22,0.08);border:1px solid rgba(249,115,22,0.2);border-radius:8px;padding:10px;text-align:center;">
    <div style="font-size:1.1rem;margin-bottom:4px;">🏭</div>
    <div style="font-weight:700;color:#fb923c;">赛道分</div>
    <div style="color:#64748b;margin-top:4px;">景气度(0-10) × 赛道权重 / 10</div>
    <div style="color:#94a3b8;font-size:0.68rem;margin-top:2px;">满分 4.0 分</div>
  </div>
  <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);border-radius:8px;padding:10px;text-align:center;">
    <div style="font-size:1.1rem;margin-bottom:4px;">📈</div>
    <div style="font-weight:700;color:#10b981;">技术分</div>
    <div style="color:#64748b;margin-top:4px;">当日涨跌幅区间加分</div>
    <div style="color:#94a3b8;font-size:0.68rem;margin-top:2px;">满分 1.0 分</div>
  </div>
  <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:10px;text-align:center;">
    <div style="font-size:1.1rem;margin-bottom:4px;">✨</div>
    <div style="font-weight:700;color:#f59e0b;">共振加成</div>
    <div style="color:#64748b;margin-top:4px;">命中策略越多额外加成</div>
    <div style="color:#94a3b8;font-size:0.68rem;margin-top:2px;">≥4条 +2.0，3条 +1.0</div>
  </div>
</div>
</div>
""")

        ac1, ac2, ac3 = st.columns(3)

        # 策略权重
        with ac1:
            st.markdown(
                '<div style="font-size:0.78rem;font-weight:700;color:#94a3b8;margin-bottom:8px;">'
                '⚡ 策略权重</div>',
                unsafe_allow_html=True
            )
            sorted_strats = sorted(STRATEGY_WEIGHTS.items(), key=lambda x: -x[1])
            STRAT_META = {
                "Mainforce":  ("💰主力吸筹", "#ef4444"),
                "Northbound": ("🔗北向资金", "#06b6d4"),
                "Breakout":   ("📈技术突破", "#8b5cf6"),
                "Hotspot":    ("🏭热点赛道", "#f97316"),
                "Momentum":   ("🔥动量追击", "#10b981"),
                "Growth":     ("🌟成长之星", "#f59e0b"),
                "Value":      ("💎价值发现", "#3b82f6"),
            }
            rows_html = ""
            max_w = max(STRATEGY_WEIGHTS.values())
            for k, w in sorted_strats:
                zh, clr = STRAT_META.get(k, (k, "#64748b"))
                pct = w / max_w * 100
                rows_html += (
                    f'<div style="margin-bottom:8px;">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'font-size:0.72rem;margin-bottom:3px;">'
                    f'<span style="color:#94a3b8;">{zh}</span>'
                    f'<span style="color:{clr};font-weight:700;">{w}</span></div>'
                    f'<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:4px;">'
                    f'<div style="background:{clr};height:100%;width:{pct:.0f}%;border-radius:3px;"></div>'
                    f'</div></div>'
                )
            st.html(rows_html)

        # 赛道景气度
        with ac2:
            st.markdown(
                '<div style="font-size:0.78rem;font-weight:700;color:#94a3b8;margin-bottom:8px;">'
                '🏭 赛道景气 & 权重</div>')
            sorted_sectors = sorted(SECTOR_META.items(), key=lambda x: -(x[1]["boom_score"] * x[1]["weight"]))
            sec_html = ""
            for sk, sm in sorted_sectors:
                sec_data = HOTSPOT_2026.get(sk, {})
                sname = sec_data.get("name", sk)
                scolor = sec_data.get("color", "#64748b")
                boom = sm["boom_score"]
                weight = sm["weight"]
                heat = round(boom * weight / 10, 1)
                pct = min(heat / 4.0 * 100, 100)
                sec_html += (
                    f'<div style="margin-bottom:7px;">'
                    f'<div style="display:flex;justify-content:space-between;font-size:0.7rem;margin-bottom:2px;">'
                    f'<span style="color:{scolor};">{sname}</span>'
                    f'<span style="color:#64748b;">景气{boom} × 权重{weight} = '
                    f'<span style="color:{scolor};font-weight:700;">{heat}</span></span></div>'
                    f'<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:4px;">'
                    f'<div style="background:{scolor};height:100%;width:{pct:.0f}%;border-radius:3px;"></div>'
                    f'</div></div>'
                )
            st.html(sec_html)

        # 评级 + 技术分规则
        with ac3:
            st.markdown(
                '<div style="font-size:0.78rem;font-weight:700;color:#94a3b8;margin-bottom:8px;">'
                '🏆 评级标准</div>')
            grades = [
                ("S",  "≥ 12分", "强烈推荐", "#f43f5e"),
                ("A+", "≥ 9分",  "积极推荐", "#fb923c"),
                ("A",  "≥ 6分",  "推荐关注", "#f59e0b"),
                ("B",  "≥ 3.5分","适度关注", "#10b981"),
                ("C",  "< 3.5分","轻仓观察", "#64748b"),
            ]
            grade_html = ""
            for g, rng, lbl, clr in grades:
                grade_html += (
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">'
                    f'<span style="background:{clr}18;border:1px solid {clr}40;color:{clr};'
                    f'font-weight:800;font-size:0.82rem;padding:2px 8px;border-radius:6px;min-width:28px;text-align:center;">{g}</span>'
                    f'<span style="font-size:0.72rem;color:#64748b;">{rng}</span>'
                    f'<span style="font-size:0.7rem;color:#475569;">{lbl}</span>'
                    f'</div>'
                )
            st.html(grade_html)

            st.markdown(
                '<div style="font-size:0.78rem;font-weight:700;color:#94a3b8;margin:10px 0 6px;">'
                '📈 技术分规则</div>'
                '<div style="font-size:0.7rem;color:#475569;line-height:1.8;">'
                '涨 1-3% → +0.5（健康上涨）<br>'
                '涨 3-5% → +1.0（强势突破）<br>'
                '涨 >5% → +0.5（追高谨慎）<br>'
                '轻微回调 → +0.2（蓄势调整）'
                '</div>')

        st.markdown(
            '<div style="font-size:0.68rem;color:#334155;margin-top:8px;padding:8px;'
            'border-top:1px solid rgba(255,255,255,0.04);">'
            '⚠️ 本系统推荐仅供参考，不构成投资建议。股市有风险，投资需谨慎。</div>',
            unsafe_allow_html=True
        )

    CACHE_TTL = 15 * 60
    now = datetime.now()
    result = st.session_state.get("rec_result_v2")
    ts     = st.session_state.get("rec_ts_v2")
    valid  = result and ts and (now - ts).total_seconds() < CACHE_TTL and not refresh

    if not valid:
        with st.spinner("⚡ 多策略引擎运行中..."):
            try:
                from core.recommender import run_recommendation_engine
                result = run_recommendation_engine(top_n=30)
                st.session_state["rec_result_v2"] = result
                st.session_state["rec_ts_v2"] = now
            except Exception as e:
                st.error(f"引擎异常：{e}")
                return

    stocks_df  = result["stocks"]
    sectors_df = result["sectors"]
    summary    = result["summary"]

    if stocks_df.empty:
        st.info("暂无推荐数据，请在交易时段内使用或点击刷新")
        return

    # ── 🌎 全球宏观雷达与美股映射卡片 ──────────────────────────────────────
    rt = get_global_realtime_data()
    premiums = summary.get("global_premiums", {})
    
    if rt:
        def format_item(name, data):
            if not data: return ""
            price = data["price"]
            chg = data["change_pct"]
            color = "#f43f5e" if chg >= 0 else "#10b981"
            sign = "+" if chg >= 0 else ""
            return (
                f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);'
                f'border-radius:8px;padding:10px;text-align:center;min-width:110px;flex:1;">'
                f'<div style="font-size:0.65rem;color:#64748b;margin-bottom:2px;">{name}</div>'
                f'<div style="font-size:0.95rem;font-weight:700;color:#f1f5f9;font-family:monospace;">{price:,.2f}</div>'
                f'<div style="font-size:0.68rem;color:{color};font-weight:600;">{sign}{chg:.2f}%</div>'
                f'</div>'
            )
        
        items_list = []
        for key, name in [("纳斯达克", "NASDAQ"), ("标普500", "S&P 500"), ("费城半导体SOX", "SOX半导体"), ("恐慌指数VIXY", "VIXY(恐慌)"), ("离岸人民币", "USD/CNH"), ("A50期货", "A50期指")]:
            if key in rt:
                items_list.append(format_item(name, rt[key]))
        
        items_html = "".join(items_list)
        sent_desc = premiums.get("market_sentiment", {}).get("reason", "全球市场宏观流动性整体平稳。")
        sent_score = premiums.get("market_sentiment", {}).get("score", 0.0)
        risk_disc = premiums.get("risk_discount", 0.0)
        fx_disc = premiums.get("fx_discount", 0.0)
        
        sent_color = "#f43f5e" if sent_score >= 0 else "#10b981"
        
        radar_html = f"""
<div style="background:linear-gradient(135deg,rgba(10,20,45,0.92),rgba(12,22,48,0.96));
  border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:14px;margin-bottom:15px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:6px;">
    <span style="font-size:0.8rem;font-weight:800;color:#38bdf8;letter-spacing:0.5px;">🌎 全球宏观雷达与美股映射联动 (GLOBAL REGIME)</span>
    <span style="font-size:0.65rem;color:#475569;">隔夜与外汇实时传导</span>
  </div>
  
  <div style="display:flex;gap:8px;overflow-x:auto;padding-bottom:6px;margin-bottom:10px;justify-content:space-between;flex-wrap:wrap;">
    {items_html}
  </div>
  
  <div style="font-size:0.72rem;line-height:1.5;color:#94a3b8;background:rgba(56,189,248,0.03);border:1px solid rgba(56,189,248,0.08);border-radius:8px;padding:8px 12px;">
    📢 <b>情绪传导评述</b>：{sent_desc} <br>
    ⚖️ <b>全球溢折修正</b>：
    美股开盘情绪 <span style="color:{sent_color};font-weight:700;">{sent_score:+.2f}分</span> | 
    VIX风险偏好折价 <span style="color:#ef4444;font-weight:700;">{risk_disc:+.2f}分</span> | 
    汇率资本流动折价 <span style="color:#10b981;font-weight:700;">{fx_disc:+.2f}分</span>
  </div>
</div>
"""
        st.html(radar_html)

    # ── 顶部统计 ─────────────────────────────────────────────────
    kc = st.columns(5)
    kpis = [
        ("扫描标的",  summary["total_candidates"],  "支",     "#38bdf8"),
        ("推荐标的",  summary["recommended_cnt"],   "支",     "#10b981"),
        ("强烈推荐 S", summary["grade_s_cnt"],      "支",     "#f43f5e"),
        ("积极推荐 A+", summary["grade_ap_cnt"],    "支",     "#fb923c"),
        ("活跃策略",  summary["strategies_active"], "条",     "#8b5cf6"),
    ]
    for i, (lbl, val, unit, clr) in enumerate(kpis):
        with kc[i]:
            st.html(_kpi(lbl, val, unit, clr))

    st.caption(f"📍 {summary['generated_at']} 生成 · 15分钟缓存 · 最热赛道：{summary['top_sector']} 景气{summary['top_sector_boom']}/10")
    st.divider()

    # ── 筛选控制 ─────────────────────────────────────────────────
    fc = st.columns([1, 1, 1, 1, 2])
    with fc[0]:
        top_n = st.selectbox("显示数量", [10, 15, 20, 30], index=1, key="rec_n")
    with fc[1]:
        min_hits = st.selectbox("最少命中策略", [1, 2, 3], index=1, key="rec_hits")
    with fc[2]:
        grade_filter = st.selectbox("最低评级", ["全部", "B+", "A+", "仅S"], index=0, key="rec_grade")
    with fc[3]:
        sec_options = ["全部赛道"] + sectors_df["sector_name"].tolist()
        sec_filter = st.selectbox("筛选赛道", sec_options, key="rec_sector")

    # 应用筛选
    filtered = stocks_df[stocks_df["命中数"] >= min_hits].copy()
    grade_map = {"全部": [], "B+": ["S","A+","A","B"], "A+": ["S","A+","A"], "仅S": ["S"]}
    if grade_map.get(grade_filter):
        filtered = filtered[filtered["评级"].isin(grade_map[grade_filter])]
    if sec_filter != "全部赛道":
        filtered = filtered[filtered["赛道名"] == sec_filter]
    filtered = filtered.head(top_n)

    # ── 主视图 Tabs ───────────────────────────────────────────────
    tab_stocks, tab_sectors, tab_table = st.tabs(["📋 个股推荐", "🗺️ 赛道分析", "📊 数据表格"])

    # ── Tab1: 个股卡片 ────────────────────────────────────────────
    with tab_stocks:
        if filtered.empty:
            st.info("当前条件无结果，请放宽筛选")
        else:
            # Top 3 精选高亮
            top3 = filtered.head(3)
            st.html(
                '<div style="font-size:0.78rem;color:#f59e0b;font-weight:600;'
                'margin-bottom:8px;">🏆 今日精选 TOP 3</div>'
            )
            for _, row in top3.iterrows():
                st.html(_stock_card(row.to_dict(), int(row["排名"]), my_stocks))
                bc = st.columns([3, 1, 1])
                with bc[0]:
                    if st.button(f"🔬 深度分析 {row['名称']}", key=f"ra_{row['代码']}",
                                 use_container_width=True, type="primary"):
                        st.session_state["selected_stock"] = row["代码"]
                        st.session_state["current_page"] = "market"
                        st.session_state["market_view"] = "📊 深度分析"
                        st.rerun()
                with bc[1]:
                    code = row["代码"]
                    if code in my_stocks:
                        if st.button("💔 移除", key=f"rrm_{code}", use_container_width=True):
                            my_stocks.remove(code)
                            from pages import save_watchlist; save_watchlist(my_stocks)
                            st.rerun()
                    else:
                        if st.button("⭐ 自选", key=f"rad_{code}", use_container_width=True):
                            my_stocks.append(code)
                            from pages import save_watchlist; save_watchlist(my_stocks)
                            st.rerun()

            # 其余推荐
            rest = filtered.iloc[3:]
            if not rest.empty:
                st.html(
                    '<div style="font-size:0.78rem;color:#475569;margin:12px 0 8px;">📌 更多推荐</div>')
                for _, row in rest.iterrows():
                    st.html(_stock_card(row.to_dict(), int(row["排名"]), my_stocks))
                    bc = st.columns([3, 1])
                    with bc[0]:
                        if st.button(f"🔬 深度分析 {row['名称']}", key=f"ra_{row['代码']}",
                                     use_container_width=True):
                            st.session_state["selected_stock"] = row["代码"]
                            st.session_state["current_page"] = "market"
                            st.session_state["market_view"] = "📊 深度分析"
                            st.rerun()
                    with bc[1]:
                        code = row["代码"]
                        lbl = "💔 移除" if code in my_stocks else "⭐ 自选"
                        if st.button(lbl, key=f"rw_{code}", use_container_width=True):
                            if code in my_stocks:
                                my_stocks.remove(code)
                            else:
                                my_stocks.append(code)
                            from pages import save_watchlist; save_watchlist(my_stocks)
                            st.rerun()

    # ── Tab2: 赛道分析 ────────────────────────────────────────────
    with tab_sectors:
        st.html(
            '<div style="font-size:0.78rem;color:#475569;margin-bottom:12px;">'
            '赛道热度 = 景气度 × 赛道权重，越高代表 2026 年确定性越强</div>'
        )
        sc1, sc2 = st.columns([1, 1])
        half = len(sectors_df) // 2 + 1
        with sc1:
            for _, row in sectors_df.iloc[:half].iterrows():
                st.html(_sector_card(row.to_dict()))
        with sc2:
            for _, row in sectors_df.iloc[half:].iterrows():
                st.html(_sector_card(row.to_dict()))

        # 赛道-推荐数量图
        st.markdown("**各赛道推荐标的分布**")
        chart_df = sectors_df[["sector_name", "recommended_cnt", "boom_score"]].copy()
        chart_df.columns = ["赛道", "推荐数", "景气度"]
        chart_df = chart_df.set_index("赛道")
        st.bar_chart(chart_df["推荐数"])

    # ── Tab3: 数据表格 ────────────────────────────────────────────
    with tab_table:
        show_df = filtered[[
            "排名","代码","名称","最新价","涨跌幅","总评分",
            "策略分","赛道分","技术分","共振加成",
            "评级","命中数","赛道名","操作建议","荐股理由"
        ]].copy()
        show_df["最新价"] = show_df["最新价"].apply(lambda x: f"{x:.2f}" if x > 0 else "—")
        show_df["涨跌幅"] = show_df["涨跌幅"].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(
            show_df, hide_index=True, use_container_width=True,
            column_config={
                "总评分": st.column_config.ProgressColumn("总评分", min_value=0, max_value=20, format="%.1f"),
                "策略分": st.column_config.NumberColumn("策略分", format="%.1f"),
                "赛道分": st.column_config.NumberColumn("赛道分", format="%.1f"),
            }
        )
        # 导出提示
        st.caption("💡 在表格右上角点击下载按钮可导出 CSV")
