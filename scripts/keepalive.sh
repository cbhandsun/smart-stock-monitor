#!/bin/bash
export PATH="/home/node/.local/bin:$PATH"
cd /home/node/.openclaw/workspace-dev/smart-stock-monitor

while true; do
    if ! pgrep -f "streamlit run app.py" > /dev/null; then
        echo "$(date): Streamlit not running, starting..."
        nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true > /dev/null 2>&1 &
    fi
    sleep 30
done
