# Smart Stock Monitor (智能看盘助手)

这是一个基于 Python 的智能股票监控工具，旨在帮助股民实时掌握市场趋势、热点板块、寻找价值洼地并提供买卖点参考。

## 核心功能规划

1.  **趋势监控**：每日大盘走势分析，自动识别牛/熊/震荡市。
2.  **热点板块**：实时抓取涨幅领先板块及其领涨股，识别资金流向。
3.  **价值洼地**：基于 PE/PB/股息率等多维度指标筛选低估值优质标的。
4.  **智能买卖点**：集成经典技术指标（如 MACD, RSI, KDJ）与自定义策略，提示交易信号。
5.  **实时通知**：支持飞书/钉钉等平台推送关键异动。

## 技术栈

-   **数据源**: [AkShare](https://github.com/akfamily/akshare) (支持 A 股、港股、美股等)
-   **分析引擎**: Pandas, Numpy
-   **可视化**: Matplotlib / Plotly
-   **回测框架**: Backtrader (可选)

## 快速开始

```bash
# 安装依赖
pip install akshare pandas matplotlib

# 运行监控
python main.py
```

## 免责声明

本工具仅供学习交流使用，不构成任何投资建议。股市有风险，入市需谨慎。
