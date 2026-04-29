#!/bin/bash
# ============================================
#  📚 Novel Analyzer - 小说智能分析系统
#  by:蓝桉, 微信:379794746
# ============================================
#
# 启动方式：
#   双击此文件（Linux桌面环境）
#   或命令行: ./start.sh
#   或后台运行: ./start.sh --daemon
#
# 访问地址: http://localhost:8989
# API文档:  http://localhost:8989/docs
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ======== 日志配置 ========
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/novel-analyzer-$(date +%Y%m%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "  📚 Novel Analyzer - 小说智能分析系统"
log "  by:蓝桉, 微信:379794746"
log "========================================"

# ======== 清除代理环境变量 ========
# 国内API不走代理，防止socks协议报错
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy
log "🧹 已清除代理环境变量"

# ======== 检查Python ========
PYTHON_CMD=""
if [ -d "$SCRIPT_DIR/venv" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
    
    # GPU加速：设置CUDA/cuDNN库路径（在Python启动前设置，确保onnxruntime-gpu能找到）
    CUDA_LIB_PATH=$($PYTHON_CMD -c "
import os
paths = []
for pkg in ['nvidia.cudnn', 'nvidia.cublas', 'nvidia.cuda_nvrtc']:
    try:
        m = __import__(pkg, fromlist=['__path__'])
        d = os.path.join(m.__path__[0], 'lib')
        if os.path.isdir(d):
            paths.append(d)
    except ImportError:
        pass
print(':'.join(paths))
" 2>/dev/null)
    if [ -n "$CUDA_LIB_PATH" ]; then
        export LD_LIBRARY_PATH="$CUDA_LIB_PATH${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        log "🎮 GPU加速库路径已设置"
    fi
else
    # 尝试系统Python
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &>/dev/null; then
        PYTHON_CMD="python"
    else
        log "❌ 未找到Python，请安装Python 3.10+"
        read -p "按回车退出..."
        exit 1
    fi
fi

# ======== 首次运行：创建虚拟环境并安装依赖 ========
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    log "🔧 首次运行，创建Python虚拟环境..."
    $PYTHON_CMD -m venv "$SCRIPT_DIR/venv"
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
    
    log "📦 安装后端依赖（首次可能需要几分钟）..."
    "$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/backend/requirements.txt" -q 2>&1 | tee -a "$LOG_FILE"
    log "✅ 后端依赖安装完成"
fi

# ======== 首次运行：构建前端 ========
if [ ! -d "$SCRIPT_DIR/frontend/dist" ]; then
    log "🔧 首次运行，构建前端..."
    if ! command -v npm &>/dev/null; then
        log "❌ 未找到npm，请安装Node.js 18+"
        read -p "按回车退出..."
        exit 1
    fi
    cd "$SCRIPT_DIR/frontend"
    npm install 2>&1 | tee -a "$LOG_FILE"
    npm run build 2>&1 | tee -a "$LOG_FILE"
    cd "$SCRIPT_DIR"
    log "✅ 前端构建完成"
fi

# ======== 检查端口占用 ========
PORT=8989
if lsof -ti:$PORT &>/dev/null; then
    log "⚠️ 端口 $PORT 已被占用，尝试释放..."
    kill $(lsof -ti:$PORT) 2>/dev/null || true
    sleep 1
fi

# ======== 启动后端 ========
DAEMON_MODE=false
if [ "$1" = "--daemon" ]; then
    DAEMON_MODE=true
fi

log "🚀 启动后端服务..."
log "   访问地址: http://localhost:$PORT"
log "   API文档:  http://localhost:$PORT/docs"
log "   日志文件: $LOG_FILE"

cd "$SCRIPT_DIR/backend"

if [ "$DAEMON_MODE" = true ]; then
    # 后台运行
    nohup "$SCRIPT_DIR/venv/bin/uvicorn" app.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --log-level info \
        >> "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$SCRIPT_DIR/logs/server.pid"
    log "✅ 后台启动成功 (PID: $SERVER_PID)"
    log "   停止命令: kill $SERVER_PID 或 ./stop.sh"
else
    # 前台运行：stderr直接到终端（进度条\r原地刷新），日志由Python logging自动写文件
    "$SCRIPT_DIR/venv/bin/uvicorn" app.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --log-level info &
    SERVER_PID=$!
    
    # 等待服务启动
    sleep 3
    
    # 检查是否启动成功
    if curl -s "http://localhost:$PORT/api/health" > /dev/null 2>&1; then
        log "✅ 服务启动成功！"
    else
        log "❌ 服务启动失败，请查看日志: $LOG_FILE"
        read -p "按回车退出..."
        exit 1
    fi
    
    # ======== 自动打开浏览器 ========
    log "🌐 正在打开浏览器..."
    if command -v xdg-open &>/dev/null; then
        xdg-open "http://localhost:$PORT" 2>/dev/null &
    elif command -v sensible-browser &>/dev/null; then
        sensible-browser "http://localhost:$PORT" 2>/dev/null &
    elif [ "$(uname)" = "Darwin" ]; then
        open "http://localhost:$PORT" &
    fi
    
    log "========================================"
    log "  ✅ Novel Analyzer 正在运行"
    log "  🌐 http://localhost:$PORT"
    log "  📋 日志: $LOG_FILE"
    log "  🛑 关闭此窗口或按 Ctrl+C 停止"
    log "========================================"
    
    # 等待用户Ctrl+C
    wait $SERVER_PID 2>/dev/null || true
fi
