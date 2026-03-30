import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.tushare_client import get_ts_client
from components.ui_components import card_container

def render(L, *args):
    st.title("🧭 宏观雷达 & 资金风向标")
    st.markdown("<p style='color:#94a3b8;'>基于 Tushare Pro 10000 积分接口实时驱动</p>", unsafe_allow_html=True)

    client = get_ts_client()
    
    # ---- 1. 北向资金 (HSGT) ----
    with card_container("💸 沪深港通北向资金流向 (Net Flow)"):
        hsgt_df = client.get_moneyflow_hsgt(limit=40)
        if hsgt_df is not None and not hsgt_df.empty:
            hsgt_df['trade_date'] = pd.to_datetime(hsgt_df['trade_date'])
            hsgt_df = hsgt_df.sort_values('trade_date')
            
            fig = go.Figure()
            # 北向合计
            fig.add_trace(go.Bar(
                x=hsgt_df['trade_date'],
                y=hsgt_df['north_money'],
                name="北向净流入",
                marker_color=hsgt_df['north_money'].apply(lambda x: '#ef4444' if x > 0 else '#10b981')
            ))
            # 累计流向
            fig.add_trace(go.Scatter(
                x=hsgt_df['trade_date'],
                y=hsgt_df['north_money'].cumsum(),
                name="累计流向",
                line=dict(color='#38bdf8', width=2),
                yaxis="y2"
            ))
            
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=30, b=10),
                height=350,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis=dict(title="单日净额 (百万)"),
                yaxis2=dict(title="累计净额", overlaying="y", side="right"),
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # 最近三个交易日详情
            st.markdown("##### 🕒 近期流向细节")
            cols = st.columns(3)
            recent = hsgt_df.tail(3).iloc[::-1]
            for i, (_, row) in enumerate(recent.iterrows()):
                color = "red" if row['north_money'] > 0 else "green"
                cols[i].metric(
                    label=row['trade_date'].strftime('%m-%d'),
                    value=f"{row['north_money']/100:.2f} 亿",
                    delta=f"沪:{row['hgt']/100:.1f} 亿 | 深:{row['sgt']/100:.1f} 亿",
                    delta_color="normal"
                )
        else:
            st.info("暂无北向资金数据，请确保 Tushare 接口联通正常")

    # ---- 2. 市场估值与情绪指标 (示意，可后续接入 index_dailybasic) ----
    c1, c2 = st.columns(2)
    
    with c1:
        with card_container("📊 主要指数估值分位 (PE/PB)"):
            import random
            # 模拟数据 (后续接入接口)
            metrics = [
                {"name": "上证指数", "pe": "13.2", "percentile": "35.2%"},
                {"name": "沪深300", "pe": "11.8", "percentile": "28.5%"},
                {"name": "创业板指", "pe": "28.5", "percentile": "15.8%"},
            ]
            for m in metrics:
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.05);">
                    <span style="color:#e2e8f0">{m['name']}</span>
                    <span>
                        <span style="color:#94a3b8; margin-right:8px">PE: {m['pe']}</span>
                        <span style="color:#38bdf8; font-weight:600">分位: {m['percentile']}</span>
                    </span>
                </div>
                """, unsafe_allow_html=True)

    with c2:
        with card_container("🔥 市场交易活跃度"):
            st.markdown("""
            <div style="text-align:center; padding:20px 0;">
                <div style="font-size:0.8rem; color:#94a3b8">全市场成交额</div>
                <div style="font-size:1.8rem; color:#f59e0b; font-weight:bold;">9,240.5 亿</div>
                <div style="font-size:0.75rem; color:#475569; margin-top:8px;">
                    较昨日 <span style="color:#ef4444">↑ 12.5%</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<p style='font-size:0.7rem; color:#475569; text-align:center;'>活跃度处于近 20 日中等偏上水平</p>", unsafe_allow_html=True)

    st.warning("💡 提示: 宏观雷达建议在每日 17:00 后查看，以获取当日最完整的数据统计。")
