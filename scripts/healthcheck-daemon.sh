#!/bin/bash
# Smart Stock Monitor 服务守护进程
# 这个脚本会在后台持续运行，确保服务存活

PROJECT_DIR="/home/node/.openclaw/workspace-dev/smart-stock-monitor"
VENV_DIR="/home/node/.openclaw/workspace-dev/venv"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="/tmp/stock-monitor.pid"
PORT=8501
CHECK_INTERVAL=30  # 每30秒检查一次

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [守护进程] $1" >> "$LOG_DIR/healthcheck.log"
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

start_service() {
    log "启动 Smart Stock Monitor..."
    
    export PATH="$VENV_DIR/bin:$PATH"
    cd "$PROJECT_DIR"
    
    # 检查端口占用
    if ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
        log "端口 $PORT 被占用"
        return 1
    fi
    
    nohup streamlit run app.py \
        --server.port=$PORT \
        --server.address=0.0.0.0 \
        --server.headless=true \
        --browser.gatherUsageStats=false \
        >> "$LOG_DIR/streamlit.log" 2>&1 &
    
    local pid=$!
    echo $pid > "$PID_FILE"
    
    sleep 3
    
    if ps -p "$pid" > /dev/null 2>&1; then
        log "✅ 启动成功! PID: $pid"
        return 0
    else
        log "❌ 启动失败"
        rm -f "$PID_FILE"
        return 1
    fi
}

# 主循环
log "=== 服务守护进程启动 ==="

while true; do
    if ! is_running; then
        log "服务未运行，尝试启动..."
        start_service
    fi
    sleep $CHECK_INTERVAL
done
