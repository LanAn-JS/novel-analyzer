#!/bin/bash
# 停止 Novel Analyzer 服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$SCRIPT_DIR/logs/server.pid" ]; then
    PID=$(cat "$SCRIPT_DIR/logs/server.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "✅ 已停止 Novel Analyzer (PID: $PID)"
    else
        echo "⚠️ 进程 $PID 不存在，可能已停止"
    fi
    rm -f "$SCRIPT_DIR/logs/server.pid"
else
    # 尝试用端口查找
    PID=$(lsof -ti:8989 2>/dev/null)
    if [ -n "$PID" ]; then
        kill $PID
        echo "✅ 已停止 Novel Analyzer (PID: $PID)"
    else
        echo "⚠️ 未找到运行中的服务"
    fi
fi
