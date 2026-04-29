"""Novel Analyzer - API路由：小说管理"""

import os
import logging
import shutil
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..config import UPLOAD_DIR, SUPPORTED_FORMATS
from ..models.schemas import Novel, NovelOut, NovelAnalysisOut, NovelAnalysis, ExportFormat
from ..services.parser import parse_novel, chunk_text
from ..services.chroma import add_novel_chunks, delete_novel_chunks, search_novels
from ..services.llm import LLMService

logger = logging.getLogger("novel-analyzer")
from ..services.exporter import export_analysis

router = APIRouter(prefix="/api/novels", tags=["小说管理"])

# ======== 分析进度全局存储 ========
import asyncio
from typing import Dict as DictType, Set as SetType

# {novel_id: {"step": "标签提取", "progress": "1/9", "status": "analyzing", "detail": "..."}}
_analysis_progress: DictType[int, dict] = {}
# {novel_id: [asyncio.Queue, ...]}  SSE订阅者
_analysis_subscribers: DictType[int, list] = {}
# 暂停中的小说ID集合
_analysis_paused: SetType[int] = set()
# 暂停事件（用于唤醒暂停的分析）
_analysis_resume_events: DictType[int, asyncio.Event] = {}

def _update_analysis_progress(novel_id: int, step: str, progress: str, detail: str = ""):
    """更新分析进度并通知SSE订阅者"""
    data = {"step": step, "progress": progress, "status": "analyzing", "detail": detail}
    _analysis_progress[novel_id] = data
    logger.info(f"  [{progress}] {step}" + (f" - {detail}" if detail else ""))
    # 通知所有SSE订阅者
    for q in _analysis_subscribers.get(novel_id, []):
        try:
            q.put_nowait(data)
        except:
            pass

def _finish_analysis_progress(novel_id: int, status: str = "done", error: str = ""):
    """结束分析进度"""
    data = {"step": "完成" if status == "done" else "失败", "progress": "done", "status": status, "detail": error}
    _analysis_progress[novel_id] = data
    for q in _analysis_subscribers.get(novel_id, []):
        try:
            q.put_nowait(data)
        except:
            pass
    # 清理订阅者
    _analysis_subscribers.pop(novel_id, None)
    # 清理暂停状态
    _analysis_paused.discard(novel_id)
    _analysis_resume_events.pop(novel_id, None)


def _pause_analysis_progress(novel_id: int):
    """暂停分析进度"""
    _analysis_paused.add(novel_id)
    current = _analysis_progress.get(novel_id, {})
    data = {**current, "status": "paused", "detail": "⏸️ 已暂停"}
    _analysis_progress[novel_id] = data
    for q in _analysis_subscribers.get(novel_id, []):
        try:
            q.put_nowait(data)
        except:
            pass


def _resume_analysis_progress(novel_id: int):
    """恢复分析进度"""
    _analysis_paused.discard(novel_id)
    event = _analysis_resume_events.get(novel_id)
    if event:
        event.set()
    current = _analysis_progress.get(novel_id, {})
    data = {**current, "status": "analyzing", "detail": "▶️ 继续分析"}
    _analysis_progress[novel_id] = data
    for q in _analysis_subscribers.get(novel_id, []):
        try:
            q.put_nowait(data)
        except:
            pass


@router.post("/open-directory")
async def open_directory(path: str = ""):
    """打开文件所在目录（Linux桌面环境）"""
    import subprocess
    if not path or not os.path.exists(path):
        raise HTTPException(400, "路径不存在")
    
    directory = path if os.path.isdir(path) else os.path.dirname(path)
    if not directory:
        directory = "/"
    
    try:
        subprocess.Popen(["xdg-open", directory], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"message": "已打开目录", "directory": directory}
    except Exception as e:
        raise HTTPException(500, f"打开目录失败: {str(e)}")


@router.post("/upload", response_model=NovelOut)
async def upload_novel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传小说文件"""
    # 检查格式
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(400, f"不支持的格式: {ext}，支持: {list(SUPPORTED_FORMATS.keys())}")
    
    # 保存文件
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in file.filename)
    file_path = os.path.join(str(UPLOAD_DIR), safe_name)
    
    # 避免重名
    counter = 1
    base_path = file_path
    while os.path.exists(file_path):
        name, e = os.path.splitext(base_path)
        file_path = f"{name}_{counter}{e}"
        counter += 1
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 解析小说
    try:
        text, fmt, word_count, content_hash = parse_novel(file_path)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(400, f"文件解析失败: {str(e)}")
    
    # 检查重复
    existing = await db.execute(
        select(Novel).where(Novel.content_hash == content_hash)
    )
    if existing.scalar_one_or_none():
        os.remove(file_path)
        raise HTTPException(409, "该小说已存在（内容相同）")
    
    # 推断标题（文件名去扩展名）
    title = os.path.splitext(file.filename)[0]
    
    # 创建记录
    novel = Novel(
        title=title,
        file_name=file.filename,
        file_path=file_path,
        file_format=ext,
        file_size=os.path.getsize(file_path),
        word_count=word_count,
        content_hash=content_hash,
        status="pending",
    )
    db.add(novel)
    await db.commit()
    await db.refresh(novel)
    
    # 在后台做向量嵌入，立刻返回给用户
    novel_id = novel.id
    novel_text = text
    
    def _do_embed():
        try:
            logger.info(f"📤 上传成功: 《{title}》| {word_count:,}字 | {novel.file_size/1024/1024:.1f}MB")
            chunks = chunk_text(novel_text)
            logger.info(f"📄 文本分块: {len(chunks)} 块")
            add_novel_chunks(novel_id, chunks, title=title)
        except Exception as e:
            logger.error(f"❌ 向量库写入失败(novel_id={novel_id}): {e}")
    
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _do_embed)
    
    return NovelOut.model_validate(novel)


@router.get("/", response_model=List[NovelOut])
async def list_novels(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """列出所有小说，支持筛选"""
    query = select(Novel).order_by(Novel.created_at.desc())
    if category:
        query = query.where(Novel.category == category)
    if status:
        query = query.where(Novel.status == status)
    if tag:
        query = query.where(Novel.tags.contains([tag]))
    
    result = await db.execute(query)
    novels = result.scalars().all()
    return [NovelOut.model_validate(n) for n in novels]


@router.get("/{novel_id}", response_model=NovelOut)
async def get_novel(novel_id: int, db: AsyncSession = Depends(get_db)):
    """获取小说详情"""
    result = await db.execute(select(Novel).where(Novel.id == novel_id))
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(404, "小说不存在")
    return NovelOut.model_validate(novel)


@router.get("/{novel_id}/analysis", response_model=Optional[NovelAnalysisOut])
async def get_analysis(novel_id: int, db: AsyncSession = Depends(get_db)):
    """获取小说分析结果"""
    from ..models.schemas import NovelAnalysis
    result = await db.execute(
        select(NovelAnalysis).where(NovelAnalysis.novel_id == novel_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        return None
    return NovelAnalysisOut.model_validate(analysis)


@router.post("/{novel_id}/analyze")
async def analyze_novel(
    novel_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """触发小说分析"""
    result = await db.execute(select(Novel).where(Novel.id == novel_id))
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(404, "小说不存在")
    
    if novel.status == "analyzing":
        raise HTTPException(409, "正在分析中，请勿重复触发")
    
    # 删除旧分析结果（如果有），避免 unique 冲突
    old_analysis = await db.execute(
        select(NovelAnalysis).where(NovelAnalysis.novel_id == novel_id)
    )
    old = old_analysis.scalar_one_or_none()
    if old:
        await db.delete(old)
        await db.flush()
    
    # 更新状态
    novel.status = "analyzing"
    await db.commit()
    
    # 初始化进度
    _update_analysis_progress(novel_id, "准备中", "0/9", "读取文件...")
    
    # 后台执行分析
    background_tasks.add_task(_do_analyze, novel_id, novel.file_path, novel.title)
    
    return {"message": "分析已开始", "novel_id": novel_id}


@router.get("/{novel_id}/analyze/stream")
async def analyze_stream(novel_id: int):
    """SSE 流式推送分析进度"""
    from starlette.responses import StreamingResponse
    import json as _json
    
    queue = asyncio.Queue()
    _analysis_subscribers.setdefault(novel_id, []).append(queue)
    
    async def event_generator():
        try:
            # 先发当前进度
            current = _analysis_progress.get(novel_id)
            if current:
                yield f"data: {_json.dumps(current, ensure_ascii=False)}\n\n"
            
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {_json.dumps(data, ensure_ascii=False)}\n\n"
                    if data.get("progress") == "done":
                        break
                except asyncio.TimeoutError:
                    # 心跳，防止连接断开
                    yield ": heartbeat\n\n"
        finally:
            subscribers = _analysis_subscribers.get(novel_id, [])
            if queue in subscribers:
                subscribers.remove(queue)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{novel_id}/analyze/pause")
async def pause_analysis(novel_id: int, db: AsyncSession = Depends(get_db)):
    """暂停分析"""
    if novel_id not in _analysis_progress or _analysis_progress[novel_id].get("status") not in ("analyzing",):
        raise HTTPException(409, "当前没有正在进行的分析")
    _pause_analysis_progress(novel_id)
    return {"message": "已暂停", "novel_id": novel_id}


@router.post("/{novel_id}/analyze/resume")
async def resume_analysis(novel_id: int, db: AsyncSession = Depends(get_db)):
    """继续分析"""
    if novel_id not in _analysis_progress or _analysis_progress[novel_id].get("status") != "paused":
        raise HTTPException(409, "当前没有已暂停的分析")
    _resume_analysis_progress(novel_id)
    return {"message": "继续分析", "novel_id": novel_id}


async def _check_and_wait_pause(novel_id: int):
    """检查是否暂停，如果暂停则等待恢复。返回True表示继续，False表示应取消"""
    if novel_id not in _analysis_paused:
        return True
    # 创建恢复事件
    if novel_id not in _analysis_resume_events:
        _analysis_resume_events[novel_id] = asyncio.Event()
    event = _analysis_resume_events[novel_id]
    event.clear()
    # 等待恢复信号
    await event.wait()
    # 恢复后检查是否又被暂停或删除
    return novel_id not in _analysis_paused


async def _do_analyze(novel_id: int, file_path: str, title: str):
    """后台分析任务（支持暂停/继续）"""
    from ..database import AsyncSessionLocal
    from ..models.schemas import Novel, NovelAnalysis
    
    async with AsyncSessionLocal() as db:
        try:
            # 解析内容
            _update_analysis_progress(novel_id, "读取文件", "0/9", f"正在读取《{title}》...")
            text, _, _, _ = parse_novel(file_path)
            
            # 获取当前模型
            llm = LLMService(db)
            provider = await llm.get_active_provider()
            model_name = provider.name if provider else "unknown"
            _update_analysis_progress(novel_id, "读取文件", "0/9", f"使用模型: {model_name}")
            
            # 执行分析（带进度回调 + 暂停支持）
            step_names = [
                ("tags", "标签提取", "1/9"),
                ("summary", "内容总结", "2/9"),
                ("writing_style", "文笔分析", "3/9"),
                ("structure", "结构分析", "4/9"),
                ("outline", "大纲提取", "5/9"),
                ("detailed_outline", "细纲提取", "6/9"),
                ("worldview", "世界观分析", "7/9"),
                ("character_growth", "人物分析", "8/9"),
                ("popularity_analysis", "流行性评估", "9/9"),
            ]
            
            results = await llm.analyze_novel_with_progress(
                text, title, novel_id,
                step_names=step_names,
                progress_callback=_update_analysis_progress,
                pause_check=lambda nid=novel_id: _check_and_wait_pause(nid),
            )
            
            # 自动分类
            all_tags = results.get("all_tags", [])
            category = _classify_novel(all_tags, results.get("genre_tags", []))
            
            # 保存结果
            _update_analysis_progress(novel_id, "保存结果", "done", "写入数据库...")
            analysis = NovelAnalysis(
                novel_id=novel_id,
                tags=all_tags,
                genre_tags=results.get("genre_tags", []),
                style_tags=results.get("style_tags", []),
                summary=results.get("summary", ""),
                writing_style=results.get("writing_style", ""),
                structure=results.get("structure", ""),
                outline=results.get("outline", ""),
                detailed_outline=results.get("detailed_outline", ""),
                worldview=results.get("worldview", ""),
                character_growth=results.get("character_growth", ""),
                character_relations=results.get("character_growth", ""),  # 人物关系包含在人物分析中
                character_graph=results.get("character_graph", None),
                popularity_analysis=results.get("popularity_analysis", ""),
                market_potential=results.get("popularity_analysis", ""),
                genre_heat=results.get("genre_heat", 0),
                rise_potential=results.get("rise_potential", 0),
                analyzed_by=model_name,
                analyzed_at=datetime.utcnow(),
            )
            db.add(analysis)
            
            # 更新小说状态
            novel = await db.execute(select(Novel).where(Novel.id == novel_id))
            n = novel.scalar_one()
            n.status = "done"
            n.tags = all_tags
            n.category = category
            
            await db.commit()
            _finish_analysis_progress(novel_id, "done")
            
        except Exception as e:
            # 标记失败
            novel = await db.execute(select(Novel).where(Novel.id == novel_id))
            n = novel.scalar_one()
            n.status = "failed"
            n.error_message = str(e)
            await db.commit()
            _finish_analysis_progress(novel_id, "failed", str(e))


def _classify_novel(tags: List[str], genre_tags: List[str]) -> str:
    """根据标签自动分类"""
    category_map = {
        "玄幻": ["玄幻", "修仙", "仙侠", "奇幻"],
        "都市": ["都市", "现实", "社会"],
        "言情": ["言情", "甜宠", "虐恋", "古言", "现言"],
        "科幻": ["科幻", "末世", "赛博"],
        "历史": ["历史", "穿越", "古代"],
        "游戏": ["游戏", "电竞", "虚拟"],
        "悬疑": ["悬疑", "推理", "惊悚"],
        "军事": ["军事", "战争"],
    }
    
    all_t = set(tags + genre_tags)
    for cat, keywords in category_map.items():
        if all_t & set(keywords):
            return cat
    return "其他"


@router.get("/{novel_id}/export")
async def export_novel_analysis(
    novel_id: int,
    format: ExportFormat = ExportFormat.markdown,
    db: AsyncSession = Depends(get_db),
):
    """导出分析报告"""
    from ..models.schemas import NovelAnalysis
    
    result = await db.execute(select(Novel).where(Novel.id == novel_id))
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(404, "小说不存在")
    
    a_result = await db.execute(
        select(NovelAnalysis).where(NovelAnalysis.novel_id == novel_id)
    )
    analysis = a_result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "分析结果不存在，请先执行分析")
    
    analysis_dict = NovelAnalysisOut.model_validate(analysis).model_dump()
    novel_info = {
        "file_name": novel.file_name,
        "word_count": novel.word_count,
        "category": novel.category,
    }
    
    try:
        path = await export_analysis(
            novel_title=novel.title,
            novel_info=novel_info,
            analysis=analysis_dict,
            fmt=format.value,
        )
    except Exception as e:
        raise HTTPException(500, f"导出失败: {str(e)}")
    
    return {"message": "导出成功", "file_path": path, "format": format.value}


@router.delete("/{novel_id}")
async def delete_novel(novel_id: int, db: AsyncSession = Depends(get_db)):
    """删除小说（同时取消正在进行的嵌入和分析）"""
    from ..models.schemas import NovelAnalysis
    
    result = await db.execute(select(Novel).where(Novel.id == novel_id))
    novel = result.scalar_one_or_none()
    if not novel:
        raise HTTPException(404, "小说不存在")
    
    # 删除文件
    if os.path.exists(novel.file_path):
        os.remove(novel.file_path)
    
    # 取消向量嵌入 + 删除已有向量数据
    delete_novel_chunks(novel_id)
    
    # 取消分析进度
    _analysis_progress.pop(novel_id, None)
    _analysis_subscribers.pop(novel_id, None)
    
    # 删除分析记录
    a_result = await db.execute(
        select(NovelAnalysis).where(NovelAnalysis.novel_id == novel_id)
    )
    analysis = a_result.scalar_one_or_none()
    if analysis:
        await db.delete(analysis)
    
    # 删除小说记录
    await db.delete(novel)
    await db.commit()
    
    return {"message": "已删除"}


@router.get("/categories/list")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """获取所有分类"""
    result = await db.execute(
        select(Novel.category).distinct().where(Novel.category.isnot(None))
    )
    categories = [r[0] for r in result.all()]
    return {"categories": categories}


@router.get("/tags/list")
async def list_tags(db: AsyncSession = Depends(get_db)):
    """获取所有标签"""
    result = await db.execute(select(Novel.tags).where(Novel.tags != []))
    all_tags = set()
    for row in result.all():
        if row[0]:
            all_tags.update(row[0])
    return {"tags": sorted(list(all_tags))}


