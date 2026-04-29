"""Novel Analyzer - 小说文件解析器"""

import os
import hashlib
from typing import Tuple, Optional
from pathlib import Path

from ..config import SUPPORTED_FORMATS


def get_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_txt(file_path: str) -> str:
    """解析TXT文件，尝试多种编码"""
    encodings = ["utf-8", "gbk", "gb18030", "big5", "utf-16"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"无法解码文件: {file_path}")


def parse_epub(file_path: str) -> str:
    """解析EPUB文件"""
    from ebooklib import epub
    book = epub.read_epub(file_path)
    texts = []
    for item in book.get_items_of_type(9):  # ITEM_DOCUMENT
        content = item.get_content().decode("utf-8", errors="ignore")
        # 简单提取文本，去掉HTML标签
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        texts.append(soup.get_text(separator="\n", strip=True))
    return "\n\n".join(texts)


def parse_pdf(file_path: str) -> str:
    """解析PDF文件"""
    import pdfplumber
    texts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
    return "\n\n".join(texts)


def parse_docx(file_path: str) -> str:
    """解析DOCX文件"""
    from docx import Document
    doc = Document(file_path)
    texts = []
    for para in doc.paragraphs:
        if para.text.strip():
            texts.append(para.text)
    return "\n\n".join(texts)


def parse_markdown(file_path: str) -> str:
    """解析Markdown文件"""
    return parse_txt(file_path)  # MD本质是文本


def parse_novel(file_path: str) -> Tuple[str, str, int, str]:
    """
    解析小说文件
    返回: (内容文本, 文件格式, 字数, 内容哈希)
    """
    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的文件格式: {ext}")

    parsers = {
        ".txt": parse_txt,
        ".epub": parse_epub,
        ".pdf": parse_pdf,
        ".docx": parse_docx,
        ".md": parse_markdown,
        ".rtf": parse_txt,  # RTF简单处理为文本
    }

    parser = parsers.get(ext)
    if not parser:
        raise ValueError(f"暂不支持解析 {ext} 格式")

    content = parser(file_path)
    word_count = len(content.replace(" ", "").replace("\n", ""))
    content_hash = get_content_hash(content)

    return content, ext, word_count, content_hash


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list:
    """
    将长文本分块
    chunk_size: 每块字数
    overlap: 重叠字数
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        # 尝试在句号/换行处断开
        if end < len(text):
            for sep in ["。", "！", "？", "\n", ".", " "]:
                last_sep = chunk.rfind(sep)
                if last_sep > chunk_size // 2:
                    chunk = chunk[:last_sep + 1]
                    end = start + last_sep + 1
                    break
        chunks.append(chunk)
        start = end - overlap
    return chunks
