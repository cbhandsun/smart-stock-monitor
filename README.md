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

## 🐳 Docker 部署

默认 `docker-compose.yml` 面向长期部署：应用代码固定在镜像内，只暴露 Streamlit Web 端口，Redis/PostgreSQL 仅在 Docker 内网访问。

```bash
cp .env.example .env
# 编辑 .env，填入 API Key、Tushare Token、PG_PASSWORD、JWT_SECRET_KEY 等真实值

docker compose up -d --build
```

Compose 会先运行 `alembic upgrade head`；迁移成功后才启动 Web、Worker 和 Beat。`PG_PASSWORD` 或至少 32 位的 `JWT_SECRET_KEY` 缺失时部署会直接拒绝启动。

访问地址默认是 `http://服务器IP:8502`，可通过 `.env` 里的 `APP_PORT` 调整宿主机端口。

开发调试时如果需要把当前源码目录挂进容器，并临时暴露 Redis/PostgreSQL：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

## 🛠️ 安装依赖

```bash
pip install -r requirements.txt
alembic upgrade head
```

## 🚀 启动系统

```bash
# 启动主应用
streamlit run streamlit_app.py

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

# Docker 发布标识与端口
APP_VERSION=replace-with-image-version-or-git-sha
APP_PORT=8502

# Docker 内部 PostgreSQL 配置
PG_USER=ssm
PG_DATABASE=stock_data
PG_PASSWORD=replace-with-a-long-random-database-password

# JWT 签名密钥（至少 32 位，生产环境使用密码管理系统生成与保管）
JWT_SECRET_KEY=replace-with-at-least-32-random-characters

# 可选：通用 Webhook 必须同时配置 HTTPS 地址与允许主机
ALERT_WEBHOOK_URL=https://alerts.example.com/ssm
ALERT_WEBHOOK_ALLOWED_HOSTS=alerts.example.com
```

Compose 会在容器网络内生成 `DATABASE_URL`、`CELERY_BROKER_URL` 和
`CELERY_RESULT_BACKEND`，Docker 部署不需要在 `.env` 中把这些地址指向
`localhost`。不要提交 `.env`，也不要复用示例值。

## 备份、恢复与回滚

发布前备份 PostgreSQL，并把备份文件保存到加密且有保留策略的位置：

```bash
mkdir -p backups
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/stock_data.dump
docker compose exec -T postgres pg_restore --list < backups/stock_data.dump
```

恢复会覆盖目标数据库，只能在已核对 Compose 项目和目标库名、停止 Web/Worker/Beat 并再次备份后执行：

```bash
docker compose stop stock-monitor worker beat
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' < backups/stock_data.dump
docker compose run --rm migrate
docker compose up -d stock-monitor worker beat
```

首次发布或重大迁移前，应先把备份恢复到一个不映射宿主机端口的全新
PostgreSQL 实例，逐表比较行数、核对 `alembic_version`，并检查外键约束后再
进入生产变更窗口。只验证 `pg_restore --list` 不等同于完成恢复演练。

镜像通过 `APP_VERSION`/Git SHA 标识。回滚时使用上一已验收的不可变镜像 digest，先验证迁移是否向后兼容；不兼容时按迁移说明回退数据库或从备份恢复，禁止只回滚 Web 容器。

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
