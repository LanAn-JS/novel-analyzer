# 📚 Novel Analyzer - 小说智能分析系统

> **by:蓝桉, 微信:379794746**

AI驱动的小说分析工具，支持多格式上传、智能分析、语义搜索、报告导出。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Vue](https://img.shields.io/badge/Vue-3-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ 功能特性

- 📖 **多格式支持** — TXT / EPUB / PDF / DOCX / MD / RTF
- 🤖 **9项AI分析** — 主题、人物、情节、风格、世界观、情感线、结构、节奏、亮点一次性全出
- 🔍 **语义搜索** — 用自然语言搜小说内容，基于向量检索
- 📤 **多格式导出** — Markdown / PDF / JSON / DOCX
- 🌐 **智能体接口** — RESTful API，供外部程序/Agent调用
- 🔧 **API自由配置** — 支持任意 OpenAI 兼容接口
- 🚀 **GPU加速** — 可选CUDA加速，向量嵌入速度提升10-15倍
- 💾 **本地存储** — 数据全部本地，不上传任何服务器

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+（仅首次构建前端需要）

### GPU加速（可选）
有NVIDIA GPU的系统可安装GPU加速依赖，向量嵌入速度提升 **10-15倍**：
```bash
pip install -r backend/requirements-gpu.txt
```
需要CUDA 12+和驱动支持。未安装则自动使用CPU，功能不受影响。

### 启动方式

**方式1：一键启动（推荐）**
```bash
./start.sh
```
首次运行会自动创建虚拟环境、安装依赖、构建前端。

**方式2：后台运行**
```bash
./start.sh --daemon
```

**方式3：停止服务**
```bash
./stop.sh
```

启动后自动打开浏览器访问 http://localhost:8989

### 桌面快捷方式（Linux）
双击 `Novel-Analyzer.desktop` 文件即可启动。

---

## 📋 使用流程

1. **配置API** → 打开「API设置」，添加你的LLM API（支持OpenAI兼容接口）
2. **上传小说** → 点击「上传小说」，支持 TXT/EPUB/PDF/DOCX/MD/RTF
3. **自动分析** → 上传后自动触发9项AI分析
4. **查看结果** → 点击小说卡片查看详细分析
5. **语义搜索** → 在「语义搜索」中用自然语言查找
6. **导出报告** → 支持 Markdown/PDF/JSON/DOCX 导出

---

## 🤖 外部智能体接口

Novel Analyzer 提供RESTful API，供其他程序/智能体调用：

### 基础地址
```
http://localhost:8989/api
```

### 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/providers/` | GET | 列出API配置 |
| `/providers/` | POST | 添加API配置 |
| `/providers/{id}/activate` | POST | 激活某个API |
| `/providers/test` | POST | 测试API连接 |
| `/novels/upload` | POST | 上传小说文件 |
| `/novels/` | GET | 列出所有小说 |
| `/novels/{id}` | GET | 获取小说详情 |
| `/novels/{id}/analyze` | POST | 触发AI分析 |
| `/novels/{id}/analysis` | GET | 获取分析结果 |
| `/novels/{id}/export?format=markdown` | GET | 导出报告 |
| `/novels/{id}/raw` | GET | 获取小说原文 |
| `/novels/{id}/analysis/json` | GET | 获取分析JSON |
| `/search` | POST | 语义搜索 |
| `/query` | POST | 智能体自然语言查询 |
| `/stats` | GET | 数据库统计 |

### 智能体查询示例

```bash
# 语义搜索
curl -X POST http://localhost:8989/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "修仙穿越的小说", "top_k": 5}'

# 自然语言查询（给智能体用）
curl -X POST http://localhost:8989/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "有哪些热度高的玄幻小说？"}'

# 上传小说
curl -X POST http://localhost:8989/api/novels/upload \
  -F "file=@/path/to/novel.txt"

# 添加API配置
curl -X POST http://localhost:8989/api/providers/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DeepSeek",
    "model_name": "deepseek-chat",
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "sk-your-key-here"
  }'
```

### API文档
启动后访问 http://localhost:8989/docs 查看完整Swagger文档。

---

## 🔧 技术架构

### 目录结构

```
Novel Analyzer/
├── start.sh              # 一键启动脚本
├── stop.sh               # 停止脚本
├── Novel-Analyzer.desktop # Linux桌面快捷方式
├── README.md
├── LICENSE
├── backend/
│   ├── requirements.txt  # Python依赖
│   ├── requirements-gpu.txt  # GPU加速依赖
│   └── app/
│       ├── main.py       # FastAPI入口
│       ├── config.py     # 配置管理
│       ├── database.py   # 数据库初始化
│       ├── models/       # SQLAlchemy数据模型
│       ├── routers/      # API路由
│       └── services/     # 核心业务逻辑
│           ├── llm.py    # LLM分析引擎
│           ├── parser.py # 多格式文件解析
│           ├── chroma.py # 向量存储与检索
│           └── exporter.py # 多格式报告导出
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.vue       # 主布局
│       ├── api/          # 后端API调用
│       ├── router/       # Vue Router
│       └── views/        # 页面组件
├── data/                 # 运行时数据（自动创建，已gitignore）
│   ├── novels.db         # SQLite数据库
│   ├── chroma_db/        # 向量数据库
│   ├── uploads/          # 上传的小说文件
│   └── exports/          # 导出的报告
└── logs/                 # 日志（自动创建，已gitignore）
```

### 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | FastAPI | 高性能异步Python Web框架 |
| ORM | SQLAlchemy | 数据库操作 |
| 向量数据库 | ChromaDB | 本地向量存储，无需外部服务 |
| 关系数据库 | SQLite | 本地存储，无需外部服务 |
| LLM调用 | OpenAI SDK | 兼容所有OpenAI格式API |
| 前端框架 | Vue 3 | 渐进式前端框架 |
| UI组件库 | Element Plus | Vue 3 企业级组件库 |
| CSS | TailwindCSS | 原子化CSS |
| 文件解析 | python-docx / ebooklib / PyPDF2 | 多格式小说解析 |
| 报告导出 | markdown / reportlab / python-docx | 多格式输出 |

---

## 📝 日志

日志文件位于 `logs/` 目录，按日期命名：
```
logs/novel-analyzer-20260428.log
```

---

## ⚠️ 注意事项

- 本程序**不包含任何API Key**，启动后需在「API设置」中自行配置
- 支持 OpenAI 兼容接口（DeepSeek、Qwen、GPT、本地LM Studio等）
- 数据存储在本地 `data/` 目录，不会上传到任何服务器

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

*by:蓝桉, 微信:379794746*
