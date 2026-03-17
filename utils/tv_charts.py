import streamlit.components.v1 as components
import json
import pandas as pd

def render_tv_chart(df: pd.DataFrame, height=500, theme="dark", indicators=None):
    """
    使用 TradingView Lightweight Charts 渲染原生 K 线图
    """
    if df is None or df.empty:
        return

    # 数据整理：LW Charts 需要的时间格式必须是 'YYYY-MM-DD' 字符串或 Unix Timestamp
    df = df.copy()
    if '日期' in df.columns:
        dt_series = pd.to_datetime(df['日期'], errors='coerce')
    elif df.index.name == '日期':
        dt_series = pd.to_datetime(df.index, errors='coerce')
    else:
        # 强制创建一个伪造的连续日期，防止 JS 崩溃
        import datetime
        start_date = datetime.datetime.now() - datetime.timedelta(days=len(df))
        dt_series = pd.date_range(start=start_date, periods=len(df))
        
    # 判断是否包含盘中时间 (判断小时/分钟是否全为0)
    is_intraday = (dt_series.dt.hour != 0).any() or (dt_series.dt.minute != 0).any()
    
    if is_intraday:
        # Intraday 必须用 Unix Timestamp。假定当前系统的 Local Timezone 转换
        df['time'] = dt_series.apply(lambda x: int(x.timestamp()) if pd.notnull(x) else None)
    else:
        # Daily 数据推荐用 YYYY-MM-DD 字符串，避免时区偏移
        df['time'] = dt_series.dt.strftime('%Y-%m-%d')

    # 清洗：删除无效时间、去除重复时间、强制按时间升序 (Lightweight Charts 严格要求)
    df = df.dropna(subset=['time'])
    df = df.drop_duplicates(subset=['time'], keep='last')
    df = df.sort_values(by='time')

    # 主图 K 线数据与成交量数据
    kline_data = []
    volume_data = []
    for _, row in df.iterrows():
        # 处理可能的列名差异 (兼容 AKShare 默认命名与现有处理)
        open_p = row.get('开盘', row.get('open', 0))
        high_p = row.get('最高', row.get('high', 0))
        low_p = row.get('最低', row.get('low', 0))
        close_p = row.get('收盘', row.get('close', 0))
        vol_p = row.get('成交量', row.get('volume', 0))
        
        # 过滤 NaN 值，防止 JSON 注入出异常
        if pd.isna(open_p) or pd.isna(high_p) or pd.isna(low_p) or pd.isna(close_p) or pd.isna(vol_p):
            continue

        c_open, c_close = float(open_p), float(close_p)
        kline_data.append({
            "time": row['time'],
            "open": c_open,
            "high": float(high_p),
            "low": float(low_p),
            "close": c_close
        })
        
        # A 股习惯：涨红跌绿
        vol_color = 'rgba(239, 68, 68, 0.5)' if c_close >= c_open else 'rgba(16, 185, 129, 0.5)'
        volume_data.append({
            "time": row['time'],
            "value": float(vol_p),
            "color": vol_color
        })

    # 处理指标线 (MA, 布林带等)
    lines_data = {}
    import math
    if indicators:
        for ind in indicators:
            if ind in df.columns:
                line_pts = []
                for _, row in df.iterrows():
                    val = row[ind]
                    if pd.notna(val) and not math.isinf(val) and not pd.isna(val):
                        line_pts.append({
                            "time": row['time'],
                            "value": float(val)
                        })
                lines_data[ind] = line_pts

    # 序列化为 JSON
    kline_json = json.dumps(kline_data)
    volume_json = json.dumps(volume_data)
    lines_json = json.dumps(lines_data)

    # 配色方案
    is_dark = (theme == "dark")
    bg_color = '#0e1117' if is_dark else '#ffffff'
    text_color = '#a3a8b8' if is_dark else '#333333'
    grid_color = 'rgba(255, 255, 255, 0.05)' if is_dark else 'rgba(0, 0, 0, 0.05)'

    # 构建 HTML 内容
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; background-color: {bg_color}; overflow: hidden; color: {text_color}; font-family: sans-serif; }}
            #tv_chart {{ width: 100%; height: {height}px; position: relative; }}
            #error_log {{ color: #ef4444; padding: 10px; word-wrap: break-word; font-size: 14px; }}
            #loading {{ display: flex; align-items: center; justify-content: center; height: {height}px; color: #94a3b8; font-size: 14px; }}
            @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
            .spinner {{ width: 20px; height: 20px; border: 2px solid rgba(255,255,255,0.1); border-top-color: #38bdf8; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 10px; }}
            #legend {{
                position: absolute; top: 8px; left: 8px; z-index: 10;
                display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
                padding: 6px 12px;
                background: rgba(15, 23, 42, 0.75);
                backdrop-filter: blur(8px);
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.06);
                font-size: 12px; color: #94a3b8;
                pointer-events: none;
                font-family: 'JetBrains Mono', 'Menlo', monospace;
            }}
            #legend .val {{ color: #e2e8f0; font-weight: 600; }}
            #legend .up {{ color: #ef4444; }}
            #legend .dn {{ color: #10b981; }}
            #legend .lbl {{ color: #64748b; margin-right: 2px; }}
        </style>
    </head>
    <body>
        <div id="loading"><div class="spinner"></div>加载图表引擎中...</div>
        <div id="tv_chart">
            <div id="legend"></div>
        </div>
        <div id="error_log"></div>
        <script>
            // 双 CDN 容灾加载
            function loadScript(url) {{
                return new Promise(function(resolve, reject) {{
                    var s = document.createElement('script');
                    s.src = url;
                    s.onload = resolve;
                    s.onerror = reject;
                    document.head.appendChild(s);
                }});
            }}

            var cdnUrls = [
                'https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js',
                'https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js'
            ];

            function tryLoad(idx) {{
                if (idx >= cdnUrls.length) {{
                    document.getElementById('loading').innerHTML = '⚠️ 图表引擎加载失败，请检查网络连接';
                    return;
                }}
                loadScript(cdnUrls[idx]).then(initChart).catch(function() {{
                    tryLoad(idx + 1);
                }});
            }}

            function initChart() {{
                document.getElementById('loading').style.display = 'none';
                try {{
                const chartOptions = {{
                    layout: {{
                        textColor: '{text_color}',
                        background: {{ type: 'solid', color: '{bg_color}' }}
                    }},
                    grid: {{
                        vertLines: {{ color: '{grid_color}' }},
                        horzLines: {{ color: '{grid_color}' }}
                    }},
                    crosshair: {{
                        mode: LightweightCharts.CrosshairMode.Normal,
                    }},
                    rightPriceScale: {{
                        borderColor: '{grid_color}',
                    }},
                    timeScale: {{
                        borderColor: '{grid_color}',
                        timeVisible: true,
                        secondsVisible: false,
                    }},
                    watermark: {{
                        color: 'rgba(255, 255, 255, 0.04)',
                        visible: true,
                        text: 'Smart Stock Monitor',
                        fontSize: 48,
                        horzAlign: 'center',
                        vertAlign: 'center',
                    }}
                }};

                const chart = LightweightCharts.createChart(document.getElementById('tv_chart'), chartOptions);
                
                // 自适应尺寸
                new ResizeObserver(entries => {{
                    if (entries.length === 0 || entries[0].target !== document.body) {{ return; }}
                    chart.applyOptions({{ width: document.body.clientWidth, height: document.body.clientHeight }});
                }}).observe(document.body);

                // 蜡烛图
                const candlestickSeries = chart.addCandlestickSeries({{
                    upColor: '#ef4444',      // A股涨红
                    downColor: '#10b981',    // A股跌绿
                    borderVisible: false,
                    wickUpColor: '#ef4444',
                    wickDownColor: '#10b981',
                }});

                const mainData = {kline_json};
                candlestickSeries.setData(mainData);

                // 成交量辅助图 (位于底部 20% 区域)
                const volumeSeries = chart.addHistogramSeries({{
                    priceFormat: {{ type: 'volume' }},
                    priceScaleId: '', // 作为独立覆盖层
                }});

                chart.priceScale('').applyOptions({{
                    scaleMargins: {{
                        top: 0.8,    // 最高占比图表 20%
                        bottom: 0,
                    }},
                }});

                const volumeData = {volume_json};
                volumeSeries.setData(volumeData);

                // 叠加指标线
                const linesData = {lines_json};
                const colors = ['#3b82f6', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6'];
                let colorIdx = 0;

                for (const indName in linesData) {{
                    const lineSeries = chart.addLineSeries({{
                        color: colors[colorIdx % colors.length],
                        lineWidth: 2,
                        title: indName
                    }});
                    lineSeries.setData(linesData[indName]);
                    colorIdx++;
                }}

                // 留出右侧空间
                chart.timeScale().fitContent();

                // ---- 十字光标浮动信息 ----
                const legendEl = document.getElementById('legend');
                // 构建 mainData 索引 (time -> bar)
                const barMap = {{}};
                mainData.forEach(b => {{ barMap[b.time] = b; }});
                const volMap = {{}};
                volumeData.forEach(v => {{ volMap[v.time] = v.value; }});

                function fmtNum(n) {{ return n != null ? n.toFixed(2) : '-'; }}
                function fmtVol(v) {{
                    if (v == null) return '-';
                    if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿';
                    if (v >= 1e4) return (v / 1e4).toFixed(1) + '万';
                    return v.toFixed(0);
                }}

                // 默认显示最新一根
                function showBar(bar, vol) {{
                    if (!bar) {{ legendEl.innerHTML = ''; return; }}
                    const chg = bar.open > 0 ? ((bar.close - bar.open) / bar.open * 100) : 0;
                    const cls = bar.close >= bar.open ? 'up' : 'dn';
                    const arrow = bar.close >= bar.open ? '▲' : '▼';
                    legendEl.innerHTML =
                        `<span class="lbl">日期</span><span class="val">${{bar.time}}</span>` +
                        `<span class="lbl">开</span><span class="val">${{fmtNum(bar.open)}}</span>` +
                        `<span class="lbl">高</span><span class="up">${{fmtNum(bar.high)}}</span>` +
                        `<span class="lbl">低</span><span class="dn">${{fmtNum(bar.low)}}</span>` +
                        `<span class="lbl">收</span><span class="${{cls}}">${{fmtNum(bar.close)}}</span>` +
                        `<span class="${{cls}}">${{arrow}}${{Math.abs(chg).toFixed(2)}}%</span>` +
                        `<span class="lbl">量</span><span class="val">${{fmtVol(vol)}}</span>`;
                }}

                // 初始化显示最后一根
                if (mainData.length > 0) {{
                    const last = mainData[mainData.length - 1];
                    showBar(last, volMap[last.time]);
                }}

                chart.subscribeCrosshairMove(function(param) {{
                    if (!param.time) {{
                        // 光标移出图表区域，显示最新
                        if (mainData.length > 0) {{
                            const last = mainData[mainData.length - 1];
                            showBar(last, volMap[last.time]);
                        }}
                        return;
                    }}
                    const bar = barMap[param.time];
                    const vol = volMap[param.time];
                    showBar(bar, vol);
                }});

            }} catch (err) {{
                document.getElementById('error_log').innerHTML += '<p>Catch: ' + err.message + '</p>';
            }}
            }}

            // 启动加载
            tryLoad(0);
        </script>
    </body>
    </html>
    """

    # 渲染 Streamlit HTML 组件
    components.html(html_content, height=height)
