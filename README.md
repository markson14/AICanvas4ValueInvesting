# AlphaSeeker - 智能价值投资分析工具

AlphaSeeker 是一个基于 AI 的智能价值投资分析平台，帮助投资者进行深入的股票分析和估值评估。

## 功能特性

### 核心功能
- **智能股票分析**: 基于 AI 的深度公司分析，包括商业模式、护城河、财务健康度等
- **ReAct 推演**: 基于最新财报数据，自动更新分析结果和估值
- **多维度评分**: 雷达图展示护城河、管理层、财务、增长、估值五个维度评分
- **投资大师观点**: 模拟巴菲特、芒格、段永平三位投资大师的投资视角
- **多种估值模型**: 支持 DCF、PEG、PB、PS 等多种估值方法
- **北极星指标**: 自定义关键业务指标，跟踪公司核心数据
- **历史记录管理**: 自动保存分析历史，支持按股票代码筛选和查看

### 技术特点
- **前后端分离**: FastAPI 后端 + 单页前端应用
- **AI 驱动**: 基于 LangChain 和 OpenAI 的智能分析引擎
- **数据持久化**: JSONL 格式存储分析历史
- **实时更新**: 支持基于新财报数据的增量分析

## 项目结构

```
AICanvas/
├── backend/                 # 后端服务
│   ├── server.py           # FastAPI 主服务
│   ├── ai_engine.py        # AI 分析引擎
│   ├── config/             # 配置模块
│   │   └── history_schema.py  # 数据模型定义
│   ├── prompts/            # AI 提示词模板
│   │   ├── analyze.txt     # 初始分析提示词
│   │   ├── react_earnings.txt  # ReAct 定性分析提示词
│   │   └── react_valuation.txt # ReAct 定量估值提示词
│   ├── static/             # 静态前端文件
│   │   ├── index.html      # 主界面
│   │   └── archive.html    # 归档页面
│   ├── utils/              # 工具模块
│   │   ├── storage.py      # 数据存储管理
│   │   └── llm_json.py     # LLM JSON 解析工具
│   └── data/               # 数据目录
│       └── history.jsonl   # 分析历史记录
├── requirements.txt        # Python 依赖
└── README.md              # 项目文档
```

## 安装与配置

### 环境要求
- Python 3.8+
- pip

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd AICanvas
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**

在项目根目录创建 `.env` 文件，配置 OpenAI API 信息：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o
```

**注意**: 
- `OPENAI_BASE_URL` 如果使用官方 OpenAI API，可以留空或使用默认值
- `OPENAI_MODEL_NAME` 默认为 `gpt-4o`，可根据需要修改

4. **启动服务**

```bash
cd backend
python server.py
```

服务将在 `http://localhost:12123` 启动，浏览器会自动打开。

## 使用指南

### 基础分析流程

1. **输入股票信息**
   - 在顶部输入框输入股票代码（如：`9992.HK`）
   - 输入当前股价
   - （可选）输入财务数据：营收、净利润、PE、增长率

2. **执行分析**
   - 点击「分析/推演」按钮
   - 系统会自动判断：
     - 如果该股票没有历史记录，执行**初始分析**
     - 如果已有历史记录，执行**ReAct 推演**（基于新财报数据更新分析）

3. **查看结果**
   - 查看公司基本信息、估值结论、安全边际
   - 查看雷达图综合评分
   - 查看投资大师观点
   - 查看详细估值模型和推理过程

### ReAct 推演

当股票已有历史分析记录时，系统会自动进入 ReAct 推演模式：

1. **更新财务数据**: 在顶部输入框更新最新的财务指标
2. **点击「分析/推演」**: 系统会基于历史分析和新数据，进行增量更新
3. **查看变化**: 对比新旧分析结果，了解公司变化趋势

### 北极星指标

1. **添加指标**: 在右侧「北极星指标」卡片中，输入指标名称和值
2. **编辑指标**: 鼠标悬停在指标上，点击编辑图标
3. **删除指标**: 点击删除图标移除不需要的指标

### 历史记录

1. **查看历史**: 点击左侧文件夹图标打开历史记录抽屉
2. **筛选**: 使用下拉菜单按股票代码筛选
3. **加载**: 点击历史记录项，自动恢复该次分析的所有数据

### 数据导入导出

1. **导入 JSON**: 点击导入按钮，粘贴 JSON 格式的分析数据
2. **自动保存**: 导入的数据会自动保存到历史记录

## API 接口

### 健康检查
```
GET /api/health
```

### 股票分析
```
POST /api/analyze
Body: {
  "ticker": "9992.HK",
  "price": 100.0,
  "custom_metrics": [
    {"name": "指标名", "current_value": "值", "unit": "单位"}
  ]
}
```

### ReAct 推演
```
POST /api/react
Body: {
  "old_context": {...},  // 历史分析数据
  "financial_snapshot": {
    "period": "Latest",
    "metrics": {
      "revenue": "100",
      "net_profit": "20",
      "pe_ttm": "25",
      "revenue_growth_yoy": "30%"
    }
  },
  "custom_metrics": [...],
  "price": 100.0
}
```

### 获取历史记录
```
GET /api/history?ticker=9992.HK
```

### 保存记录
```
POST /api/save
Body: {
  "ticker": "9992.HK",
  "data": {...},
  "price": 100.0,
  "timestamp": "2024-01-01T00:00:00"
}
```

## 技术架构

### 后端技术栈
- **FastAPI**: 现代 Python Web 框架
- **LangChain**: AI 应用开发框架
- **OpenAI**: 大语言模型 API
- **Pydantic**: 数据验证和序列化
- **Uvicorn**: ASGI 服务器

### 前端技术栈
- **Tailwind CSS**: 实用优先的 CSS 框架
- **Chart.js**: 图表库（雷达图）
- **Font Awesome**: 图标库
- **原生 JavaScript**: 无框架依赖

### 数据存储
- **JSONL 格式**: 每行一个 JSON 对象，便于追加和读取
- **文件路径**: `backend/data/history.jsonl`

## 开发说明

### 代码结构

- **server.py**: FastAPI 应用入口，定义所有 API 路由
- **ai_engine.py**: AI 分析引擎，封装 LangChain 调用逻辑
- **storage.py**: 数据存储抽象层，提供保存和加载接口
- **history_schema.py**: 数据模型定义，确保数据结构一致性

### 扩展开发

1. **添加新的分析维度**: 修改 `prompts/analyze.txt` 和相关渲染逻辑
2. **自定义估值模型**: 在 `ai_engine.py` 中添加新的估值方法
3. **修改前端界面**: 编辑 `backend/static/index.html`

## 注意事项

1. **API 密钥安全**: 不要将 `.env` 文件提交到版本控制系统
2. **数据备份**: 定期备份 `backend/data/history.jsonl` 文件
3. **API 费用**: 使用 OpenAI API 会产生费用，注意控制调用频率
4. **数据准确性**: AI 分析结果仅供参考，投资决策需结合多方信息

## 版本信息

- **当前版本**: 3.4
- **最后更新**: 2024

## 许可证

本项目仅供学习和研究使用。

## 贡献

欢迎提交 Issue 和 Pull Request。

