"""Novel Analyzer - 主应用入口"""

import os

# ============ GPU加速：在所有import之前设置CUDA库路径 ============
def _setup_cuda_env():
    """提前设置CUDA/cuDNN库路径，确保onnxruntime-gpu能找到"""
    _cuda_paths = []
    for _pkg_name in ['nvidia.cudnn', 'nvidia.cublas', 'nvidia.cuda_nvrtc']:
        try:
            _pkg = __import__(_pkg_name, fromlist=['__path__'])
            _lib_dir = os.path.join(_pkg.__path__[0], 'lib')
            if os.path.isdir(_lib_dir):
                _cuda_paths.append(_lib_dir)
        except ImportError:
            pass
    if _cuda_paths:
        _existing = os.environ.get('LD_LIBRARY_PATH', '')
        _new = ':'.join(_cuda_paths)
        os.environ['LD_LIBRARY_PATH'] = _new + (':' + _existing if _existing else '')

_setup_cuda_env()
# ============ END GPU加速 ============
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.routing import Mount, Route
from starlette.responses import Response

from .config import APP_NAME, APP_VERSION, APP_SIGNATURE, DATA_DIR, BASE_DIR
from .database import init_db
from .routers import providers, novels, query


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=f"{APP_NAME} - 小说智能分析系统",
    version=APP_VERSION,
    description=f"{APP_NAME} v{APP_VERSION}\n{APP_SIGNATURE}",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 日志配置
import logging
LOG_DIR = os.path.join(str(BASE_DIR), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"novel-analyzer-{__import__('datetime').datetime.now().strftime('%Y%m%d')}.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("novel-analyzer")

# 注册API路由
app.include_router(providers.router)
app.include_router(novels.router)
app.include_router(query.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "signature": APP_SIGNATURE,
    }


# 静态文件（前端）- 使用mount确保API路由优先
frontend_dist = os.path.join(str(BASE_DIR), "frontend", "dist")
if os.path.isdir(frontend_dist):
    # Assets静态文件
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Favicon等静态资源
    @app.get("/favicon.svg")
    async def favicon():
        favicon_path = os.path.join(frontend_dist, "favicon.svg")
        if os.path.isfile(favicon_path):
            return FileResponse(favicon_path)
        return Response(status_code=404)

    # SPA首页
    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(frontend_dist, "index.html"))

    # SPA fallback - 前端路由（novels、search、settings等）
    # 注意：这个必须放在所有API路由之后，且只处理非/api/路径
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # 不拦截API和assets路径
        if path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if path.startswith("assets/"):
            return Response(status_code=404)
        
        file_path = os.path.join(frontend_dist, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # SPA fallback: 所有未知路径返回index.html，让前端路由处理
        return FileResponse(os.path.join(frontend_dist, "index.html"))
