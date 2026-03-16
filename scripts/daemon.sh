#!/bin/bash
# Smart Stock Monitor 守护进程启动脚本
# 用法: ./daemon.sh [start|stop|status|restart]

PROJECT_DIR="/home/node/.openclaw/workspace-dev/smart-stock-monitor"
VENV_DIR="/home/node/.openclaw/workspace-dev/venv"
PID_FILE="/tmp/stock-monitor.pid"
LOG_FILE="$PROJECT_DIR/logs/daemon.log"
PORT=8501

mkdir -p "$PROJECT_DIR/logs"

check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

start() {
    if check_running; then
        echo "✅ Smart Stock Monitor 已在运行 (PID: $(cat $PID_FILE))"
        echo "   访问地址: http://localhost:$PORT"
        return 0
    fi
    
    echo "🚀 启动 Smart Stock Monitor..."
    
    # 检查虚拟环境
    if [ ! -f "$VENV_DIR/bin/streamlit" ]; then
        echo "📦 安装依赖中..."
        $VENV_DIR/bin/python3 -m pip install -r "$PROJECT_DIR/requirements.txt" >> "$LOG_FILE" 2>&1
    fi
    
    export PATH="$VENV_DIR/bin:$PATH"
    cd "$PROJECT_DIR"
    
    # 检查端口占用
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "🔄 端口 $PORT 被占用，正在释放..."
        lsof -Pi :$PORT -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
        sleep 2
    fi
    
    # 启动应用
    nohup streamlit run app.py \
        --server.port=$PORT \
        --server.address=0.0.0.0 \
        --server.headless=true \
        --browser.gatherUsageStats=false \
        >> "$LOG_FILE" 2>&1 &
    
    NEW_PID=$!
    echo $NEW_PID > "$PID_FILE"
    
    # 等待启动
    sleep 3
    
    if ps -p "$NEW_PID" > /dev/null 2>&1; then
        echo "✅ 启动成功!"
        echo "   PID: $NEW_PID"
        echo "   访问地址: http://localhost:$PORT"
        echo "   日志文件: $LOG_FILE"
    else
        echo "❌ 启动失败，查看日志:"
        tail -20 "$LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop() {
    if ! check_running; then
        echo "ℹ️ Smart Stock Monitor 未在运行"
        rm -f "$PID_FILE"
        return 0
    fi
    
    PID=$(cat "$PID_FILE")
    echo "🛑 停止 Smart Stock Monitor (PID: $PID)..."
    
    kill "$PID" 2>/dev/null
    sleep 2
    
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️ 强制终止..."
        kill -9 "$PID" 2>/dev/null
    fi
    
    rm -f "$PID_FILE"
    echo "✅ 已停止"
}

status() {
    if check_running; then
        PID=$(cat "$PID_FILE")
        echo "✅ Smart Stock Monitor 运行中"
        echo "   PID: $PID"
        echo "   访问地址: http://localhost:$PORT"
        echo "   日志文件: $LOG_FILE"
    else
        echo "ℹ️ Smart Stock Monitor 未在运行"
    fi
}

restart() {
    stop
    sleep 1
    start
}

# 主逻辑
case "${1:-start}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    restart)
        restart
        ;;
    *)
        echo "用法: $0 [start|stop|status|restart]"
        exit 1
        ;;
esac
