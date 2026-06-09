"""
🔔 预警系统页面 — V2.0
彩色预警卡片 + 统计仪表盘 + 状态徽章
"""
import streamlit as st
try:
    from utils.html_renderer import render_html
except ImportError:
    render_html = lambda h: st.html(h)
import pandas as pd
from modules.alerts.alert_system import AlertManager, AlertType
from components.ui_components import (
    page_header, info_card, empty_state, nav_to_page, stock_selector, status_badge_html
)

alert_manager = AlertManager()

# 预警类型定义 (中文标签 + 枚举)
ALERT_TYPES = [
    ("价格高于", AlertType.PRICE_ABOVE),
    ("价格低于", AlertType.PRICE_BELOW),
    ("涨幅超过", AlertType.CHANGE_PCT_ABOVE),
    ("跌幅超过", AlertType.CHANGE_PCT_BELOW),
    ("RSI高于", AlertType.RSI_ABOVE),
    ("RSI低于", AlertType.RSI_BELOW),
]


def _alert_level_color(alert_type_value):
    """根据预警类型判断严重度颜色"""
    danger_types = ['price_below', 'change_pct_below', 'rsi_below']
    warning_types = ['price_above', 'change_pct_above', 'rsi_above']
    val = alert_type_value.lower() if isinstance(alert_type_value, str) else str(alert_type_value).lower()
    if any(t in val for t in danger_types):
        return "#ef4444", "danger"
    elif any(t in val for t in warning_types):
        return "#f59e0b", "warning"
    return "#3b82f6", "info"


def render(L):
    page_header("预警系统", icon="🔔")

    alerts = alert_manager.list_all_alerts()

    # ---- 统计仪表盘 ----
    total_triggers = sum(a.trigger_count for a in alerts) if alerts else 0
    active_count = len([a for a in alerts if a.status.value == 'active']) if alerts else 0

    m1, m2, m3 = st.columns(3)
    with m1:
        info_card("活跃预警", str(active_count), icon="🔔", color="#f59e0b")
    with m2:
        info_card("总触发次数", str(total_triggers), icon="⚡", color="#ef4444")
    with m3:
        info_card("预警规则总数", str(len(alerts)), icon="📋", color="#3b82f6")

    st.markdown("")

    tab1, tab2 = st.tabs(["📋 活跃预警", "➕ 创建预警"])

    with tab1:
        if alerts:
            for i, a in enumerate(alerts):
                color, level = _alert_level_color(a.alert_type.value)
                badge = status_badge_html(a.status.value.upper(), level)

                card_col, action_col = st.columns([5, 1])
                with card_col:
                    st.html(f'''<div style="background: rgba(30,41,59,0.35);
                        border: 1px solid rgba(255,255,255,0.06);
                        border-left: 4px solid {color};
                        border-radius: 12px; padding: 14px 18px; margin: 3px 0;
                        animation: fadeInUp 0.35s ease-out backwards;
                        animation-delay: {i * 0.05}s;">
                        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom: 6px;">
                            <div>
                                <span style="font-weight:700; color:#f1f5f9; font-size:0.95rem;">{a.symbol}</span>
                                <span style="margin-left:8px; color:#94a3b8; font-size:0.82rem;">{a.alert_type.value}</span>
                            </div>
                            <div>{badge}</div>
                        </div>
                        <div style="display:flex; gap:20px; font-size:0.8rem; color:#94a3b8;">
                            <span>阈值: <strong style="color:#e2e8f0;">{a.threshold}</strong></span>
                            <span>触发: <strong style="color:#e2e8f0;">{a.trigger_count}次</strong></span>
                            <span>创建: {str(a.created_at)[:16]}</span>
                        </div>
                    </div>''')

                with action_col:
                    if st.button("🗑️", key=f"del_alert_{i}_{a.symbol}",
                                use_container_width=True, help="删除预警"):
                        alert_manager.remove_alert(a.id)
                        st.toast(f"已删除 {a.symbol} 的预警", icon="🗑️")
                        st.rerun()
        else:
            empty_state(
                icon="🔔",
                title="还没有预警规则",
                description="创建预警规则，当条件触发时第一时间获得通知"
            )

    with tab2:
        with st.expander("📖 预警判定规则与消息推送说明（点击展开说明）", expanded=False):
            st.markdown("""
            ##### ⚙️ 预警工作流与执行周期
            - **自动检测**: 系统后台集成了 **Celery 异步调度任务**。在 A 股交易时间（工作日 **09:25 - 15:05**）内，系统会高频自动轮询获取最新价格和技术指标进行规则校验。
            - **消息推送**: 预警一旦触发，除了在系统首页及通知栏标记外，还会通过您在配置文件中配置的**飞书 / Lark / 企业微信机器人 Webhook** 实时将 Markdown 格式的消息推送到工作群。
            
            ##### 📋 预警条件与阈值设定指南
            
            | 预警类型 | 对应参数 (枚举) | 阈值单位 | 触发说明 |
            | :--- | :--- | :--- | :--- |
            | **价格高于** | `PRICE_ABOVE` | 价格 (元) | 最新成交价 $\\ge$ 设定阈值时触发。适用于突破买入或止盈场景。 |
            | **价格低于** | `PRICE_BELOW` | 价格 (元) | 最新成交价 $\\le$ 设定阈值时触发。适用于回撤止损或抄底场景。 |
            | **涨幅超过** | `CHANGE_PCT_ABOVE` | 百分比 (%) | 当日涨幅超过阈值（如输入 `5.0` 表示涨幅达到 $+5\\%$）。 |
            | **跌幅超过** | `CHANGE_PCT_BELOW` | 百分比 (%) | 当日跌幅超过阈值（如输入 `5.0` 表示跌幅达到 $-5\\%$）。 |
            | **RSI 高于** | `RSI_ABOVE` | 指标值 (0-100) | 14日相对强弱指标超买阈值（通常设定为 `70` 或 `80`）。 |
            | **RSI 低于** | `RSI_BELOW` | 指标值 (0-100) | 14日相对强弱指标超卖阈值（通常设定为 `30` 或 `20`）。 |
            """)

        with st.form("create_alert"):
            col1, col2 = st.columns(2)
            with col1:
                symbol = stock_selector(key_suffix="alerts")
                alert_type = st.selectbox(
                    "预警类型", 
                    ALERT_TYPES, 
                    format_func=lambda x: x[0],
                    help="选择您想监控的触发条件类型。系统后台将根据此条件自动监测指标或股价动向。"
                )
            with col2:
                threshold = st.number_input(
                    "阈值", 
                    value=100.0,
                    help="触发预警的数值限制。若选择价格类预警，请输入目标价（元）；若选择涨跌幅，请输入百分比数值（如输入 5.0 代表 5%）；若选择 RSI 指标，请输入 0~100 的数值（超买常用 70，超卖常用 30）。"
                )
                message = st.text_input(
                    "预警消息", 
                    value="", 
                    placeholder="触发后显示的消息...",
                    help="自定义预警触发时的通知内容。若留空，系统将根据触发条件自动生成描述文字。"
                )

            # 预览
            if symbol and alert_type:
                preview_color, _ = _alert_level_color(alert_type[1].value)
                st.html(f'''<div style="background:rgba(30,41,59,0.3); border-radius:8px;
                    padding:8px 14px; font-size:0.82rem; border-left:3px solid {preview_color}; margin-top:4px;">
                    📌 预览: 当 <strong>{symbol}</strong> {alert_type[0]} <strong>{threshold}</strong> 时触发
                </div>''')

            submitted = st.form_submit_button("✨ 创建预警", type="primary", use_container_width=True)
            if submitted:
                msg = message or f"{symbol} 触发预警"
                alert = alert_manager.add_alert(symbol, alert_type[1], threshold, msg)
                st.success(f"✅ 预警 '{alert.id}' 创建成功！")
                st.rerun()

    # 底部导航
    st.divider()
    st.caption("📌 下一步")
    c1, c2 = st.columns(2)
    with c1:
        nav_to_page('market', '前往市场看盘', icon='📡')
    with c2:
        nav_to_page('anomaly', '查看异常检测', icon='🚨')
