"""
🚨 异常检测监控页面
"""
import streamlit as st
from modules.data_loader import fetch_kline
from modules.ai.anomaly_detector import AnomalyDetector, SmartAlertSystem

anomaly_detector = AnomalyDetector()
smart_alert_system = SmartAlertSystem(anomaly_detector)

from components.dna_analyzer import render_dna_analyzer

def render(L, my_stocks, name_map):
    st.header("🚨 异常检测监控")

    symbol = st.text_input("股票代码", value=st.session_state['selected_stock'], key="anomaly_symbol")

    if symbol:
        tab1, tab2, tab3 = st.tabs(["实时异常", "历史异常", "监控设置"])

        with tab1:
            st.subheader("实时异常检测")
            full_symbol = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
            kline = fetch_kline(full_symbol, period='daily', datalen=60)

            if not kline.empty and len(kline) > 2:
                latest = kline.iloc[-1]
                prev = kline.iloc[-2]

                current_data = {
                    'open': latest['开盘'], 'high': latest['最高'],
                    'low': latest['最低'], 'close': latest['收盘'],
                    'volume': latest['成交量'], 'prev_close': prev['收盘']
                }

                anomalies = anomaly_detector.analyze(symbol, current_data, kline)

                if anomalies:
                    for event in anomalies:
                        level_color = {
                            'critical': '🔴', 'warning': '🟡', 'info': '🔵'
                        }.get(event.level.value, '⚪')

                        with st.expander(f"{level_color} {event.description} (置信度: {event.confidence * 100:.0f}%)", expanded=True):
                            st.write(f"**异常类型**: {event.anomaly_type.value}")
                            st.write(f"**建议操作**: {event.suggested_action}")
                            if event.metrics:
                                st.json(event.metrics)
                else:
                    st.success("✅ 未检测到异常")

                alerts = smart_alert_system.process_market_data(symbol, current_data, kline)
                if alerts:
                    st.subheader("智能提醒")
                    for alert in alerts:
                        alert_color = "🚨" if alert.level.value == 'critical' else "⚠️" if alert.level.value == 'warning' else "ℹ️"
                        st.info(f"{alert_color} {alert.title}\n\n{alert.message}")
            else:
                st.warning("数据不足，无法检测异常")

        with tab2:
            st.subheader("历史异常统计")
            days = st.slider("统计天数", 7, 90, 30)
            stats = anomaly_detector.get_anomaly_stats(symbol, days=days)

            col1, col2, col3 = st.columns(3)
            col1.metric("总异常数", stats['total_count'])
            col2.metric("平均置信度", f"{stats['avg_confidence'] * 100:.1f}%")

            if stats['by_level']:
                st.write("**异常等级分布**:")
                for level, count in stats['by_level'].items():
                    st.write(f"- {level}: {count}次")

            if stats['by_type']:
                st.write("**异常类型分布**:")
                for type_name, count in stats['by_type'].items():
                    st.write(f"- {type_name}: {count}次")

        with tab3:
            st.subheader("监控设置")
            st.write("**阈值配置**")
            col1, col2, col3 = st.columns(3)
            with col1:
                gap_threshold = st.number_input("跳空阈值(%)", value=3.0, step=0.5) / 100
            with col2:
                volume_threshold = st.number_input("成交量激增倍数", value=3.0, step=0.5)
            with col3:
                volatility_threshold = st.number_input("波动率激增倍数", value=2.0, step=0.5)

            if st.button("保存设置", type="primary"):
                anomaly_detector.thresholds['gap_up'] = gap_threshold
                anomaly_detector.thresholds['gap_down'] = -gap_threshold
                anomaly_detector.thresholds['volume_spike'] = volume_threshold
                anomaly_detector.thresholds['volatility_spike'] = volatility_threshold
                st.success("设置已保存")

    # Global DNA Analyzer Injection
    render_dna_analyzer(L, my_stocks, name_map, default_target=symbol)
