"""Novel Analyzer - 数据模型"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, JSON,
    create_engine, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker as async_sessionmaker

Base = declarative_base()


# ============ SQLAlchemy 模型 ============

class ApiProvider(Base):
    """API提供商配置"""
    __tablename__ = "api_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="模型别称（自定义名字）")
    model_name = Column(String(200), nullable=False, comment="模型名字")
    api_key = Column(Text, nullable=False, comment="API Key")
    base_url = Column(String(500), nullable=False, comment="接入地址")
    is_active = Column(Boolean, default=False, comment="是否当前使用")
    system_prompt = Column(Text, default="", comment="系统级提示词")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Novel(Base):
    """小说"""
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False, comment="小说标题")
    file_name = Column(String(500), nullable=False, comment="原始文件名")
    file_path = Column(Text, nullable=False, comment="存储路径")
    file_format = Column(String(20), nullable=False, comment="文件格式")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    word_count = Column(Integer, default=0, comment="字数")
    content_hash = Column(String(64), nullable=True, comment="内容哈希，去重用")
    tags = Column(JSON, default=[], comment="标签列表")
    category = Column(String(100), nullable=True, comment="自动分类")
    status = Column(String(20), default="pending", comment="pending/analyzing/done/failed")
    error_message = Column(Text, nullable=True, comment="分析失败原因")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    analysis = relationship("NovelAnalysis", back_populates="novel", uselist=False, cascade="all, delete-orphan")


class NovelAnalysis(Base):
    """小说分析结果"""
    __tablename__ = "novel_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, unique=True)

    # 标签
    tags = Column(JSON, default=[], comment="内容标签")
    genre_tags = Column(JSON, default=[], comment="题材标签")
    style_tags = Column(JSON, default=[], comment="风格标签")

    # 核心分析
    summary = Column(Text, default="", comment="内容总结")
    writing_style = Column(Text, default="", comment="文笔分析")
    structure = Column(Text, default="", comment="结构分析")
    outline = Column(Text, default="", comment="大纲")
    detailed_outline = Column(Text, default="", comment="细纲")
    worldview = Column(Text, default="", comment="世界观设定")
    character_growth = Column(Text, default="", comment="主角及主要人物成长经历")
    character_relations = Column(Text, default="", comment="人物关系")
    character_graph = Column(JSON, default=None, comment="人物关系结构图数据(nodes+edges)")

    # 流行性分析
    popularity_analysis = Column(Text, default="", comment="流行性分析")
    market_potential = Column(Text, default="", comment="市场潜力评估")
    genre_heat = Column(Float, default=0, comment="题材热度评分 0-10")
    rise_potential = Column(Float, default=0, comment="上升潜力评分 0-10")

    # 元信息
    analyzed_by = Column(String(200), nullable=True, comment="分析使用的模型")
    analyzed_at = Column(DateTime, nullable=True)

    novel = relationship("Novel", back_populates="analysis")


# ============ Pydantic 模型 (API接口) ============

class ApiProviderCreate(BaseModel):
    name: str = Field(..., description="模型别称（自定义名字）")
    model_name: str = Field(..., description="模型名字，如 deepseek-chat")
    api_key: str = Field(..., description="API Key")
    base_url: str = Field(..., description="接入地址，如 https://api.deepseek.com/v1")
    system_prompt: str = Field("", description="系统级提示词")

class ApiProviderUpdate(BaseModel):
    name: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None

class ApiProviderOut(BaseModel):
    id: int
    name: str
    model_name: str
    api_key: str  # 前端展示用，会脱敏
    base_url: str
    is_active: bool
    system_prompt: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NovelOut(BaseModel):
    id: int
    title: str
    file_name: str
    file_format: str
    file_size: int
    word_count: int
    tags: List[str] = []
    category: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NovelAnalysisOut(BaseModel):
    id: int
    novel_id: int
    tags: List[str] = []
    genre_tags: List[str] = []
    style_tags: List[str] = []
    summary: str = ""
    writing_style: str = ""
    structure: str = ""
    outline: str = ""
    detailed_outline: str = ""
    worldview: str = ""
    character_growth: str = ""
    character_relations: str = ""
    character_graph: Optional[Dict[str, Any]] = None
    popularity_analysis: str = ""
    market_potential: str = ""
    genre_heat: float = 0
    rise_potential: float = 0
    analyzed_by: Optional[str] = None
    analyzed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExportFormat(str, Enum):
    markdown = "markdown"
    pdf = "pdf"
    json = "json"
    docx = "docx"


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., description="搜索内容")
    top_k: int = Field(5, description="返回数量")
    category: Optional[str] = None


class AgentQueryRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")
    novel_id: Optional[int] = None
