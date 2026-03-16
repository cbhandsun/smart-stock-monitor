# Smart Stock Monitor v5.0 Quantum Pro

智能股票监控系统 v5.0 Quantum Pro 版本

## 🚀 新功能特性

### Phase 2: 功能增强
- **📁 组合管理模块** (`modules/portfolio/watchlist_manager.py`)
  - 创建和管理多个股票组合
  - 支持持仓记录和标签管理
  - 组合导入导出功能

- **🔔 预警提醒系统** (`modules/alerts/alert_system.py`)
  - 价格上下限预警
  - 涨跌幅预警
  - RSI指标预警
  - 成交量异常预警

- **📊 回测引擎** (`modules/backtest/backtest_engine.py`)
  - 支持多种策略模板
  - 完整的绩效分析
  - 可视化收益曲线

- **📚 研报中心** (`modules/research/research_center.py`)
  - 个股研报查询
  - 行业研报搜索
  - 评级分布分析

### Phase 3: UI/UX 升级
- **专业金融终端布局** - 多页面导航设计
- **暗黑/亮色主题切换** (`visualization/charts.py`)
- **优化数据可视化** - 交互式图表支持

### Phase 4: AI 能力
- **多模型支持** (`modules/ai/multi_model.py`)
  - GPT-4
  - Claude
  - Gemini
  - Kimi
  - DeepSeek

- **智能问答系统** (`modules/ai/intelligent_qa.py`)
  - 自然语言查询
  - 股票信息问答
  - 技术指标解读

- **预测分析模块** (`modules/ai/predictive_analysis.py`)
  - 趋势预测
  - 风险评估
  - 支撑阻力位计算

- **个性化推荐引擎** (`modules/ai/recommendation_engine.py`)
  - 基于用户偏好的推荐
  - 协同过滤推荐

### Phase 5: 架构优化
- **Redis缓存层** (`cache/redis_cache.py`)
  - 高速数据缓存
  - 会话管理

- **Celery异步任务** (`tasks/`)
  - 定时数据更新
  - 预警检查
  - 报告生成

- **用户认证系统** (`auth/user_auth.py`)
  - JWT令牌认证
  - 密码加密
  - 用户管理

- **数据库持久化** (`database/models.py`)
  - SQLAlchemy ORM
  - 完整的模型定义

## 📁 项目结构

```
smart-stock-monitor/
├── app.py                      # 主应用入口 (已更新)
├── requirements.txt            # 依赖列表
├── check_system.py             # 系统检查脚本
│
├── modules/
│   ├── portfolio/              # 组合管理模块
│   │   └── watchlist_manager.py
│   ├── alerts/                 # 预警系统模块
│   │   └── alert_system.py
│   ├── backtest/               # 回测引擎模块
│   │   └── backtest_engine.py
│   ├── research/               # 研报中心模块
│   │   └── research_center.py
│   └── ai/                     # AI能力模块
│       ├── multi_model.py
│       ├── intelligent_qa.py
│       ├── predictive_analysis.py
│       └── recommendation_engine.py
│
├── visualization/              # 可视化模块
│   └── charts.py
│
├── cache/                      # 缓存模块
│   └── redis_cache.py
│
├── tasks/                      # Celery异步任务
│   ├── celery_config.py
│   ├── market_data.py
│   ├── alerts.py
│   └── reports.py
│
├── auth/                       # 用户认证模块
│   └── user_auth.py
│
├── database/                   # 数据库模块
│   └── models.py
│
└── data/                       # 数据存储目录
    ├── portfolios/             # 组合数据
    └── alerts/                 # 预警数据
```

## 🛠️ 安装依赖

```bash
pip install -r requirements.txt
```

## 🚀 启动系统

```bash
# 启动主应用
streamlit run app.py

# 启动Celery Worker (可选)
celery -A tasks.celery_config worker --loglevel=info

# 启动Celery Beat (可选)
celery -A tasks.celery_config beat --loglevel=info
```

## 🔧 环境变量配置

创建 `.env` 文件:

```env
# AI模型API密钥
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key
KIMI_API_KEY=your_kimi_key
DEEPSEEK_API_KEY=your_deepseek_key

# Redis配置
REDIS_URL=redis://localhost:6379/0

# 数据库配置
DATABASE_URL=sqlite:///./data/stock_monitor.db

# JWT密钥
JWT_SECRET_KEY=your_secret_key

# Celery配置
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

## 📊 功能页面

1. **📡 实时信号流** - 市场行情和策略捕捉
2. **🧬 深度决策中心** - 个股分析和AI报告
3. **📁 组合管理** - 自选股组合管理
4. **🔔 预警系统** - 价格和技术指标预警
5. **📊 回测引擎** - 策略回测和绩效分析
6. **📚 研报中心** - 研报查询和分析
7. **🤖 AI问答** - 智能问答系统
8. **🔮 预测分析** - 趋势预测和风险评估
9. **⚙️ 设置** - 主题和系统配置

## 📝 更新日志

### v5.0 Quantum Pro (2026-03-06)
- ✅ 实现自选股组合管理模块
- ✅ 实现预警提醒系统
- ✅ 实现回测引擎
- ✅ 实现研报中心
- ✅ 优化Streamlit界面，添加专业金融终端布局
- ✅ 实现暗黑/亮色主题切换
- ✅ 优化数据可视化图表
- ✅ 实现多模型支持 (AI模块)
- ✅ 实现智能问答系统
- ✅ 实现预测分析模块
- ✅ 实现个性化推荐引擎
- ✅ 实现Redis缓存层
- ✅ 配置Celery异步任务
- ✅ 实现用户认证系统
- ✅ 配置数据库持久化

## 📄 许可证

MIT License
