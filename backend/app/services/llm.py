"""Novel Analyzer - LLM服务（多API接入）"""

import json
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator, Tuple
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.schemas import ApiProvider

logger = logging.getLogger("novel-analyzer")


# ======== 提示词模板 ========

SYSTEM_PROMPT_DEFAULT = """你是一个专业的小说分析师，擅长深度分析小说的各个方面。请用中文回答，分析要深入、专业、有条理。"""

PROMPT_TAGS = """请分析以下小说内容，提取内容标签。

要求：
1. 类型标签：如玄幻、都市、言情、科幻等
2. 题材标签：如穿越、重生、系统流、种田等  
3. 风格标签：如轻松、暗黑、爽文、虐文等
4. 关键词：3-5个核心关键词

以JSON格式返回：
{"genre_tags": ["..."], "topic_tags": ["..."], "style_tags": ["..."], "keywords": ["..."]}"""

PROMPT_SUMMARY = """请总结以下小说的核心内容，300字以内。要求涵盖：主线剧情、核心冲突、结局走向（如有）。"""

PROMPT_WRITING_STYLE = """请分析以下小说的文笔特色。

分析要点：
1. 叙事手法（第一人称/第三人称、倒叙/插叙等）
2. 语言特色（华丽/朴实/幽默/冷峻等）
3. 节奏把控（快节奏/慢热等）
4. 描写能力（场景描写、心理描写、动作描写）
5. 整体文笔评分（1-10分）及理由"""

PROMPT_STRUCTURE = """请分析以下小说的整体结构。

分析要点：
1. 章节/卷结构分布
2. 高潮/低谷节奏分布
3. 伏笔与回收
4. 结构完整性评价
5. 结构评分（1-10分）及理由"""

PROMPT_OUTLINE = """请提取以下小说的大纲。

要求：
1. 主线剧情概要
2. 分卷/分阶段概要（如有）
3. 核心冲突线
4. 以Markdown格式输出"""

PROMPT_DETAILED_OUTLINE = """请提取以下小说的细纲。

要求：
1. 每个重要章节/段落的具体剧情发展
2. 关键转折点
3. 副线剧情发展
4. 以Markdown格式输出"""

PROMPT_WORLDVIEW = """请分析以下小说的世界观设定。

分析要点：
1. 世界架构（时代背景、地理环境等）
2. 力量体系（修炼/魔法/科技等级等）
3. 社会结构
4. 核心规则/法则
5. 世界观完整度评价"""

PROMPT_CHARACTERS = """请分析以下小说的主要角色。

对每个主要角色分析：
1. 基本信息（姓名、身份、性格特征）
2. 成长经历与弧光
3. 核心动机
4. 关键转折
5. 人物塑造评价

最后分析主要人物之间的关系网络。

请同时在最后以JSON格式返回人物关系结构图数据，格式如下：
```json
{
  "nodes": [
    {"name": "人物名", "role": "主角/配角/反派/...", "desc": "一句话简介"},
    ...
  ],
  "edges": [
    {"source": "人物A", "target": "人物B", "relation": "关系描述", "type": "ally/enemy/lover/family/mentor/other"},
    ...
  ]
}
```

其中type的可选值：ally（盟友）, enemy（敌对）, lover（恋人）, family（亲人）, mentor（师徒）, other（其他）
请确保nodes和edges中的名字完全一致。"""

PROMPT_POPULARITY = """请分析以下小说的流行性和市场潜力。

参考以下主流小说平台的流行趋势：
- 起点中文网：玄幻、都市、仙侠、科幻
- 纵横中文网：军事、历史、奇幻
- 七猫/番茄小说：甜宠、爽文、系统流
- 晋江文学城：言情、耽美、古风

分析要点：
1. 该小说题材属于当前爆火类型还是低分类型？
2. 同类题材的市场表现
3. 是否有上升潜力？为什么？
4. 目标读者群体
5. 题材热度评分（0-10）
6. 上升潜力评分（0-10）

以JSON格式返回：
{"genre_heat": 0-10数值, "rise_potential": 0-10数值, "analysis": "详细分析文字"}"""


# ======== LLM 服务 ========

class LLMService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_provider(self) -> Optional[ApiProvider]:
        """获取当前激活的API配置"""
        result = await self.db.execute(
            select(ApiProvider).where(ApiProvider.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_client(self, provider: Optional[ApiProvider] = None) -> Tuple[AsyncOpenAI, ApiProvider]:
        """获取OpenAI客户端（国内API不走代理）"""
        import os
        # 清除代理环境变量，防止OpenAI SDK走socks代理报错
        for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
            os.environ.pop(k, None)
        
        if provider is None:
            provider = await self.get_active_provider()
        if provider is None:
            raise ValueError("没有可用的API配置，请先在设置中添加API")
        
        # 清理base_url中的不可见字符
        import re
        base_url = re.sub(r'[\x00-\x1f\x7f]', '', provider.base_url).strip()
        
        client = AsyncOpenAI(
            api_key=provider.api_key.strip(),
            base_url=base_url,
            timeout=120.0,
        )
        return client, provider

    async def chat(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[ApiProvider] = None,
        temperature: float = 0.7,
        max_tokens: int = 8000,
    ) -> str:
        """调用LLM对话"""
        client, prov = await self.get_client(provider)
        
        # 构建消息，加上系统提示词
        system_msg = prov.system_prompt or SYSTEM_PROMPT_DEFAULT
        full_messages = [{"role": "system", "content": system_msg}] + messages
        
        response = await client.chat.completions.create(
            model=prov.model_name,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def analyze_novel(self, content: str, novel_title: str) -> Dict[str, Any]:
        """完整分析小说，返回所有分析结果"""
        # 内容太长则截断，保留关键部分
        max_chars = 60000  # 约3万token
        if len(content) > max_chars:
            # 取开头、中间、结尾
            head = content[:max_chars // 3]
            mid_start = len(content) // 2 - max_chars // 6
            mid = content[mid_start:mid_start + max_chars // 3]
            tail = content[-(max_chars // 3):]
            truncated = f"{head}\n\n[...中间省略...]\n\n{mid}\n\n[...中间省略...]\n\n{tail}"
        else:
            truncated = content

        results = {}
        prompts = {
            "tags": PROMPT_TAGS,
            "summary": PROMPT_SUMMARY,
            "writing_style": PROMPT_WRITING_STYLE,
            "structure": PROMPT_STRUCTURE,
            "outline": PROMPT_OUTLINE,
            "detailed_outline": PROMPT_DETAILED_OUTLINE,
            "worldview": PROMPT_WORLDVIEW,
            "character_growth": PROMPT_CHARACTERS,
            "popularity_analysis": PROMPT_POPULARITY,
        }

        # 进度显示
        total_steps = len(prompts)
        step_names = {
            "tags": "标签提取",
            "summary": "内容总结",
            "writing_style": "文笔分析",
            "structure": "结构分析",
            "outline": "大纲提取",
            "detailed_outline": "细纲提取",
            "worldview": "世界观分析",
            "character_growth": "人物分析",
            "popularity_analysis": "流行性评估",
        }
        logger.info(f"🧠 开始AI分析: 《{novel_title}》| 共{total_steps}项分析")

        for i, (key, prompt) in enumerate(prompts.items(), 1):
            step_name = step_names.get(key, key)
            logger.info(f"  [{i}/{total_steps}] {step_name}...")
            try:
                messages = [
                    {"role": "user", "content": f"{prompt}\n\n---\n小说《{novel_title}》内容：\n{truncated}"}
                ]
                result = await self.chat(messages)
                results[key] = result
                logger.info(f"  [{i}/{total_steps}] {step_name} ✅")
            except Exception as e:
                results[key] = f"分析失败: {str(e)}"
                logger.error(f"  [{i}/{total_steps}] {step_name} ❌ {e}")

        # 解析标签
        self._parse_tags(results)
        # 解析流行性评分
        self._parse_popularity(results)
        # 解析人物关系图
        self._parse_character_graph(results)

        logger.info(f"✅ AI分析完成: 《{novel_title}》")
        return results

    async def analyze_novel_with_progress(
        self,
        content: str,
        novel_title: str,
        novel_id: int = 0,
        step_names: list = None,
        progress_callback = None,
        pause_check = None,
    ) -> Dict[str, Any]:
        """完整分析小说，带进度回调 + 暂停支持"""
        max_chars = 60000
        if len(content) > max_chars:
            head = content[:max_chars // 3]
            mid_start = len(content) // 2 - max_chars // 6
            mid = content[mid_start:mid_start + max_chars // 3]
            tail = content[-(max_chars // 3):]
            truncated = f"{head}\n\n[...中间省略...]\n\n{mid}\n\n[...中间省略...]\n\n{tail}"
        else:
            truncated = content

        results = {}
        prompts = {
            "tags": PROMPT_TAGS,
            "summary": PROMPT_SUMMARY,
            "writing_style": PROMPT_WRITING_STYLE,
            "structure": PROMPT_STRUCTURE,
            "outline": PROMPT_OUTLINE,
            "detailed_outline": PROMPT_DETAILED_OUTLINE,
            "worldview": PROMPT_WORLDVIEW,
            "character_growth": PROMPT_CHARACTERS,
            "popularity_analysis": PROMPT_POPULARITY,
        }

        if step_names is None:
            step_names = [(k, k, f"{i+1}/{len(prompts)}") for i, k in enumerate(prompts.keys())]

        total_steps = len(step_names)
        logger.info(f"🧠 开始AI分析: 《{novel_title}》| 共{total_steps}项分析")

        for i, (key, step_label, progress_label) in enumerate(step_names):
            # 每步前检查暂停
            if pause_check:
                should_continue = await pause_check(novel_id)
                if not should_continue:
                    logger.info(f"⏸️ 分析已取消: 《{novel_title}》步骤 {progress_label}")
                    break
            
            prompt = prompts[key]
            if progress_callback and novel_id:
                progress_callback(novel_id, step_label, progress_label, f"正在调用AI分析...")
            logger.info(f"  [{progress_label}] {step_label}...")
            try:
                messages = [
                    {"role": "user", "content": f"{prompt}\n\n---\n小说《{novel_title}》内容：\n{truncated}"}
                ]
                result = await self.chat(messages)
                results[key] = result
                if progress_callback and novel_id:
                    progress_callback(novel_id, step_label, progress_label, f"✅ 完成")
                logger.info(f"  [{progress_label}] {step_label} ✅")
            except Exception as e:
                results[key] = f"分析失败: {str(e)}"
                if progress_callback and novel_id:
                    progress_callback(novel_id, step_label, progress_label, f"❌ 失败: {str(e)[:50]}")
                logger.error(f"  [{progress_label}] {step_label} ❌ {e}")

        self._parse_tags(results)
        self._parse_popularity(results)
        self._parse_character_graph(results)

        logger.info(f"✅ AI分析完成: 《{novel_title}》")
        return results

    def _parse_tags(self, results: Dict) -> None:
        """尝试从LLM返回中解析标签JSON"""
        raw = results.get("tags", "")
        try:
            # 尝试提取JSON
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0].strip()
            elif "{" in raw and "}" in raw:
                start = raw.index("{")
                end = raw.rindex("}") + 1
                json_str = raw[start:end]
            else:
                json_str = raw
            
            parsed = json.loads(json_str)
            results["genre_tags"] = parsed.get("genre_tags", [])
            results["topic_tags"] = parsed.get("topic_tags", [])
            results["style_tags"] = parsed.get("style_tags", [])
            results["all_tags"] = (
                parsed.get("genre_tags", []) +
                parsed.get("topic_tags", []) +
                parsed.get("style_tags", [])
            )
        except (json.JSONDecodeError, ValueError):
            results["all_tags"] = []
            results["genre_tags"] = []
            results["style_tags"] = []

    def _parse_popularity(self, results: Dict) -> None:
        """尝试从流行性分析中解析评分"""
        raw = results.get("popularity_analysis", "")
        try:
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
            elif "{" in raw and "}" in raw:
                start = raw.index("{")
                end = raw.rindex("}") + 1
                json_str = raw[start:end]
            else:
                json_str = raw
            
            parsed = json.loads(json_str)
            results["genre_heat"] = float(parsed.get("genre_heat", 0))
            results["rise_potential"] = float(parsed.get("rise_potential", 0))
            if "analysis" in parsed:
                results["popularity_analysis"] = parsed["analysis"]
        except (json.JSONDecodeError, ValueError, TypeError):
            results["genre_heat"] = 0
            results["rise_potential"] = 0

    def _parse_character_graph(self, results: Dict) -> None:
        """从人物分析结果中提取人物关系结构图JSON"""
        raw = results.get("character_growth", "")
        try:
            # 找最后一个JSON块（因为prompt要求在最后返回）
            json_blocks = []
            if "```json" in raw:
                parts = raw.split("```json")
                for part in parts[1:]:
                    if "```" in part:
                        json_blocks.append(part.split("```")[0].strip())
            elif "```" in raw:
                parts = raw.split("```")
                for i in range(1, len(parts) - 1, 2):
                    json_blocks.append(parts[i].strip())
            
            # 尝试每个JSON块，找到包含nodes和edges的
            for block in reversed(json_blocks):
                try:
                    parsed = json.loads(block)
                    if isinstance(parsed, dict) and "nodes" in parsed and "edges" in parsed:
                        # 验证基本结构
                        if isinstance(parsed["nodes"], list) and isinstance(parsed["edges"], list):
                            results["character_graph"] = parsed
                            logger.info(f"  🕸️ 人物关系图解析成功: {len(parsed['nodes'])}个人物, {len(parsed['edges'])}条关系")
                            return
                except (json.JSONDecodeError, ValueError):
                    continue
            
            # 如果没找到独立JSON块，尝试从全文找
            # 找包含"nodes"的JSON对象
            import re
            brace_count = 0
            start = -1
            for i, ch in enumerate(raw):
                if ch == '{':
                    if brace_count == 0:
                        start = i
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
                    if brace_count == 0 and start >= 0:
                        candidate = raw[start:i+1]
                        if '"nodes"' in candidate and '"edges"' in candidate:
                            try:
                                parsed = json.loads(candidate)
                                if isinstance(parsed["nodes"], list) and isinstance(parsed["edges"], list):
                                    results["character_graph"] = parsed
                                    logger.info(f"  🕸️ 人物关系图解析成功: {len(parsed['nodes'])}个人物, {len(parsed['edges'])}条关系")
                                    return
                            except (json.JSONDecodeError, ValueError):
                                pass
                        start = -1
            
            logger.warning("  ⚠️ 未找到人物关系图JSON数据")
            results["character_graph"] = None
        except Exception as e:
            logger.error(f"  ❌ 人物关系图解析失败: {e}")
            results["character_graph"] = None
