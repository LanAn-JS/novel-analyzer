#!/bin/bash
# Novel Analyzer 一键安装脚本
# 要求：Python 3.10+, Node.js 18+ (仅开发模式需要)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "  📚 Novel Analyzer 安装向导"
echo "========================================="
echo ""

# 1. 检查Python
echo "🔍 检查 Python ..."
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "   ✅ Python $PY_VER"
else
    echo "   ❌ 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

# 2. 创建虚拟环境
echo ""
echo "📦 创建 Python 虚拟环境 ..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   ✅ 虚拟环境已创建"
else
    echo "   ⏭️  虚拟环境已存在，跳过"
fi

# 3. 安装后端依赖
echo ""
echo "📥 安装后端依赖（可能需要几分钟）..."
venv/bin/pip install -r backend/requirements.txt -q --disable-pip-version-check
echo "   ✅ 后端依赖安装完成"

# 4. 可选：GPU加速
echo ""
read -p "🚀 是否安装GPU加速依赖？(需要NVIDIA显卡+CUDA) [y/N] " GPU_ANSWER
if [[ "$GPU_ANSWER" =~ ^[Yy]$ ]]; then
    venv/bin/pip install -r backend/requirements-gpu.txt -q --disable-pip-version-check
    echo "   ✅ GPU依赖安装完成"
else
    echo "   ⏭️  跳过GPU依赖（将使用CPU模式）"
fi

# 5. 复制embedding模型到缓存
echo ""
echo "🧠 配置Embedding模型 ..."
MODEL_CACHE="$HOME/.cache/chroma/onnx_models/all-MiniLM-L6-V2"
if [ ! -d "$MODEL_CACHE" ] || [ -z "$(ls -A "$MODEL_CACHE" 2>/dev/null)" ]; then
    mkdir -p "$MODEL_CACHE"
    cp -r embedding_model/* "$MODEL_CACHE/"
    echo "   ✅ Embedding模型已部署到缓存"
else
    echo "   ⏭️  Embedding模型缓存已存在，跳过"
fi

# 6. 初始化数据目录
echo ""
echo "📁 初始化数据目录 ..."
mkdir -p data/uploads data/chroma data/exports logs
echo "   ✅ 数据目录就绪"

# 7. 完成
echo ""
echo "========================================="
echo "  ✅ 安装完成！"
echo "========================================="
echo ""
echo "启动方式："
echo "  生产模式：  ./start.sh"
echo "  开发模式：  ./dev.sh"
echo ""
echo "访问地址：http://localhost:8989"
echo ""
