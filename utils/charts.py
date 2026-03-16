import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

DARK_THEME = """
:root {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --accent: #3b82f6;
    --success: #10b981;
    --danger: #ef4444;
    --warning: #f59e0b;
}
"""

LIGHT_THEME = """
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f1f5f9;
    --text-primary: #0f172a;
    --text-secondary: #64748b;
    --accent: #2563eb;
    --success: #059669;
    --danger: #dc2626;
    --warning: #d97706;
}
"""

THEME_CSS = {
    "dark": """
        <style>
        .main { background-color: #0f172a; color: #f8fafc; }
        .stApp { background-color: #0f172a; }
        div[data-testid="stMetric"] { 
            background: #1e293b !important; 
            border: 1px solid #334155 !important; 
        }
        div[data-testid="stMetricLabel"] > div { color: #60a5fa !important; }
        div[data-testid="stMetricValue"] > div { color: white !important; }
        [data-testid="stSidebar"] { background-color: #020617 !important; }
        </style>
    """,
    "light": """
        <style>
        .main { background-color: #ffffff; color: #0f172a; }
        .stApp { background-color: #ffffff; }
        div[data-testid="stMetric"] { 
            background: #f1f5f9 !important; 
            border: 1px solid #cbd5e1 !important; 
        }
        div[data-testid="stMetricLabel"] > div { color: #2563eb !important; }
        div[data-testid="stMetricValue"] > div { color: #0f172a !important; }
        [data-testid="stSidebar"] { background-color: #f8fafc !important; }
        </style>
    """
}

def apply_theme(theme: str) -> str:
    """应用主题并返回CSS"""
    return THEME_CSS.get(theme, THEME_CSS["dark"])

def create_candlestick_chart(df, indicators=None, theme="dark"):
    """创建K线图"""
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=[0.7, 0.3]
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.get('date', df.get('日期')),
        open=df.get('open', df.get('开盘')),
        high=df.get('high', df.get('最高')),
        low=df.get('low', df.get('最低')),
        close=df.get('close', df.get('收盘')),
        name="Price"
    ), row=1, col=1)
    
    # Volume
    colors = ['#ef4444' if c < o else '#10b981' for c, o in zip(
        df.get('close', df.get('收盘', [])), 
        df.get('open', df.get('开盘', []))
    )]
    fig.add_trace(go.Bar(
        x=df.get('date', df.get('日期')), 
        y=df.get('volume', df.get('成交量', [])), 
        marker_color=colors,
        name="Volume"
    ), row=2, col=1)
    
    # Add indicators
    if indicators:
        for indicator in indicators:
            if indicator in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.get('date', df.get('日期')), 
                    y=df[indicator], 
                    name=indicator,
                    line=dict(width=1.5)
                ), row=1, col=1)
    
    fig.update_layout(
        template=template, 
        height=600,
        xaxis_rangeslider_visible=True,
        xaxis_rangeslider_thickness=0.03,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_xaxes(showspikes=True, spikemode="across", spikecolor="#888", spikethickness=1)
    fig.update_yaxes(showspikes=True, spikemode="across", spikecolor="#888", spikethickness=1)
    
    return fig

def create_performance_chart(daily_values, theme="dark"):
    """创建收益曲线图"""
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    
    df = pd.DataFrame(daily_values)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['total_value'],
        mode='lines',
        name='Portfolio Value',
        line=dict(color='#3b82f6', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['cash'],
        mode='lines',
        name='Cash',
        line=dict(color='#10b981', width=1.5, dash='dash')
    ))
    
    fig.update_layout(
        template=template,
        height=400,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="Value"),
        xaxis=dict(title="Date")
    )
    
    return fig

def create_drawdown_chart(daily_values, theme="dark"):
    """创建回撤图"""
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    
    df = pd.DataFrame(daily_values)
    df['cummax'] = df['total_value'].cummax()
    df['drawdown'] = (df['total_value'] - df['cummax']) / df['cummax'] * 100
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['drawdown'],
        mode='lines',
        name='Drawdown %',
        fill='tozeroy',
        line=dict(color='#ef4444', width=1.5),
        fillcolor='rgba(239, 68, 68, 0.2)'
    ))
    
    fig.update_layout(
        template=template,
        height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        showlegend=False,
        yaxis=dict(title="Drawdown %"),
        xaxis=dict(title="Date")
    )
    
    return fig

def create_radar_chart(metrics, theme="dark"):
    """创建雷达图"""
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    
    categories = list(metrics.keys())
    values = list(metrics.values())
    
    fig = go.Figure(data=go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        line=dict(color='#3b82f6', width=2),
        fillcolor='rgba(59, 130, 246, 0.3)'
    ))
    
    fig.update_layout(
        template=template,
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )
        ),
        height=400,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    
    return fig

def create_pie_chart(data, labels, theme="dark"):
    """创建饼图"""
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    
    colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=data,
        hole=0.4,
        marker_colors=colors
    )])
    
    fig.update_layout(
        template=template,
        height=350,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
    )
    
    return fig

def create_bar_chart(x, y, title="", theme="dark"):
    """创建柱状图"""
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    
    fig = go.Figure(data=[go.Bar(
        x=x,
        y=y,
        marker_color='#3b82f6'
    )])
    
    fig.update_layout(
        template=template,
        height=350,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        title=title if title else None,
        xaxis=dict(title=""),
        yaxis=dict(title="")
    )
    
    return fig
