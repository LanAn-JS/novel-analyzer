"""Novel Analyzer - ChromaDB 向量存储

嵌入模型说明：
- 上传小说时需要将文字转换为向量（embedding），才能实现语义搜索
- 就像给每段文字生成一个"指纹"，相似内容的指纹也相似
- 这就是为什么上传小说时需要用到嵌入模型
- 模型文件已内置在项目的 embedding_model/ 目录，无需联网下载
"""

import os
import sys
import shutil
import logging
import threading
import chromadb
from typing import List, Dict, Optional, Set
from ..config import CHROMA_DIR, BASE_DIR

logger = logging.getLogger("novel-analyzer")

# 正在嵌入的novel_id集合，删除时用来取消
_embedding_in_progress: Set[int] = set()
_embedding_lock = threading.Lock()

_client = None
_gpu_available = None  # None=未检测, True/False
_gpu_providers = None  # 缓存检测到的providers

# 内置嵌入模型路径
BUILTIN_MODEL_DIR = os.path.join(str(BASE_DIR), "embedding_model")
# ChromaDB缓存路径
CHROMA_MODEL_DIR = os.path.expanduser("~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx")


def _ensure_embedding_model():
    """确保嵌入模型文件存在（从项目内置目录复制到缓存目录）"""
    if os.path.isdir(CHROMA_MODEL_DIR) and os.path.isfile(os.path.join(CHROMA_MODEL_DIR, "model.onnx")):
        return  # 缓存已有模型
    
    if not os.path.isdir(BUILTIN_MODEL_DIR):
        # 没有内置模型，让ChromaDB自己下载
        return
    
    # 清除代理，避免下载失败
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
        os.environ.pop(key, None)
    
    # 复制内置模型到缓存目录
    os.makedirs(CHROMA_MODEL_DIR, exist_ok=True)
    for fname in os.listdir(BUILTIN_MODEL_DIR):
        src = os.path.join(BUILTIN_MODEL_DIR, fname)
        dst = os.path.join(CHROMA_MODEL_DIR, fname)
        if not os.path.isfile(dst):
            shutil.copy2(src, dst)


def _detect_gpu() -> bool:
    """检测GPU是否可用于嵌入加速"""
    global _gpu_available, _gpu_providers
    if _gpu_available is not None:
        return _gpu_available
    
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if 'CUDAExecutionProvider' in providers:
            _gpu_providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            _gpu_available = True
            logger.info(f"🎮 GPU加速已启用 (providers: {', '.join(providers)})")
            return True
    except Exception as e:
        logger.debug(f"GPU检测异常: {e}")
    
    _gpu_providers = ['CPUExecutionProvider']
    _gpu_available = False
    logger.info("💻 使用CPU嵌入（未检测到GPU）")
    return False


def get_embedding_function():
    """获取嵌入函数（自动检测GPU加速）"""
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
    
    if _detect_gpu():
        return ONNXMiniLM_L6_V2(preferred_providers=_gpu_providers)
    else:
        return ONNXMiniLM_L6_V2(preferred_providers=['CPUExecutionProvider'])


def get_chroma_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        # 清除代理环境变量，避免ChromaDB的httpx下载模型时遇到socks代理报错
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
            os.environ.pop(key, None)
        
        # 确保模型文件可用
        _ensure_embedding_model()
        
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=chromadb.Settings(
                allow_reset=True,
                anonymized_telemetry=False,
            )
        )
    return _client


def get_or_create_collection(name: str = "novels") -> chromadb.Collection:
    client = get_chroma_client()
    ef = get_embedding_function()
    return client.get_or_create_collection(
        name=name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )


def add_novel_chunks(
    novel_id: int,
    chunks: List[str],
    metadatas: Optional[List[Dict]] = None,
    title: str = "",
) -> bool:
    """将小说分块存入向量库（分批处理，带进度条）
    
    Returns:
        True=完成, False=被取消
    """
    collection = get_or_create_collection()
    total = len(chunks)
    batch_size = 50
    
    display_name = f"《{title}》" if title else f"novel_{novel_id}"
    logger.info(f"📥 开始向量嵌入: {display_name} | {total} 块 | 文件大小约 {sum(len(c.encode()) for c in chunks)/1024/1024:.1f}MB")
    
    # 标记为正在嵌入
    with _embedding_lock:
        _embedding_in_progress.add(novel_id)
    
    # 进度条宽度
    BAR_WIDTH = 30
    last_pct = -1
    
    try:
        for i in range(0, total, batch_size):
            # 检查是否被取消
            with _embedding_lock:
                if novel_id not in _embedding_in_progress:
                    logger.info(f"⚠️ 向量嵌入已取消: {display_name}")
                    # 清理已写入的部分数据
                    _cleanup_novel_chunks(novel_id)
                    return False
            
            batch_chunks = chunks[i:i+batch_size]
            batch_ids = [f"novel_{novel_id}_chunk_{i+j}" for j in range(len(batch_chunks))]
            batch_metas = metadatas[i:i+batch_size] if metadatas else [
                {"novel_id": novel_id, "chunk_index": i+j} for j in range(len(batch_chunks))
            ]
            collection.add(
                ids=batch_ids,
                documents=batch_chunks,
                metadatas=batch_metas,
            )
            
            # 进度条 — 始终用\r原地刷新
            done = min(i + batch_size, total)
            pct = done * 100 // total
            if pct != last_pct:
                last_pct = pct
                filled = BAR_WIDTH * done // total
                bar = '█' * filled + '░' * (BAR_WIDTH - filled)
                line = f"  向量嵌入[{display_name}] {bar} {done}/{total}块 {pct}%"
                sys.stderr.write(f'\r{line}')
                sys.stderr.flush()
        
        # 完成后换行
        sys.stderr.write('\n')
        sys.stderr.flush()
        logger.info(f"✅ 向量嵌入完成: {display_name} | {total} 块已存入向量库")
        return True
    
    finally:
        # 清理标记
        with _embedding_lock:
            _embedding_in_progress.discard(novel_id)


def search_novels(
    query: str,
    top_k: int = 5,
    novel_id: Optional[int] = None,
    category: Optional[str] = None,
) -> List[Dict]:
    """语义搜索"""
    collection = get_or_create_collection()
    where_filter = {}
    conditions = []
    if novel_id is not None:
        conditions.append({"novel_id": novel_id})
    if category is not None:
        conditions.append({"category": category})
    if len(conditions) == 1:
        where_filter = conditions[0]
    elif len(conditions) > 1:
        where_filter = {"$and": conditions}

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter if where_filter else None,
        include=["documents", "metadatas", "distances"],
    )
    return results


def _cleanup_novel_chunks(novel_id: int) -> None:
    """清理某小说的所有向量数据（内部用）"""
    try:
        collection = get_or_create_collection()
        all_ids = collection.get(
            where={"novel_id": novel_id},
            include=[],
        )
        if all_ids and all_ids.get("ids"):
            collection.delete(ids=all_ids["ids"])
            logger.info(f"🧹 已清理向量数据: novel_id={novel_id} | {len(all_ids['ids'])}条")
    except Exception as e:
        logger.error(f"❌ 清理向量数据失败: novel_id={novel_id}: {e}")


def delete_novel_chunks(novel_id: int) -> None:
    """删除某小说的所有分块（同时取消正在进行的嵌入）"""
    # 先取消正在进行的嵌入
    with _embedding_lock:
        _embedding_in_progress.discard(novel_id)
    
    # 删除已有的向量数据
    _cleanup_novel_chunks(novel_id)


def novel_chunks_exist(novel_id: int) -> bool:
    """检查某小说的分块是否已存在"""
    collection = get_or_create_collection()
    result = collection.get(
        where={"novel_id": novel_id},
        include=[],
    )
    return bool(result and result.get("ids"))
