#!/bin/bash
# Smart Stock Monitor 容器启动服务
# 这个脚本应该在容器启动时执行

PROJECT_DIR="/home/node/.openclaw/workspace-dev/smart-stock-monitor"
VENV_DIR="/home/node/.openclaw/workspace-dev/venv"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="/tmp/stock-monitor.pid"
PORT=8501

# 创建日志目录
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/startup.log"
}

# 等待系统就绪
sleep 5

log "=== Smart Stock Monitor 启动服务 ==="

# 检查虚拟环境
if [ ! -f "$VENV_DIR/bin/streamlit" ]; then
    log "安装依赖中..."
    $VENV_DIR/bin/python3 -m pip install -r "$PROJECT_DIR/requirements.txt" -q >> "$LOG_DIR/startup.log" 2>&1
fi

# 检查是否已在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        log "应用已在运行 (PID: $OLD_PID)"
        exit 0
    fi
fi

# 检查端口占用
if ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
    log "端口 $PORT 被占用，尝试释放..."
    fuser -k "$PORT/tcp" 2>/dev/null || true
    sleep 2
fi

# 启动应用
export PATH="$VENV_DIR/bin:$PATH"
cd "$PROJECT_DIR"

log "启动 Streamlit 服务..."
nohup streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    --server.maxUploadSize=200 \
    >> "$LOG_DIR/streamlit.log" 2>&1 &

PID=$!
echo $PID > "$PID_FILE"

# 等待启动
sleep 3

if ps -p "$PID" > /dev/null 2>&1; then
    log "✅ 启动成功! PID: $PID, 端口: $PORT"
else
    log "❌ 启动失败"
    exit 1
fi
