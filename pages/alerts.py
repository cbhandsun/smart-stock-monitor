"""
🔔 预警系统页面
"""
import streamlit as st
import pandas as pd
from modules.alerts.alert_system import AlertManager, AlertType

alert_manager = AlertManager()


def render(L):
    from components.ui_components import page_header
    page_header("预警系统", icon="🔔")

    tab1, tab2 = st.tabs(["活跃预警", "创建预警"])

    with tab1:
        alerts = alert_manager.list_all_alerts()
        if alerts:
            alert_data = []
            for a in alerts:
                alert_data.append({
                    "股票": a.symbol, "类型": a.alert_type.value,
                    "阈值": a.threshold, "状态": a.status.value,
                    "触发次数": a.trigger_count, "创建时间": a.created_at
                })
            st.dataframe(pd.DataFrame(alert_data), use_container_width=True)
        else:
            st.info("暂无预警规则")

    with tab2:
        with st.form("create_alert"):
            col1, col2 = st.columns(2)
            with col1:
                symbol = st.text_input("股票代码", value=st.session_state['selected_stock'])
                alert_type = st.selectbox("预警类型", [
                    ("价格高于", AlertType.PRICE_ABOVE),
                    ("价格低于", AlertType.PRICE_BELOW),
                    ("涨幅超过", AlertType.CHANGE_PCT_ABOVE),
                    ("跌幅超过", AlertType.CHANGE_PCT_BELOW),
                    ("RSI高于", AlertType.RSI_ABOVE),
                    ("RSI低于", AlertType.RSI_BELOW),
                ], format_func=lambda x: x[0])
            with col2:
                threshold = st.number_input("阈值", value=100.0)
                message = st.text_input("预警消息", value=f"{symbol} 触发预警")

            submitted = st.form_submit_button("创建预警", type="primary")
            if submitted:
                alert = alert_manager.add_alert(symbol, alert_type[1], threshold, message)
                st.success(f"预警 '{alert.id}' 创建成功！")
                st.rerun()
