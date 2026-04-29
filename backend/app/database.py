"""Novel Analyzer - 数据库管理"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker as async_sessionmaker
from .config import DB_PATH
from .models.schemas import Base

engine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """初始化数据库表 + 自动迁移新列 + 修复卡住的分析状态"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 自动迁移：检查表是否缺少列，如果有则添加
        await conn.run_sync(_auto_migrate)
    
    # 修复服务重启后卡在 analyzing 的记录（内存中的进度已丢失）
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, update
        from .models.schemas import Novel
        result = await session.execute(
            select(Novel).where(Novel.status == "analyzing")
        )
        stuck = result.scalars().all()
        if stuck:
            for n in stuck:
                n.status = "failed"
                n.error_message = "服务重启，分析中断，请重新分析"
                print(f"  ⚠️ 修复卡住的分析: 《{n.title}》→ failed")
            await session.commit()


def _auto_migrate(connection):
    """自动检测并添加缺失的列（仅新增列，不修改/删除）"""
    import sqlalchemy as sa
    
    for table in Base.metadata.sorted_tables:
        # 获取表中实际存在的列
        try:
            inspector = sa.inspect(connection)
            existing_cols = {col['name'] for col in inspector.get_columns(table.name)}
        except Exception:
            continue
        
        # 对比模型定义的列
        for column in table.columns:
            if column.name not in existing_cols:
                col_type = column.type.compile(connection.dialect)
                default_sql = ""
                if column.default is not None:
                    default_sql = f" DEFAULT {column.default.arg}"
                elif column.nullable or column.default is None:
                    default_sql = " DEFAULT NULL"
                
                sql = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}{default_sql}"
                try:
                    connection.execute(sa.text(sql))
                    print(f"  ✅ 迁移: {table.name}.{column.name} ({col_type})")
                except Exception as e:
                    print(f"  ⚠️ 迁移跳过: {table.name}.{column.name}: {e}")


async def get_db():
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
