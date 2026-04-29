"""Novel Analyzer - API路由：搜索与智能体接口"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models.schemas import Novel, NovelAnalysis, SemanticSearchRequest, AgentQueryRequest
from ..services.chroma import search_novels
from ..services.llm import LLMService

router = APIRouter(prefix="/api", tags=["搜索与查询"])


@router.post("/search")
async def semantic_search(request: SemanticSearchRequest, db: AsyncSession = Depends(get_db)):
    """语义搜索小说"""
    results = search_novels(
        query=request.query,
        top_k=request.top_k,
        category=request.category,
    )
    
    # 补充小说元信息
    enriched = []
    if results and results.get("ids") and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            novel_id = meta.get("novel_id")
            distance = results["distances"][0][i] if results["distances"] else 0
            
            # 查小说信息
            novel_result = await db.execute(select(Novel).where(Novel.id == novel_id))
            novel = novel_result.scalar_one_or_none()
            
            enriched.append({
                "novel_id": novel_id,
                "title": novel.title if novel else "未知",
                "category": novel.category if novel else None,
                "tags": novel.tags if novel else [],
                "relevance": round(1 - distance, 4),
                "chunk_preview": results["documents"][0][i][:200] if results["documents"] else "",
            })
    
    return {"results": enriched, "total": len(enriched)}


@router.post("/query")
async def agent_query(request: AgentQueryRequest, db: AsyncSession = Depends(get_db)):
    """
    智能体/外部模型查询接口
    
    支持自然语言查询，自动检索相关小说并生成回答
    """
    # 先做语义搜索找到相关小说
    search_results = search_novels(
        query=request.query,
        top_k=5,
        novel_id=request.novel_id,
    )
    
    # 收集相关内容
    context_parts = []
    novel_ids = set()
    if search_results and search_results.get("ids") and search_results["ids"][0]:
        for i, doc_id in enumerate(search_results["ids"][0]):
            meta = search_results["metadatas"][0][i] if search_results["metadatas"] else {}
            doc = search_results["documents"][0][i] if search_results["documents"] else ""
            novel_id = meta.get("novel_id")
            novel_ids.add(novel_id)
            context_parts.append(f"[小说ID:{novel_id}]\n{doc[:1000]}")
    
    context = "\n\n---\n\n".join(context_parts) if context_parts else "未找到相关内容"
    
    # 补充分析结果
    analysis_parts = []
    for nid in novel_ids:
        a_result = await db.execute(
            select(NovelAnalysis).where(NovelAnalysis.novel_id == nid)
        )
        analysis = a_result.scalar_one_or_none()
        n_result = await db.execute(select(Novel).where(Novel.id == nid))
        novel = n_result.scalar_one_or_none()
        if analysis and novel:
            analysis_parts.append(
                f"《{novel.title}》分析：\n"
                f"- 标签：{', '.join(analysis.tags or [])}\n"
                f"- 分类：{novel.category}\n"
                f"- 总结：{analysis.summary[:300]}\n"
                f"- 流行性：热度{analysis.genre_heat}/10，潜力{analysis.rise_potential}/10"
            )
    
    if analysis_parts:
        context += "\n\n=== 分析数据 ===\n\n" + "\n\n".join(analysis_parts)
    
    # 调用LLM回答
    llm = LLMService(db)
    messages = [
        {
            "role": "system",
            "content": "你是小说分析数据库的查询助手。根据提供的小说内容和分析数据，回答用户的查询。如果数据不足，请如实说明。"
        },
        {
            "role": "user",
            "content": f"数据库内容：\n{context}\n\n用户查询：{request.query}"
        }
    ]
    
    try:
        answer = await llm.chat(messages)
    except Exception as e:
        # 如果LLM不可用，返回原始检索结果
        answer = f"LLM不可用({str(e)})，以下是检索结果：\n{context[:2000]}"
    
    return {
        "answer": answer,
        "related_novels": list(novel_ids),
        "context_used": len(context_parts),
    }


@router.get("/novels/{novel_id}/raw")
async def get_novel_raw(novel_id: int, db: AsyncSession = Depends(get_db)):
    """获取小说原文（供外部程序读取）"""
    result = await db.execute(select(Novel).where(Novel.id == novel_id))
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(404, "小说不存在")
    
    from ..services.parser import parse_novel
    try:
        text, _, _, _ = parse_novel(novel.file_path)
    except Exception as e:
        raise HTTPException(500, f"读取失败: {str(e)}")
    
    return {
        "id": novel.id,
        "title": novel.title,
        "content": text,
        "word_count": novel.word_count,
        "tags": novel.tags,
        "category": novel.category,
    }


@router.get("/novels/{novel_id}/analysis/json")
async def get_analysis_json(novel_id: int, db: AsyncSession = Depends(get_db)):
    """获取分析结果JSON（供外部程序读取）"""
    result = await db.execute(
        select(NovelAnalysis).where(NovelAnalysis.novel_id == novel_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "分析结果不存在")
    
    from ..models.schemas import NovelAnalysisOut
    return NovelAnalysisOut.model_validate(analysis).model_dump()


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """获取数据库统计信息"""
    from sqlalchemy import func
    import os
    import shutil
    from ..config import DB_PATH, DATA_DIR
    
    total = await db.execute(select(func.count(Novel.id)))
    analyzed = await db.execute(select(func.count(Novel.id)).where(Novel.status == "done"))
    categories = await db.execute(
        select(Novel.category, func.count(Novel.id))
        .group_by(Novel.category)
    )
    
    # 数据库占用空间
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    
    # 数据目录总占用（含chroma、uploads、exports等）
    data_size = 0
    for dirpath, dirnames, filenames in os.walk(DATA_DIR):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            data_size += os.path.getsize(fp)
    
    # 磁盘剩余空间
    disk_usage = shutil.disk_usage(DATA_DIR)
    
    def fmt_size(b):
        if b < 1024: return f"{b}B"
        if b < 1048576: return f"{b/1024:.1f}KB"
        if b < 1073741824: return f"{b/1048576:.1f}MB"
        return f"{b/1073741824:.1f}GB"
    
    return {
        "total_novels": total.scalar(),
        "analyzed_novels": analyzed.scalar(),
        "categories": {r[0] or "未分类": r[1] for r in categories.all()},
        "storage": {
            "db_size": db_size,
            "db_size_human": fmt_size(db_size),
            "data_size": data_size,
            "data_size_human": fmt_size(data_size),
            "disk_total": disk_usage.total,
            "disk_total_human": fmt_size(disk_usage.total),
            "disk_used": disk_usage.used,
            "disk_used_human": fmt_size(disk_usage.used),
            "disk_free": disk_usage.free,
            "disk_free_human": fmt_size(disk_usage.free),
            "breakdown": _storage_breakdown(DATA_DIR, fmt_size),
        }
    }

def _storage_breakdown(data_dir, fmt_size):
    """返回数据目录各子目录的大小"""
    import os
    result = {}
    for entry in sorted(os.scandir(data_dir), key=lambda e: e.name):
        if entry.is_file():
            result[entry.name] = {"size": entry.stat().st_size, "size_human": fmt_size(entry.stat().st_size)}
        elif entry.is_dir():
            size = 0
            for dirpath, dirnames, filenames in os.walk(entry.path):
                for f in filenames:
                    size += os.path.getsize(os.path.join(dirpath, f))
            result[entry.name + "/"] = {"size": size, "size_human": fmt_size(size)}
    return result
