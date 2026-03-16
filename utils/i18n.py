"""
🌐 国际化翻译字典
所有 UI 文本集中管理
"""

LANG_MAP = {
    "zh": {
        # 全局
        "title": "SSM 智投终端",
        "subtitle": "Quantum Pro v7.0",
        "refresh": "🔄 刷新",
        "loading": "加载中...",
        "no_data": "暂无数据",
        "save": "保存",
        "cancel": "取消",
        "delete": "删除",
        "confirm": "确认",
        "export": "📤 导出数据",
        "export_csv": "📊 导出 CSV",
        "export_report": "📝 导出报告",

        # 导航
        "market_discovery": "📡 实时信号流",
        "dna_analysis": "🧬 深度决策中心",
        "strat_capture": "策略捕捉引擎",
        "invoke_ai": "启动多模态 AI 研判",
        "overweight": "建议增持",
        "hold": "建议观察",
        "select_invoke": "请锁定标的以启动分析",
        "fin_health": "财务健康分",
        "rsi_strength": "相对强度(RSI)",
        "ann_vol": "年化波动率",
        "agent_verdict": "智能演算结论",
        "portfolio": "📁 组合管理",
        "alerts": "🔔 预警系统",
        "backtest": "📊 回测引擎",
        "research": "📚 研报中心",
        "ai_chat": "🤖 AI问答",
        "predict": "🔮 预测分析",
        "settings": "⚙️ 设置",
        "research_analyzer": "📖 智能研报",
        "sentiment": "💭 情绪分析",
        "anomaly": "🚨 异常监控",
        "investment_advisor": "🎯 智能投顾",
        "time_period": "时间周期",
        "indicators": "技术指标",

        # 市场页面
        "market_overview": "市场概览",
        "stock_analysis": "个股分析",
        "strategy_value": "💎 价值发现",
        "strategy_momentum": "🔥 动量追击",
        "strategy_growth": "🌟 成长之星",
        "sync_workspace": "同步到工作区",
        "data_time": "数据时间",
        "ai_report_cached": "📄 已有今日 AI 报告",
        "ai_report_generate": "🤖 点击生成 AI 分析报告",
        "ai_analyzing": "🧠 AI 正在分析市场数据...",
        "analysis_done": "✅ 分析完成！",
        "report_saved": "报告已保存",

        # 组合管理
        "my_portfolios": "我的组合",
        "create_portfolio": "创建组合",
        "portfolio_name": "组合名称",
        "portfolio_desc": "组合描述",

        # 预警系统
        "active_alerts": "活跃预警",
        "create_alert": "创建预警",
        "alert_type": "预警类型",
        "threshold": "阈值",

        # 回测
        "start_backtest": "开始回测",
        "total_return": "总收益率",
        "annual_return": "年化收益率",
        "max_drawdown": "最大回撤",
        "sharpe_ratio": "夏普比率",

        # 预测
        "trend_prediction": "趋势预测",
        "risk_assessment": "风险评估",
        "support_resistance": "支撑阻力",
        "predict_method": "预测方法",
        "predict_days": "预测天数",
        "current_price": "当前价格",
        "predicted_price": "预测价格",

        # 情绪
        "sentiment_index": "情绪指数",
        "sentiment_monitor": "情绪监控",
        "sentiment_report": "情绪报告",
        "bullish": "看多",
        "bearish": "看空",
        "neutral": "中性",

        # 异常
        "realtime_anomaly": "实时异常",
        "history_anomaly": "历史异常",
        "monitor_settings": "监控设置",

        # 投顾
        "user_profile": "用户画像",
        "asset_allocation": "资产配置",
        "risk_eval": "风险评估",
        "investment_advice": "投资建议",

        # 设置
        "appearance": "外观设置",
        "system_info": "系统信息",
        "theme": "主题",

        # 认证
        "login": "🔑 登录",
        "register": "📝 注册",
        "username": "用户名",
        "password": "密码",
        "email": "邮箱",
        "logout": "🚪 登出",
        "login_success": "✅ 登录成功！",
        "login_failed": "❌ 用户名或密码错误",
    },

    "en": {
        # Global
        "title": "SSM Quantum",
        "subtitle": "Quantum Pro v7.0",
        "refresh": "🔄 Refresh",
        "loading": "Loading...",
        "no_data": "No data available",
        "save": "Save",
        "cancel": "Cancel",
        "delete": "Delete",
        "confirm": "Confirm",
        "export": "📤 Export",
        "export_csv": "📊 Export CSV",
        "export_report": "📝 Export Report",

        # Navigation
        "market_discovery": "📡 Signal Stream",
        "dna_analysis": "🧬 Decision Center",
        "strat_capture": "Strategy Engine",
        "invoke_ai": "Invoke Multi-modal AI",
        "overweight": "Overweight",
        "hold": "Neutral",
        "select_invoke": "Select Target for Synthesis",
        "fin_health": "Financial Score",
        "rsi_strength": "RSI (14)",
        "ann_vol": "Annual Vol",
        "agent_verdict": "Verdict",
        "portfolio": "📁 Portfolio",
        "alerts": "🔔 Alerts",
        "backtest": "📊 Backtest",
        "research": "📚 Research",
        "ai_chat": "🤖 AI Chat",
        "predict": "🔮 Predict",
        "settings": "⚙️ Settings",
        "research_analyzer": "📖 Research AI",
        "sentiment": "💭 Sentiment",
        "anomaly": "🚨 Anomaly Monitor",
        "investment_advisor": "🎯 AI Advisor",
        "time_period": "Time Period",
        "indicators": "Indicators",

        # Market
        "market_overview": "Market Overview",
        "stock_analysis": "Stock Analysis",
        "strategy_value": "💎 Value Discovery",
        "strategy_momentum": "🔥 Momentum Max",
        "strategy_growth": "🌟 Growth Star",
        "sync_workspace": "Sync to Workspace",
        "data_time": "Data Time",
        "ai_report_cached": "📄 Today's AI report available",
        "ai_report_generate": "🤖 Click to generate AI analysis",
        "ai_analyzing": "🧠 AI analyzing market data...",
        "analysis_done": "✅ Analysis complete!",
        "report_saved": "Report saved",

        # Portfolio
        "my_portfolios": "My Portfolios",
        "create_portfolio": "Create Portfolio",
        "portfolio_name": "Portfolio Name",
        "portfolio_desc": "Description",

        # Alerts
        "active_alerts": "Active Alerts",
        "create_alert": "Create Alert",
        "alert_type": "Alert Type",
        "threshold": "Threshold",

        # Backtest
        "start_backtest": "Start Backtest",
        "total_return": "Total Return",
        "annual_return": "Annual Return",
        "max_drawdown": "Max Drawdown",
        "sharpe_ratio": "Sharpe Ratio",

        # Prediction
        "trend_prediction": "Trend Prediction",
        "risk_assessment": "Risk Assessment",
        "support_resistance": "Support & Resistance",
        "predict_method": "Method",
        "predict_days": "Forecast Days",
        "current_price": "Current Price",
        "predicted_price": "Predicted Price",

        # Sentiment
        "sentiment_index": "Sentiment Index",
        "sentiment_monitor": "Sentiment Monitor",
        "sentiment_report": "Sentiment Report",
        "bullish": "Bullish",
        "bearish": "Bearish",
        "neutral": "Neutral",

        # Anomaly
        "realtime_anomaly": "Real-time Anomaly",
        "history_anomaly": "Historical Anomaly",
        "monitor_settings": "Monitor Settings",

        # Advisor
        "user_profile": "User Profile",
        "asset_allocation": "Asset Allocation",
        "risk_eval": "Risk Evaluation",
        "investment_advice": "Investment Advice",

        # Settings
        "appearance": "Appearance",
        "system_info": "System Info",
        "theme": "Theme",

        # Auth
        "login": "🔑 Login",
        "register": "📝 Register",
        "username": "Username",
        "password": "Password",
        "email": "Email",
        "logout": "🚪 Logout",
        "login_success": "✅ Login successful!",
        "login_failed": "❌ Invalid username or password",
    }
}


def get_lang(lang_code: str = 'zh') -> dict:
    """获取指定语言的翻译字典"""
    return LANG_MAP.get(lang_code, LANG_MAP['zh'])
