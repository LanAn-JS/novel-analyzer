"""Novel Analyzer - 配置模块"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma"
DB_PATH = DATA_DIR / "novel_analyzer.db"

# 确保目录存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# 支持的文件格式
SUPPORTED_FORMATS = {
    ".txt": "纯文本",
    ".epub": "EPUB电子书",
    ".pdf": "PDF文档",
    ".docx": "Word文档",
    ".md": "Markdown",
    ".rtf": "RTF文档",
}

# 流行性分析参考站点
NOVEL_SITES = {
    "qidian": "起点中文网",
    "zongheng": "纵横中文网",
    "qimao": "七猫小说",
    "tomato": "番茄小说",
    "jjwxc": "晋江文学城",
    "faloo": "飞卢小说",
}

# 应用信息
APP_SIGNATURE = "by:蓝桉, 微信:379794746"
APP_NAME = "Novel Analyzer"
APP_VERSION = "1.0.0"
