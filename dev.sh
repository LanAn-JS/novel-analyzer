#!/bin/bash
# Novel Analyzer 开发模式启动（前后端分离）
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  📚 Novel Analyzer - 开发模式"
echo "  by:蓝桉, 微信:379794746"
echo "========================================"

# 后端
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r backend/requirements.txt -q
else
    source venv/bin/activate
fi

echo "🚀 启动后端: http://localhost:8989"
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8989 --reload &
BACK_PID=$!
cd "$SCRIPT_DIR"

# 前端
echo "🚀 启动前端: http://localhost:3000"
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run dev &
FRONT_PID=$!
cd "$SCRIPT_DIR"

echo ""
echo "✅ 服务已启动"
echo "   后端PID: $BACK_PID"
echo "   前端PID: $FRONT_PID"
echo "   按 Ctrl+C 停止"

trap "kill $BACK_PID $FRONT_PID 2>/dev/null; exit" INT TERM
wait
