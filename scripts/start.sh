#!/bin/bash
# Smart Stock Monitor 自动启动脚本
# 在容器启动时运行

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动 Smart Stock Monitor..."

PROJECT_DIR="/home/node/.openclaw/workspace-dev/smart-stock-monitor"
VENV_DIR="/home/node/.openclaw/workspace-dev/venv"
LOG_FILE="/home/node/.openclaw/workspace-dev/smart-stock-monitor/logs/startup.log"

# 创建日志目录
mkdir -p "$(dirname "$LOG_FILE")"

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "[错误] 虚拟环境不存在: $VENV_DIR" | tee -a "$LOG_FILE"
    exit 1
fi

# 激活虚拟环境
export PATH="$VENV_DIR/bin:$PATH"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# 检查 streamlit 是否安装
if ! command -v streamlit &> /dev/null; then
    echo "[错误] streamlit 未安装，尝试安装依赖..." | tee -a "$LOG_FILE"
    python3 -m pip install -r "$PROJECT_DIR/requirements.txt" >> "$LOG_FILE" 2>&1
fi

# 检查端口是否被占用
PORT=8501
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "[警告] 端口 $PORT 已被占用，尝试停止旧进程..." | tee -a "$LOG_FILE"
    lsof -Pi :$PORT -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
    sleep 2
fi

# 启动 Streamlit
cd "$PROJECT_DIR"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动 Streamlit 应用..." | tee -a "$LOG_FILE"

nohup streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    >> "$LOG_FILE" 2>&1 &

STREAMLIT_PID=$!
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Streamlit PID: $STREAMLIT_PID" | tee -a "$LOG_FILE"

# 等待启动
sleep 5

# 检查是否成功启动
if ps -p $STREAMLIT_PID > /dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Smart Stock Monitor 启动成功!" | tee -a "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 访问地址: http://localhost:8501" | tee -a "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 启动失败，检查日志..." | tee -a "$LOG_FILE"
    tail -20 "$LOG_FILE"
    exit 1
fi
