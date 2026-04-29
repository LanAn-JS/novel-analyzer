"""Novel Analyzer - API路由：API提供商管理"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List

from ..database import get_db
from ..models.schemas import (
    ApiProvider, ApiProviderCreate, ApiProviderUpdate, ApiProviderOut
)

router = APIRouter(prefix="/api/providers", tags=["API提供商"])


def mask_api_key(key: str) -> str:
    """脱敏API Key"""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("/", response_model=List[ApiProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    """列出所有API配置"""
    result = await db.execute(select(ApiProvider).order_by(ApiProvider.id))
    providers = result.scalars().all()
    out = []
    for p in providers:
        d = ApiProviderOut.model_validate(p)
        d.api_key = mask_api_key(p.api_key)
        out.append(d)
    return out


@router.post("/", response_model=ApiProviderOut)
async def create_provider(data: ApiProviderCreate, db: AsyncSession = Depends(get_db)):
    """添加API配置"""
    import re
    # 清理输入中的不可见字符和空白
    clean_data = data.model_dump()
    for field in ('base_url', 'api_key', 'model_name', 'name'):
        if clean_data.get(field):
            clean_data[field] = re.sub(r'[\x00-\x1f\x7f]', '', clean_data[field]).strip()
    # 如果设为激活，先取消其他激活
    provider = ApiProvider(**clean_data)
    # 第一个默认激活
    count_result = await db.execute(select(ApiProvider))
    if len(count_result.scalars().all()) == 0:
        provider.is_active = True
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    out = ApiProviderOut.model_validate(provider)
    out.api_key = mask_api_key(provider.api_key)
    return out


@router.put("/{provider_id}", response_model=ApiProviderOut)
async def update_provider(
    provider_id: int,
    data: ApiProviderUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新API配置"""
    result = await db.execute(select(ApiProvider).where(ApiProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "API配置不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # 清理输入中的不可见字符和空白
    import re
    for field in ('base_url', 'api_key', 'model_name', 'name'):
        if field in update_data and update_data[field]:
            update_data[field] = re.sub(r'[\x00-\x1f\x7f]', '', update_data[field]).strip()
    
    # 如果设为激活，取消其他激活
    if data.is_active is True:
        await db.execute(
            update(ApiProvider).values(is_active=False)
        )
    
    for key, value in update_data.items():
        setattr(provider, key, value)
    
    await db.commit()
    await db.refresh(provider)
    out = ApiProviderOut.model_validate(provider)
    out.api_key = mask_api_key(provider.api_key)
    return out


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    """删除API配置"""
    result = await db.execute(select(ApiProvider).where(ApiProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "API配置不存在")
    
    was_active = provider.is_active
    await db.delete(provider)
    await db.commit()
    
    # 如果删除的是激活的，自动激活第一个
    if was_active:
        first = await db.execute(select(ApiProvider).order_by(ApiProvider.id).limit(1))
        first_provider = first.scalar_one_or_none()
        if first_provider:
            first_provider.is_active = True
            await db.commit()
    
    return {"message": "已删除"}


@router.post("/{provider_id}/activate")
async def activate_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    """激活某个API配置"""
    result = await db.execute(select(ApiProvider).where(ApiProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "API配置不存在")
    
    # 取消其他激活
    await db.execute(update(ApiProvider).values(is_active=False))
    provider.is_active = True
    await db.commit()
    return {"message": f"已激活: {provider.name}"}


@router.post("/test")
async def test_connection(data: ApiProviderCreate):
    """测试API连接"""
    import os
    import re
    from openai import AsyncOpenAI
    # 清除代理环境变量，防止socks协议报错
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
        os.environ.pop(k, None)
    # 清理输入中的不可见字符和空白
    base_url = re.sub(r'[\x00-\x1f\x7f]', '', data.base_url).strip()
    api_key = data.api_key.strip()
    model_name = data.model_name.strip()
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "你好，请回复'连接成功'"}],
            max_tokens=20,
        )
        return {"success": True, "response": response.choices[0].message.content}
    except Exception as e:
        return {"success": False, "error": str(e)}
