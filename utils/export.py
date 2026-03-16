"""
📤 数据导出工具模块
支持 CSV 和 Markdown 格式导出
"""
import io
import csv
import datetime
import pandas as pd
import streamlit as st
from typing import Optional


def export_dataframe_csv(df: pd.DataFrame, filename_prefix: str = "export") -> Optional[bytes]:
    """将 DataFrame 导出为 CSV 字节流"""
    if df is None or df.empty:
        return None
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    return output.getvalue().encode('utf-8-sig')


def export_report_markdown(content: str, symbol: str = "", title: str = "AI 分析报告") -> bytes:
    """将文本报告导出为 Markdown 文件"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    header = f"# {title}\n\n"
    header += f"- **股票**: {symbol}\n" if symbol else ""
    header += f"- **生成时间**: {now}\n\n---\n\n"
    full = header + content
    return full.encode('utf-8')


def render_download_button(data: bytes, filename: str, label: str = "📥 下载",
                           mime: str = "text/csv", key: str = None):
    """渲染 Streamlit 下载按钮"""
    st.download_button(
        label=label,
        data=data,
        file_name=filename,
        mime=mime,
        key=key or f"download_{filename}",
        use_container_width=True,
    )


def render_export_panel(df: pd.DataFrame = None, report_text: str = None,
                        symbol: str = "", key_prefix: str = "export"):
    """
    渲染导出面板 — 支持 CSV + Markdown 下载
    在任何页面中调用以添加导出功能
    """
    with st.expander("📤 导出数据", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            if df is not None and not df.empty:
                csv_data = export_dataframe_csv(df)
                now = datetime.datetime.now().strftime('%Y%m%d_%H%M')
                render_download_button(
                    csv_data,
                    f"{symbol}_{now}.csv" if symbol else f"data_{now}.csv",
                    label="📊 导出 CSV",
                    mime="text/csv",
                    key=f"{key_prefix}_csv"
                )
            else:
                st.caption("无表格数据可导出")

        with col2:
            if report_text:
                md_data = export_report_markdown(report_text, symbol)
                now = datetime.datetime.now().strftime('%Y%m%d_%H%M')
                render_download_button(
                    md_data,
                    f"{symbol}_report_{now}.md" if symbol else f"report_{now}.md",
                    label="📝 导出报告",
                    mime="text/markdown",
                    key=f"{key_prefix}_md"
                )
            else:
                st.caption("无报告可导出")
